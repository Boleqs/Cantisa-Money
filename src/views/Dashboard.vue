<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Dashboard</h1>
        <p class="subtitle">Vue d'ensemble de vos finances.</p>
      </div>
      <button class="btn" :disabled="loading" @click="reload">
        <span v-if="!loading">↻ Rafraîchir</span>
        <span v-else>Chargement…</span>
      </button>
    </header>

    <div v-if="error" class="alert">{{ error }}</div>

    <!-- KPI Cards -->
    <div class="kpi-grid">
      <div class="kpi-card kpi-card--featured">
        <div class="kpi-label">Patrimoine net</div>
        <div class="kpi-value" :class="kpis.net_worth >= 0 ? 'pos' : 'neg'">
          {{ fmtAmount(kpis.net_worth) }}
        </div>
        <div class="kpi-sub">Current + Assets + Equity</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Solde courant</div>
        <div class="kpi-value" :class="kpis.current_balance >= 0 ? 'pos' : 'neg'">
          {{ fmtAmount(kpis.current_balance) }}
        </div>
        <div class="kpi-sub">Comptes courants</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Revenus du mois</div>
        <div class="kpi-value pos">+ {{ fmtAmount(kpis.monthly_income) }}</div>
        <div class="kpi-sub">{{ currentMonthLabel }}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Dépenses du mois</div>
        <div class="kpi-value neg">- {{ fmtAmount(kpis.monthly_expenses) }}</div>
        <div class="kpi-sub">{{ currentMonthLabel }}</div>
      </div>
    </div>

    <!-- Net worth history -->
    <div class="card">
      <div class="card-title">Évolution du patrimoine net — 12 derniers mois</div>
      <div v-if="networthHistory.length < 2" class="no-data">Pas assez de données.</div>
      <div v-else class="svg-wrapper">
        <svg :viewBox="`0 0 ${SVG_W} ${SVG_H}`" preserveAspectRatio="none" class="chart-svg">
          <defs>
            <linearGradient id="nwGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#10b981" stop-opacity="0.30"/>
              <stop offset="100%" stop-color="#10b981" stop-opacity="0.02"/>
            </linearGradient>
          </defs>

          <!-- Zero line -->
          <line v-if="nwZeroY !== null"
            :x1="NW_PAD.l" :y1="nwZeroY" :x2="SVG_W - NW_PAD.r" :y2="nwZeroY"
            stroke="rgba(148,163,184,0.2)" stroke-width="1" stroke-dasharray="4,3"
          />

          <!-- Area fill -->
          <polygon :points="nwAreaPoints" fill="url(#nwGrad)" />

          <!-- Line -->
          <polyline :points="nwLinePoints" fill="none" stroke="#10b981" stroke-width="1.8" stroke-linejoin="round"/>

          <!-- Dots at each data point -->
          <circle
            v-for="(d, i) in networthHistory"
            :key="d.month"
            :cx="nwScaleX(i)" :cy="nwScaleY(d.net_worth)"
            r="2.5" fill="#10b981"
          />

          <!-- Y labels -->
          <text :x="NW_PAD.l - 4" :y="NW_PAD.t + 4" text-anchor="end" class="svg-label">
            {{ fmtAmountShort(nwMax) }}
          </text>
          <text :x="NW_PAD.l - 4" :y="SVG_H - NW_PAD.b" text-anchor="end" class="svg-label">
            {{ fmtAmountShort(nwMin) }}
          </text>

          <!-- X labels -->
          <text
            v-for="lbl in nwXLabels"
            :key="lbl.label"
            :x="lbl.x" :y="SVG_H - 4"
            text-anchor="middle" class="svg-label"
          >{{ lbl.label }}</text>
        </svg>
      </div>
    </div>

    <!-- Charts -->
    <div class="charts-grid">

      <!-- Balance history -->
      <div class="card">
        <div class="card-title">Évolution du solde — 30 derniers jours</div>
        <div v-if="balanceHistory.length < 2" class="no-data">Pas assez de données.</div>
        <div v-else class="svg-wrapper">
          <svg :viewBox="`0 0 ${SVG_W} ${SVG_H}`" preserveAspectRatio="none" class="chart-svg">
            <defs>
              <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.25"/>
                <stop offset="100%" stop-color="#3b82f6" stop-opacity="0.02"/>
              </linearGradient>
            </defs>

            <!-- Zero line -->
            <line v-if="zeroY !== null"
              :x1="PAD.l" :y1="zeroY" :x2="SVG_W - PAD.r" :y2="zeroY"
              stroke="rgba(148,163,184,0.2)" stroke-width="1" stroke-dasharray="4,3"
            />

            <!-- Area fill -->
            <polygon :points="areaPoints" fill="url(#areaGrad)" />

            <!-- Line -->
            <polyline :points="linePoints" fill="none" stroke="#3b82f6" stroke-width="1.5" stroke-linejoin="round"/>

            <!-- Y labels -->
            <text :x="PAD.l - 4" :y="PAD.t + 4" text-anchor="end" class="svg-label">
              {{ fmtAmountShort(chartMax) }}
            </text>
            <text :x="PAD.l - 4" :y="SVG_H - PAD.b" text-anchor="end" class="svg-label">
              {{ fmtAmountShort(chartMin) }}
            </text>

            <!-- X labels -->
            <text :x="PAD.l" :y="SVG_H - 2" class="svg-label">
              {{ balanceHistory[0]?.date?.slice(5) }}
            </text>
            <text :x="SVG_W - PAD.r" :y="SVG_H - 2" text-anchor="end" class="svg-label">
              {{ balanceHistory[balanceHistory.length - 1]?.date?.slice(5) }}
            </text>
          </svg>
        </div>
      </div>

      <!-- Expenses by category -->
      <div class="card">
        <div class="card-title">Dépenses par catégorie — {{ currentMonthLabel }}</div>
        <div v-if="!expensesByCategory.length" class="no-data">Aucune dépense ce mois.</div>
        <div v-else class="cat-list">
          <div v-for="c in expensesByCategory" :key="c.name" class="cat-row">
            <div class="cat-name">{{ c.name }}</div>
            <div class="cat-bar-wrap">
              <div class="cat-bar" :style="{ width: (c.total / maxExpense * 100) + '%' }"></div>
            </div>
            <div class="cat-amount">{{ fmtAmount(c.total) }}</div>
          </div>
        </div>
      </div>

    </div>

    <!-- Bottom grid -->
    <div class="bottom-grid">

      <!-- Accounts -->
      <div class="card">
        <div class="card-title">Comptes</div>
        <div v-if="!accounts.length" class="no-data">Aucun compte.</div>
        <div v-else class="acc-list">
          <div
            v-for="a in sortedAccounts"
            :key="a.id"
            class="acc-row"
            :class="{ 'acc-row--child': a._depth > 0 }"
            :style="a._depth > 0 ? { marginLeft: (a._depth * 20) + 'px' } : {}"
          >
            <div class="acc-left">
              <span v-if="a._depth > 0" class="tree-prefix">└</span>
              <span class="acc-name">{{ a.name }}</span>
              <span class="acc-type chip">{{ a.account_type }}</span>
            </div>
            <span class="acc-balance" :class="accountBalance(a) >= 0 ? 'pos' : 'neg'">
              {{ fmtAmount(accountBalance(a)) }}
            </span>
          </div>
        </div>
      </div>

      <!-- Active budgets -->
      <div class="card">
        <div class="card-title">Budgets actifs</div>
        <div v-if="!activeBudgets.length" class="no-data">Aucun budget actif.</div>
        <div v-else class="budget-list">
          <div v-for="b in activeBudgets" :key="b.id" class="budget-row">
            <div class="budget-top">
              <span class="budget-dates">{{ fmtDate(b.start_date) }} → {{ fmtDate(b.end_date) }}</span>
              <span class="budget-amounts">
                {{ fmtAmount(b.amount_spent) }} / {{ fmtAmount(b.amount_allocated) }}
              </span>
            </div>
            <div class="progress-track">
              <div
                class="progress-bar"
                :class="budgetColor(b)"
                :style="{ width: Math.min(budgetPct(b), 100) + '%' }"
              ></div>
            </div>
            <div class="budget-pct" :class="budgetColor(b)">{{ budgetPct(b) }}%</div>
          </div>
        </div>
      </div>

    </div>

    <!-- Recent transactions -->
    <div class="card mt">
      <div class="card-title">Activité récente</div>
      <div v-if="!recentTransactions.length" class="no-data">Aucune transaction.</div>
      <div v-else class="tx-list">
        <div v-for="tx in recentTransactions" :key="tx.id" class="tx-row">
          <div class="tx-left">
            <span class="tx-date">{{ fmtDate(tx.post_date) }}</span>
            <span class="tx-desc">{{ tx.description || '—' }}</span>
          </div>
          <div class="tx-splits">
            <span v-for="s in tx.splits" :key="s.id"
              :class="['tx-amount', s.quantity >= 0 ? 'pos' : 'neg']">
              {{ fmtAmountSigned(s.quantity) }}
            </span>
          </div>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

// ── Data ──────────────────────────────────────────────────────────────────────
const kpis = ref({ current_balance: 0, assets_balance: 0, monthly_income: 0, monthly_expenses: 0, net_worth: 0 })
const balanceHistory = ref([])
const networthHistory = ref([])
const expensesByCategory = ref([])
const accounts = ref([])
const budgets = ref([])
const transactions = ref([])

const loading = ref(false)
const error = ref('')

// ── SVG constants ─────────────────────────────────────────────────────────────
const SVG_W = 500
const SVG_H = 130
const PAD = { t: 14, b: 18, l: 44, r: 10 }
const innerW = SVG_W - PAD.l - PAD.r
const innerH = SVG_H - PAD.t - PAD.b

// net worth chart uses same dimensions
const NW_PAD = { t: 14, b: 22, l: 52, r: 10 }

// ── Helpers ───────────────────────────────────────────────────────────────────
const currentMonthLabel = computed(() => {
  const d = new Date()
  return d.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
})

function fmtAmount(v) {
  const n = Number(v ?? 0)
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(n)
}
function fmtAmountSigned(v) {
  const n = Number(v ?? 0)
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2, signDisplay: 'always' }).format(n)
}
function fmtAmountShort(v) {
  const n = Number(v ?? 0)
  if (Math.abs(n) >= 1000) return (n / 1000).toFixed(1) + 'k'
  return Math.round(n).toString()
}
function fmtDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' })
}

function accountBalance(a) {
  return (Number(a.total_earned) || 0) - (Number(a.total_spent) || 0)
}

function budgetPct(b) {
  if (!b.amount_allocated) return 0
  return Math.round((b.amount_spent / b.amount_allocated) * 100)
}
function budgetColor(b) {
  const p = budgetPct(b)
  if (p >= 100) return 'danger'
  if (p >= 80) return 'warn'
  return 'ok'
}

// ── Computed ──────────────────────────────────────────────────────────────────
const maxExpense = computed(() => Math.max(...expensesByCategory.value.map(c => c.total), 1))

function buildTreeFlat(items) {
  const itemIds = new Set(items.map(a => String(a.id)))
  const byParent = new Map()
  byParent.set(null, [])

  for (const item of items) {
    const pid = item.parent_id && itemIds.has(String(item.parent_id))
      ? String(item.parent_id)
      : null
    if (!byParent.has(pid)) byParent.set(pid, [])
    byParent.get(pid).push(item)
  }

  const result = []
  function traverse(parentId, depth) {
    const children = [...(byParent.get(parentId) || [])].sort((a, b) =>
      (a.name || '').localeCompare(b.name || '', 'fr')
    )
    for (const child of children) {
      result.push({ ...child, _depth: depth })
      traverse(String(child.id), depth + 1)
    }
  }
  traverse(null, 0)
  return result
}

const sortedAccounts = computed(() => buildTreeFlat(accounts.value))

const activeBudgets = computed(() => {
  const today = new Date().toISOString().slice(0, 10)
  return budgets.value.filter(b => b.start_date <= today && b.end_date >= today)
})

const recentTransactions = computed(() =>
  [...transactions.value]
    .sort((a, b) => new Date(b.post_date) - new Date(a.post_date))
    .slice(0, 10)
)

// ── SVG chart ─────────────────────────────────────────────────────────────────
const chartMin = computed(() => Math.min(...balanceHistory.value.map(d => d.balance)))
const chartMax = computed(() => Math.max(...balanceHistory.value.map(d => d.balance)))

function scaleX(i) {
  const n = balanceHistory.value.length
  return PAD.l + (n <= 1 ? 0 : (i / (n - 1)) * innerW)
}
function scaleY(val) {
  const range = chartMax.value - chartMin.value || 1
  return PAD.t + (1 - (val - chartMin.value) / range) * innerH
}

const linePoints = computed(() =>
  balanceHistory.value.map((d, i) => `${scaleX(i)},${scaleY(d.balance)}`).join(' ')
)
const areaPoints = computed(() => {
  if (!balanceHistory.value.length) return ''
  const n = balanceHistory.value.length
  const bottom = PAD.t + innerH
  const left = `${PAD.l},${bottom}`
  const right = `${scaleX(n - 1)},${bottom}`
  return `${left} ${linePoints.value} ${right}`
})
const zeroY = computed(() => {
  const min = chartMin.value
  const max = chartMax.value
  if (min >= 0 || max <= 0) return null   // pas de ligne zéro si tout positif/négatif
  return scaleY(0)
})

// ── Net worth SVG chart ────────────────────────────────────────────────────────
const nwInnerW = SVG_W - NW_PAD.l - NW_PAD.r
const nwInnerH = SVG_H - NW_PAD.t - NW_PAD.b

const nwMin = computed(() => Math.min(...networthHistory.value.map(d => d.net_worth), 0))
const nwMax = computed(() => Math.max(...networthHistory.value.map(d => d.net_worth), 1))

function nwScaleX(i) {
  const n = networthHistory.value.length
  return NW_PAD.l + (n <= 1 ? 0 : (i / (n - 1)) * nwInnerW)
}
function nwScaleY(val) {
  const range = nwMax.value - nwMin.value || 1
  return NW_PAD.t + (1 - (val - nwMin.value) / range) * nwInnerH
}

const nwLinePoints = computed(() =>
  networthHistory.value.map((d, i) => `${nwScaleX(i)},${nwScaleY(d.net_worth)}`).join(' ')
)
const nwAreaPoints = computed(() => {
  if (!networthHistory.value.length) return ''
  const n = networthHistory.value.length
  const bottom = NW_PAD.t + nwInnerH
  return `${NW_PAD.l},${bottom} ${nwLinePoints.value} ${nwScaleX(n - 1)},${bottom}`
})
const nwZeroY = computed(() => {
  if (nwMin.value >= 0 || nwMax.value <= 0) return null
  return nwScaleY(0)
})
// X-axis label positions: first, middle, last
const nwXLabels = computed(() => {
  const h = networthHistory.value
  if (!h.length) return []
  const idxs = [0, Math.floor((h.length - 1) / 2), h.length - 1]
  return [...new Set(idxs)].map(i => ({ x: nwScaleX(i), label: h[i].month }))
})

// ── Fetch ─────────────────────────────────────────────────────────────────────
async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [statsRes, accRes, budRes, txRes] = await Promise.all([
      axios.get('/api/dashboard/stats'),
      axios.get('/api/accounts'),
      axios.get('/api/budgets'),
      axios.get('/api/transactions', { params: { per_page: 10, page: 1 } }),
    ])
    const stats = statsRes.data?.response_data
    kpis.value = stats?.kpis ?? kpis.value
    balanceHistory.value = Array.isArray(stats?.balance_history) ? stats.balance_history : []
    networthHistory.value = Array.isArray(stats?.networth_history) ? stats.networth_history : []
    expensesByCategory.value = Array.isArray(stats?.expenses_by_category) ? stats.expenses_by_category : []
    accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
    budgets.value = Array.isArray(budRes.data?.response_data) ? budRes.data.response_data : []
    const txRd = txRes.data?.response_data
    transactions.value = Array.isArray(txRd?.transactions) ? txRd.transactions : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
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
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
}
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 4px 0 0; font-size: 14px; color: #9ca3af; }

.btn {
  border: 1px solid rgba(148,163,184,0.25);
  background: rgba(15,23,42,0.7);
  color: #e5e7eb;
  padding: 8px 14px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.alert {
  border: 1px solid rgba(239,68,68,0.4);
  background: rgba(239,68,68,0.08);
  padding: 10px 14px;
  border-radius: 10px;
  color: #fca5a5;
  font-size: 13px;
}

/* ── KPI ────────────────────────────────────────────────────────────────────── */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
@media (max-width: 900px) { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 500px) { .kpi-grid { grid-template-columns: 1fr; } }

.kpi-card {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 18px 20px;
}
.kpi-card--featured {
  border-color: rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.06);
}
.kpi-label { font-size: 12px; color: #9ca3af; margin-bottom: 6px; }
.kpi-value { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
.kpi-sub { font-size: 11px; color: #4b5563; margin-top: 4px; }

/* ── Charts ─────────────────────────────────────────────────────────────────── */
.charts-grid {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 14px;
}
@media (max-width: 800px) { .charts-grid { grid-template-columns: 1fr; } }

/* ── Bottom ─────────────────────────────────────────────────────────────────── */
.bottom-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 700px) { .bottom-grid { grid-template-columns: 1fr; } }

/* ── Card ───────────────────────────────────────────────────────────────────── */
.card {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 18px 20px;
}
.mt { margin-top: 0; }
.card-title { font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 14px; }
.no-data { font-size: 13px; color: #4b5563; }

/* ── SVG chart ──────────────────────────────────────────────────────────────── */
.svg-wrapper { width: 100%; }
.chart-svg { width: 100%; height: 130px; overflow: visible; }
.svg-label { font-size: 9px; fill: #6b7280; }

/* ── Category bars ──────────────────────────────────────────────────────────── */
.cat-list { display: flex; flex-direction: column; gap: 10px; }
.cat-row { display: grid; grid-template-columns: 120px 1fr 70px; align-items: center; gap: 10px; }
.cat-name { font-size: 12px; color: #cbd5e1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cat-bar-wrap { background: rgba(148,163,184,0.1); border-radius: 999px; height: 8px; }
.cat-bar { background: linear-gradient(90deg, #3b82f6, #6366f1); border-radius: 999px; height: 8px; transition: width 0.4s ease; }
.cat-amount { font-size: 12px; color: #9ca3af; text-align: right; font-variant-numeric: tabular-nums; }

/* ── Accounts ───────────────────────────────────────────────────────────────── */
.acc-list { display: flex; flex-direction: column; gap: 8px; }
.acc-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 10px; border-radius: 8px;
  background: rgba(2,6,23,0.35);
  border: 1px solid rgba(148,163,184,0.08);
}
.acc-left { display: flex; align-items: center; gap: 8px; min-width: 0; flex: 1; }
.acc-name { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.acc-balance { font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; white-space: nowrap; }
.acc-row--child { border-left: 2px solid rgba(96, 165, 250, 0.3); }
.tree-prefix { color: rgba(148, 163, 184, 0.35); font-size: 13px; flex-shrink: 0; }
.chip {
  font-size: 10px; padding: 2px 7px; border-radius: 999px;
  border: 1px solid rgba(148,163,184,0.2);
  color: #9ca3af; white-space: nowrap;
}

/* ── Budgets ────────────────────────────────────────────────────────────────── */
.budget-list { display: flex; flex-direction: column; gap: 14px; }
.budget-row {}
.budget-top { display: flex; justify-content: space-between; font-size: 12px; color: #9ca3af; margin-bottom: 6px; }
.budget-amounts { font-variant-numeric: tabular-nums; }
.progress-track { background: rgba(148,163,184,0.12); border-radius: 999px; height: 8px; }
.progress-bar { height: 8px; border-radius: 999px; transition: width 0.4s ease; }
.progress-bar.ok { background: linear-gradient(90deg, #22c55e, #16a34a); }
.progress-bar.warn { background: linear-gradient(90deg, #f59e0b, #d97706); }
.progress-bar.danger { background: linear-gradient(90deg, #ef4444, #dc2626); }
.budget-pct { font-size: 11px; text-align: right; margin-top: 4px; }
.budget-pct.ok { color: #4ade80; }
.budget-pct.warn { color: #fbbf24; }
.budget-pct.danger { color: #f87171; }

/* ── Transactions ───────────────────────────────────────────────────────────── */
.tx-list { display: flex; flex-direction: column; gap: 6px; }
.tx-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 10px; border-radius: 8px;
  background: rgba(2,6,23,0.35);
  border: 1px solid rgba(148,163,184,0.08);
  gap: 12px;
}
.tx-left { display: flex; align-items: center; gap: 12px; min-width: 0; flex: 1; }
.tx-date { font-size: 12px; color: #6b7280; white-space: nowrap; }
.tx-desc { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tx-splits { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.tx-amount { font-size: 12px; font-variant-numeric: tabular-nums; }

/* ── Colors ─────────────────────────────────────────────────────────────────── */
.pos { color: #4ade80; }
.neg { color: #f87171; }
</style>