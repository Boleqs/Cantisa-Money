import { createRouter, createWebHistory } from 'vue-router'
import axios from 'axios'
import {defineEmits} from "vue";
import showEventBool from "@/App.vue"
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
        path: '/Signin',
        name: 'Signin',
        component: () => import('../views/Signin.vue')
    },
    {
        path: '/init/Signup',
        name: 'Signup',
        component: () => import('../views/initialization/Signup.vue')
    },
    {
        path: '/error',
        name: 'ConnectionError',
        component: () => import('../views/ConnectionError.vue')
    },
    {
        path: '/accounts',
        name: 'Accounts',
        component: () => import('../views/Accounts.vue')
    }

]

const router = createRouter({
    history: createWebHistory(),
    routes
  })

router.beforeEach(async (to, from, next) => {
  document.title = 'CMM | ' + to.name;

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
        // si erreur network → pas de connexion à l'api
    if (err.message === 'Network Error') {
        next('/error')
    } else {
        // sinon, go to signin
        next('/Signin')
    }
  }
})


  export default router