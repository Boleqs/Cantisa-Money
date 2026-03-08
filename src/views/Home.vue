<template>
  <div class="page">
    <!-- Welcome -->
    <div class="welcome-block">
      <div>
        <h1 class="welcome-title">Bonjour, {{ user?.username || '…' }} 👋</h1>
        <p class="welcome-date">{{ todayLabel }}</p>
      </div>
    </div>

    <!-- Alerts -->
    <section v-if="alerts.length" class="section">
      <h2 class="section-title">Alertes</h2>
      <div class="alerts-list">
        <div
          v-for="(a, i) in alerts"
          :key="i"
          :class="['alert-item', a.level]"
        >
          <span class="alert-icon">{{ a.icon }}</span>
          <span class="alert-text">{{ a.text }}</span>
          <router-link :to="a.link" class="alert-link">Voir →</router-link>
        </div>
      </div>
    </section>

    <!-- Quick nav -->
    <section class="section">
      <h2 class="section-title">Navigation rapide</h2>
      <div class="nav-grid">
        <router-link
          v-for="card in navCards"
          :key="card.to"
          :to="card.to"
          class="nav-card"
        >
          <span class="nav-icon">{{ card.icon }}</span>
          <span class="nav-label">{{ card.label }}</span>
          <span class="nav-desc">{{ card.desc }}</span>
        </router-link>
      </div>
    </section>

    <!-- KPI strip (reused from dashboard) -->
    <section v-if="kpis" class="section">
      <h2 class="section-title">Aperçu du mois</h2>
      <div class="kpi-strip">
        <div class="kpi-card">
          <span class="kpi-label">Solde courant</span>
          <span class="kpi-value">{{ fmt(kpis.current_balance) }} €</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Revenus du mois</span>
          <span class="kpi-value positive">{{ fmt(kpis.monthly_income) }} €</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Dépenses du mois</span>
          <span class="kpi-value negative">{{ fmt(kpis.monthly_expenses) }} €</span>
        </div>
        <div class="kpi-card">
          <span class="kpi-label">Épargne / Actifs</span>
          <span class="kpi-value">{{ fmt(kpis.assets_balance) }} €</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const user = ref(null)
const kpis = ref(null)
const budgets = ref([])
const subscriptions = ref([])

const todayLabel = computed(() => {
  return new Date().toLocaleDateString('fr-FR', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  })
})

const navCards = [
  { to: '/dashboard',   icon: '📊', label: 'Tableau de bord', desc: 'Solde, flux, dépenses' },
  { to: '/accounts',    icon: '🏦', label: 'Comptes',          desc: 'Gérer vos comptes' },
  { to: '/transactions',icon: '💳', label: 'Transactions',     desc: 'Historique complet' },
  { to: '/budgets',     icon: '🎯', label: 'Budgets',          desc: 'Suivi des enveloppes' },
  { to: '/subscriptions',icon: '🔄', label: 'Abonnements',     desc: 'Dépenses récurrentes' },
  { to: '/portfolio',   icon: '📈', label: 'Portefeuille',     desc: 'Actifs et positions' },
  { to: '/reports',     icon: '📋', label: 'Rapports',         desc: 'Analyses détaillées' },
  { to: '/categories',  icon: '🏷️',  label: 'Catégories',      desc: 'Organiser les dépenses' },
]

const alerts = computed(() => {
  const list = []

  // Budget alerts
  for (const b of budgets.value) {
    if (!b.amount_allocated) continue
    const pct = (b.amount_spent / b.amount_allocated) * 100
    if (pct >= 100) {
      list.push({
        level: 'danger',
        icon: '🚨',
        text: `Budget « ${b.name} » dépassé (${pct.toFixed(0)}%)`,
        link: '/budgets',
      })
    } else if (pct >= 80) {
      list.push({
        level: 'warn',
        icon: '⚠️',
        text: `Budget « ${b.name} » à ${pct.toFixed(0)}% — attention`,
        link: '/budgets',
      })
    }
  }

  // Subscription alerts — due within 7 days
  const now = Date.now()
  for (const s of subscriptions.value) {
    if (!s.created_at || !s.recurrence) continue
    const created = new Date(s.created_at).getTime()
    const recurrenceMs = s.recurrence * 24 * 60 * 60 * 1000
    const elapsed = now - created
    const cyclePos = elapsed % recurrenceMs
    const daysLeft = Math.ceil((recurrenceMs - cyclePos) / (24 * 60 * 60 * 1000))
    if (daysLeft <= 7) {
      list.push({
        level: daysLeft <= 2 ? 'danger' : 'warn',
        icon: '🔄',
        text: `Abonnement « ${s.name} » prévu dans ${daysLeft} jour${daysLeft > 1 ? 's' : ''} (${fmtAmt(s.amount)} €)`,
        link: '/subscriptions',
      })
    }
  }

  return list
})

function fmt(v) {
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(v ?? 0)
}
function fmtAmt(v) {
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(v ?? 0)
}

async function load() {
  const [meRes, statsRes, budgetRes, subRes] = await Promise.allSettled([
    axios.get('/api/auth/me'),
    axios.get('/api/dashboard/stats'),
    axios.get('/api/budgets'),
    axios.get('/api/subscriptions'),
  ])
  if (meRes.status === 'fulfilled') user.value = meRes.value.data?.response_data
  if (statsRes.status === 'fulfilled') kpis.value = statsRes.value.data?.response_data?.kpis
  if (budgetRes.status === 'fulfilled') budgets.value = Array.isArray(budgetRes.value.data?.response_data) ? budgetRes.value.data.response_data : []
  if (subRes.status === 'fulfilled') subscriptions.value = Array.isArray(subRes.value.data?.response_data) ? subRes.value.data.response_data : []
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
  gap: 32px;
}

/* Welcome */
.welcome-block {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.welcome-title {
  margin: 0;
  font-size: 30px;
  font-weight: 700;
  color: #f1f5f9;
}
.welcome-date {
  margin: 6px 0 0;
  color: #9ca3af;
  font-size: 14px;
  text-transform: capitalize;
}

/* Sections */
.section {}
.section-title {
  margin: 0 0 14px;
  font-size: 16px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* Alerts */
.alerts-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.alert-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
}
.alert-item.warn {
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.3);
  color: #fde68a;
}
.alert-item.danger {
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.35);
  color: #fca5a5;
}
.alert-icon { font-size: 16px; flex-shrink: 0; }
.alert-text { flex: 1; }
.alert-link {
  color: inherit;
  font-weight: 600;
  text-decoration: none;
  opacity: 0.85;
  white-space: nowrap;
}
.alert-link:hover { opacity: 1; text-decoration: underline; }

/* Nav grid */
.nav-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.nav-card {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(2, 6, 23, 0.45);
  border-radius: 14px;
  text-decoration: none;
  color: #e5e7eb;
  transition: background 0.15s, border-color 0.15s;
}
.nav-card:hover {
  background: rgba(37, 99, 235, 0.12);
  border-color: rgba(99, 102, 241, 0.4);
}
.nav-icon { font-size: 24px; }
.nav-label { font-size: 14px; font-weight: 600; margin-top: 4px; }
.nav-desc { font-size: 12px; color: #6b7280; }

/* KPI strip */
.kpi-strip {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.kpi-card {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 16px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(2, 6, 23, 0.45);
  border-radius: 14px;
}
.kpi-label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
.kpi-value { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
.kpi-value.positive { color: #86efac; }
.kpi-value.negative { color: #fca5a5; }
</style>
