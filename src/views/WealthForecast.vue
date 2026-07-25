<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Prédiction du patrimoine</h1>
        <p class="subtitle">
          Projection indicative de votre patrimoine financier net (portefeuille − crédits, hors soldes bancaires — même
          périmètre que Vue d'ensemble), en {{ currency }}, à partir d'hypothèses de croissance et de flux mensuels
          simplifiées — ne constitue pas un conseil financier.
        </p>
      </div>
      <button class="btn" :disabled="loading" @click="reload">
        <span v-if="!loading">↻ Recalculer</span>
        <span v-else>Calcul…</span>
      </button>
    </header>

    <div v-if="error" class="alert">{{ error }}</div>

    <!-- Hypothèses -->
    <div class="card">
      <div class="card-title">Hypothèses</div>
      <div class="hyp-grid">
        <div class="hyp-field">
          <label>Horizon</label>
          <div class="pill-row">
            <button
              v-for="h in HORIZONS"
              :key="h.months"
              type="button"
              class="pill"
              :class="{ active: horizonMonths === h.months }"
              @click="horizonMonths = h.months"
            >{{ h.label }}</button>
          </div>
        </div>

        <div class="hyp-field">
          <label>Croissance actifs financiers (actions/ETF) — %/an</label>
          <input v-model.number="growthFinancial" type="number" step="0.1" />
        </div>

        <div class="hyp-field">
          <label>Croissance actifs physiques (immobilier/véhicules) — %/an</label>
          <input v-model.number="growthPhysical" type="number" step="0.1" />
        </div>

        <div class="hyp-field">
          <label>Rendement de l'épargne/liquidités non investies — %/an</label>
          <input v-model.number="growthCash" type="number" step="0.1" />
          <p class="field-hint">Appliqué à la trésorerie qui s'accumule mois après mois (salaire net des dépenses) — sans ça, cette épargne resterait figée sans composer.</p>
        </div>

        <div class="hyp-field hyp-field--wide">
          <label>Flux mensuel moyen (hors abonnements et échéances de crédit, déjà projetés séparément)</label>
          <div class="pill-row">
            <button type="button" class="pill" :class="{ active: netFlowMode === 'auto' }" @click="netFlowMode = 'auto'">Automatique</button>
            <button type="button" class="pill" :class="{ active: netFlowMode === 'manual' }" @click="netFlowMode = 'manual'">Manuel</button>
          </div>
          <input
            v-if="netFlowMode === 'manual'"
            v-model.number="manualNetFlow"
            type="number"
            step="10"
            placeholder="ex: 500 (positif = épargne, négatif = déficit)"
            class="net-flow-input"
          />
          <p v-else-if="result" class="field-hint">
            Calculé automatiquement sur les 12 derniers mois : <strong :class="result.params.avg_monthly_net_flow >= 0 ? 'pos' : 'neg'">{{ fmtAmount(result.params.avg_monthly_net_flow) }}</strong>
            /mois (revenus et dépenses réels, hors abonnements et crédits déjà comptés à part).
          </p>
        </div>
      </div>
      <button class="btn btn-primary apply-btn" :disabled="loading" @click="reload">Appliquer</button>
    </div>

    <div v-if="loading && !result" class="empty">Calcul de la projection…</div>

    <template v-else-if="result">
      <!-- Résultat -->
      <div class="hero-row">
        <div class="hero-card">
          <div class="hero-label">Patrimoine financier net projeté — {{ endDateLabel }}</div>
          <div class="hero-value" :class="endNetWorth >= 0 ? 'pos' : 'neg'">{{ fmtAmount(endNetWorth) }}</div>
          <div class="hero-sub">
            {{ delta >= 0 ? '+' : '' }}{{ fmtAmount(delta) }} par rapport à aujourd'hui
            <span v-if="deltaPct !== null">({{ deltaPct >= 0 ? '+' : '' }}{{ deltaPct.toFixed(1) }} %)</span>
          </div>
        </div>
        <div class="side-stats">
          <div class="stat-card">
            <div class="stat-label">Patrimoine financier net aujourd'hui</div>
            <div class="stat-value">{{ fmtAmount(startNetWorth) }}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Trésorerie projetée — {{ endDateLabel }}</div>
            <div class="stat-value">{{ fmtAmount(endBankCash) }}</div>
          </div>
          <div class="stat-card" v-if="endLiabilities === 0 && startLiabilities > 0">
            <div class="stat-label">Crédits</div>
            <div class="stat-value pos">Soldés avant l'horizon</div>
          </div>
        </div>
      </div>

      <LineGraph
        title="Évolution projetée du patrimoine financier net"
        :subtitle="`Aujourd'hui → ${endDateLabel}, hypothèses ci-dessus — hors soldes bancaires (voir Trésorerie projetée à part)`"
        :labels="chartLabels"
        :series="chartSeries"
        :format-value="fmtAmount"
        height="280px"
      />
      <p class="chart-note">
        Le patrimoine net combine la croissance du portefeuille (qui compose bien, voir la courbe "Valeur du portefeuille" ci-dessus)
        et la baisse des crédits en cours (qui s'annule une fois soldée) — cette seconde composante peut masquer visuellement la
        composition sur la courbe combinée une fois la dette remboursée.
      </p>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { currency } from '@/utils/settings.js'
import LineGraph from '../components/graphs/LineGraph.vue'

const HORIZONS = [
  { months: 12, label: '1 an' },
  { months: 36, label: '3 ans' },
  { months: 60, label: '5 ans' },
  { months: 120, label: '10 ans' },
  { months: 240, label: '20 ans' },
]

const horizonMonths = ref(60)
const growthFinancial = ref(5)
const growthPhysical = ref(2)
const growthCash = ref(3)
const netFlowMode = ref('auto')
const manualNetFlow = ref(0)

const result = ref(null)
const loading = ref(false)
const error = ref('')

function fmtAmount(v) {
  const n = Number(v ?? 0)
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 0 }).format(n) + ' ' + currency.value
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const params = {
      horizon_months: horizonMonths.value,
      growth_financial_pct: growthFinancial.value,
      growth_physical_pct: growthPhysical.value,
      growth_cash_pct: growthCash.value,
      currency: currency.value,
    }
    if (netFlowMode.value === 'manual') params.avg_monthly_net_flow = manualNetFlow.value
    const res = await axios.get('/api/forecast/wealth', { params })
    result.value = res.data?.response_data ?? null
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

onMounted(reload)

const startPoint = computed(() => result.value?.points?.[0] ?? null)
const endPoint = computed(() => {
  const pts = result.value?.points
  return pts && pts.length ? pts[pts.length - 1] : null
})
// financial_net_worth = portefeuille - crédits, hors trésorerie bancaire — même périmètre que
// "Patrimoine financier net" sur /patrimoine (WealthOverview.vue). La trésorerie reste simulée et
// affichée à part (endBankCash) mais ne doit jamais être mélangée dans ce chiffre, sinon /patrimoine
// et /patrimoine/prediction affichent deux valeurs différentes pour "le même" patrimoine net.
const startNetWorth = computed(() => startPoint.value?.financial_net_worth ?? 0)
const endNetWorth = computed(() => endPoint.value?.financial_net_worth ?? 0)
const endBankCash = computed(() => endPoint.value?.bank_cash ?? 0)
const startLiabilities = computed(() => startPoint.value?.liabilities ?? 0)
const endLiabilities = computed(() => endPoint.value?.liabilities ?? 0)
const delta = computed(() => endNetWorth.value - startNetWorth.value)
const deltaPct = computed(() => startNetWorth.value ? (delta.value / Math.abs(startNetWorth.value)) * 100 : null)

const endDateLabel = computed(() => {
  if (!endPoint.value) return ''
  return new Date(endPoint.value.date).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
})

const chartLabels = computed(() =>
  (result.value?.points ?? []).map(p => new Date(p.date).toLocaleDateString('fr-FR', { month: 'short', year: 'numeric' }))
)

// Trois courbes plutôt qu'une seule "Patrimoine net" : la composition du portefeuille (qui
// accélère visiblement, courbe convexe) est autrement masquée par la baisse des crédits (qui
// s'arrête une fois la dette soldée) quand les deux sont fondus dans une seule ligne combinée —
// retour utilisateur du 2026-07-25 ("toujours pas d'intérêt composé").
const chartSeries = computed(() => {
  const pts = result.value?.points ?? []
  const series = [
    { label: 'Patrimoine financier net', values: pts.map(p => p.financial_net_worth), color: '#10b981' },
    { label: 'Valeur du portefeuille', values: pts.map(p => p.portfolio_value), color: '#818cf8' },
  ]
  if (pts.length && pts[0].liabilities > 0) {
    series.push({ label: 'Crédits restants', values: pts.map(p => p.liabilities), color: '#f87171' })
  }
  return series
})
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
.page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; font-size: 13px; color: #9ca3af; max-width: 70ch; line-height: 1.6; }

.btn {
  border: 1px solid rgba(148,163,184,0.25);
  background: rgba(15,23,42,0.7);
  color: #e5e7eb;
  padding: 8px 14px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  flex-shrink: 0;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary { background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2)); border-color: transparent; color: #fff; }

.alert {
  border: 1px solid rgba(239,68,68,0.4);
  background: rgba(239,68,68,0.08);
  padding: 10px 14px;
  border-radius: 10px;
  color: #fca5a5;
  font-size: 13px;
}

.card {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 18px 20px;
}
.card-title { font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 14px; }

.hyp-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px 24px;
}
@media (max-width: 700px) { .hyp-grid { grid-template-columns: 1fr; } }
.hyp-field { display: flex; flex-direction: column; gap: 6px; }
.hyp-field--wide { grid-column: 1 / -1; }
.hyp-field label { font-size: 12px; color: #9ca3af; }
.hyp-field input {
  background: #020617;
  border: 1px solid #1f2937;
  border-radius: 8px;
  padding: 7px 10px;
  color: #e5e7eb;
  font-size: 13px;
  width: 160px;
}
.hyp-field input:focus { outline: none; border-color: var(--color-accent); }
.net-flow-input { width: 260px !important; margin-top: 4px; }

.pill-row { display: flex; gap: 6px; flex-wrap: wrap; }
.pill {
  border: 1px solid rgba(148,163,184,0.25);
  background: rgba(2,6,23,0.6);
  color: #cbd5e1;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 12.5px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, color 0.15s;
}
.pill:hover { border-color: rgba(148,163,184,0.4); }
.pill.active { border-color: var(--color-accent); background: rgba(59,130,246,0.12); color: #fff; }

.field-hint { margin: 2px 0 0; font-size: 12px; color: #6b7280; line-height: 1.5; }
.field-hint .pos { color: #4ade80; font-weight: 600; }
.field-hint .neg { color: #f87171; font-weight: 600; }

.apply-btn { margin-top: 16px; }

.chart-note {
  margin: -6px 0 0;
  font-size: 12px;
  color: #6b7280;
  line-height: 1.6;
  max-width: 80ch;
}

.empty {
  padding: 18px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 14px;
  color: #cbd5e1;
}

.hero-row { display: flex; gap: 14px; flex-wrap: wrap; }
.hero-card {
  flex: 1 1 320px;
  border: 1px solid rgba(16,185,129,0.3);
  background: rgba(16,185,129,0.06);
  border-radius: 16px;
  padding: 22px 24px;
}
.hero-label { font-size: 12px; color: #9ca3af; font-weight: 600; }
.hero-value { font-size: 32px; font-weight: 700; font-variant-numeric: tabular-nums; margin-top: 6px; }
.hero-value.pos { color: #86efac; }
.hero-value.neg { color: #fca5a5; }
.hero-sub { font-size: 12.5px; color: #9ca3af; margin-top: 8px; }

.side-stats { flex: 0 1 220px; display: flex; flex-direction: column; gap: 14px; }
.stat-card {
  border: 1px solid rgba(148,163,184,0.15);
  background: rgba(15,23,42,0.7);
  border-radius: 14px;
  padding: 16px 18px;
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.stat-label { font-size: 11px; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; }
.stat-value { font-size: 18px; font-weight: 700; margin-top: 5px; }
.stat-value.pos { color: #4ade80; }
</style>
