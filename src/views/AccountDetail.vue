<template>
  <div class="page">
    <!-- Header -->
    <header class="page-header">
      <div class="title-block">
        <button class="back-btn" @click="$router.push('/accounts')">← Comptes</button>
        <div v-if="account" class="name-row">
          <h1>{{ account.name }}</h1>
          <span v-if="account.code" class="code">#{{ account.code }}</span>
          <span class="badge">{{ account.account_type }}</span>
          <span v-if="account.account_subtype" class="badge soft">{{ account.account_subtype }}</span>
          <span v-if="account.is_hidden" class="badge danger">Hidden</span>
          <span v-if="account.is_virtual" class="badge warn">Virtual</span>
        </div>
        <p v-if="account?.description" class="subtitle">{{ account.description }}</p>
      </div>

      <div class="header-actions">
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn btn-primary" @click="openCreate">+ Nouvelle transaction</button>
      </div>
    </header>

    <div v-if="error" class="alert">
      <strong>Erreur :</strong> {{ error }}
    </div>

    <!-- KPIs -->
    <div v-if="account" class="kpi-row">
      <div class="kpi-card">
        <div class="kpi-label">Solde</div>
        <div class="kpi-value" :class="solde >= 0 ? 'positive' : 'negative'">
          {{ fmtAmount(solde) }} {{ currencyShort }}
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Total crédité</div>
        <div class="kpi-value positive">
          +{{ fmtAmount(account.total_earned) }} {{ currencyShort }}
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Total débité</div>
        <div class="kpi-value negative">
          {{ fmtAmount(account.total_spent) }} {{ currencyShort }}
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Transactions</div>
        <div class="kpi-value">{{ txTotal }}</div>
      </div>
      <div v-if="hasChildren" class="kpi-card">
        <div class="kpi-label">Solde consolidé (avec sous-comptes)</div>
        <div class="kpi-value" :class="soldeConsolide >= 0 ? 'positive' : 'negative'">
          {{ fmtAmount(soldeConsolide) }} {{ currencyShort }}
        </div>
      </div>
    </div>

    <!-- Filtres -->
    <div class="filters">
      <div class="search-wrapper">
        <span class="search-icon">🔍</span>
        <input
          v-model="search"
          class="search-input"
          type="text"
          placeholder="Rechercher une description…"
        />
      </div>
      <label class="toggle">
        <input type="checkbox" v-model="onlyCleared" />
        <span>Pointées uniquement</span>
      </label>
    </div>

    <!-- Table transactions -->
    <div v-if="loading && !transactions.length" class="skeleton">Chargement…</div>
    <div v-else-if="!loading && !filteredTx.length" class="empty">Aucune transaction pour ce compte.</div>

    <div v-else class="tx-list">
      <div class="tx-list-header">
        <span>Date</span>
        <span>Description</span>
        <span>Catégorie</span>
        <span class="align-right">Montant</span>
        <span class="align-right">Pointé</span>
        <span></span>
      </div>

      <div
        v-for="tx in filteredTx"
        :key="tx.id"
        class="tx-row"
      >
        <span class="tx-date">{{ fmtDate(tx.post_date) }}</span>
        <span class="tx-desc">{{ tx.description || '—' }}</span>
        <span class="tx-cat">{{ categoryName(tx.category_id) }}</span>
        <span class="tx-amount align-right" :class="accountSplit(tx).quantity >= 0 ? 'positive' : 'negative'">
          {{ accountSplit(tx).quantity >= 0 ? '+' : '' }}{{ fmtAmount(accountSplit(tx).quantity) }} {{ currencyShort }}
        </span>
        <span class="align-right">
          <span :class="tx.is_cleared ? 'cleared' : 'uncleared'">
            {{ tx.is_cleared ? '✓' : '○' }}
          </span>
        </span>
        <span class="tx-actions">
          <button class="btn-action" @click="openEdit(tx)">✎</button>
          <button class="btn-action btn-danger" @click="deleteTx(tx)">✕</button>
        </span>
      </div>
    </div>
  </div>

  <TransactionModal
    v-model="showModal"
    :mode="modalMode"
    :transaction="selectedTx"
    @save="handleSave"
    @ocr-applied="reload"
  />
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import axios from 'axios'
import TransactionModal from '@/components/modal/TransactionModal.vue'

const route = useRoute()
const accountId = route.params.id

const account = ref(null)
const allAccounts = ref([])
const transactions = ref([])
const categories = ref([])
const commodities = ref([])

const loading = ref(false)
const error = ref('')
const txTotal = ref(0)

const search = ref('')
const onlyCleared = ref(false)

const showModal = ref(false)
const modalMode = ref('create')
const selectedTx = ref(null)

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [accRes, allAccRes, txRes, catRes, comRes] = await Promise.all([
      axios.get('/api/accounts', { params: { account_id: accountId } }),
      axios.get('/api/accounts'),
      axios.get('/api/transactions', { params: { account_id: accountId } }),
      axios.get('/api/categories'),
      axios.get('/api/commodities'),
    ])
    account.value = accRes.data?.response_data ?? null
    allAccounts.value = Array.isArray(allAccRes.data?.response_data) ? allAccRes.data.response_data : []
    const rd = txRes.data?.response_data
    transactions.value = Array.isArray(rd?.transactions) ? rd.transactions : []
    txTotal.value = rd?.total ?? transactions.value.length
    categories.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
    commodities.value = Array.isArray(comRes.data?.response_data) ? comRes.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

onMounted(reload)

const currencyShort = computed(() => {
  if (!account.value) return ''
  const c = commodities.value.find(c => String(c.id) === String(account.value.currency_id))
  return c?.short_name?.toUpperCase() || ''
})

const solde = computed(() => {
  if (!account.value) return 0
  return (Number(account.value.total_earned) || 0) - (Number(account.value.total_spent) || 0)
})

const hasChildren = computed(() =>
  allAccounts.value.some(a => String(a.parent_id) === String(accountId))
)

const soldeConsolide = computed(() => {
  if (!account.value) return 0
  return (Number(account.value.consolidated_earned) || 0) - (Number(account.value.consolidated_spent) || 0)
})

function categoryName(id) {
  if (!id) return '—'
  const c = categories.value.find(c => String(c.id) === String(id))
  return c?.name || '—'
}

// Somme des splits de cette transaction liés au compte courant (une transaction peut avoir
// plusieurs splits sur le même compte, ex: les lignes d'un ticket de caisse importé)
function accountSplit(tx) {
  const matching = tx.splits?.filter(s => String(s.account_id) === String(accountId)) || []
  const quantity = matching.reduce((sum, s) => sum + Number(s.quantity), 0)
  return { quantity }
}

function fmtAmount(v) {
  if (v === null || v === undefined) return '0'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(n)
}

function fmtDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString('fr-FR')
}

const filteredTx = computed(() => {
  const q = search.value.toLowerCase().trim()
  return transactions.value.filter(tx => {
    if (onlyCleared.value && !tx.is_cleared) return false
    if (q && !(tx.description || '').toLowerCase().includes(q)) return false
    return true
  })
})

function openCreate() {
  selectedTx.value = null
  modalMode.value = 'create'
  showModal.value = true
}

function openEdit(tx) {
  selectedTx.value = { ...tx }
  modalMode.value = 'edit'
  showModal.value = true
}

async function handleSave(form) {
  try {
    if (modalMode.value === 'create') {
      await axios.post('/api/transactions', {
        description: form.description,
        post_date: form.post_date,
        effective_date: form.effective_date || null,
        category_id: form.category_id || null,
        is_cleared: form.is_cleared,
        splits: form.splits,
      })
    } else {
      await axios.patch('/api/transactions', {
        transaction_id: form.id,
        description: form.description,
        post_date: form.post_date,
        effective_date: form.effective_date || null,
        category_id: form.category_id || null,
        is_cleared: form.is_cleared,
        splits: form.splits,
      })
    }
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function deleteTx(tx) {
  if (!confirm(`Supprimer la transaction « ${tx.description || 'sans libellé'} » ?`)) return
  try {
    await axios.delete('/api/transactions', { params: { transaction_id: tx.id } })
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}
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
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.title-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.back-btn {
  background: transparent;
  border: none;
  color: #6b7280;
  font-size: 13px;
  cursor: pointer;
  padding: 0;
  text-align: left;
}
.back-btn:hover { color: #cbd5e1; }

.name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.name-row h1 {
  margin: 0;
  font-size: 26px;
}

.code {
  color: #93c5fd;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(96, 165, 250, 0.25);
  background: rgba(96, 165, 250, 0.10);
}

.badge {
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(148, 163, 184, 0.10);
  color: #e5e7eb;
}
.badge.soft { background: rgba(148, 163, 184, 0.06); }
.badge.danger { border-color: rgba(239,68,68,.35); background: rgba(239,68,68,.10); color: #fecaca; }
.badge.warn { border-color: rgba(245,158,11,.35); background: rgba(245,158,11,.10); color: #fde68a; }

.subtitle {
  margin: 0;
  color: #9ca3af;
  font-size: 14px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.alert {
  border: 1px solid rgba(239,68,68,.5);
  background: rgba(239,68,68,.08);
  padding: 12px 14px;
  border-radius: 12px;
  margin-bottom: 16px;
  color: #fecaca;
}

/* KPIs */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
@media (max-width: 800px) {
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
}

.kpi-card {
  border: 1px solid rgba(148,163,184,.18);
  background: rgba(15,23,42,.55);
  border-radius: 14px;
  padding: 16px;
}
.kpi-label {
  font-size: 12px;
  color: #9ca3af;
  margin-bottom: 6px;
}
.kpi-value {
  font-size: 22px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.positive { color: #86efac; }
.negative { color: #fca5a5; }

/* Filtres */
.filters {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.search-wrapper { position: relative; }
.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0.7;
}
.search-input {
  padding: 8px 10px 8px 32px;
  border-radius: 10px;
  border: 1px solid rgba(148,163,184,.25);
  background: rgba(15,23,42,.7);
  color: #e5e7eb;
  outline: none;
  width: 280px;
  max-width: 70vw;
  font-size: 13px;
}

.toggle {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: #cbd5e1;
  user-select: none;
}
.toggle input { accent-color: #60a5fa; }

/* Table */
.skeleton, .empty {
  padding: 18px;
  border: 1px solid rgba(148,163,184,.18);
  background: rgba(15,23,42,.55);
  border-radius: 14px;
  color: #cbd5e1;
}

.tx-list {
  border: 1px solid rgba(148,163,184,.18);
  background: rgba(15,23,42,.55);
  border-radius: 14px;
  overflow: hidden;
}

.tx-list-header {
  display: grid;
  grid-template-columns: 100px 1fr 140px 140px 60px 70px;
  gap: 8px;
  padding: 10px 16px;
  font-size: 11px;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid rgba(148,163,184,.12);
}

.tx-row {
  display: grid;
  grid-template-columns: 100px 1fr 140px 140px 60px 70px;
  gap: 8px;
  padding: 11px 16px;
  font-size: 13px;
  border-bottom: 1px solid rgba(148,163,184,.07);
  align-items: center;
  transition: background 0.1s;
}
.tx-row:last-child { border-bottom: none; }
.tx-row:hover { background: rgba(148,163,184,.04); }

.tx-date { color: #9ca3af; font-size: 12px; }
.tx-desc { color: #e5e7eb; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tx-cat { color: #9ca3af; font-size: 12px; }
.tx-amount { font-variant-numeric: tabular-nums; font-weight: 500; }
.align-right { text-align: right; }

.cleared { color: #86efac; }
.uncleared { color: #4b5563; }

.tx-actions {
  display: flex;
  gap: 4px;
  justify-content: flex-end;
}

.btn-action {
  background: transparent;
  border: 1px solid rgba(148,163,184,.25);
  color: #cbd5e1;
  padding: 3px 7px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}
.btn-action:hover { background: rgba(148,163,184,.1); }
.btn-danger { border-color: rgba(239,68,68,.4); color: #fca5a5; }
.btn-danger:hover { background: rgba(239,68,68,.1); }

.btn {
  border: 1px solid rgba(148,163,184,.25);
  background: rgba(15,23,42,.7);
  color: #e5e7eb;
  padding: 8px 12px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-primary {
  background: linear-gradient(90deg, #2563eb, #4f46e5);
  border-color: transparent;
  color: #fff;
}
</style>
