<template>
  <div class="page">
    <!-- Header -->
    <header class="page-header">
      <div class="title-block">
        <h1>Transactions</h1>
        <p class="subtitle">Toutes les transactions de l'utilisateur connecté.</p>
      </div>

      <div class="header-actions">
        <div class="search-wrapper">
          <span class="search-icon">🔍</span>
          <input
            v-model="search"
            class="search-input"
            type="text"
            placeholder="Rechercher (description, compte)…"
          />
        </div>

        <label class="toggle">
          <input type="checkbox" v-model="showCleared" />
          <span>Pointées uniquement</span>
        </label>

        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>

        <button class="btn btn-primary" @click="openCreate">+ Nouvelle transaction</button>
      </div>
    </header>

    <!-- Error -->
    <div v-if="error" class="alert">
      <strong>Erreur :</strong> {{ error }}
    </div>

    <!-- Skeleton / Empty -->
    <div v-if="loading && !transactions.length" class="empty">
      Chargement des transactions…
    </div>

    <div v-else-if="!loading && !filteredTransactions.length" class="empty">
      Aucune transaction à afficher.
    </div>

    <!-- Liste -->
    <div v-else class="list">
      <div v-for="tx in filteredTransactions" :key="tx.id" class="card">
        <div class="card-top">
          <div class="meta">
            <div class="date-row">
              <span class="date">{{ fmtDate(tx.post_date) }}</span>
              <span v-if="tx.effective_date && tx.effective_date !== tx.post_date" class="date-eff">
                (eff. {{ fmtDate(tx.effective_date) }})
              </span>
            </div>
            <p class="desc">{{ tx.description || '—' }}</p>
          </div>

          <div class="badges">
            <span class="badge">{{ currencyShort(tx.currency_id) }}</span>
            <span v-if="tx.is_cleared" class="badge ok">Pointé</span>
            <span v-else class="badge pending">Non pointé</span>
          </div>
        </div>

        <!-- Splits -->
        <div class="splits">
          <div v-for="split in tx.splits" :key="split.id" class="split-row">
            <span class="split-account">{{ accountName(split.account_id) }}</span>
            <span :class="['split-amount', split.quantity >= 0 ? 'pos' : 'neg']">
              {{ fmtAmount(split.quantity) }}
            </span>
          </div>
        </div>

        <div class="card-actions">
          <button class="btn-action" @click="openEdit(tx)">✎ Modifier</button>
          <button class="btn-action btn-danger" @click="deleteTransaction(tx)">✕ Supprimer</button>
        </div>
      </div>
    </div>
  </div>

  <TransactionModal
    v-model="showModal"
    :mode="modalMode"
    :transaction="selectedTx"
    @save="handleSave"
  />
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import TransactionModal from '@/components/modal/TransactionModal.vue'

const transactions = ref([])
const commodities = ref([])
const accounts = ref([])

const showModal = ref(false)
const modalMode = ref('create')
const selectedTx = ref(null)

const loading = ref(false)
const error = ref('')
const search = ref('')
const showCleared = ref(false)

// ── helpers ───────────────────────────────────────────────────────────────────

function normalizeText(v) {
  return (v ?? '').toString().toLowerCase().trim()
}

function fmtDate(v) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toLocaleDateString('fr-FR')
}

function fmtAmount(v) {
  if (v === null || v === undefined) return '0'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  const fmt = new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2, signDisplay: 'always' })
  return fmt.format(n)
}

function accountName(id) {
  const a = accounts.value.find(a => String(a.id) === String(id))
  return a ? a.name : String(id)
}

function currencyShort(id) {
  const c = commodities.value.find(c => String(c.id) === String(id))
  return c?.short_name?.toUpperCase() || '—'
}

// ── data fetching ─────────────────────────────────────────────────────────────

async function fetchAll() {
  // Charger devises et comptes en premier (nécessaires pour les dropdowns du modal)
  const [comRes, accRes] = await Promise.all([
    axios.get('/api/commodities'),
    axios.get('/api/accounts'),
  ])
  commodities.value = Array.isArray(comRes.data?.response_data) ? comRes.data.response_data : []
  accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []

  // Charger les transactions séparément
  const txRes = await axios.get('/api/transactions')
  transactions.value = Array.isArray(txRes.data?.response_data) ? txRes.data.response_data : []
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    await fetchAll()
  } catch (e) {
    error.value =
      e?.response?.data?.response_data || e?.response?.statusText || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

// ── modal ─────────────────────────────────────────────────────────────────────

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
        description: form.description || null,
        currency_id: form.currency_id,
        post_date: form.post_date,
        effective_date: form.effective_date || null,
        category_id: form.category_id || null,
        is_cleared: form.is_cleared,
        splits: form.splits,
      })
    } else {
      await axios.patch('/api/transactions', {
        transaction_id: form.id,
        description: form.description || null,
        currency_id: form.currency_id,
        post_date: form.post_date,
        effective_date: form.effective_date || null,
        category_id: form.category_id || null,
        is_cleared: form.is_cleared,
        splits: form.splits,
      })
    }
    await reload()
  } catch (e) {
    error.value =
      e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function deleteTransaction(tx) {
  if (!confirm(`Supprimer la transaction « ${tx.description || tx.id} » ?`)) return
  try {
    await axios.delete('/api/transactions', { params: { transaction_id: tx.id } })
    await reload()
  } catch (e) {
    error.value =
      e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

// ── filtering ─────────────────────────────────────────────────────────────────

const filteredTransactions = computed(() => {
  const q = normalizeText(search.value)

  return transactions.value
    .filter(tx => (showCleared.value ? tx.is_cleared : true))
    .filter(tx => {
      if (!q) return true
      const accountNames = (tx.splits || [])
        .map(s => normalizeText(accountName(s.account_id)))
        .join(' ')
      const blob = [tx.description, accountNames].map(normalizeText).join(' ')
      return blob.includes(q)
    })
})

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

.title-block h1 {
  margin: 0;
  font-size: 28px;
}

.subtitle {
  margin: 6px 0 0;
  color: #9ca3af;
  font-size: 14px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.search-wrapper {
  position: relative;
}

.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0.7;
}

.search-input {
  padding: 10px 10px 10px 32px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  outline: none;
  width: 280px;
  max-width: 70vw;
}

.toggle {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: #cbd5e1;
  user-select: none;
}
.toggle input {
  accent-color: #60a5fa;
}

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: linear-gradient(90deg, #2563eb, #4f46e5);
  border-color: transparent;
  color: #fff;
}

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

/* Cards */
.list {
  display: grid;
  gap: 12px;
}

.card {
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(2, 6, 23, 0.45);
  border-radius: 14px;
  padding: 14px;
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.date-row {
  display: flex;
  gap: 8px;
  align-items: baseline;
}

.date {
  font-size: 14px;
  font-weight: 600;
  color: #e5e7eb;
}

.date-eff {
  font-size: 12px;
  color: #6b7280;
}

.desc {
  margin: 4px 0 0;
  color: #9ca3af;
  font-size: 13px;
}

.badges {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.badge {
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(148, 163, 184, 0.10);
  color: #e5e7eb;
}

.badge.ok {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.10);
  color: #86efac;
}

.badge.pending {
  border-color: rgba(245, 158, 11, 0.3);
  background: rgba(245, 158, 11, 0.08);
  color: #fde68a;
}

/* Splits */
.splits {
  margin-top: 10px;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
  padding-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.split-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
}

.split-account {
  color: #cbd5e1;
}

.split-amount {
  font-variant-numeric: tabular-nums;
  font-weight: 500;
}

.split-amount.pos {
  color: #86efac;
}

.split-amount.neg {
  color: #fca5a5;
}

/* Actions */
.card-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  justify-content: flex-end;
}

.btn-action {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
  padding: 5px 10px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
}

.btn-action:hover {
  background: rgba(148, 163, 184, 0.1);
}

.btn-danger {
  border-color: rgba(239, 68, 68, 0.4);
  color: #fca5a5;
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.1);
}
</style>
