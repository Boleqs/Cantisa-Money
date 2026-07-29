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

        <button class="btn btn-filter" :class="{ active: activeFilterCount > 0 }" @click="filtersOpen = !filtersOpen">
          ⚙ Filtres<span v-if="activeFilterCount > 0" class="filter-badge">{{ activeFilterCount }}</span>
        </button>

        <div class="export-menu">
          <button class="btn" @click="exportMenuOpen = !exportMenuOpen">↓ Exporter</button>
          <div v-if="exportMenuOpen" class="export-dropdown">
            <button @click="exportTransactions('csv')">📄 CSV (.csv)</button>
            <button @click="exportTransactions('pdf')">🖨️ PDF (.pdf)</button>
          </div>
        </div>

        <button class="btn btn-primary" @click="openCreate">+ Nouvelle transaction</button>
      </div>
    </header>

    <!-- Filter panel -->
    <div v-if="filtersOpen" class="filter-panel">
      <div class="filter-grid">
        <div class="filter-group">
          <label class="filter-label">Date de début</label>
          <input type="date" v-model="filters.date_from" class="filter-input" @change="onFilterChange" />
        </div>
        <div class="filter-group">
          <label class="filter-label">Date de fin</label>
          <input type="date" v-model="filters.date_to" class="filter-input" @change="onFilterChange" />
        </div>
        <div class="filter-group">
          <label class="filter-label">Montant min (€)</label>
          <input type="number" v-model.number="filters.amount_min" class="filter-input" min="0" step="0.01" placeholder="0" @input="onAmountInput" />
        </div>
        <div class="filter-group">
          <label class="filter-label">Montant max (€)</label>
          <input type="number" v-model.number="filters.amount_max" class="filter-input" min="0" step="0.01" placeholder="∞" @input="onAmountInput" />
        </div>
        <div class="filter-group">
          <label class="filter-label">Compte</label>
          <select v-model="filters.account_id" class="filter-input" @change="onFilterChange">
            <option value="">— Tous —</option>
            <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.name }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label class="filter-label">Catégorie</label>
          <select v-model="filters.category_id" class="filter-input" @change="onFilterChange">
            <option value="">— Toutes —</option>
            <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </div>
        <div class="filter-group">
          <label class="filter-label">Tag</label>
          <select v-model="filters.tag_id" class="filter-input" @change="onFilterChange">
            <option value="">— Tous —</option>
            <option v-for="t in tags" :key="t.id" :value="t.id">{{ t.name }}</option>
          </select>
        </div>
      </div>
      <div class="filter-actions">
        <button class="btn btn-sm" @click="resetFilters">✕ Réinitialiser les filtres</button>
      </div>
    </div>

    <!-- Error -->
    <div v-if="error" class="alert">
      <strong>Erreur :</strong> {{ error }}
    </div>

    <!-- Skeleton / Empty -->
    <div v-if="loading && !transactions.length" class="empty">
      Chargement des transactions…
    </div>

    <div v-else-if="!loading && !transactions.length" class="empty">
      Aucune transaction à afficher.
    </div>

    <!-- Liste -->
    <div v-else class="list">
      <!-- Sélection groupée -->
      <div class="select-all-row">
        <label class="tx-select">
          <input type="checkbox" :checked="allSelectedOnPage" @change="toggleSelectAllOnPage" />
          <span>Tout sélectionner sur cette page</span>
        </label>
      </div>
      <div v-if="selectedIds.size > 0" class="bulk-toolbar">
        <span class="bulk-count">{{ selectedIds.size }} sélectionnée(s)</span>
        <button class="btn btn-sm" @click="clearSelection">Désélectionner tout</button>
        <span class="controls-sep"></span>
        <select v-model="bulkCategoryId" class="filter-input bulk-select">
          <option :value="null">— Catégorie —</option>
          <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
        </select>
        <button class="btn btn-sm" :disabled="bulkCategoryId === null || bulkApplying" @click="applyBulkCategory">Appliquer la catégorie</button>
        <button class="btn btn-sm" :disabled="bulkApplying" @click="applyBulkCleared(true)">Marquer pointées</button>
        <button class="btn btn-sm" :disabled="bulkApplying" @click="applyBulkCleared(false)">Marquer non pointées</button>
        <button class="btn btn-sm btn-danger" :disabled="bulkApplying" @click="bulkDelete">✕ Supprimer la sélection</button>
      </div>

      <div v-for="tx in transactions" :key="tx.id" class="card" :class="{ 'card-selected': selectedIds.has(tx.id) }">
        <div class="card-top">
          <label class="tx-select">
            <input type="checkbox" :checked="selectedIds.has(tx.id)" @change="toggleSelect(tx.id)" />
          </label>
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
            <span class="split-account">
              {{ accountName(split.account_id) }}
              <span v-if="split.description" class="split-memo">— {{ split.description }}</span>
            </span>
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

    <!-- Pagination -->
    <div v-if="pages > 1 || total > 0" class="pagination">
      <span class="pagination-info">{{ total }} transaction(s) — page {{ page }} / {{ pages }}</span>
      <div class="pagination-controls">
        <button class="btn-page" title="Première page" aria-label="Première page" :disabled="page <= 1" @click="goToPage(1)">«</button>
        <button class="btn-page" title="Page précédente" aria-label="Page précédente" :disabled="page <= 1" @click="goToPage(page - 1)">‹</button>
        <template v-for="p in pageRange" :key="p">
          <button v-if="p !== '…'" class="btn-page" :class="{ active: p === page }" :aria-label="`Page ${p}`" :aria-current="p === page ? 'page' : undefined" @click="goToPage(p)">{{ p }}</button>
          <span v-else class="page-ellipsis" aria-hidden="true">…</span>
        </template>
        <button class="btn-page" title="Page suivante" aria-label="Page suivante" :disabled="page >= pages" @click="goToPage(page + 1)">›</button>
        <button class="btn-page" title="Dernière page" aria-label="Dernière page" :disabled="page >= pages" @click="goToPage(pages)">»</button>
      </div>
    </div>
  </div>

  <TransactionModal
    v-model="showModal"
    :mode="modalMode"
    :transaction="selectedTx"
    @save="handleSave"
    @ocr-applied="reloadTx"
  />
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'
import TransactionModal from '@/components/modal/TransactionModal.vue'
import { confirmDialog } from '@/utils/confirmDialog'
import { useToast } from '@/utils/toast'
import { formatDate } from '@/utils/dateFormat.js'

const toast = useToast()

const route = useRoute()
const router = useRouter()

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
const exportMenuOpen = ref(false)
const filtersOpen = ref(false)

// Advanced filters
const filters = ref({ date_from: '', date_to: '', amount_min: '', amount_max: '', category_id: '', tag_id: '', account_id: '' })
const categories = ref([])
const tags = ref([])

// Pagination
const page = ref(1)
const perPage = ref(50)
const total = ref(0)
const pages = ref(1)

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtDate(v) {
  return formatDate(v)
}

function fmtAmount(v) {
  if (v === null || v === undefined) return '0'
  const n = Number(v)
  if (Number.isNaN(n)) return String(v)
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2, signDisplay: 'always' }).format(n)
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

async function fetchReferentials() {
  const [comRes, accRes, catRes, tagRes] = await Promise.all([
    axios.get('/api/commodities'),
    axios.get('/api/accounts'),
    axios.get('/api/categories'),
    axios.get('/api/tags'),
  ])
  commodities.value = Array.isArray(comRes.data?.response_data) ? comRes.data.response_data : []
  accounts.value   = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
  categories.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
  tags.value       = Array.isArray(tagRes.data?.response_data) ? tagRes.data.response_data : []
}

function buildParams() {
  const params = { page: page.value, per_page: perPage.value }
  if (search.value.trim())          params.search      = search.value.trim()
  if (showCleared.value)            params.is_cleared  = true
  if (filters.value.date_from)      params.date_from   = filters.value.date_from
  if (filters.value.date_to)        params.date_to     = filters.value.date_to
  if (filters.value.amount_min !== '') params.amount_min = filters.value.amount_min
  if (filters.value.amount_max !== '') params.amount_max = filters.value.amount_max
  if (filters.value.category_id)    params.category_id = filters.value.category_id
  if (filters.value.tag_id)         params.tag_id      = filters.value.tag_id
  if (filters.value.account_id)     params.account_id  = filters.value.account_id
  return params
}

async function fetchTransactions() {
  const txRes = await axios.get('/api/transactions', { params: buildParams() })
  const rd = txRes.data?.response_data
  transactions.value = Array.isArray(rd?.transactions) ? rd.transactions : []
  total.value = rd?.total ?? 0
  pages.value = rd?.pages ?? 1
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    await Promise.all([fetchReferentials(), fetchTransactions()])
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.response?.statusText || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

async function reloadTx() {
  loading.value = true
  error.value = ''
  // La sélection groupée ne survit pas à un rechargement (page/filtre changé, ou action groupée
  // déjà appliquée) — évite une sélection "fantôme" sur des transactions qui ne sont plus affichées.
  selectedIds.value = new Set()
  try {
    await fetchTransactions()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

// ── sélection groupée ─────────────────────────────────────────────────────────

const selectedIds = ref(new Set())
const bulkCategoryId = ref(null)
const bulkApplying = ref(false)

function toggleSelect(id) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

const allSelectedOnPage = computed(() =>
  transactions.value.length > 0 && transactions.value.every(t => selectedIds.value.has(t.id))
)

function toggleSelectAllOnPage() {
  const next = new Set(selectedIds.value)
  if (allSelectedOnPage.value) {
    transactions.value.forEach(t => next.delete(t.id))
  } else {
    transactions.value.forEach(t => next.add(t.id))
  }
  selectedIds.value = next
}

function clearSelection() {
  selectedIds.value = new Set()
}

function selectedTransactions() {
  return transactions.value.filter(t => selectedIds.value.has(t.id))
}

// PATCH /api/transactions attend une représentation complète de la transaction (pas un patch
// partiel) — on repart donc de chaque transaction déjà chargée, en ne changeant que le(s) champ(s)
// visé(s) par l'action groupée, splits et description inclus pour ne rien écraser par erreur.
function buildFullPatch(tx, overrides) {
  return {
    transaction_id: tx.id,
    description: tx.description || null,
    post_date: (tx.post_date || '').slice(0, 10),
    effective_date: tx.effective_date ? tx.effective_date.slice(0, 10) : null,
    category_id: tx.category_id || null,
    is_cleared: tx.is_cleared,
    splits: tx.splits.map(s => ({ account_id: s.account_id, quantity: s.quantity, description: s.description || null })),
    ...overrides,
  }
}

async function applyBulkCategory() {
  if (bulkCategoryId.value === null || bulkApplying.value) return
  const targets = selectedTransactions()
  if (!targets.length) return
  bulkApplying.value = true
  error.value = ''
  try {
    await Promise.all(targets.map(tx => axios.patch('/api/transactions', buildFullPatch(tx, { category_id: bulkCategoryId.value }))))
    toast.success(`Catégorie appliquée à ${targets.length} transaction(s).`)
    bulkCategoryId.value = null
    await reloadTx()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la mise à jour groupée'
  } finally {
    bulkApplying.value = false
  }
}

async function applyBulkCleared(value) {
  const targets = selectedTransactions()
  if (!targets.length || bulkApplying.value) return
  bulkApplying.value = true
  error.value = ''
  try {
    await Promise.all(targets.map(tx => axios.patch('/api/transactions', buildFullPatch(tx, { is_cleared: value }))))
    toast.success(`${targets.length} transaction(s) mise(s) à jour.`)
    await reloadTx()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la mise à jour groupée'
  } finally {
    bulkApplying.value = false
  }
}

async function bulkDelete() {
  const targets = selectedTransactions()
  if (!targets.length) return
  const ok = await confirmDialog({
    title: 'Supprimer les transactions sélectionnées',
    message: `Supprimer définitivement ${targets.length} transaction(s) ? Cette action est irréversible.`,
    confirmLabel: 'Supprimer',
    danger: true,
  })
  if (!ok) return
  bulkApplying.value = true
  error.value = ''
  try {
    await Promise.all(targets.map(tx => axios.delete('/api/transactions', { params: { transaction_id: tx.id } })))
    toast.success(`${targets.length} transaction(s) supprimée(s).`)
    await reloadTx()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la suppression groupée'
  } finally {
    bulkApplying.value = false
  }
}

// ── pagination ────────────────────────────────────────────────────────────────

function goToPage(p) {
  if (p < 1 || p > pages.value) return
  page.value = p
  reloadTx()
}

// ── search / filter with debounce ─────────────────────────────────────────────

let searchTimer = null
watch(search, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; reloadTx() }, 300)
})

watch(showCleared, () => { page.value = 1; reloadTx() })

onUnmounted(() => { clearTimeout(searchTimer); clearTimeout(amountTimer) })

// ── advanced filters ──────────────────────────────────────────────────────────

const activeFilterCount = computed(() =>
  Object.values(filters.value).filter(v => v !== '' && v !== null && v !== undefined).length
)

function onFilterChange() { page.value = 1; reloadTx() }

let amountTimer = null
function onAmountInput() {
  clearTimeout(amountTimer)
  amountTimer = setTimeout(() => { page.value = 1; reloadTx() }, 400)
}

function resetFilters() {
  filters.value = { date_from: '', date_to: '', amount_min: '', amount_max: '', category_id: '', tag_id: '', account_id: '' }
  page.value = 1
  reloadTx()
}

// ── export ────────────────────────────────────────────────────────────────────

async function exportTransactions(fmt) {
  exportMenuOpen.value = false
  try {
    const p = buildParams()
    p.format = fmt
    delete p.page
    delete p.per_page
    const params = new URLSearchParams(Object.entries(p).filter(([, v]) => v !== undefined && v !== ''))
    const res = await axios.get(`/api/transactions/export?${params}`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `transactions.${fmt}`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = 'Erreur lors de l\'export'
  }
}

// Numéros de pages à afficher (max 7 boutons avec ellipses)
const pageRange = computed(() => {
  const p = pages.value
  if (p <= 7) return Array.from({ length: p }, (_, i) => i + 1)
  const cur = page.value
  const set = new Set([1, 2, p - 1, p, cur - 1, cur, cur + 1].filter(x => x >= 1 && x <= p))
  const sorted = [...set].sort((a, b) => a - b)
  const result = []
  for (let i = 0; i < sorted.length; i++) {
    if (i > 0 && sorted[i] - sorted[i - 1] > 1) result.push('…')
    result.push(sorted[i])
  }
  return result
})

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
        post_date: form.post_date,
        effective_date: form.effective_date || null,
        category_id: form.category_id || null,
        is_cleared: form.is_cleared,
        splits: form.splits,
      })
    }
    await reloadTx()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function deleteTransaction(tx) {
  const ok = await confirmDialog({
    title: 'Supprimer la transaction',
    message: `Supprimer la transaction « ${tx.description || tx.id} » ?`,
    confirmLabel: 'Supprimer',
    danger: true,
  })
  if (!ok) return
  try {
    await axios.delete('/api/transactions', { params: { transaction_id: tx.id } })
    await reloadTx()
    toast.success('Transaction supprimée.')
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

function closeExportMenu(e) {
  if (!e.target.closest('.export-menu')) exportMenuOpen.value = false
}

// Ouverture directe d'une transaction depuis un lien externe (ex: liste des justificatifs de
// la page Factures) via /transactions?tx_id=...
async function openFromQuery() {
  const txId = route.query.tx_id
  if (!txId) return
  try {
    const { data } = await axios.get('/api/transactions', { params: { transaction_id: txId } })
    if (data?.response_data) openEdit(data.response_data)
  } catch (e) {
    error.value = 'Transaction introuvable'
  } finally {
    router.replace({ query: {} })
  }
}

onMounted(() => document.addEventListener('click', closeExportMenu))
onMounted(reload)
onMounted(openFromQuery)
onUnmounted(() => document.removeEventListener('click', closeExportMenu))
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
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
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

.card-selected {
  border-color: rgba(96, 165, 250, 0.55);
  background: rgba(59, 130, 246, 0.08);
}

.tx-select {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #9ca3af;
  cursor: pointer;
  user-select: none;
}

.tx-select input[type='checkbox'] {
  width: 16px;
  height: 16px;
  accent-color: #3b82f6;
  cursor: pointer;
}

.select-all-row {
  padding: 4px 4px 2px;
}

.bulk-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 12px 14px;
  border: 1px solid rgba(96, 165, 250, 0.35);
  background: rgba(59, 130, 246, 0.08);
  border-radius: 12px;
}

.bulk-count {
  font-size: 13px;
  font-weight: 600;
  color: #93c5fd;
  white-space: nowrap;
}

.controls-sep {
  width: 1px;
  align-self: stretch;
  background: rgba(148, 163, 184, 0.25);
}

.bulk-select {
  min-width: 200px;
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

.split-memo {
  color: #6b7280;
  font-size: 12px;
  font-style: italic;
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

/* Filter button */
.btn-filter { position: relative; }
.btn-filter.active { border-color: rgba(96, 165, 250, 0.5); color: #93c5fd; }

.filter-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #3b82f6;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  margin-left: 6px;
}

/* Filter panel */
.filter-panel {
  border: 1px solid rgba(96, 165, 250, 0.2);
  background: rgba(15, 23, 42, 0.6);
  border-radius: 14px;
  padding: 16px 20px;
  margin-bottom: 16px;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px 16px;
  margin-bottom: 14px;
}

.filter-group { display: flex; flex-direction: column; gap: 5px; }

.filter-label {
  font-size: 12px;
  color: #9ca3af;
}

.filter-input {
  padding: 7px 10px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 13px;
  outline: none;
}

.filter-input:focus { border-color: rgba(96, 165, 250, 0.5); }
.filter-input option { background: #1e293b; }

.filter-actions { display: flex; gap: 8px; }

.btn-sm {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #9ca3af;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
}
.btn-sm:hover { background: rgba(148, 163, 184, 0.1); color: #e5e7eb; }

/* Export menu */
.export-menu {
  position: relative;
}

.export-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  background: #1e293b;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 10px;
  padding: 6px;
  z-index: 50;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 160px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
}

.export-dropdown button {
  background: transparent;
  border: none;
  color: #cbd5e1;
  padding: 8px 12px;
  border-radius: 7px;
  text-align: left;
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
}

.export-dropdown button:hover {
  background: rgba(148, 163, 184, 0.1);
}

/* Pagination */
.pagination {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
}

.pagination-info {
  font-size: 13px;
  color: #9ca3af;
}

.pagination-controls {
  display: flex;
  gap: 4px;
  align-items: center;
}

.btn-page {
  min-width: 32px;
  height: 32px;
  padding: 0 6px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(15, 23, 42, 0.7);
  color: #cbd5e1;
  border-radius: 7px;
  font-size: 13px;
  cursor: pointer;
  transition: 0.15s;
}

.btn-page:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.btn-page:not(:disabled):hover {
  background: rgba(148, 163, 184, 0.12);
}

.btn-page.active {
  background: rgba(37, 99, 235, 0.25);
  border-color: rgba(96, 165, 250, 0.5);
  color: #93c5fd;
  font-weight: 600;
}

.page-ellipsis {
  color: #6b7280;
  padding: 0 4px;
  font-size: 13px;
}

/* Écran étroit (tablette/mobile) : audit UX du 2026-07-27 — aucun breakpoint jusqu'ici sur l'un
   des deux écrans les plus utilisés au quotidien. Le padding généreux et la recherche en largeur
   fixe étaient les premiers points de débordement réel, même si flex-wrap limitait déjà les dégâts
   ailleurs (cartes, filtres, pagination). */
@media (max-width: 640px) {
  .page { padding: 14px; }
  .page-header { align-items: stretch; }
  .header-actions { width: 100%; }
  .search-wrapper { flex: 1 1 100%; }
  .search-input { width: 100%; max-width: none; }
  .card-top { flex-wrap: wrap; }
  .badges { justify-content: flex-start; }
  .filter-grid { grid-template-columns: 1fr; }
}
</style>
