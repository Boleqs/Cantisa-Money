<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Rapprochement bancaire</h1>
        <p class="subtitle">Vérifiez vos transactions par rapport à votre relevé bancaire.</p>
      </div>
    </header>

    <!-- Sélecteur de compte + solde relevé -->
    <div class="setup-card card">
      <div class="setup-grid">
        <div class="form-group">
          <label class="form-label">Compte à rapprocher</label>
          <select v-model="selectedAccountId" class="form-select" @change="loadData">
            <option value="">— Sélectionner un compte —</option>
            <option v-for="a in accounts" :key="a.id" :value="a.id">
              {{ a.name }} ({{ a.account_type }})
            </option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Solde final du relevé ({{ selectedAccountCurrency }})</label>
          <input
            type="number"
            v-model.number="statementBalance"
            step="0.01"
            class="form-input"
            placeholder="ex: 1 234,56"
            :disabled="!selectedAccountId"
          />
        </div>
      </div>

      <!-- KPIs -->
      <div v-if="selectedAccountId && data" class="kpi-row">
        <div class="kpi-card">
          <div class="kpi-label">Solde rapproché actuel</div>
          <div class="kpi-value">{{ fmtAmount(data.reconciled_balance) }} {{ selectedAccountCurrency }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Sélectionnés</div>
          <div class="kpi-value">{{ fmtAmount(checkedSum) }} {{ selectedAccountCurrency }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Solde après rapprochement</div>
          <div class="kpi-value" :class="afterBalance >= 0 ? 'pos' : 'neg'">
            {{ fmtAmount(afterBalance) }} {{ selectedAccountCurrency }}
          </div>
        </div>
        <div class="kpi-card" :class="{ 'kpi-ok': isBalanced, 'kpi-warn': !isBalanced }">
          <div class="kpi-label">Différence</div>
          <div class="kpi-value" :class="isBalanced ? 'pos' : 'neg'">
            {{ fmtAmount(difference) }} {{ selectedAccountCurrency }}
          </div>
        </div>
      </div>
    </div>

    <div v-if="error" class="alert">{{ error }}</div>
    <div v-if="loading" class="empty">Chargement…</div>

    <!-- Table des transactions à rapprocher -->
    <div v-if="data && !loading" class="card">
      <div class="table-header">
        <h2>
          Transactions non rapprochées
          <span class="count-badge">{{ pending.length }}</span>
        </h2>
        <div class="table-actions">
          <button class="btn btn-sm" @click="selectAll(true)">Tout cocher</button>
          <button class="btn btn-sm" @click="selectAll(false)">Tout décocher</button>
          <button class="btn btn-sm" @click="selectCleared">Cocher les pointées</button>
        </div>
      </div>

      <div v-if="!pending.length" class="empty-inner">
        Aucune transaction en attente — tout est déjà rapproché.
      </div>

      <div v-else class="table-scroll">
        <table class="tx-table">
          <thead>
            <tr>
              <th class="col-check">
                <input type="checkbox" :checked="allChecked" @change="selectAll(!allChecked)" />
              </th>
              <th>Date</th>
              <th>Description</th>
              <th class="col-amount">Montant</th>
              <th>État</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="row in pending"
              :key="row.split_id"
              :class="{ 'row-checked': row.checked, 'row-uncleared': !row.is_cleared }"
              @click="row.checked = !row.checked"
            >
              <td class="col-check" @click.stop>
                <input type="checkbox" v-model="row.checked" />
              </td>
              <td class="col-date">{{ fmtDate(row.date) }}</td>
              <td class="col-desc">{{ row.description || '—' }}</td>
              <td class="col-amount" :class="row.amount >= 0 ? 'pos' : 'neg'">
                {{ fmtAmount(row.amount) }}
              </td>
              <td>
                <span v-if="row.is_cleared" class="badge ok">Pointée</span>
                <span v-else class="badge warn">Non pointée</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Actions -->
      <div class="confirm-bar">
        <div class="confirm-info" :class="isBalanced ? 'balanced' : 'unbalanced'">
          <span v-if="isBalanced">✓ Soldes équilibrés — vous pouvez confirmer le rapprochement.</span>
          <span v-else>Différence restante : {{ fmtAmount(difference) }} {{ selectedAccountCurrency }} — cochez les transactions correspondant à votre relevé.</span>
        </div>
        <button
          class="btn btn-primary"
          :disabled="!isBalanced || checkedIds.length === 0 || confirming"
          @click="confirm"
        >
          <span v-if="confirming">Confirmation…</span>
          <span v-else>✓ Confirmer le rapprochement ({{ checkedIds.length }})</span>
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const accounts = ref([])
const commodities = ref([])
const selectedAccountId = ref('')
const statementBalance = ref(0)
const data = ref(null)
const pending = ref([])
const loading = ref(false)
const error = ref('')
const confirming = ref(false)

// ── computed ──────────────────────────────────────────────────────────────────

const checkedIds = computed(() => pending.value.filter(r => r.checked).map(r => r.split_id))
const checkedSum = computed(() => pending.value.filter(r => r.checked).reduce((s, r) => s + r.amount, 0))
const afterBalance = computed(() => (data.value?.reconciled_balance ?? 0) + checkedSum.value)
const difference = computed(() => statementBalance.value - afterBalance.value)
const isBalanced = computed(() => Math.abs(difference.value) < 0.01)
const allChecked = computed(() => pending.value.length > 0 && pending.value.every(r => r.checked))
// Chaque compte a sa propre devise — pas de "devise par défaut" ici (contrairement au patrimoine
// global) puisque le rapprochement porte toujours sur UN SEUL compte à la fois.
const selectedAccountCurrency = computed(() => {
  const acc = accounts.value.find(a => String(a.id) === String(selectedAccountId.value))
  if (!acc) return ''
  const c = commodities.value.find(c => String(c.id) === String(acc.currency_id))
  return c ? c.short_name : ''
})

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtAmount(v) {
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(v ?? 0))
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR')
}

// ── data ──────────────────────────────────────────────────────────────────────

async function loadAccounts() {
  const [accRes, comRes] = await Promise.all([
    axios.get('/api/accounts'),
    axios.get('/api/commodities'),
  ])
  accounts.value = (Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : [])
    .filter(a => ['Current', 'Assets'].includes(a.account_type))
  commodities.value = Array.isArray(comRes.data?.response_data) ? comRes.data.response_data : []
}

async function loadData() {
  if (!selectedAccountId.value) { data.value = null; pending.value = []; return }
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get('/api/reconcile', { params: { account_id: selectedAccountId.value } })
    data.value = res.data.response_data
    pending.value = (data.value.pending || []).map(r => ({ ...r, checked: r.is_cleared }))
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur chargement'
  } finally {
    loading.value = false
  }
}

// ── selection ─────────────────────────────────────────────────────────────────

function selectAll(val) { pending.value.forEach(r => (r.checked = val)) }
function selectCleared() { pending.value.forEach(r => (r.checked = r.is_cleared)) }

// ── confirm ───────────────────────────────────────────────────────────────────

async function confirm() {
  if (!isBalanced.value || checkedIds.value.length === 0) return
  confirming.value = true
  error.value = ''
  try {
    await axios.post('/api/reconcile/confirm', {
      account_id: selectedAccountId.value,
      split_ids: checkedIds.value,
    })
    await loadData()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur confirmation'
  } finally {
    confirming.value = false
  }
}

onMounted(loadAccounts)
</script>

<style scoped>
.page {
  padding: 28px;
  color: #e5e7eb;
  background: #0b1220;
  min-height: 100vh;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}

.page-header { margin-bottom: 24px; }
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; }

.card {
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 16px;
  padding: 20px 24px;
  margin-bottom: 16px;
}

.setup-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 20px;
}
@media (max-width: 600px) { .setup-grid { grid-template-columns: 1fr; } }

.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-label { font-size: 13px; color: #9ca3af; }
.form-select, .form-input {
  padding: 9px 12px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 14px;
  outline: none;
}
.form-select:focus, .form-input:focus { border-color: rgba(96, 165, 250, 0.5); }
.form-select option { background: #1e293b; }

/* KPIs */
.kpi-row { display: flex; gap: 14px; flex-wrap: wrap; }

.kpi-card {
  flex: 1;
  min-width: 130px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.5);
  border-radius: 12px;
  padding: 12px 16px;
}

.kpi-ok  { border-color: rgba(16, 185, 129, 0.4); background: rgba(16, 185, 129, 0.07); }
.kpi-warn { border-color: rgba(245, 158, 11, 0.4); background: rgba(245, 158, 11, 0.07); }

.kpi-label { font-size: 11px; color: #9ca3af; margin-bottom: 4px; }
.kpi-value { font-size: 20px; font-weight: 700; color: #e5e7eb; font-variant-numeric: tabular-nums; }
.kpi-value.pos { color: #6ee7b7; }
.kpi-value.neg { color: #fca5a5; }

/* Alert */
.alert {
  border: 1px solid rgba(239,68,68,0.5);
  background: rgba(239,68,68,0.08);
  padding: 12px 14px;
  border-radius: 12px;
  margin-bottom: 16px;
  color: #fecaca;
  font-size: 14px;
}

.empty { padding: 18px; color: #9ca3af; }

/* Table header */
.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  flex-wrap: wrap;
  gap: 10px;
}

.table-header h2 {
  margin: 0;
  font-size: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(96, 165, 250, 0.2);
  border: 1px solid rgba(96, 165, 250, 0.35);
  color: #93c5fd;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  padding: 1px 8px;
}

.table-actions { display: flex; gap: 6px; }

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 8px 14px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  transition: 0.15s;
}
.btn:disabled { opacity: 0.4; cursor: not-allowed; }
.btn:not(:disabled):hover { background: rgba(148, 163, 184, 0.1); }
.btn-primary {
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
  border-color: transparent;
  color: #fff;
  padding: 10px 20px;
  font-size: 14px;
}
.btn-primary:not(:disabled):hover { background: linear-gradient(90deg, #1d4ed8, #4338ca); }
.btn-sm { padding: 5px 10px; font-size: 12px; }

.empty-inner { color: #9ca3af; font-size: 14px; padding: 12px 0; }

/* Table */
.table-scroll { overflow-x: auto; border-radius: 10px; border: 1px solid rgba(148,163,184,0.12); }

.tx-table { width: 100%; border-collapse: collapse; font-size: 13px; }

.tx-table th {
  background: rgba(15, 23, 42, 0.8);
  color: #9ca3af;
  font-weight: 600;
  padding: 10px 12px;
  text-align: left;
  white-space: nowrap;
}

.tx-table td {
  padding: 9px 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.08);
  color: #e5e7eb;
  cursor: pointer;
  transition: background 0.1s;
}

.tx-table tbody tr:hover td { background: rgba(148, 163, 184, 0.05); }
.row-checked td { background: rgba(37, 99, 235, 0.08); }
.row-uncleared td { color: #9ca3af; }

.col-check { width: 40px; text-align: center; }
.col-date  { width: 100px; white-space: nowrap; }
.col-desc  { max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.col-amount { text-align: right; font-variant-numeric: tabular-nums; font-weight: 500; }
.pos { color: #6ee7b7; }
.neg { color: #fca5a5; }

/* Badges */
.badge {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148,163,184,0.22);
  background: rgba(148,163,184,0.1);
  color: #e5e7eb;
}
.badge.ok   { border-color: rgba(16,185,129,0.35); background: rgba(16,185,129,0.1); color: #6ee7b7; }
.badge.warn { border-color: rgba(245,158,11,0.35); background: rgba(245,158,11,0.1); color: #fde68a; }

/* Confirm bar */
.confirm-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid rgba(148,163,184,0.12);
  flex-wrap: wrap;
}

.confirm-info {
  font-size: 13px;
  flex: 1;
}
.balanced   { color: #6ee7b7; }
.unbalanced { color: #9ca3af; }
</style>
