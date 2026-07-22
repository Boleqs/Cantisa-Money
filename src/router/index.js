import { createRouter, createWebHistory } from 'vue-router'
import axios from 'axios'
import { ensureSettingsLoaded } from '@/utils/settings.js'
import { ensurePermissionsLoaded } from '@/utils/permissions.js'

axios.defaults.withCredentials = true
axios.defaults.baseURL = 'http://localhost:5000'
// Protection CSRF côté backend (flask-jwt-extended, double-submit cookie) : axios lit
// automatiquement ce cookie non-httponly et l'envoie dans ce header sur chaque requête.
axios.defaults.xsrfCookieName = 'csrf_access_token'
axios.defaults.xsrfHeaderName = 'X-CSRF-TOKEN'
// Depuis axios 1.6, le cookie XSRF n'est plus relayé en header sur les requêtes cross-origin
// (frontend:5173 vs backend:5000 = origines différentes) sans ce flag explicite — sans lui,
// tous les POST/PUT/PATCH/DELETE échouent en 401 "Missing CSRF token" (les GET passent car
// non concernés par la protection CSRF de flask-jwt-extended).
axios.defaults.withXSRFToken = true

const routes = [
    {
        path: '/',
        name: 'Home',
        component: () => import('../views/Home.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/Dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/Signin',
        name: 'Signin',
        component: () => import('../views/Signin.vue'),
        meta: { guestOnly: true }
    },
    {
        path: '/init/Signup',
        name: 'Signup',
        component: () => import('../views/initialization/Signup.vue'),
        meta: { guestOnly: true }
    },
    {
        path: '/error',
        name: 'ConnectionError',
        component: () => import('../views/ConnectionError.vue')
    },
    {
        path: '/accounts',
        name: 'Accounts',
        component: () => import('../views/Accounts.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/accounts/:id',
        name: 'AccountDetail',
        component: () => import('../views/AccountDetail.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/transactions',
        name: 'Transactions',
        component: () => import('../views/Transactions.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/budgets',
        name: 'Budgets',
        component: () => import('../views/Budgets.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/categories',
        name: 'Categories',
        component: () => import('../views/Categories.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/tags',
        name: 'Tags',
        component: () => import('../views/Tags.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/subscriptions',
        name: 'Subscriptions',
        component: () => import('../views/Subscriptions.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/credits',
        name: 'Credits',
        component: () => import('../views/Credits.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/credits/:id',
        name: 'LoanDetail',
        component: () => import('../views/LoanDetail.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/portfolio',
        name: 'Portfolio',
        component: () => import('../views/Portfolio.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/markets/analyse',
        name: 'MarketsAnalyse',
        component: () => import('../views/MarketsAnalyse.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/markets/watchlist',
        name: 'MarketsWatchlist',
        component: () => import('../views/MarketsWatchlist.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/markets/scan',
        name: 'MarketsScan',
        component: () => import('../views/MarketsScan.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/invoices',
        name: 'Invoices',
        component: () => import('../views/Invoices.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/reports',
        name: 'Reports',
        component: () => import('../views/Reports.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/admin/users',
        name: 'AdminUsers',
        component: () => import('../views/AdminUsers.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/admin/roles',
        name: 'AdminRoles',
        component: () => import('../views/AdminRoles.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/import',
        name: 'Import',
        component: () => import('../views/Import.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/reconcile',
        name: 'Reconcile',
        component: () => import('../views/Reconcile.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/parametres',
        name: 'Parametres',
        component: () => import('../views/Parametres.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/patrimoine',
        name: 'WealthOverview',
        component: () => import('../views/WealthOverview.vue'),
        meta: { requiresAuth: true }
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

async function checkAuth() {
    try {
        await axios.get('/api/auth/check-auth', { withCredentials: true })
        return true
    } catch (err) {
        if (err.message === 'Network Error') return 'network_error'
        return false
    }
}

router.beforeEach(async (to, from, next) => {
    document.title = 'CMM | ' + to.name

    if (to.meta.requiresAuth || to.meta.guestOnly) {
        const authStatus = await checkAuth()

        if (authStatus === 'network_error') {
            return next('/error')
        }

        if (to.meta.requiresAuth && !authStatus) {
            return next('/Signin')
        }

        if (to.meta.guestOnly && authStatus === true) {
            return next('/Dashboard')
        }

        if (authStatus === true) {
            await Promise.all([ensureSettingsLoaded(), ensurePermissionsLoaded()])
        }
    }

    next()
})

export default router
