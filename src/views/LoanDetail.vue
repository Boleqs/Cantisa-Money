<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <button class="back-btn" @click="$router.push('/credits')">← Crédits</button>
        <div v-if="loan" class="name-row">
          <h1>{{ loan.name }}</h1>
          <span v-if="loan.is_closed" class="badge soft">Soldé</span>
          <span v-else-if="loan.auto_debit" class="badge">Auto-débit</span>
          <span v-if="loan.is_existing_loan" class="badge warn">Crédit existant</span>
        </div>
      </div>
      <div class="header-actions" v-if="loan && !loan.is_closed">
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn" @click="showRevisionModal = true">🔁 Réviser le taux</button>
        <button class="btn btn-danger" @click="payoff">🏁 Remboursement anticipé total</button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !loan" class="empty">Chargement…</div>

    <template v-else-if="loan">
      <div class="kpi-row">
        <div class="kpi-card">
          <div class="kpi-label">Capital initial</div>
          <div class="kpi-value">{{ fmtAmount(loan.principal) }} {{ loan.currency }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Capital restant dû</div>
          <div class="kpi-value negative">{{ fmtAmount(loan.remaining_principal) }} {{ loan.currency }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Taux actuel</div>
          <div class="kpi-value">{{ loan.annual_rate }} %</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Coût total des intérêts</div>
          <div class="kpi-value negative">{{ fmtAmount(loan.total_interest_cost) }} {{ loan.currency }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Mensualité actuelle</div>
          <div class="kpi-value">{{ loan.next_installment ? `${fmtAmount(loan.next_installment.total_amount)} ${loan.currency}` : '—' }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Prochaine échéance</div>
          <div class="kpi-value">{{ loan.next_installment ? fmtDate(loan.next_installment.due_date) : '—' }}</div>
        </div>
      </div>

      <LineGraph
        v-if="installments.length"
        title="Capital restant dû"
        :subtitle="`Échéancier planifié (échéances payées et à venir) — en ${loan.currency}`"
        :labels="installments.map(i => fmtDate(i.due_date))"
        :values="installments.map(i => i.remaining_principal_after)"
        dataset-label="Capital restant dû"
        color="#f59e0b"
        :format-value="fmtAmount"
      />

      <section class="section">
        <div class="section-header">
          <h2>Échéancier <span class="muted">(montants en {{ loan.currency }})</span></h2>
        </div>
        <table class="table">
          <thead>
            <tr>
              <th>#</th>
              <th>Date</th>
              <th>Capital</th>
              <th>Intérêts</th>
              <th>Assurance</th>
              <th>Total</th>
              <th>Restant dû après</th>
              <th>Statut</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="i in installments" :key="i.id" :class="{ 'row-overdue': i.is_overdue }">
              <td>{{ i.installment_number }}</td>
              <td :class="i.is_overdue ? 'overdue' : ''">{{ fmtDate(i.due_date) }}</td>
              <td>{{ fmtAmount(i.principal_portion) }}</td>
              <td>{{ fmtAmount(i.interest_portion) }}</td>
              <td>{{ fmtAmount(i.insurance_portion) }}</td>
              <td>{{ fmtAmount(i.total_amount) }}</td>
              <td class="muted">{{ fmtAmount(i.remaining_principal_after) }}</td>
              <td>
                <span v-if="i.is_paid" class="badge soft">Payée</span>
                <span v-else-if="i.is_overdue" class="badge-overdue">En retard</span>
                <span v-else class="muted">À venir</span>
              </td>
              <td>
                <button
                  v-if="!i.is_paid && !loan.is_closed && isNextUnpaid(i)"
                  class="btn-action btn-execute"
                  :disabled="executing"
                  @click="executeInstallment(i)"
                  title="Exécuter cette échéance"
                >
                  <span v-if="executing">…</span>
                  <span v-else>▶</span>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="section" v-if="revisions.length">
        <div class="section-header"><h2>Historique des révisions de taux</h2></div>
        <table class="table">
          <thead>
            <tr><th>Date d'effet</th><th>Nouveau taux</th><th>Mode</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in revisions" :key="r.id">
              <td>{{ fmtDate(r.effective_date) }}</td>
              <td>{{ r.new_annual_rate }} %</td>
              <td class="muted">{{ r.recalc_mode === 'keep_term' ? 'Durée conservée' : 'Mensualité conservée' }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>

    <LoanRateRevisionModal v-model="showRevisionModal" :loan-id="loanId" @saved="reload" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import LineGraph from '../components/graphs/LineGraph.vue'
import LoanRateRevisionModal from '../components/modal/LoanRateRevisionModal.vue'
import { confirmDialog } from '@/utils/confirmDialog'
import { useToast } from '@/utils/toast'

const toast = useToast()

const route = useRoute()
const loanId = computed(() => route.params.id)

const loan = ref(null)
const installments = ref([])
const revisions = ref([])
const loading = ref(false)
const error = ref('')
const executing = ref(false)
const showRevisionModal = ref(false)

function fmtAmount(v) {
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(Number(v ?? 0))
}
function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
function isNextUnpaid(i) {
  const firstUnpaid = installments.value.find(x => !x.is_paid)
  return firstUnpaid && firstUnpaid.id === i.id
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [loanRes, instRes, revRes] = await Promise.all([
      axios.get('/api/loans', { params: { loan_id: loanId.value } }),
      axios.get('/api/loans/installments', { params: { loan_id: loanId.value } }),
      axios.get('/api/loans/rate-revisions', { params: { loan_id: loanId.value } }),
    ])
    loan.value = loanRes.data?.response_data || null
    installments.value = Array.isArray(instRes.data?.response_data) ? instRes.data.response_data : []
    revisions.value = Array.isArray(revRes.data?.response_data) ? revRes.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

async function executeInstallment(i) {
  executing.value = true
  error.value = ''
  try {
    await axios.post('/api/loans/execute', { installment_id: i.id })
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || "Erreur lors de l'exécution"
  } finally {
    executing.value = false
  }
}

async function payoff() {
  const ok = await confirmDialog({
    title: 'Solder le crédit',
    message: `Solder intégralement le crédit « ${loan.value.name} » maintenant ?`,
    confirmLabel: 'Solder',
    danger: true,
  })
  if (!ok) return
  error.value = ''
  try {
    await axios.post('/api/loans/payoff', { loan_id: loanId.value })
    await reload()
    toast.success(`Crédit « ${loan.value.name} » soldé.`)
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

onMounted(() => reload())
</script>

<style scoped>
.page {
  padding: 28px;
  color: #e5e7eb;
  background: #0b1220;
  min-height: 100vh;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.back-btn {
  background: transparent;
  border: none;
  color: #9ca3af;
  cursor: pointer;
  font-size: 13px;
  padding: 0 0 8px;
}
.back-btn:hover { color: #e5e7eb; }
.name-row { display: flex; align-items: center; gap: 10px; }
.name-row h1 { margin: 0; font-size: 26px; }
.header-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 8px 12px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-danger { border-color: rgba(239,68,68,0.4); color: #fca5a5; }
.btn-danger:hover { background: rgba(239,68,68,0.08); }

.alert {
  border: 1px solid rgba(239, 68, 68, 0.5);
  background: rgba(239, 68, 68, 0.08);
  padding: 12px 14px;
  border-radius: 12px;
  margin-bottom: 16px;
  color: #fecaca;
}
.empty {
  padding: 18px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 14px;
  color: #cbd5e1;
}

.badge {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(96,165,250,0.4);
  background: rgba(96,165,250,0.1);
  color: #93c5fd;
}
.badge.soft { border-color: rgba(148,163,184,0.3); background: rgba(148,163,184,0.08); color: #cbd5e1; }
.badge.warn { border-color: rgba(245,158,11,0.4); background: rgba(245,158,11,0.1); color: #fde68a; }

.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin: 18px 0;
}
.kpi-card {
  border: 1px solid #1f2937;
  background: rgba(15, 23, 42, 0.55);
  border-radius: 14px;
  padding: 12px 14px;
}
.kpi-label { font-size: 12px; color: #9ca3af; margin-bottom: 4px; }
.kpi-value { font-size: 20px; font-weight: 600; }
.kpi-value.negative { color: #fca5a5; }

.section { margin-top: 22px; }
.section-header { margin-bottom: 10px; }
.section-header h2 { margin: 0; font-size: 16px; }

.table { width: 100%; border-collapse: collapse; font-size: 13px; }
.table th {
  text-align: left;
  padding: 8px 10px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
  color: #9ca3af;
  font-weight: 500;
}
.table td { padding: 8px 10px; border-bottom: 1px solid rgba(148, 163, 184, 0.08); }
.muted { color: #9ca3af; }
.overdue { color: #fde68a !important; font-weight: 600; }
.row-overdue td { background: rgba(245, 158, 11, 0.04); }

.badge-overdue {
  display: inline-block;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid rgba(245,158,11,0.4);
  background: rgba(245,158,11,0.1);
  color: #fde68a;
}

.btn-action {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}
.btn-execute { border-color: rgba(16,185,129,0.4); color: #6ee7b7; }
.btn-execute:hover { background: rgba(16,185,129,0.1); }
.btn-execute:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
