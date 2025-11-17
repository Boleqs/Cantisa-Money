import { createRouter, createWebHistory } from 'vue-router'
//import createRouter from 'vue-router'
//import createWebHistory from 'vue-router'

const routes = [
    {
        path: '/',
        name: 'Home',
        component: () => import('../views/Home.vue')
    },
    {
        path: '/Dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue')
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
  
  export default router