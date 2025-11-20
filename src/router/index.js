import { createRouter, createWebHistory } from 'vue-router'
import axios from 'axios'
//import createRouter from 'vue-router'
//import createWebHistory from 'vue-router'

axios.defaults.withCredentials = true
axios.defaults.baseURL = 'http://localhost:5000'

const routes = [
    {
        path: '/',
        name: 'Home',
        component: () => import('../views/Home.vue')
    },
    {
        path: '/Dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
        meta: { requiresAuth: true }
    },
    {
        path: '/Accounts',
        name: 'Accounts',
        component: () => import('../views/Accounts.vue')
    },
    {
        path: '/login',
        name: 'Login',
        component: () => import('../views/Login.vue')
    }

]


const router = createRouter({
    history: createWebHistory(),
    routes
  })

router.beforeEach(async (to, from, next) => {
  if (!to.meta.requiresAuth) {
    return next()
  }

  try {
    // demande à Flask : "est-ce que l'utilisateur est connecté ?"
    await axios.get('http://localhost:5000/api/auth/check-auth', {
      withCredentials: true
    })
    // si Flask ne renvoie PAS d'erreur → OK
    next()

  } catch (err) {
    // si Flask renvoie erreur → pas connecté
    next('/login')
  }
})

  export default router