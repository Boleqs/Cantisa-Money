<template>
  <div class="page">
    <!-- Header -->
    <header class="page-header">
      <div class="title-block">
        <button class="back-btn" @click="$router.push('/accounts')">← Comptes</button>
        <p v-if="accountBreadcrumb" class="breadcrumb">{{ accountBreadcrumb }}</p>
        <div v-if="account" class="name-row">
          <h1>{{ account.name }}</h1>
          <span v-if="account.code" class="code">#{{ account.code }}</span>
          <span class="badge">{{ account.account_type }}</span>
          <span v-if="account.account_subtype" class="badge soft">{{ account.account_subtype }}</span>
          <span v-if="account.is_hidden" class="badge danger">Caché</span>
          <span v-if="account.is_virtual" class="badge warn">Virtuel</span>
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

    <!-- Figure clé + stats latérales -->
    <div v-if="account && accountFigure" class="hero-row">
      <div class="hero-card">
        <div class="hero-label">{{ accountFigure.label }}</div>
        <div class="hero-value" :class="accountFigure.colorClass">
          {{ fmtAssetAmount(accountFigure.value, accountFigure.currency) }}
        </div>
        <div v-if="accountFigure.kind !== 'flow' && accountFigure.kind !== 'assets'" class="flow-split">
          <div class="flow-item">
            <div class="fl">Crédité</div>
            <div class="fv">{{ fmtAssetAmount(accountFigure.earned, accountFigure.currency) }}</div>
          </div>
          <div class="flow-item">
            <div class="fl">Débité</div>
            <div class="fv">{{ fmtAssetAmount(accountFigure.spent, accountFigure.currency) }}</div>
          </div>
        </div>
        <div v-if="accountFigure.kind !== 'flow' && accountFigure.kind !== 'assets'" class="flow-bar">
          <div class="seg-pos" :style="{ width: flowPct.pos + '%' }"></div>
          <div class="seg-neg" :style="{ width: flowPct.neg + '%' }"></div>
        </div>
      </div>

      <div class="side-stats">
        <div class="stat-card">
          <div class="stat-label">Transactions</div>
          <div class="stat-value">{{ txTotal }}</div>
        </div>
        <div v-if="isAssetAccount && accountPositions.length" class="stat-card">
          <div class="stat-label">Positions ouvertes</div>
          <div class="stat-value">{{ openPositionsCount }} / {{ accountPositions.length }}</div>
        </div>
        <div v-else-if="hasChildren" class="stat-card">
          <div class="stat-label">Sous-comptes</div>
          <div class="stat-value">{{ childAccountsCount }}</div>
        </div>
      </div>
    </div>

    <!-- Actifs détenus (compte-titre) -->
    <div v-if="isAssetAccount" class="asset-section">
      <div class="asset-section-header">
        <h2>Actifs détenus</h2>
        <router-link to="/portfolio" class="link-portfolio">Gérer via Portfolio →</router-link>
      </div>
      <div v-if="!accountPositions.length" class="empty">Aucun actif détenu sur ce compte.</div>
      <div v-else class="tx-list asset-list">
        <div class="tx-list-header asset-row-grid">
          <span>Actif</span>
          <span class="align-right">Quantité</span>
          <span class="align-right">Prix d'achat</span>
          <span class="align-right">Valeur actuelle</span>
        </div>
        <div
          v-for="{ possession: p, asset: a } in accountPositions"
          :key="p.id"
          class="tx-row asset-row-grid"
          :class="{ 'possession-closed': remainingQty(p) === 0 }"
        >
          <span class="tx-desc">{{ a.symbol }} — {{ a.name }}</span>
          <span class="align-right">{{ p.disposals?.length ? `${remainingQty(p)} / ${p.quantity}` : p.quantity }}</span>
          <span class="align-right muted">{{ p.purchase_price != null ? fmtAssetAmount(p.purchase_price, a.display_currency) : '—' }}</span>
          <span class="align-right tx-amount">{{ fmtAssetAmount(remainingQty(p) * a.converted_value_per_unit, a.display_currency) }}</span>
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
import { hasPermission } from '@/utils/permissions.js'
import { currency as defaultCurrency } from '@/utils/settings.js'
import { confirmDialog } from '@/utils/confirmDialog'
import { useToast } from '@/utils/toast'
import { normalizeSearch } from '@/utils/search.js'
import { formatDate } from '@/utils/dateFormat.js'
import { accountDisplayLabel } from '@/utils/accountDisplay.js'
import { ensureInstitutionsLoaded } from '@/utils/institutions.js'

const toast = useToast()

const route = useRoute()
const accountId = route.params.id

const account = ref(null)
const allAccounts = ref([])
const transactions = ref([])
const categories = ref([])
const commodities = ref([])
const assets = ref([])
// Valeur autoritaire (positions + cash libre) du compte-titre, calculée côté backend — voir
// accountAssetsValue plus bas.
const accountValues = ref(new Map())

const loading = ref(false)
const error = ref('')
const txTotal = ref(0)

const search = ref('')
const onlyCleared = ref(false)

const showModal = ref(false)
const modalMode = ref('create')
const selectedTx = ref(null)

// /api/transactions pagine côté backend (200 par page max) — la vue détail de compte n'a pas
// de pagination dans son UI et doit donc afficher tout l'historique du compte : on boucle sur
// les pages plutôt que de se limiter à la première (bug constaté le 2026-08-16 : un compte avec
// plus de 50 transactions en perdait silencieusement la fin, page 1 par défaut jamais dépassée).
async function fetchAllAccountTransactions() {
  const perPage = 200
  const first = await axios.get('/api/transactions', { params: { account_id: accountId, page: 1, per_page: perPage } })
  const rd = first.data?.response_data
  const all = Array.isArray(rd?.transactions) ? rd.transactions.slice() : []
  const pages = rd?.pages || 1
  const fetches = []
  for (let p = 2; p <= pages; p++) {
    fetches.push(axios.get('/api/transactions', { params: { account_id: accountId, page: p, per_page: perPage } }))
  }
  const rest = await Promise.all(fetches)
  for (const res of rest) {
    const page = res.data?.response_data
    if (Array.isArray(page?.transactions)) all.push(...page.transactions)
  }
  return { transactions: all, total: rd?.total ?? all.length }
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const calls = [
      axios.get('/api/accounts', { params: { account_id: accountId } }),
      axios.get('/api/accounts'),
      fetchAllAccountTransactions(),
      axios.get('/api/categories'),
      axios.get('/api/commodities'),
      ensureInstitutionsLoaded(),
    ]
    // Compte-titre potentiel : on ne sait pas encore le account_type avant la réponse, donc on
    // ne fetch les actifs que si l'utilisateur a la permission — le filtrage par type se fait
    // ensuite à l'affichage (isAssetAccount).
    if (hasPermission('Patrimoine')) {
      calls.push(axios.get('/api/assets'))
      calls.push(axios.get('/api/wealth/account-values', { params: { currency: defaultCurrency.value } }))
    }
    // `institutionsData` n'est jamais lu : ensureInstitutionsLoaded() peuple le ref partagé
    // `institutions` en effet de bord, seul son ordre dans `calls` compte pour la déstructuration
    // (un slot anonyme ici décalait assetsRes/accountValuesRes d'un cran).
    const [accRes, allAccRes, txData, catRes, comRes, institutionsData, assetsRes, accountValuesRes] = await Promise.all(calls)
    account.value = accRes.data?.response_data ?? null
    allAccounts.value = Array.isArray(allAccRes.data?.response_data) ? allAccRes.data.response_data : []
    transactions.value = txData.transactions
    txTotal.value = txData.total
    categories.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
    commodities.value = Array.isArray(comRes.data?.response_data) ? comRes.data.response_data : []
    assets.value = Array.isArray(assetsRes?.data?.response_data) ? assetsRes.data.response_data : []
    const accountValuesData = accountValuesRes?.data?.response_data?.values || {}
    accountValues.value = new Map(Object.entries(accountValuesData))
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

const hasChildren = computed(() =>
  allAccounts.value.some(a => String(a.parent_id) === String(accountId))
)

// Institution + chaîne de parents (sans le compte lui-même, déjà affiché en <h1>) — ce compte
// peut porter le même nom qu'un autre compte du même utilisateur (voir rt_accounts.py, l'unicité
// n'est plus globale), donc utile pour confirmer qu'on est bien sur le bon dans certains cas.
const accountBreadcrumb = computed(() => {
  if (!account.value) return '';
  const full = accountDisplayLabel(account.value, allAccounts.value);
  const ownName = account.value.name;
  // Retire le dernier segment (le nom du compte courant) de "Institution → Parent → Compte"
  const idx = full.lastIndexOf(` → ${ownName}`);
  return idx !== -1 ? full.slice(0, idx) : '';
})

const childAccountsCount = computed(() =>
  allAccounts.value.filter(a => String(a.parent_id) === String(accountId)).length
)

// Un compte-titre (Assets/Equity) porte des positions d'actifs (AssetPossession) plutôt que des
// soldes classiques — cf. add_possession backend qui n'autorise ces positions que sur ces types.
const isAssetAccount = computed(() => ['Assets', 'Equity'].includes(account.value?.account_type))

function remainingQty(p) {
  return p.remaining_quantity != null ? p.remaining_quantity : p.quantity
}

// Une position n'expose que son account_id ; on la recombine ici avec l'actif parent (symbole,
// nom, valeur convertie dans la devise par défaut déjà calculée côté backend GET /api/assets).
const accountPositions = computed(() => {
  const rows = []
  for (const a of assets.value) {
    for (const p of a.possessions || []) {
      if (String(p.account_id) === String(accountId)) rows.push({ possession: p, asset: a })
    }
  }
  return rows
})

// Repli position-seule tant que accountValues n'a pas répondu ; la valeur autoritaire (positions +
// cash libre éventuellement laissé sur le compte) vient du backend, voir GET /api/wealth/account-values.
const accountAssetsValue = computed(() => {
  const backendValue = accountValues.value.get(String(accountId))
  if (backendValue != null) return backendValue
  return accountPositions.value.reduce((sum, { possession, asset }) =>
    sum + remainingQty(possession) * (asset.converted_value_per_unit || 0), 0)
})

function fmtAssetAmount(v, currency) {
  return `${new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v || 0)} ${currency || ''}`.trim()
}

const openPositionsCount = computed(() =>
  accountPositions.value.filter(({ possession }) => remainingQty(possession) > 0).length
)

// Figure clé du compte, même logique que Accounts.vue (accountFigure) : valeur des actifs pour un
// compte-titre actif, capital restant dû pour un passif, cumul neutre pour Income/Expense (le
// trigger SQL crédite toujours ces comptes en négatif/positif selon le sens du flux — soustraire
// earned - spent donnerait un signe trompeur, ex. "Solde -9 600" sur un compte de salaires), solde
// classique sinon.
const accountFigure = computed(() => {
  if (!account.value) return null
  if (isAssetAccount.value && accountPositions.value.length) {
    return {
      kind: 'assets', label: 'Valeur des actifs', value: accountAssetsValue.value,
      currency: accountPositions.value[0].asset.display_currency, colorClass: 'neutral',
    }
  }
  const hc = hasChildren.value
  const earned = Number(hc ? account.value.consolidated_earned : account.value.total_earned) || 0
  const spent = Number(hc ? account.value.consolidated_spent : account.value.total_spent) || 0
  const currency = currencyShort.value

  if (account.value.account_type === 'Liability') {
    return { kind: 'liability', label: 'Capital restant dû', value: Math.abs(earned - spent), currency, colorClass: 'neg', earned, spent }
  }
  if (account.value.account_type === 'Income') {
    return { kind: 'flow', label: hc ? 'Total perçu (consolidé)' : 'Total perçu', value: spent, currency, colorClass: 'neutral', earned, spent }
  }
  if (account.value.account_type === 'Expense') {
    return { kind: 'flow', label: hc ? 'Total dépensé (consolidé)' : 'Total dépensé', value: earned, currency, colorClass: 'neutral', earned, spent }
  }
  const solde = earned - spent
  return { kind: hc ? 'solde-consolide' : 'solde', label: hc ? 'Solde consolidé' : 'Solde', value: solde, currency, colorClass: solde >= 0 ? 'pos' : 'neg', earned, spent }
})

const flowPct = computed(() => {
  const f = accountFigure.value
  if (!f || f.kind === 'flow' || f.kind === 'assets') return { pos: 50, neg: 50 }
  const total = f.earned + f.spent
  if (!total) return { pos: 50, neg: 50 }
  return { pos: (f.earned / total) * 100, neg: (f.spent / total) * 100 }
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

const fmtDate = formatDate

const filteredTx = computed(() => {
  const q = normalizeSearch(search.value)
  return transactions.value.filter(tx => {
    if (onlyCleared.value && !tx.is_cleared) return false
    if (q && !normalizeSearch(tx.description || '').includes(q)) return false
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
  const ok = await confirmDialog({
    title: 'Supprimer la transaction',
    message: `Supprimer la transaction « ${tx.description || 'sans libellé'} » ?`,
    confirmLabel: 'Supprimer',
    danger: true,
  })
  if (!ok) return
  try {
    await axios.delete('/api/transactions', { params: { transaction_id: tx.id } })
    await reload()
    toast.success('Transaction supprimée.')
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

.breadcrumb {
  margin: 0;
  color: #6b7280;
  font-size: 12px;
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

/* Figure clé + stats latérales */
.hero-row {
  display: flex;
  gap: 14px;
  align-items: stretch;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.hero-card {
  flex: 1 1 300px;
  border: 1px solid rgba(148,163,184,.18);
  border-radius: 16px;
  background: linear-gradient(165deg, rgba(59,130,246,.10), rgba(15,23,42,.4));
  padding: 22px 24px;
}
.hero-label { font-size: 12px; color: #9ca3af; font-weight: 600; }
.hero-value {
  font-size: 32px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  margin-top: 6px;
  letter-spacing: -.01em;
  color: #e5e7eb;
}
.hero-value.pos { color: #86efac; }
.hero-value.neg { color: #fca5a5; }
.hero-value.neutral { color: #e5e7eb; }

.flow-split { display: flex; gap: 20px; margin-top: 16px; }
.flow-item { flex: 1; }
.flow-item .fl { font-size: 10.5px; color: #9ca3af; text-transform: uppercase; letter-spacing: .05em; }
.flow-item .fv { font-size: 14px; font-weight: 600; font-variant-numeric: tabular-nums; margin-top: 3px; color: #e5e7eb; }
.flow-bar {
  height: 5px;
  border-radius: 999px;
  background: rgba(148,163,184,.12);
  margin-top: 14px;
  overflow: hidden;
  display: flex;
}
.flow-bar .seg-pos { background: #4ade80; }
.flow-bar .seg-neg { background: #f87171; }

.side-stats {
  flex: 0 1 200px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.stat-card {
  border: 1px solid rgba(148,163,184,.18);
  background: rgba(15,23,42,.55);
  border-radius: 14px;
  padding: 16px 18px;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.stat-label { font-size: 11px; color: #9ca3af; text-transform: uppercase; letter-spacing: .05em; }
.stat-value { font-size: 20px; font-weight: 700; margin-top: 5px; font-variant-numeric: tabular-nums; color: #e5e7eb; }

/* Actifs détenus */
.asset-section { margin-bottom: 20px; }
.asset-section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 10px;
}
.asset-section-header h2 {
  margin: 0;
  font-size: 15px;
  color: #cbd5e1;
}
.link-portfolio {
  font-size: 12px;
  color: #93c5fd;
  text-decoration: none;
}
.link-portfolio:hover { text-decoration: underline; }
.asset-row-grid { grid-template-columns: 1fr 120px 160px 160px; }
.possession-closed { opacity: 0.45; }

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
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
  border-color: transparent;
  color: #fff;
}
</style>
