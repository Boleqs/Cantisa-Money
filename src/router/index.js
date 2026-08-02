import { createRouter, createWebHistory } from 'vue-router'
import axios from 'axios'
import { ensureSettingsLoaded, onboardingCompleted } from '@/utils/settings.js'
import { ensurePermissionsLoaded } from '@/utils/permissions.js'

axios.defaults.withCredentials = true
// API_HOST/API_PORT/API_HTTPS (voir .env.example) : "localhost" en dur empêchait tout accès au
// backend depuis un autre appareil que celui servant le frontend (localhost désigne toujours la
// machine de l'utilisateur, pas le serveur) — voir backlog_external_hosting.
const apiProtocol = import.meta.env.API_HTTPS === 'true' ? 'https' : 'http'
const apiHost = import.meta.env.API_HOST || 'localhost'
const apiPort = import.meta.env.API_PORT || '5000'
axios.defaults.baseURL = `${apiProtocol}://${apiHost}:${apiPort}`
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
        path: '/onboarding',
        name: 'Onboarding',
        component: () => import('../views/initialization/Onboarding.vue'),
        meta: { requiresAuth: true }
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
        path: '/accounts/income-expense',
        name: 'IncomeExpenseAccounts',
        component: () => import('../views/IncomeExpenseAccounts.vue'),
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
        path: '/institutions',
        name: 'Institutions',
        component: () => import('../views/Institutions.vue'),
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
        path: '/dca',
        name: 'Dca',
        component: () => import('../views/DCA.vue'),
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
        path: '/admin/backup',
        name: 'AdminBackup',
        component: () => import('../views/AdminBackup.vue'),
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
    },
    {
        path: '/patrimoine/prediction',
        name: 'WealthForecast',
        component: () => import('../views/WealthForecast.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/fiscalite',
        name: 'FiscaliteOverview',
        component: () => import('../views/FiscaliteOverview.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/fiscalite/simulateur',
        name: 'FiscaliteSimulateur',
        component: () => import('../views/FiscaliteSimulateur.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/fiscalite/regime',
        name: 'FiscaliteRegime',
        component: () => import('../views/FiscaliteRegime.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/fiscalite/foyer',
        name: 'FiscaliteFoyer',
        component: () => import('../views/FiscaliteFoyer.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/fiscalite/dossier',
        name: 'FiscaliteDossier',
        component: () => import('../views/FiscaliteDossier.vue'),
        meta: { requiresAuth: true }
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

function getCookie(name) {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
    return match ? decodeURIComponent(match[2]) : null
}

// Rafraîchissement automatique de l'access token (1h de durée de vie) via le refresh token (24h) —
// jusqu'ici POST /api/auth/refresh existait côté backend mais n'était jamais appelé par le
// frontend, donc toute requête après 1h échouait en 401 et redirigeait vers /Signin même avec un
// refresh token encore valide. Intercepteur global plutôt qu'un correctif ciblé sur checkAuth() :
// une requête API en pleine session (pas seulement à la navigation) peut tout aussi bien tomber
// sur un access token expiré.
let refreshPromise = null

function requestRefresh() {
    if (!refreshPromise) {
        // Le refresh token a son PROPRE cookie CSRF (csrf_refresh_token), distinct de celui de
        // l'access token (csrf_access_token) qu'axios envoie par défaut sur toute autre requête
        // (voir xsrfCookieName ci-dessus) — sans ce header explicite, flask-jwt-extended rejette
        // l'appel en 401 "CSRF double submit tokens do not match" avant même de vérifier le token.
        refreshPromise = axios.post('/api/auth/refresh', {}, {
            headers: { 'X-CSRF-TOKEN': getCookie('csrf_refresh_token') },
        }).finally(() => { refreshPromise = null })
    }
    return refreshPromise
}

const AUTH_PATHS_EXCLUDED_FROM_REFRESH = ['/auth/refresh', '/auth/login', '/auth/signup']

axios.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config
        const status = error.response?.status
        const url = originalRequest?.url || ''
        const isExcluded = AUTH_PATHS_EXCLUDED_FROM_REFRESH.some((p) => url.includes(p))

        if (status === 401 && !isExcluded && !originalRequest._retry) {
            originalRequest._retry = true
            try {
                await requestRefresh()
                return axios(originalRequest)
            } catch (refreshError) {
                // Refresh token lui-même expiré (>24h) ou absent : session réellement terminée,
                // pas seulement l'access token. Redirige même si l'appel qui a échoué ne vient pas
                // de la navigation (ex: action déclenchée en pleine session), sinon l'utilisateur
                // resterait bloqué sur une page dont plus aucun appel API ne peut aboutir.
                router.push('/Signin')
                return Promise.reject(refreshError)
            }
        }
        return Promise.reject(error)
    }
)

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

            // Assistant de premier login : tant qu'un utilisateur n'a pas le minimum (devise +
            // au moins un compte), on le bloque sur /onboarding avant d'accéder au reste de l'app.
            if (!onboardingCompleted.value && to.name !== 'Onboarding') {
                return next('/onboarding')
            }
            if (onboardingCompleted.value && to.name === 'Onboarding') {
                return next('/Dashboard')
            }
        }
    }

    next()
})

export default router
