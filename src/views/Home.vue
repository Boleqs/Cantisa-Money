<template>
  <div class="page">
    <!-- Hero -->
    <div class="hero">
      <div class="hero-left">
        <p class="hero-eyebrow">{{ todayLabel }}</p>
        <h1 class="hero-greeting">{{ greeting }}, {{ user?.username || '…' }}.</h1>
        <p v-if="insight" class="hero-insight">{{ insight }}</p>
      </div>
      <div v-if="streakBadge" class="streak">
        <div class="streak-badge" :class="{ warn: !streakBadge.good && !streakBadge.neutral, neutral: streakBadge.neutral }">
          <span class="streak-dot" :class="{ warn: !streakBadge.good && !streakBadge.neutral, neutral: streakBadge.neutral }"></span> {{ streakBadge.text }}
        </div>
        <span v-if="streakBadge.caption" class="streak-caption">{{ streakBadge.caption }}</span>
      </div>
    </div>

    <!-- Fraîcheur des données -->
    <div v-if="freshnessWarning" class="freshness-banner">
      <span class="freshness-icon">⚠</span>
      <span>{{ freshnessWarning }}</span>
    </div>

    <!-- Briefing : patrimoine + à venir -->
    <section v-if="hasPermission('Patrimoine') || hasPermission('Planification')" class="section">
      <h2 class="eyebrow">Patrimoine &amp; échéances</h2>
      <div class="briefing">
        <div v-if="hasPermission('Patrimoine') && wealth" class="card">
          <div class="worth-head">
            <span class="worth-label">Patrimoine total</span>
            <span v-if="deltaPct !== null" class="worth-delta" :class="{ negative: deltaPct < 0 }">
              {{ deltaPct >= 0 ? '▲' : '▼' }} {{ Math.abs(deltaPct).toFixed(1) }} % / 30 j
            </span>
          </div>
          <div class="worth-value">{{ fmt(wealth.net_worth_total) }} {{ currency }}</div>
          <div class="worth-sub">Bancaire <strong>{{ fmt(wealth.bank_net_worth) }}</strong> · Portefeuille <strong>{{ fmt(wealth.portfolio_value) }}</strong></div>

          <div v-if="sparkGeometry" class="spark-wrap">
            <div class="spark-tip" :class="{ show: hoverPoint }" :style="hoverTipStyle">{{ hoverPoint?.label }}</div>
            <svg viewBox="0 0 560 120" width="100%" height="120" style="overflow:visible;display:block;">
              <defs>
                <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="var(--color-accent-2)" stop-opacity="0.35"/>
                  <stop offset="100%" stop-color="var(--color-accent-2)" stop-opacity="0"/>
                </linearGradient>
              </defs>
              <line x1="0" y1="30" x2="560" y2="30" stroke="rgba(148,163,184,0.10)" stroke-width="1"/>
              <line x1="0" y1="90" x2="560" y2="90" stroke="rgba(148,163,184,0.10)" stroke-width="1"/>
              <path :d="sparkGeometry.area" fill="url(#sparkFill)" stroke="none"/>
              <path :d="sparkGeometry.line" fill="none" stroke="var(--color-accent)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
              <circle :cx="sparkGeometry.last[0]" :cy="sparkGeometry.last[1]" r="4.5" fill="var(--color-accent)" stroke="#0b1220" stroke-width="2"/>
              <circle
                v-for="(p, i) in sparkGeometry.coords" :key="i"
                :cx="p[0]" :cy="p[1]" r="9" fill="transparent" style="cursor:pointer"
                @mouseenter="hoverIndex = i" @mouseleave="hoverIndex = null"
              />
            </svg>
            <p class="spark-caption">Évolution sur les 6 derniers mois</p>
          </div>
        </div>

        <div v-if="hasPermission('Planification')" class="card">
          <p class="up-title-head">À venir</p>
          <div v-if="upcoming.length" class="up-list">
            <router-link v-for="(u, i) in upcoming" :key="i" :to="u.to" class="up-item">
              <span class="up-glyph" :class="u.severity">
                <svg v-if="u.severity === 'crit'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/></svg>
                <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 2v4M7 2v4M3 9h18M4 6h16a1 1 0 0 1 1 1v12a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1Z"/></svg>
              </span>
              <span class="up-text">
                <span class="up-item-title">{{ u.title }}</span>
                <span class="up-sub">{{ u.sub }}</span>
              </span>
              <span class="up-when" :class="u.severity">{{ u.when }}</span>
            </router-link>
          </div>
          <p v-else class="up-empty">Rien à signaler pour l'instant.</p>
        </div>
      </div>
    </section>

    <!-- Santé budgétaire -->
    <section v-if="hasPermission('Planification') && budgetsWithPct.length" class="section">
      <h2 class="eyebrow">Santé budgétaire</h2>
      <div class="card rings-card">
        <div class="rings-title-row">
          <span class="rings-title">Enveloppes du mois</span>
          <router-link class="rings-link" to="/budgets">Tous les budgets →</router-link>
        </div>
        <div class="rings-grid">
          <div v-for="b in budgetsWithPct" :key="b.id" class="ring-item">
            <div class="ring-wrap">
              <svg class="ring-svg" width="76" height="76" viewBox="0 0 76 76">
                <circle class="ring-track" cx="38" cy="38" r="30"/>
                <circle
                  class="ring-fill" cx="38" cy="38" r="30"
                  :stroke="ringColor(b.pct)"
                  stroke-dasharray="188.5"
                  :stroke-dashoffset="188.5 - (Math.min(b.pct, 100) / 100) * 188.5"
                />
              </svg>
              <div class="ring-center"><span class="ring-pct" :style="{ color: ringColor(b.pct) }">{{ b.pct }}%</span></div>
            </div>
            <span class="ring-name">{{ b.name }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- Ce mois-ci -->
    <section v-if="hasPermission('Pilotage') && kpis" class="section">
      <h2 class="eyebrow">Ce mois-ci</h2>
      <div class="mini-row">
        <div class="mini-card">
          <span class="mini-label">Solde courant</span>
          <span class="mini-value">{{ fmt(kpis.current_balance) }} {{ currency }}</span>
        </div>
        <div class="mini-card">
          <span class="mini-label">Revenus du mois</span>
          <span class="mini-value positive">{{ fmt(kpis.monthly_income) }} {{ currency }}</span>
        </div>
        <div class="mini-card">
          <span class="mini-label">Dépenses du mois</span>
          <span class="mini-value negative">{{ fmt(kpis.monthly_expenses) }} {{ currency }}</span>
        </div>
        <div v-if="!hasPermission('Patrimoine')" class="mini-card">
          <span class="mini-label">Épargne / Actifs</span>
          <span class="mini-value">{{ fmt(kpis.assets_balance) }} {{ currency }}</span>
        </div>
      </div>
    </section>

    <!-- Raccourcis -->
    <section v-if="shortcuts.length" class="section">
      <h2 class="eyebrow">Raccourcis</h2>
      <div class="shortcuts-grid">
        <router-link v-for="s in shortcuts" :key="s.to" :to="s.to" class="shortcut">
          <span class="shortcut-icon" v-html="s.icon"></span>
          <span class="shortcut-label">{{ s.label }}</span>
        </router-link>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { currency } from '@/utils/settings.js'
import { hasPermission } from '@/utils/permissions.js'

const user = ref(null)
const kpis = ref(null)
const dataFreshness = ref(null)
const wealth = ref(null)
const wealthHistory = ref([])
const budgets = ref([])
const subscriptions = ref([])
const hoverIndex = ref(null)

const todayLabel = computed(() => {
  return new Date().toLocaleDateString('fr-FR', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  })
})

const greeting = computed(() => (new Date().getHours() < 18 ? 'Bonjour' : 'Bonsoir'))

function fmt(v) {
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(v ?? 0)
}

// ── Patrimoine : courbe + variation 30 jours ──────────────────────────────
// Source = /api/wealth/history (WealthSnapshot), la même méthodologie que
// wealth.net_worth_total affiché juste au-dessus — volontairement pas
// /api/dashboard/stats.networth_history, qui est un périmètre différent
// (Current/Assets/Equity seulement, sans la valorisation de portefeuille) :
// afficher une tendance qui ne correspond pas au chiffre du dessus induirait
// en erreur (voir memory feedback_cross_page_metric_consistency).
const SPARK_W = 560, SPARK_H = 120, SPARK_PAD = 6

const sparkGeometry = computed(() => {
  const hist = wealthHistory.value
  if (hist.length < 2) return null
  const values = hist.map(h => h.total)
  const min = Math.min(...values), max = Math.max(...values)
  const span = max - min || 1
  const xAt = i => (i / (values.length - 1)) * SPARK_W
  const yAt = v => SPARK_H - SPARK_PAD - ((v - min) / span) * (SPARK_H - SPARK_PAD * 2)
  const coords = values.map((v, i) => [xAt(i), yAt(v)])
  const line = coords.map((p, i) => (i === 0 ? 'M' : 'L') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ')
  const area = line + ` L${SPARK_W},${SPARK_H} L0,${SPARK_H} Z`
  return { coords, line, area, last: coords[coords.length - 1] }
})

const hoverPoint = computed(() => {
  if (hoverIndex.value === null || !wealthHistory.value[hoverIndex.value]) return null
  const h = wealthHistory.value[hoverIndex.value]
  const dateLabel = new Date(h.date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' })
  return { label: `${dateLabel} — ${fmt(h.total)} ${currency.value}` }
})

const hoverTipStyle = computed(() => {
  if (!sparkGeometry.value || hoverIndex.value === null) return {}
  const p = sparkGeometry.value.coords[hoverIndex.value]
  return { left: (p[0] / SPARK_W * 100) + '%', top: (p[1] / SPARK_H * 100) + '%' }
})

const deltaPct = computed(() => {
  const hist = wealthHistory.value
  if (hist.length < 2) return null
  const last = hist[hist.length - 1]
  const targetTime = new Date(last.date).getTime() - 30 * 24 * 60 * 60 * 1000
  let closest = hist[0], closestDiff = Infinity
  for (const h of hist) {
    const diff = Math.abs(new Date(h.date).getTime() - targetTime)
    if (diff < closestDiff) { closestDiff = diff; closest = h }
  }
  if (!closest.total) return null
  return ((last.total - closest.total) / Math.abs(closest.total)) * 100
})

// ── Budgets : santé + entrées "à venir" ────────────────────────────────────
// GET /api/budgets renvoie TOUT l'historique des budgets (Budgets.vue s'en sert comme d'un
// navigateur d'historique), pas seulement ceux en cours — sans ce filtre par période, l'Accueil
// afficherait des budgets expirés comme s'ils étaient "du mois en cours" (constaté avec les
// données de démo : budgets datés de mars encore renvoyés en août, jamais reconduits car
// renew_period n'était pas défini dessus).
const nowDate = new Date()
const budgetsWithPct = computed(() =>
  budgets.value
    .filter(b => b.amount_allocated && new Date(b.start_date) <= nowDate && nowDate <= new Date(b.end_date))
    // Math.max(0, ...) : un budget peut avoir amount_spent négatif (remboursement net sur la
    // période) — un pourcentage négatif n'a pas de sens à afficher, 0 % (rien consommé net) est
    // la lecture honnête la plus proche.
    .map(b => ({ ...b, pct: Math.max(0, Math.round((b.amount_spent / b.amount_allocated) * 100)) }))
)
const budgetsOverCount = computed(() => budgetsWithPct.value.filter(b => b.pct >= 100).length)
const worstBudget = computed(() =>
  budgetsWithPct.value.length
    ? budgetsWithPct.value.reduce((a, b) => (b.pct > a.pct ? b : a))
    : null
)

function ringColor(pct) {
  if (pct >= 100) return 'var(--color-danger)'
  if (pct >= 80) return 'var(--color-warning)'
  return 'var(--color-success)'
}

// ── Série "sans dépassement" : GET /api/budgets/streak (mois civils complets,
// hors mois en cours déjà couvert par les anneaux/insight ci-dessus).
const streak = ref(null)

function formatMonthLabel(ym) {
  const [y, m] = ym.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
}

const streakBadge = computed(() => {
  if (!streak.value) return null
  if (streak.value.stale) {
    return { text: 'Données pas à jour', good: false, neutral: true }
  }
  if (streak.value.months === 0) {
    if (!streak.value.last_overrun) return null
    return { text: `Dépassement le mois dernier (${streak.value.last_overrun.name})`, good: false }
  }
  const caption = streak.value.last_overrun
    ? `Dernier dépassement : ${streak.value.last_overrun.name}, ${formatMonthLabel(streak.value.last_overrun.month)}`
    : null
  return { text: `${streak.value.months} mois sans dépassement`, caption, good: true }
})

// ── Bandeau de fraîcheur : GET /api/dashboard/stats.data_freshness ───────
const freshnessWarning = computed(() => {
  if (!dataFreshness.value?.stale) return ''
  const { last_transaction_date, days_since } = dataFreshness.value
  if (!last_transaction_date) return "Aucune transaction enregistrée pour l'instant."
  const dateLabel = new Date(last_transaction_date).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })
  return `Vos données ne sont peut-être pas à jour — dernière transaction importée le ${dateLabel}` +
    (days_since ? ` (il y a ${days_since} jour${days_since > 1 ? 's' : ''}).` : '.')
})

const insight = computed(() => {
  const parts = []
  if (hasPermission('Pilotage') && kpis.value?.expenses_vs_avg_pct !== null && kpis.value?.expenses_vs_avg_pct !== undefined) {
    const pct = kpis.value.expenses_vs_avg_pct
    const sign = pct >= 0 ? 'au-dessus de' : 'en dessous de'
    parts.push(`Vos dépenses ce mois-ci sont ${Math.abs(pct).toFixed(0)} % ${sign} votre moyenne des mois précédents`)
  }
  if (hasPermission('Planification') && budgetsWithPct.value.length) {
    if (budgetsOverCount.value === 1) parts.push(`le budget « ${worstBudget.value.name} » dépasse son enveloppe ce mois-ci`)
    else if (budgetsOverCount.value > 1) parts.push(`${budgetsOverCount.value} budgets dépassent leur enveloppe ce mois-ci`)
    else if (parts.length) parts.push('tous vos budgets sont dans les clous')
  }
  if (!parts.length) return ''
  const joined = parts.join(' — ')
  return joined.charAt(0).toUpperCase() + joined.slice(1) + '.'
})

// ── À venir : budgets en alerte + abonnements proches, fusionnés ─────────
const upcoming = computed(() => {
  const list = []
  for (const b of budgetsWithPct.value) {
    if (b.pct >= 100) {
      list.push({ severity: 'crit', title: `Budget « ${b.name} » dépassé`, sub: `${b.pct} % de l'enveloppe mensuelle`, when: 'Ce mois-ci', to: '/budgets' })
    } else if (b.pct >= 80) {
      list.push({ severity: 'warn', title: `Budget « ${b.name} »`, sub: `${b.pct} % consommé`, when: 'À surveiller', to: '/budgets' })
    }
  }
  const now = Date.now()
  for (const s of subscriptions.value) {
    if (!s.next_due_at) continue
    const daysLeft = Math.ceil((new Date(s.next_due_at).getTime() - now) / (24 * 60 * 60 * 1000))
    if (daysLeft >= 0 && daysLeft <= 7) {
      list.push({
        severity: daysLeft <= 2 ? 'crit' : 'warn',
        title: s.name,
        sub: `Prélèvement prévu · ${fmt(s.amount)} ${currency.value}`,
        when: daysLeft === 0 ? "Aujourd'hui" : daysLeft === 1 ? 'Demain' : `Dans ${daysLeft} jours`,
        to: '/subscriptions',
      })
    }
  }
  const order = { crit: 0, warn: 1 }
  return list.sort((a, b) => order[a.severity] - order[b.severity])
})

// ── Raccourcis : une entrée par grand module, pas une par écran ──────────
const ICONS = {
  portfolio: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18M7 15l4-5 3 3 5-7"/></svg>',
  accounts: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10h18M5 10V6l7-3 7 3v4M4 10v9h16v-9M9 14v3m6-3v3"/></svg>',
  budgets: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 3v9l6 3"/></svg>',
  reports: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19h16M8 19V9m4 10V5m4 14v-7"/></svg>',
  markets: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 9 19.4a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.09a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.09a1.7 1.7 0 0 0-1.51 1Z"/></svg>',
}
const SHORTCUTS_DEF = [
  { to: '/portfolio', icon: ICONS.portfolio, label: 'Portefeuille', perm: 'Patrimoine' },
  { to: '/accounts', icon: ICONS.accounts, label: 'Comptes', perm: 'Comptabilité' },
  { to: '/budgets', icon: ICONS.budgets, label: 'Budgets', perm: 'Planification' },
  { to: '/reports', icon: ICONS.reports, label: 'Rapports', perm: 'Pilotage' },
  { to: '/markets/analyse', icon: ICONS.markets, label: 'Marchés', perm: 'Patrimoine' },
  { to: '/parametres', icon: ICONS.settings, label: 'Paramétrage', perm: 'Réglages personnels' },
]
const shortcuts = computed(() => SHORTCUTS_DEF.filter(s => hasPermission(s.perm)))

async function load() {
  const calls = [axios.get('/api/auth/me')]
  const keys = ['me']

  if (hasPermission('Pilotage')) { calls.push(axios.get('/api/dashboard/stats')); keys.push('stats') }
  if (hasPermission('Patrimoine')) {
    calls.push(axios.get('/api/wealth/overview', { params: { currency: currency.value } })); keys.push('wealth')
    const startDate = new Date(Date.now() - 180 * 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
    calls.push(axios.get('/api/wealth/history', { params: { currency: currency.value, start_date: startDate } })); keys.push('wealthHistory')
  }
  if (hasPermission('Planification')) {
    calls.push(axios.get('/api/budgets')); keys.push('budgets')
    calls.push(axios.get('/api/subscriptions')); keys.push('subscriptions')
    calls.push(axios.get('/api/budgets/streak')); keys.push('streak')
  }

  const results = await Promise.allSettled(calls)
  const byKey = Object.fromEntries(keys.map((k, i) => [k, results[i]]))

  if (byKey.me?.status === 'fulfilled') user.value = byKey.me.value.data?.response_data
  if (byKey.stats?.status === 'fulfilled') {
    kpis.value = byKey.stats.value.data?.response_data?.kpis
    dataFreshness.value = byKey.stats.value.data?.response_data?.data_freshness
  }
  if (byKey.wealth?.status === 'fulfilled') wealth.value = byKey.wealth.value.data?.response_data?.kpis
  if (byKey.wealthHistory?.status === 'fulfilled') wealthHistory.value = Array.isArray(byKey.wealthHistory.value.data?.response_data) ? byKey.wealthHistory.value.data.response_data : []
  if (byKey.budgets?.status === 'fulfilled') budgets.value = Array.isArray(byKey.budgets.value.data?.response_data) ? byKey.budgets.value.data.response_data : []
  if (byKey.subscriptions?.status === 'fulfilled') subscriptions.value = Array.isArray(byKey.subscriptions.value.data?.response_data) ? byKey.subscriptions.value.data.response_data : []
  if (byKey.streak?.status === 'fulfilled') streak.value = byKey.streak.value.data?.response_data
}

onMounted(load)
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
  gap: 30px;
}

/* Hero */
.hero {
  position: relative;
  overflow: hidden;
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  padding: 30px 32px;
  background:
    radial-gradient(120% 160% at 100% 0%, color-mix(in srgb, var(--color-accent-2) 30%, transparent), transparent 55%),
    radial-gradient(90% 140% at 0% 100%, color-mix(in srgb, var(--color-accent) 25%, transparent), transparent 60%),
    rgba(2, 6, 23, 0.55);
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 24px;
  flex-wrap: wrap;
}
.hero-left { max-width: 620px; }
.hero-eyebrow {
  font-size: 12px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase;
  color: #a5b4fc; margin: 0 0 8px;
}
.hero-greeting { margin: 0; font-size: 30px; font-weight: 800; color: #f8fafc; letter-spacing: -0.01em; }
.hero-insight { margin: 12px 0 0; font-size: 15.5px; color: #cbd5e1; max-width: 58ch; }

.streak { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; flex-shrink: 0; }
.streak-badge {
  display: flex; align-items: center; gap: 8px;
  background: rgba(34, 197, 94, 0.14);
  border: 1px solid rgba(34, 197, 94, 0.35);
  color: #86efac;
  padding: 8px 14px; border-radius: 999px;
  font-size: 13px; font-weight: 700; white-space: nowrap;
}
.streak-badge.warn { background: rgba(245, 158, 11, 0.14); border-color: rgba(245, 158, 11, 0.35); color: #fde68a; }
.streak-badge.neutral { background: rgba(148, 163, 184, 0.14); border-color: rgba(148, 163, 184, 0.3); color: #cbd5e1; }
.streak-dot { width: 7px; height: 7px; border-radius: 50%; background: #22c55e; box-shadow: 0 0 0 3px rgba(34,197,94,0.18); }
.streak-dot.warn { background: #f59e0b; box-shadow: 0 0 0 3px rgba(245,158,11,0.18); }
.streak-dot.neutral { background: #94a3b8; box-shadow: 0 0 0 3px rgba(148,163,184,0.18); }
.streak-caption { font-size: 12px; color: #6b7280; text-align: right; }

.freshness-banner {
  display: flex; align-items: center; gap: 10px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: #fde68a;
  border-radius: 12px;
  padding: 12px 16px;
  font-size: 13.5px;
}
.freshness-icon { font-size: 14px; flex-shrink: 0; }

@media (max-width: 640px) {
  .streak { align-items: flex-start; }
  .streak-caption { text-align: left; }
}

/* Section eyebrow */
.eyebrow {
  font-size: 13px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
  color: #9ca3af; margin: 0 0 14px;
}

/* Cards */
.card {
  background: rgba(2, 6, 23, 0.45);
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 16px;
  padding: 20px 22px;
}

/* Briefing */
.briefing { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 16px; }

.worth-head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; }
.worth-label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.06em; }
.worth-delta { font-size: 12.5px; font-weight: 700; color: #86efac; font-variant-numeric: tabular-nums; }
.worth-delta.negative { color: #fca5a5; }
.worth-value { font-size: 34px; font-weight: 800; color: #f8fafc; font-variant-numeric: tabular-nums; margin: 4px 0 2px; }
.worth-sub { font-size: 13px; color: #9ca3af; margin-bottom: 14px; }
.worth-sub strong { color: #cbd5e1; font-weight: 600; }

.spark-wrap { position: relative; }
.spark-tip {
  position: absolute; transform: translate(-50%, -132%);
  background: #020617; border: 1px solid rgba(148,163,184,0.3);
  border-radius: 8px; padding: 6px 9px; font-size: 12px;
  color: #e5e7eb; white-space: nowrap; pointer-events: none;
  opacity: 0; transition: opacity 0.1s ease;
}
.spark-tip.show { opacity: 1; }
.spark-caption { margin: 8px 0 0; font-size: 11.5px; color: #6b7280; }

/* Upcoming */
.up-title-head { margin: 0 0 12px; font-size: 13px; font-weight: 700; color: #e5e7eb; }
.up-list { display: flex; flex-direction: column; }
.up-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(148, 163, 184, 0.1);
  text-decoration: none;
}
.up-item:last-child { border-bottom: none; padding-bottom: 0; }
.up-item:first-child { padding-top: 0; }
.up-glyph {
  width: 32px; height: 32px; border-radius: 9px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}
.up-glyph svg { width: 15px; height: 15px; }
.up-glyph.crit { background: rgba(239,68,68,0.12); color: #f87171; }
.up-glyph.warn { background: rgba(245,158,11,0.12); color: #f59e0b; }
.up-text { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.up-item-title { font-size: 13.5px; color: #e5e7eb; font-weight: 600; }
.up-sub { font-size: 12px; color: #6b7280; margin-top: 1px; }
.up-when { font-size: 11.5px; font-weight: 700; padding: 4px 9px; border-radius: 999px; white-space: nowrap; }
.up-when.crit { background: rgba(239,68,68,0.12); color: #fca5a5; }
.up-when.warn { background: rgba(245,158,11,0.12); color: #fde68a; }
.up-empty { font-size: 13px; color: #6b7280; margin: 0; }

/* Budget rings */
.rings-card { display: flex; flex-direction: column; gap: 16px; }
.rings-title-row { display: flex; align-items: center; justify-content: space-between; }
.rings-title { font-size: 13px; font-weight: 700; color: #e5e7eb; }
.rings-link { font-size: 12.5px; color: #a5b4fc; text-decoration: none; font-weight: 600; }
.rings-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(90px, 1fr)); gap: 14px; }
.ring-item { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.ring-svg { transform: rotate(-90deg); }
.ring-track { fill: none; stroke: rgba(148, 163, 184, 0.16); stroke-width: 7; }
.ring-fill { fill: none; stroke-width: 7; stroke-linecap: round; transition: stroke-dashoffset 0.5s ease; }
.ring-wrap { position: relative; width: 76px; height: 76px; }
.ring-center { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; }
.ring-pct { font-size: 13px; font-weight: 800; font-variant-numeric: tabular-nums; }
.ring-name { font-size: 12px; color: #9ca3af; text-align: center; }

/* Mini KPI row */
.mini-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
.mini-card {
  display: flex; flex-direction: column; gap: 6px;
  padding: 16px; border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(2, 6, 23, 0.45); border-radius: 14px;
}
.mini-label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
.mini-value { font-size: 20px; font-weight: 700; font-variant-numeric: tabular-nums; }
.mini-value.positive { color: #86efac; }
.mini-value.negative { color: #fca5a5; }

/* Shortcuts */
.shortcuts-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 10px; }
.shortcut {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
  padding: 16px 10px;
  border: 1px solid rgba(148, 163, 184, 0.16); border-radius: 14px;
  background: rgba(2, 6, 23, 0.45);
  text-decoration: none;
  transition: border-color 0.15s, transform 0.15s, background 0.15s;
}
.shortcut:hover { border-color: rgba(99,102,241,0.45); background: rgba(37,99,235,0.08); transform: translateY(-2px); }
.shortcut-icon {
  width: 34px; height: 34px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, color-mix(in srgb, var(--color-accent) 20%, transparent), color-mix(in srgb, var(--color-accent-2) 16%, transparent));
  color: #a5b4fc;
}
.shortcut-icon svg { width: 16px; height: 16px; }
.shortcut-label { font-size: 12.5px; color: #cbd5e1; font-weight: 600; text-align: center; }

@media (max-width: 640px) {
  .hero { flex-direction: column; align-items: flex-start; }
}
</style>
