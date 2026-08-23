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

        <div class="hyp-field hyp-field--wide">
          <label>Part du flux investie (plutôt que laissée en trésorerie)</label>
          <div class="pill-row">
            <button type="button" class="pill" :class="{ active: investMode === 'amount' }" @click="investMode = 'amount'">Montant (€/mois)</button>
            <button type="button" class="pill" :class="{ active: investMode === 'percent' }" @click="investMode = 'percent'">Pourcentage du flux</button>
          </div>
          <div class="invest-row">
            <div class="invest-field">
              <label>Actifs financiers {{ investMode === 'percent' ? '(%)' : `(${currency}/mois)` }}</label>
              <input v-model.number="investFinancial" type="number" :step="investMode === 'percent' ? 1 : 10" min="0" />
            </div>
            <div class="invest-field">
              <label>Actifs physiques {{ investMode === 'percent' ? '(%)' : `(${currency}/mois)` }}</label>
              <input v-model.number="investPhysical" type="number" :step="investMode === 'percent' ? 1 : 10" min="0" />
            </div>
          </div>
          <p class="field-hint" v-if="result">
            Sur les <strong>{{ fmtAmount(result.params.avg_monthly_net_flow) }}</strong>/mois de flux, <strong>{{ fmtAmount(result.params.invest_financial_amount) }}</strong> investis en financier
            et <strong>{{ fmtAmount(result.params.invest_physical_amount) }}</strong> en physique — le reste
            (<strong>{{ fmtAmount(result.params.avg_monthly_net_flow - result.params.invest_financial_amount - result.params.invest_physical_amount) }}</strong>) part vers la trésorerie,
            qui absorbe ensuite ses propres abonnements et échéances de crédit (comptés à part, voir courbe ci-dessous) — ce n'est donc pas ce montant net qui s'accumule chaque mois.
          </p>
        </div>
      </div>
      <button class="btn btn-primary apply-btn" :disabled="loading" @click="reload">Appliquer</button>
    </div>

    <!-- Objectifs de vie -->
    <div class="card">
      <div class="card-title-row">
        <div class="card-title">Objectifs de vie</div>
        <button class="btn btn-sm" type="button" @click="openCreateGoal">+ Nouvel objectif</button>
      </div>
      <p class="section-hint">
        Chaque objectif retire son montant de la trésorerie projetée (voir courbes ci-dessous) — un objectif est marqué
        « à risque » si la trésorerie passerait sous zéro à ce moment-là dans la simulation.
      </p>

      <div v-if="goalsError" class="alert">{{ goalsError }}</div>
      <div v-if="!goals.length" class="empty goals-empty">Aucun objectif défini — la projection ci-dessous reste une simple hypothèse de croissance.</div>

      <ul v-else class="goal-list">
        <li v-for="g in goals" :key="g.id" class="goal-row">
          <div class="goal-main">
            <span class="goal-name">{{ g.name }}</span>
            <span class="goal-badge">{{ g.goal_type === 'recurring' ? 'Récurrent' : 'Ponctuel' }}</span>
            <span v-if="goalStatus(g.id)" :class="['goal-badge', 'status-' + goalStatus(g.id)]">
              {{ goalStatusLabel(goalStatus(g.id)) }}
            </span>
          </div>
          <div class="goal-detail">
            {{ fmtAmount(g.target_amount) }}{{ g.goal_type === 'recurring' ? ' / mois' : '' }}
            — {{ fmtDate(g.target_date) }}<template v-if="g.goal_type === 'recurring'"> → {{ g.end_date ? fmtDate(g.end_date) : "fin de l'horizon" }}</template>
          </div>
          <div class="goal-actions">
            <button class="btn-action" @click="openEditGoal(g)">✎</button>
            <button class="btn-action btn-danger" @click="deleteGoal(g)">✕</button>
          </div>
        </li>
      </ul>
    </div>

    <div v-if="loading && !result" class="empty">Calcul de la projection…</div>

    <template v-else-if="result">
      <!-- Résultat -->
      <div v-if="treasuryNegativeDate" class="alert alert-warning">
        ⚠ Avec ces hypothèses, votre trésorerie projetée passerait sous 0 € à partir de <strong>{{ treasuryNegativeDate }}</strong> —
        vos abonnements, échéances de crédit et part investie dépassent ce que votre flux mensuel peut couvrir. Le
        « Patrimoine financier net » ci-dessous reste positif car il ne compte pas la trésorerie (voir "Trésorerie projetée").
      </div>

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
            <div class="stat-value" :class="endBankCash >= 0 ? 'pos' : 'neg'">{{ fmtAmount(endBankCash) }}</div>
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

  <GoalModal
    v-model="showGoalModal"
    :mode="goalModalMode"
    :goal="selectedGoal"
    @save="handleGoalSave"
  />
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { currency } from '@/utils/settings.js'
import LineGraph from '../components/graphs/LineGraph.vue'
import GoalModal from '../components/modal/GoalModal.vue'
import { confirmDialog } from '@/utils/confirmDialog'
import { useToast } from '@/utils/toast'

const toast = useToast()

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
const investMode = ref('amount')
const investFinancial = ref(0)
const investPhysical = ref(0)

const result = ref(null)
const loading = ref(false)
const error = ref('')

// ── objectifs de vie ─────────────────────────────────────────────────────────
const goals = ref([])
const goalsError = ref('')
const showGoalModal = ref(false)
const goalModalMode = ref('create')
const selectedGoal = ref(null)

async function loadGoals() {
  goalsError.value = ''
  try {
    const { data } = await axios.get('/api/goals')
    goals.value = Array.isArray(data?.response_data) ? data.response_data : []
  } catch (e) {
    goalsError.value = e?.response?.data?.response_data || e?.message || 'Erreur lors du chargement des objectifs'
  }
}

function openCreateGoal() {
  selectedGoal.value = null
  goalModalMode.value = 'create'
  showGoalModal.value = true
}

function openEditGoal(g) {
  selectedGoal.value = { ...g }
  goalModalMode.value = 'edit'
  showGoalModal.value = true
}

async function handleGoalSave(form) {
  goalsError.value = ''
  try {
    const payload = {
      name: form.name,
      goal_type: form.goal_type,
      target_amount: form.target_amount,
      target_date: form.target_date,
      end_date: form.goal_type === 'recurring' ? (form.end_date || null) : null,
    }
    if (goalModalMode.value === 'create') {
      await axios.post('/api/goals', payload)
    } else {
      await axios.patch('/api/goals', { goal_id: form.id, ...payload })
    }
    await loadGoals()
    await reload()
    toast.success(goalModalMode.value === 'create' ? `Objectif « ${form.name} » créé.` : `Objectif « ${form.name} » mis à jour.`)
  } catch (e) {
    goalsError.value = e?.response?.data?.response_data || e?.message || "Erreur lors de l'enregistrement de l'objectif"
  }
}

async function deleteGoal(g) {
  const ok = await confirmDialog({
    title: "Supprimer l'objectif",
    message: `Supprimer l'objectif « ${g.name} » ?`,
    confirmLabel: 'Supprimer',
    danger: true,
  })
  if (!ok) return
  try {
    await axios.delete('/api/goals', { params: { goal_id: g.id } })
    await loadGoals()
    await reload()
    toast.success(`Objectif « ${g.name} » supprimé.`)
  } catch (e) {
    goalsError.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la suppression'
  }
}

function goalStatus(goalId) {
  return result.value?.goals_result?.find(gr => gr.id === goalId)?.status || null
}

const GOAL_STATUS_LABELS = { feasible: '✓ Atteignable', at_risk: '⚠ À risque', out_of_range: 'Hors horizon' }
function goalStatusLabel(status) {
  return GOAL_STATUS_LABELS[status] || status
}

function fmtDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
}

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
    params.invest_mode = investMode.value
    if (investMode.value === 'percent') {
      params.invest_financial_pct = investFinancial.value
      params.invest_physical_pct = investPhysical.value
    } else {
      params.invest_financial_amount = investFinancial.value
      params.invest_physical_amount = investPhysical.value
    }
    const res = await axios.get('/api/forecast/wealth', { params })
    result.value = res.data?.response_data ?? null
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  reload()
  loadGoals()
})

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

// Le "Patrimoine financier net" (portefeuille - crédits) reste positif même quand la trésorerie
// simulée passe sous 0 (les deux périmètres sont volontairement disjoints, voir commentaire sur
// financial_net_worth plus bas) — sans cet avertissement dédié, un déficit structurel (abonnements +
// crédits + part investie > flux mensuel) passe inaperçu tant qu'on ne regarde pas la courbe de
// trésorerie en détail. Utilise la courbe "avec objectifs" si des objectifs existent (trajectoire
// réellement pertinente pour l'utilisateur), sinon la trajectoire de base.
const treasuryNegativeDate = computed(() => {
  const pts = result.value?.points ?? []
  const hasGoals = goals.value.length > 0
  const negativePoint = pts.find(p => (hasGoals ? (p.bank_cash_with_goals ?? p.bank_cash) : p.bank_cash) < 0)
  if (!negativePoint) return null
  return new Date(negativePoint.date).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
})
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
  // Deux courbes de trésorerie plutôt qu'une seule dès qu'un objectif est défini : la différence
  // visuelle entre "hypothèse" et "avec objectifs" est le point de tout le Lifetime Planner —
  // sans les deux courbes côte à côte, le creux causé par un objectif passerait inaperçu.
  if (goals.value.length && pts.some(p => p.bank_cash_with_goals != null)) {
    series.push({ label: 'Trésorerie (hypothèse)', values: pts.map(p => p.bank_cash), color: '#38bdf8' })
    series.push({ label: 'Trésorerie (avec objectifs)', values: pts.map(p => p.bank_cash_with_goals ?? p.bank_cash), color: '#fbbf24' })
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
.alert-warning {
  border-color: rgba(245,158,11,0.4);
  background: rgba(245,158,11,0.08);
  color: #fcd34d;
  line-height: 1.6;
}

.card {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 18px 20px;
}
.card-title { font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 14px; }

.card-title-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 6px; }
.card-title-row .card-title { margin-bottom: 0; }

.btn-sm { padding: 5px 10px; font-size: 12px; border-radius: 8px; }

.section-hint { margin: 0 0 14px; font-size: 12px; color: #6b7280; line-height: 1.6; max-width: 80ch; }

.goals-empty { margin: 0; }

.goal-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }

.goal-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 12px;
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 10px;
  background: rgba(2,6,23,0.4);
}

.goal-main { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; flex: 1 1 220px; }
.goal-name { font-size: 14px; font-weight: 600; color: #e5e7eb; }

.goal-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148,163,184,0.25);
  color: #9ca3af;
}
.goal-badge.status-feasible   { border-color: rgba(34,197,94,0.35);  background: rgba(34,197,94,0.1);  color: #86efac; }
.goal-badge.status-at_risk    { border-color: rgba(239,68,68,0.35);  background: rgba(239,68,68,0.1);  color: #fca5a5; }
.goal-badge.status-out_of_range { border-color: rgba(148,163,184,0.2); color: #9ca3af; }

.goal-detail { font-size: 12.5px; color: #9ca3af; flex: 1 1 260px; font-variant-numeric: tabular-nums; }

.goal-actions { display: flex; gap: 6px; flex-shrink: 0; }
.btn-action {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
  padding: 4px 9px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
}
.btn-action:hover { background: rgba(148, 163, 184, 0.1); }
.btn-action.btn-danger { border-color: rgba(239,68,68,0.4); color: #fca5a5; }
.btn-action.btn-danger:hover { background: rgba(239,68,68,0.1); }

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

.invest-row { display: flex; gap: 16px; flex-wrap: wrap; margin-top: 4px; }
.invest-field { display: flex; flex-direction: column; gap: 6px; }
.invest-field label { font-size: 12px; color: #9ca3af; }
.invest-field input {
  background: #020617;
  border: 1px solid #1f2937;
  border-radius: 8px;
  padding: 7px 10px;
  color: #e5e7eb;
  font-size: 13px;
  width: 160px;
}
.invest-field input:focus { outline: none; border-color: var(--color-accent); }

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
