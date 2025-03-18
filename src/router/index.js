import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'

const routes = [
    {
        path: '/',
        name: 'Home',
        component: Home
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
        path: '/Assets',
        name: 'Assets',
        component: () => import('../views/Assets.vue')
    },
    {
        path: '/Budgets',
        name: 'Budgets',
        component: () => import('../views/Budgets.vue')
    },
    {
        path: '/Categories',
        name: 'Categories',
        component: () => import('../views/Categories.vue')
    },
    {
        path: '/Commodities',
        name: 'Commodities',
        component: () => import('../views/Commodities.vue')
    },
    {
        path: '/Splits',
        name: 'Splits',
        component: () => import('../views/Splits.vue')
    },
    {
        path: '/Subscriptions',
        name: 'Subscriptions',
        component: () => import('../views/Subscriptions.vue')
    },
    {
        path: '/Tags',
        name: 'Tags',
        component: () => import('../views/Tags.vue')
    },
    {
        path: '/Transactions',
        name: 'Transactions',
        component: () => import('../views/Transactions.vue')
    },
    {  
        path: '/Users',
        name: 'Users',
        component: () => import('../views/Users.vue')
    },


]

const router = createRouter({
    history: createWebHistory(),
    routes
  })
  
  export default router