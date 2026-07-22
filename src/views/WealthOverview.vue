<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Vue d'ensemble patrimoniale</h1>
        <p class="subtitle">Actifs (portefeuille) et passifs (crédits) uniquement, en {{ currency }} — hors soldes bancaires, voir Rapports prédéfinis pour le patrimoine total.</p>
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
        <div class="kpi-label">Patrimoine financier net</div>
        <div class="kpi-value" :class="financialNet >= 0 ? 'pos' : 'neg'">
          {{ fmtAmount(financialNet) }}
        </div>
        <div class="kpi-sub" v-if="kpis.total_liabilities">
          Brut {{ fmtAmount(kpis.portfolio_value) }} − Crédits {{ fmtAmount(kpis.total_liabilities) }}
        </div>
        <div class="kpi-sub" v-else>Portefeuille, aucun crédit en cours</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Valeur du portefeuille</div>
        <div class="kpi-value">{{ fmtAmount(kpis.portfolio_value) }}</div>
        <div class="kpi-sub">Actifs financiers &amp; physiques (brut, avant crédits)</div>
      </div>
      <div class="kpi-card" v-if="kpis.total_liabilities">
        <div class="kpi-label">Crédits en cours</div>
        <div class="kpi-value neg">{{ fmtAmount(kpis.total_liabilities) }}</div>
        <div class="kpi-sub">Capital restant dû — déjà déduit du patrimoine financier net</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Plus-value latente</div>
        <div class="kpi-value" :class="kpis.unrealized_gain >= 0 ? 'pos' : 'neg'">
          {{ fmtAmount(kpis.unrealized_gain) }}
          <span v-if="kpis.unrealized_gain_pct != null" class="kpi-pct">
            ({{ kpis.unrealized_gain_pct >= 0 ? '+' : '' }}{{ kpis.unrealized_gain_pct }}%)
          </span>
        </div>
        <div class="kpi-sub">Actifs avec prix d'achat renseigné</div>
      </div>
    </div>

    <!-- Combined history -->
    <LineGraph
      v-if="financialHistory.length >= 2"
      title="Évolution du patrimoine financier (actifs − passifs)"
      :labels="financialHistory.map(d => d.date.slice(5))"
      :values="financialHistory.map(d => d.value)"
      dataset-label="Patrimoine financier"
      color="#10b981"
      :format-value="fmtAmount"
      :show-last-value="false"
    />
    <div v-else class="card">
      <div class="card-title">Évolution du patrimoine financier (actifs − passifs)</div>
      <div class="no-data">Pas assez de données (l'historique se construit jour après jour).</div>
    </div>

    <!-- Répartitions -->
    <div class="charts-grid">
      <div class="card">
        <div class="card-title">Répartition par type</div>
        <div v-if="!allocationByType.length" class="no-data">Aucune donnée.</div>
        <div v-else class="cat-list">
          <div v-for="c in allocationByType" :key="c.label" class="cat-row">
            <div class="cat-name">{{ c.label }}</div>
            <div class="cat-bar-wrap"><div class="cat-bar" :style="{ width: (c.value / maxAlloc(allocationByType) * 100) + '%' }"></div></div>
            <div class="cat-amount">{{ fmtAmount(c.value) }}</div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Répartition par devise</div>
        <div v-if="!allocationByCurrency.length" class="no-data">Aucune donnée.</div>
        <div v-else class="cat-list">
          <div v-for="c in allocationByCurrency" :key="c.currency" class="cat-row">
            <div class="cat-name">{{ c.currency }}</div>
            <div class="cat-bar-wrap"><div class="cat-bar" :style="{ width: (c.value / maxAlloc(allocationByCurrency) * 100) + '%' }"></div></div>
            <div class="cat-amount">{{ fmtAmount(c.value) }}</div>
          </div>
        </div>
      </div>

      <div class="card" v-if="allocationBySector.length">
        <div class="card-title">Répartition par secteur (Actions/ETF)</div>
        <div class="cat-list">
          <div v-for="c in allocationBySector" :key="c.sector" class="cat-row">
            <div class="cat-name">{{ c.sector }}</div>
            <div class="cat-bar-wrap"><div class="cat-bar" :style="{ width: (c.value / maxAlloc(allocationBySector) * 100) + '%' }"></div></div>
            <div class="cat-amount">{{ fmtAmount(c.value) }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Top / worst movers -->
    <div class="bottom-grid">
      <div class="card">
        <div class="card-title">Top gagnants</div>
        <div v-if="!topMovers.length" class="no-data">Aucun actif avec prix d'achat renseigné.</div>
        <div v-else class="mover-list">
          <div v-for="m in topMovers" :key="m.symbol" class="mover-row">
            <span class="mover-symbol">{{ m.symbol }}</span>
            <span class="mover-name">{{ m.name }}</span>
            <span class="mover-pct pos">+{{ m.gain_pct }}%</span>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-title">Top perdants</div>
        <div v-if="!worstMovers.length" class="no-data">Aucun actif avec prix d'achat renseigné.</div>
        <div v-else class="mover-list">
          <div v-for="m in worstMovers" :key="m.symbol" class="mover-row">
            <span class="mover-symbol">{{ m.symbol }}</span>
            <span class="mover-name">{{ m.name }}</span>
            <span class="mover-pct" :class="m.gain_pct >= 0 ? 'pos' : 'neg'">{{ m.gain_pct >= 0 ? '+' : '' }}{{ m.gain_pct }}%</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { currency } from '@/utils/settings.js'
import LineGraph from '../components/graphs/LineGraph.vue'

const kpis = ref({
  net_worth_total: 0, net_worth_total_gross: 0,
  bank_net_worth: 0, total_liabilities: 0, portfolio_value: 0,
  unrealized_gain: 0, unrealized_gain_pct: null,
})
const allocationByType = ref([])
const allocationByCurrency = ref([])
const allocationBySector = ref([])
const topMovers = ref([])
const worstMovers = ref([])
const history = ref([])

const loading = ref(false)
const error = ref('')

function fmtAmount(v) {
  const n = Number(v ?? 0)
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(n) + ' ' + currency.value
}

function maxAlloc(list) {
  return Math.max(...list.map(c => c.value), 1)
}

// Patrimoine financier net = actifs (portefeuille) - passifs (crédits), calculé côté client à
// partir de la réponse combinée /api/wealth/overview|history (qui reste pleine — bancaire compris
// — pour Reports.vue, voir rt_wealth.py). total - bank_net_worth = portfolio_value - dettes, par
// construction (total = bank_net_worth + portfolio_value - dettes).
const financialNet = computed(() => (kpis.value.portfolio_value ?? 0) - (kpis.value.total_liabilities ?? 0))
const financialHistory = computed(() => history.value.map(d => ({
  date: d.date,
  value: (d.total ?? 0) - (d.bank_net_worth ?? 0),
})))

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const params = { currency: currency.value }
    const [overviewRes, historyRes] = await Promise.all([
      axios.get('/api/wealth/overview', { params }),
      axios.get('/api/wealth/history', { params }),
    ])
    const overview = overviewRes.data?.response_data
    kpis.value = overview?.kpis ?? kpis.value
    allocationByType.value = Array.isArray(overview?.allocation_by_type) ? overview.allocation_by_type : []
    allocationByCurrency.value = Array.isArray(overview?.allocation_by_currency) ? overview.allocation_by_currency : []
    allocationBySector.value = Array.isArray(overview?.allocation_by_sector) ? overview.allocation_by_sector : []
    topMovers.value = Array.isArray(overview?.top_movers) ? overview.top_movers : []
    worstMovers.value = Array.isArray(overview?.worst_movers) ? overview.worst_movers : []
    history.value = Array.isArray(historyRes.data?.response_data) ? historyRes.data.response_data : []
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
.page-header { display: flex; justify-content: space-between; align-items: flex-end; }
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

.kpi-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
@media (max-width: 900px) { .kpi-grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 500px) { .kpi-grid { grid-template-columns: 1fr; } }

.kpi-card {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 18px 20px;
}
.kpi-card--featured { border-color: rgba(16, 185, 129, 0.35); background: rgba(16, 185, 129, 0.06); }
.kpi-label { font-size: 12px; color: #9ca3af; margin-bottom: 6px; }
.kpi-value { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
.kpi-pct { font-size: 13px; font-weight: 600; margin-left: 4px; }
.kpi-sub { font-size: 11px; color: #4b5563; margin-top: 4px; }

.charts-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
@media (max-width: 900px) { .charts-grid { grid-template-columns: 1fr; } }

.bottom-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
@media (max-width: 700px) { .bottom-grid { grid-template-columns: 1fr; } }

.card {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 18px 20px;
}
.card-title { font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 14px; }
.no-data { font-size: 13px; color: #4b5563; }

.cat-list { display: flex; flex-direction: column; gap: 10px; }
.cat-row { display: grid; grid-template-columns: 100px 1fr 90px; align-items: center; gap: 10px; }
.cat-name { font-size: 12px; color: #cbd5e1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cat-bar-wrap { background: rgba(148,163,184,0.1); border-radius: 999px; height: 8px; }
.cat-bar { background: linear-gradient(90deg, #3b82f6, #6366f1); border-radius: 999px; height: 8px; transition: width 0.4s ease; }
.cat-amount { font-size: 12px; color: #9ca3af; text-align: right; font-variant-numeric: tabular-nums; }

.mover-list { display: flex; flex-direction: column; gap: 8px; }
.mover-row {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px; border-radius: 8px;
  background: rgba(2,6,23,0.35);
  border: 1px solid rgba(148,163,184,0.08);
}
.mover-symbol { font-weight: 700; font-size: 12px; color: #60a5fa; font-family: monospace; min-width: 56px; }
.mover-name { flex: 1; font-size: 13px; color: #cbd5e1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mover-pct { font-size: 13px; font-weight: 700; font-variant-numeric: tabular-nums; }

.pos { color: #4ade80; }
.neg { color: #f87171; }
</style>
