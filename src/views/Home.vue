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

    <!-- KPI strip -->
    <section v-if="hasPermission('Patrimoine') || hasPermission('Pilotage')" class="section">
      <h2 class="section-title">Aperçu</h2>
      <div class="kpi-strip">
        <div v-if="hasPermission('Patrimoine') && wealth" class="kpi-card hero">
          <span class="kpi-label">Patrimoine total</span>
          <span class="kpi-value">{{ fmt(wealth.net_worth_total) }} {{ currency }}</span>
          <span class="kpi-sub">Bancaire {{ fmt(wealth.bank_net_worth) }} · Portefeuille {{ fmt(wealth.portfolio_value) }}</span>
        </div>
        <template v-if="hasPermission('Pilotage') && kpis">
          <div class="kpi-card">
            <span class="kpi-label">Solde courant</span>
            <span class="kpi-value">{{ fmt(kpis.current_balance) }} {{ currency }}</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">Revenus du mois</span>
            <span class="kpi-value positive">{{ fmt(kpis.monthly_income) }} {{ currency }}</span>
          </div>
          <div class="kpi-card">
            <span class="kpi-label">Dépenses du mois</span>
            <span class="kpi-value negative">{{ fmt(kpis.monthly_expenses) }} {{ currency }}</span>
          </div>
          <div v-if="!hasPermission('Patrimoine')" class="kpi-card">
            <span class="kpi-label">Épargne / Actifs</span>
            <span class="kpi-value">{{ fmt(kpis.assets_balance) }} {{ currency }}</span>
          </div>
        </template>
      </div>
    </section>

    <!-- Quick nav -->
    <section v-for="group in navGroups" :key="group.label" class="section">
      <h2 class="section-title">{{ group.label }}</h2>
      <div class="nav-grid">
        <router-link
          v-for="card in group.cards"
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { currency } from '@/utils/settings.js'
import { hasPermission } from '@/utils/permissions.js'

const user = ref(null)
const kpis = ref(null)
const wealth = ref(null)
const budgets = ref([])
const subscriptions = ref([])

const todayLabel = computed(() => {
  return new Date().toLocaleDateString('fr-FR', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
  })
})

// Mêmes groupes/permissions que la sidebar (cf. src/components/sidebar/Sidebar.vue) — un groupe
// n'apparaît que si l'utilisateur a la permission associée.
const NAV_GROUPS_DEF = [
  {
    label: 'Gestion financière',
    perm: 'Patrimoine',
    cards: [
      { to: '/patrimoine', icon: '💰', label: "Vue d'ensemble", desc: 'Valeur nette, allocation' },
      { to: '/portfolio', icon: '📈', label: 'Portefeuille', desc: 'Actifs et positions' },
      { to: '/markets/analyse', icon: '🔍', label: 'Marchés', desc: 'Analyse, watchlist, scanner' },
    ],
  },
  {
    label: 'Comptabilité',
    perm: 'Comptabilité',
    cards: [
      { to: '/accounts', icon: '🏦', label: 'Comptes', desc: 'Gérer vos comptes' },
      { to: '/transactions', icon: '💳', label: 'Transactions', desc: 'Historique complet' },
      { to: '/import', icon: '⬆️', label: 'Importer', desc: 'Relevés bancaires' },
      { to: '/reconcile', icon: '✅', label: 'Rapprochement', desc: 'Pointage bancaire' },
      { to: '/categories', icon: '🏷️', label: 'Catégories', desc: 'Organiser les dépenses' },
      { to: '/tags', icon: '🔖', label: 'Tags', desc: 'Étiquettes libres' },
    ],
  },
  {
    label: 'Planification',
    perm: 'Planification',
    cards: [
      { to: '/budgets', icon: '🎯', label: 'Budgets', desc: 'Suivi des enveloppes' },
      { to: '/subscriptions', icon: '🔄', label: 'Abonnements', desc: 'Dépenses récurrentes' },
    ],
  },
  {
    label: 'Pilotage',
    perm: 'Pilotage',
    cards: [
      { to: '/Dashboard', icon: '📊', label: 'Tableau de bord', desc: 'Solde, flux, dépenses' },
      { to: '/reports', icon: '📋', label: 'Rapports', desc: 'Analyses détaillées' },
    ],
  },
  {
    label: 'Réglages',
    perm: 'Réglages personnels',
    cards: [
      { to: '/parametres', icon: '⚙️', label: 'Paramétrage', desc: 'Interface, marchés, devises' },
    ],
  },
  {
    label: 'Administration',
    perm: 'Delete users',
    cards: [
      { to: '/admin/users', icon: '👤', label: 'Utilisateurs', desc: 'Gestion des comptes' },
      { to: '/admin/roles', icon: '🔐', label: 'Rôles & Permissions', desc: "Contrôle d'accès" },
    ],
  },
]

const navGroups = computed(() => NAV_GROUPS_DEF.filter(g => hasPermission(g.perm)))

const alerts = computed(() => {
  const list = []
  if (!hasPermission('Planification')) return list

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
    if (!s.next_due_at) continue
    const daysLeft = Math.ceil((new Date(s.next_due_at).getTime() - now) / (24 * 60 * 60 * 1000))
    if (daysLeft <= 7) {
      list.push({
        level: daysLeft <= 2 ? 'danger' : 'warn',
        icon: '🔄',
        text: `Abonnement « ${s.name} » prévu dans ${daysLeft} jour${daysLeft > 1 ? 's' : ''} (${fmt(s.amount)} ${currency.value})`,
        link: '/subscriptions',
      })
    }
  }

  return list
})

function fmt(v) {
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(v ?? 0)
}

async function load() {
  const calls = [axios.get('/api/auth/me')]
  const keys = ['me']

  if (hasPermission('Pilotage')) { calls.push(axios.get('/api/dashboard/stats')); keys.push('stats') }
  if (hasPermission('Patrimoine')) { calls.push(axios.get('/api/wealth/overview', { params: { currency: currency.value } })); keys.push('wealth') }
  if (hasPermission('Planification')) {
    calls.push(axios.get('/api/budgets')); keys.push('budgets')
    calls.push(axios.get('/api/subscriptions')); keys.push('subscriptions')
  }

  const results = await Promise.allSettled(calls)
  const byKey = Object.fromEntries(keys.map((k, i) => [k, results[i]]))

  if (byKey.me?.status === 'fulfilled') user.value = byKey.me.value.data?.response_data
  if (byKey.stats?.status === 'fulfilled') kpis.value = byKey.stats.value.data?.response_data?.kpis
  if (byKey.wealth?.status === 'fulfilled') wealth.value = byKey.wealth.value.data?.response_data?.kpis
  if (byKey.budgets?.status === 'fulfilled') budgets.value = Array.isArray(byKey.budgets.value.data?.response_data) ? byKey.budgets.value.data.response_data : []
  if (byKey.subscriptions?.status === 'fulfilled') subscriptions.value = Array.isArray(byKey.subscriptions.value.data?.response_data) ? byKey.subscriptions.value.data.response_data : []
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
.kpi-card.hero {
  grid-column: span 2;
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.15), rgba(79, 70, 229, 0.1));
  border-color: rgba(99, 102, 241, 0.35);
}
.kpi-label { font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; }
.kpi-value { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
.kpi-card.hero .kpi-value { font-size: 30px; color: #f1f5f9; }
.kpi-sub { font-size: 12px; color: #9ca3af; }
.kpi-value.positive { color: #86efac; }
.kpi-value.negative { color: #fca5a5; }
</style>
