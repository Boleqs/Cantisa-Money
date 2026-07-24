<template>
  <header class="topbar" :style="{ height: TOPBAR_HEIGHT, marginLeft: sidebarWidth }">
    <!-- Gauche : titre de la page + date -->
    <div class="topbar-left">
      <span class="page-title">{{ pageTitle }}</span>
      <span class="topbar-date">{{ todayLabel }}</span>
    </div>

    <!-- Droite : cloche + avatar utilisateur -->
    <div class="topbar-right">
      <!-- Cloche d'alertes -->
      <router-link to="/" class="alert-bell" title="Voir les alertes">
        <span class="bell-icon">🔔</span>
        <span v-if="alertCount > 0" class="alert-badge">{{ alertCount }}</span>
      </router-link>

      <!-- Avatar + menu déroulant -->
      <div class="user-menu" ref="menuRef">
        <button class="user-avatar" @click="menuOpen = !menuOpen" :title="user?.username">
          {{ initials }}
        </button>

        <div v-if="menuOpen" class="dropdown">
          <div class="dropdown-user">
            <span class="dropdown-username">{{ user?.username ?? '…' }}</span>
            <span class="dropdown-email">{{ user?.email ?? '' }}</span>
          </div>
          <hr class="dropdown-sep" />
          <button class="dropdown-item" @click="openAccount">👤 Mon compte</button>
          <button class="dropdown-item danger" @click="logout">🚪 Déconnexion</button>
        </div>
      </div>
    </div>
  </header>

  <!-- Modal compte réutilisée depuis la sidebar -->
  <MyAccount v-if="showMyAccount" @close="showMyAccount = false" />
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

import { TOPBAR_HEIGHT } from './state.js'
import { sidebarWidth } from '@/components/sidebar/state.js'
import MyAccount from '@/components/modal/MyAccount.vue'
import { clearPermissions } from '@/utils/permissions.js'
import { clearSettings } from '@/utils/settings.js'

const route = useRoute()
const router = useRouter()

// ── Page title mapping ────────────────────────────────────────────────────────
const PAGE_TITLES = {
  Home:        'Accueil',
  Dashboard:   'Tableau de bord',
  Accounts:    'Comptes',
  Transactions:'Transactions',
  Budgets:     'Budgets',
  Categories:  'Catégories',
  Tags:        'Tags',
  Subscriptions: 'Abonnements',
  Portfolio:   'Portefeuille',
  Markets:     'Marchés',
  Invoices:    'Factures',
  Reports:     'Rapports',
  AdminUsers:  'Utilisateurs',
}

const pageTitle = computed(() => PAGE_TITLES[route.name] ?? route.name ?? '')

// ── Date ──────────────────────────────────────────────────────────────────────
const todayLabel = computed(() =>
  new Date().toLocaleDateString('fr-FR', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  })
)

// ── User ──────────────────────────────────────────────────────────────────────
const user = ref(null)
const initials = computed(() => {
  const name = user.value?.username ?? ''
  return name.slice(0, 2).toUpperCase() || '?'
})

async function loadUser() {
  try {
    const res = await axios.get('/api/auth/me')
    user.value = res.data?.response_data ?? null
  } catch { /* pas connecté */ }
}

// ── Alerts ────────────────────────────────────────────────────────────────────
const budgets = ref([])
const subscriptions = ref([])

const alertCount = computed(() => {
  let n = 0
  for (const b of budgets.value) {
    if (b.amount_allocated && b.amount_spent / b.amount_allocated >= 0.8) n++
  }
  const now = Date.now()
  for (const s of subscriptions.value) {
    if (!s.next_due_at) continue
    const daysLeft = Math.ceil((new Date(s.next_due_at).getTime() - now) / 86400000)
    if (daysLeft <= 7) n++
  }
  return n
})

async function loadAlerts() {
  try {
    const [bRes, sRes] = await Promise.allSettled([
      axios.get('/api/budgets'),
      axios.get('/api/subscriptions'),
    ])
    if (bRes.status === 'fulfilled') budgets.value = bRes.value.data?.response_data ?? []
    if (sRes.status === 'fulfilled') subscriptions.value = sRes.value.data?.response_data ?? []
  } catch { /* silencieux */ }
}

// Recharger le badge à chaque changement de route
watch(() => route.path, loadAlerts)

// ── Dropdown ──────────────────────────────────────────────────────────────────
const menuOpen = ref(false)
const menuRef = ref(null)
const showMyAccount = ref(false)

function onClickOutside(e) {
  if (menuRef.value && !menuRef.value.contains(e.target)) {
    menuOpen.value = false
  }
}

function openAccount() {
  menuOpen.value = false
  showMyAccount.value = true
}

async function logout() {
  menuOpen.value = false
  try { await axios.post('/api/auth/logout') } catch { /* ignore */ }
  clearPermissions()
  clearSettings()
  router.push('/Signin')
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────
onMounted(() => {
  document.addEventListener('click', onClickOutside)
  loadUser()
  loadAlerts()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<style scoped>
.topbar {
  position: fixed;
  top: 0;
  right: 0;
  left: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background: #111827;
  border-bottom: 1px solid #1f2937;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
  transition: margin-left 0.5s;
}

/* Left */
.topbar-left {
  display: flex;
  align-items: baseline;
  gap: 14px;
}

.page-title {
  font-size: 15px;
  font-weight: 700;
  color: #f1f5f9;
}

.topbar-date {
  font-size: 12px;
  color: #6b7280;
  text-transform: capitalize;
}

/* Right */
.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* Bell */
.alert-bell {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  text-decoration: none;
  color: #9ca3af;
  background: transparent;
  transition: background 0.15s;
}
.alert-bell:hover { background: rgba(255,255,255,0.07); }

.bell-icon { font-size: 16px; }

.alert-badge {
  position: absolute;
  top: 3px;
  right: 3px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 999px;
  background: #ef4444;
  color: #fff;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

/* Avatar */
.user-menu { position: relative; }

.user-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 0.03em;
  transition: opacity 0.15s;
}
.user-avatar:hover { opacity: 0.85; }

/* Dropdown */
.dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  min-width: 200px;
  background: #1f2937;
  border: 1px solid #374151;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
  overflow: hidden;
  z-index: 200;
}

.dropdown-user {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 14px;
}
.dropdown-username { font-size: 13px; font-weight: 700; color: #f1f5f9; }
.dropdown-email    { font-size: 11px; color: #6b7280; }

.dropdown-sep {
  margin: 0;
  border: none;
  border-top: 1px solid #374151;
}

.dropdown-item {
  display: block;
  width: 100%;
  padding: 9px 14px;
  background: transparent;
  border: none;
  color: #d1d5db;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: background 0.12s;
}
.dropdown-item:hover          { background: rgba(255,255,255,0.06); }
.dropdown-item.danger         { color: #fca5a5; }
.dropdown-item.danger:hover   { background: rgba(239,68,68,0.1); }
</style>
