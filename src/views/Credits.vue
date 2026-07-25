<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Crédits</h1>
        <p class="subtitle">Suivez vos prêts en cours : échéancier, capital restant dû, révisions de taux.</p>
      </div>
      <div class="header-actions">
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn btn-primary" @click="openCreate">+ Nouveau crédit</button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !loans.length" class="empty">Chargement…</div>
    <div v-else-if="!loading && !loans.length" class="empty">Aucun crédit enregistré.</div>

    <table v-else class="table">
      <thead>
        <tr>
          <th>Nom</th>
          <th>Capital initial</th>
          <th>Restant dû</th>
          <th>Taux</th>
          <th>Coût total intérêts</th>
          <th>Mensualité</th>
          <th>Prochaine échéance</th>
          <th>Compte de prélèvement</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="l in loans" :key="l.id" :class="{ 'row-overdue': l.next_installment?.is_overdue, 'row-closed': l.is_closed }">
          <td>
            <router-link :to="`/credits/${l.id}`" class="loan-link">{{ l.name }}</router-link>
            <span v-if="l.is_closed" class="badge-closed">Soldé</span>
            <span v-else-if="l.auto_debit" class="badge-auto" title="Échéances prélevées automatiquement">Auto-débit</span>
            <span v-else-if="l.next_installment?.is_overdue" class="badge-overdue">En retard</span>
            <span v-if="l.is_existing_loan" class="badge-existing" title="Crédit déjà en cours à sa saisie">Existant</span>
          </td>
          <td>{{ fmtAmount(l.principal) }} {{ l.currency }}</td>
          <td>
            {{ fmtAmount(l.remaining_principal) }} {{ l.currency }}
            <div class="progress-bar"><div class="progress-fill" :style="{ width: progressPct(l) + '%' }"></div></div>
          </td>
          <td class="muted">{{ l.annual_rate }} %</td>
          <td class="muted">{{ fmtAmount(l.total_interest_cost) }} {{ l.currency }}</td>
          <td class="muted">{{ l.next_installment ? `${fmtAmount(l.next_installment.total_amount)} ${l.currency}` : '—' }}</td>
          <td :class="l.next_installment?.is_overdue ? 'overdue' : 'muted'">
            {{ l.next_installment ? fmtDate(l.next_installment.due_date) : '—' }}
          </td>
          <td class="muted">{{ accountName(l.payment_account_id) }}</td>
          <td class="actions">
            <button
              v-if="l.next_installment && !l.is_closed"
              class="btn-action btn-execute"
              :disabled="l.executing"
              @click="executeNextInstallment(l)"
              title="Exécuter la prochaine échéance"
            >
              <span v-if="l.executing">…</span>
              <span v-else>▶</span>
            </button>
            <button class="btn-action" @click="openEdit(l)" title="Modifier">✎</button>
            <button class="btn-action btn-danger" @click="deleteLoan(l)" title="Supprimer">✕</button>
          </td>
        </tr>
      </tbody>
    </table>

    <LoanModal v-model="showModal" :edit-target="editTarget" @saved="onSaved" />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import LoanModal from '../components/modal/LoanModal.vue'

const loans = ref([])
const accounts = ref([])
const loading = ref(false)
const error = ref('')
const showModal = ref(false)
const editTarget = ref(null)

function fmtAmount(v) {
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(Number(v ?? 0))
}
function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
function accountName(id) {
  const a = accounts.value.find(a => String(a.id) === String(id))
  return a ? a.name : id || '—'
}
function progressPct(l) {
  if (!l.principal) return 0
  const paid = Math.max(0, Number(l.principal) - Number(l.remaining_principal))
  return Math.min(100, Math.round((paid / Number(l.principal)) * 100))
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [loanRes, accRes] = await Promise.all([
      axios.get('/api/loans'),
      axios.get('/api/accounts'),
    ])
    loans.value = (Array.isArray(loanRes.data?.response_data) ? loanRes.data.response_data : [])
      .map(l => ({ ...l, executing: false }))
    accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  showModal.value = true
}
function openEdit(l) {
  editTarget.value = l
  showModal.value = true
}
async function onSaved() {
  await reload()
}

async function executeNextInstallment(l) {
  if (!l.next_installment) return
  l.executing = true
  error.value = ''
  try {
    const { data } = await axios.post('/api/loans/execute', { installment_id: l.next_installment.id })
    Object.assign(l, data.response_data, { executing: false })
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || "Erreur lors de l'exécution"
    l.executing = false
  }
}

async function deleteLoan(l) {
  if (!confirm(`Supprimer le crédit « ${l.name} » ? Cette action n'est possible que si aucune échéance n'a encore été payée.`)) return
  try {
    await axios.delete('/api/loans', { params: { loan_id: l.id } })
    await reload()
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
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; }
.header-actions { display: flex; gap: 10px; align-items: center; }

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2)); border-color: transparent; color: #fff; }

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

.table { width: 100%; border-collapse: collapse; font-size: 14px; }
.table th {
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
  color: #9ca3af;
  font-weight: 500;
}
.table td { padding: 10px 12px; border-bottom: 1px solid rgba(148, 163, 184, 0.08); }
.muted { color: #9ca3af; }
.actions { text-align: right; white-space: nowrap; }

.loan-link { color: #e5e7eb; text-decoration: none; font-weight: 500; }
.loan-link:hover { color: #93c5fd; text-decoration: underline; }

.progress-bar {
  margin-top: 4px;
  height: 4px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.15);
  overflow: hidden;
  width: 120px;
}
.progress-fill { height: 100%; background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2)); }

.btn-action {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  margin-left: 4px;
}
.btn-action:hover { background: rgba(148, 163, 184, 0.1); }
.btn-danger { border-color: rgba(239,68,68,0.4); color: #fca5a5; }
.btn-danger:hover { background: rgba(239,68,68,0.1); }
.btn-execute { border-color: rgba(16,185,129,0.4); color: #6ee7b7; }
.btn-execute:hover { background: rgba(16,185,129,0.1); }
.btn-execute:disabled { opacity: 0.5; cursor: not-allowed; }

.row-overdue td { background: rgba(245, 158, 11, 0.04); }
.row-closed td { opacity: 0.6; }
.overdue { color: #fde68a !important; font-weight: 600; }

.badge-overdue, .badge-auto, .badge-existing, .badge-closed {
  display: inline-block;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  margin-left: 6px;
  vertical-align: middle;
  border: 1px solid;
}
.badge-overdue { border-color: rgba(245,158,11,0.4); background: rgba(245,158,11,0.1); color: #fde68a; }
.badge-auto { border-color: rgba(16,185,129,0.4); background: rgba(16,185,129,0.1); color: #6ee7b7; }
.badge-existing { border-color: rgba(96,165,250,0.4); background: rgba(96,165,250,0.1); color: #93c5fd; }
.badge-closed { border-color: rgba(148,163,184,0.3); background: rgba(148,163,184,0.08); color: #cbd5e1; }
</style>
