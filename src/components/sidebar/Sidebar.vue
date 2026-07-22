<script>
import { computed } from 'vue';
import SidebarLink from './SidebarLink.vue';
import SidebarGroup from './SidebarGroup.vue';
import SidebarSectionTitle from './SidebarSectionTitle.vue';
import { collapsed, toggleSidebar, sidebarWidth } from './state';
import Settings from '../modal/settings.vue';
import MyAccount from '../modal/MyAccount.vue';
import { hasPermission } from '@/utils/permissions.js';

export default {
    props: {},
    components: { SidebarGroup, SidebarLink, SidebarSectionTitle, Settings, MyAccount },
    data() {
        return {
            showMyAccount: false,
            showSettings: false,
        };
    },
    methods: {
        openSettings() {
            if (!this.showMyAccount) {
            this.showSettings = true;
            }
        },
        openMyAccount() {
            this.showMyAccount = true;
        }
    },
    setup() {
        const isAdmin = computed(() => hasPermission('Delete users'))
        return { collapsed, toggleSidebar, sidebarWidth, hasPermission, isAdmin }
    }
}

</script>

<template>
    <div class="sidebar" :style="{ width: sidebarWidth}">
        <h1>
            <span class="sidebar-title" :class="{ schmall: collapsed, bwig: !collapsed }">CMM</span>
        </h1>

        <!-- Zone scrollable des liens -->
        <div class="sidebar-nav">
            <SidebarLink to="/" iconFile="Accueil.png">Accueil</SidebarLink>

            <template v-if="hasPermission('Comptabilité') || hasPermission('Pilotage') || hasPermission('Planification') || hasPermission('Crédits')">
              <SidebarSectionTitle label="Gestion bancaire"/>
              <SidebarLink v-if="hasPermission('Pilotage')" to="/Dashboard">Dashboard</SidebarLink>
              <SidebarGroup v-if="hasPermission('Comptabilité')" label="Comptes Bancaires" :paths="['/accounts', '/transactions', '/import']">
                <SidebarLink to="/accounts">Liste des comptes</SidebarLink>
                <SidebarLink to="/transactions">Transactions</SidebarLink>
                <SidebarLink to="/import">Importer</SidebarLink>
              </SidebarGroup>
              <SidebarLink v-if="hasPermission('Comptabilité')" to="/reconcile">Rapprochement</SidebarLink>
              <SidebarLink v-if="hasPermission('Planification')" to="/subscriptions">Abonnements</SidebarLink>
              <SidebarLink v-if="hasPermission('Crédits')" to="/credits">Crédits</SidebarLink>
              <SidebarLink to="/invoices">Factures</SidebarLink>
              <SidebarLink v-if="hasPermission('Planification')" to="/budgets">Budgets</SidebarLink>
            </template>

            <template v-if="hasPermission('Patrimoine')">
              <SidebarSectionTitle label="Gestion financière"/>
              <SidebarLink to="/patrimoine">Vue d'ensemble</SidebarLink>
              <SidebarGroup label="Portfolio" :paths="['/portfolio']">
                <SidebarLink to="/portfolio">Liste des actifs</SidebarLink>
              </SidebarGroup>
              <SidebarGroup label="Marchés" :paths="['/markets/analyse', '/markets/watchlist', '/markets/scan']">
                <SidebarLink to="/markets/analyse">Analyse fondamentale</SidebarLink>
                <SidebarLink to="/markets/watchlist">Watchlist</SidebarLink>
                <SidebarLink to="/markets/scan">Scanner</SidebarLink>
              </SidebarGroup>
            </template>

            <template v-if="hasPermission('Pilotage')">
              <SidebarSectionTitle label="Reporting"/>
              <SidebarLink to="/reports">Rapports prédéfinis</SidebarLink>
            </template>

            <template v-if="hasPermission('Réglages personnels')">
              <SidebarSectionTitle label="Paramètres"/>
              <SidebarLink to="/parametres">Paramétrage</SidebarLink>
            </template>

            <SidebarGroup v-if="hasPermission('Comptabilité')" label="Référentiels" :paths="['/categories', '/tags']">
              <SidebarLink to="/categories">Catégories</SidebarLink>
              <SidebarLink to="/tags">Tags</SidebarLink>
            </SidebarGroup>
            <SidebarGroup v-if="isAdmin" label="Administration" :paths="['/admin/users', '/admin/roles']">
              <SidebarLink icon-file="Users.png" to="/admin/users">Utilisateurs</SidebarLink>
              <SidebarLink to="/admin/roles">Rôles &amp; Permissions</SidebarLink>
            </SidebarGroup>
        </div>

        <!-- Barre d'icônes du bas, toujours visible -->
        <div class="sidebar-footer" :class="{ collapsed }">
            <span class="collapse-icon" @click="toggleSidebar">
                <img class="collapse-icon-img" :class="{ 'collapse-icon-img collapsed': collapsed}" src="../icons/double_fleche.png"></img>
            </span>
            <span>
                <img
                    class="icon_account"
                    :class="{'logo disabled': showMyAccount || showSettings}"
                    src="../icons/Users.png"
                    @click="openMyAccount"
                />
                <MyAccount v-if="showMyAccount" @close="showMyAccount = false"/>
            </span>
            <span>
                <img
                    class="parameter"
                    :class="{'logo disabled': showMyAccount || showSettings}"
                    src="../icons/Cog.png"
                    @click="openSettings"
                />
                <Settings v-if="showSettings" @close="showSettings = false"/>
            </span>
        </div>
    </div>
</template>


<style>
:root {
    --sidebar-bg-color: #1a4396;
    --sidebar-item-hover: #3873e7;
    --sidebar-item-active: #7896d2;
}
</style>

<style scoped>
.sidebar {
    color: white;
    background-color: var(--sidebar-bg-color);

    position: fixed;
    z-index: 1;
    top: 0;
    left: 0;
    bottom: 0;
    padding: 0.5em;

    transition: 0.5s ease;

    display: flex;
    flex-direction: column;
}

.sidebar-nav {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-width: thin;
    scrollbar-color: rgba(255,255,255,0.2) transparent;
}

.sidebar-footer {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: 0.5em;
    padding: 0.5em 0.25em;
    border-top: 1px solid rgba(255,255,255,0.15);
    margin-top: 0.5em;
}

/* Repliée : les 3 icônes ne tiennent plus sur une ligne (70px de large) — on les empile
   verticalement plutôt que de les laisser déborder du cadre. */
.sidebar-footer.collapsed {
    flex-direction: column;
    gap: 0.3em;
    padding: 0.4em 0;
}

.sidebar-title {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 100%;
    height: 100px;
    flex-shrink: 0;
}

.collapse-icon {
    cursor: pointer;
    padding: 0.5em;
    color: rgba(255, 255, 255, 0.7);
    display: flex;
    align-items: center;
}

.collapse-icon-img {
    width: 25px;
    height: 25px;
    rotate: 180deg;
    transition: 0.5s ease;
}

.collapse-icon-img.collapsed {
    rotate: 0deg;
    transition: 0.5s ease;
}

.parameter {
    cursor: pointer;
    padding: 0.25em;
    width: 36px;
    transition: 0.3s ease-in-out;
}

.logo.disabled {
    cursor: default;
}

.icon_account {
    cursor: pointer;
    padding: 0.25em;
    width: 36px;
    transition: 0.3s ease-in-out;
}

.schmall {
    font-size: 0.50em;
    transition: 0.3s ease;
}
.bwig {
    font-size: 1.10em;
    transition: 0.3s ease;
}
</style>