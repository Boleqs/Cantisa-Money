<script>
import { computed } from 'vue';
import SidebarLink from './SidebarLink.vue';
import SidebarGroup from './SidebarGroup.vue';
import SidebarSectionTitle from './SidebarSectionTitle.vue';
import { collapsed, toggleSidebar, sidebarWidth } from './state';
import Settings from '../modal/settings.vue';
import MyAccount from '../modal/MyAccount.vue';
import { hasPermission } from '@/utils/permissions.js';
import {
    faHouse, faGaugeHigh, faBuildingColumns, faListUl, faRightLeft, faFileImport,
    faCheckDouble, faArrowsRotate, faHandHoldingDollar, faFileInvoiceDollar, faChartPie,
    faSackDollar, faChartLine, faLayerGroup, faChartColumn, faMagnifyingGlassChart, faEye,
    faSatelliteDish, faScaleBalanced, faCalculator, faFileContract, faPeopleRoof,
    faFolderOpen, faChartBar, faGear, faBook, faFolderTree, faTag,
    faUserShield, faUsers, faUserLock, faDatabase, faChartArea
} from '@fortawesome/free-solid-svg-icons';

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
        return {
            collapsed, toggleSidebar, sidebarWidth, hasPermission, isAdmin,
            faHouse, faGaugeHigh, faBuildingColumns, faListUl, faRightLeft, faFileImport,
            faCheckDouble, faArrowsRotate, faHandHoldingDollar, faFileInvoiceDollar, faChartPie,
            faSackDollar, faChartLine, faLayerGroup, faChartColumn, faMagnifyingGlassChart, faEye,
            faSatelliteDish, faScaleBalanced, faCalculator, faFileContract, faPeopleRoof,
            faFolderOpen, faChartBar, faGear, faBook, faFolderTree, faTag,
            faUserShield, faUsers, faUserLock, faDatabase, faChartArea
        }
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
            <SidebarLink to="/" :icon="faHouse">Accueil</SidebarLink>

            <template v-if="hasPermission('Comptabilité') || hasPermission('Pilotage') || hasPermission('Planification') || hasPermission('Crédits')">
              <SidebarSectionTitle label="Gestion bancaire"/>
              <SidebarLink v-if="hasPermission('Pilotage')" to="/Dashboard" :icon="faGaugeHigh">Dashboard</SidebarLink>
              <SidebarGroup v-if="hasPermission('Comptabilité')" label="Comptes Bancaires" :icon="faBuildingColumns" :paths="['/accounts', '/transactions', '/import']">
                <SidebarLink to="/accounts" :icon="faListUl">Liste des comptes</SidebarLink>
                <SidebarLink to="/transactions" :icon="faRightLeft">Transactions</SidebarLink>
                <SidebarLink to="/import" :icon="faFileImport">Importer</SidebarLink>
              </SidebarGroup>
              <SidebarLink v-if="hasPermission('Comptabilité')" to="/reconcile" :icon="faCheckDouble">Rapprochement</SidebarLink>
              <SidebarLink v-if="hasPermission('Planification')" to="/subscriptions" :icon="faArrowsRotate">Abonnements</SidebarLink>
              <SidebarLink v-if="hasPermission('Crédits')" to="/credits" :icon="faHandHoldingDollar">Crédits</SidebarLink>
              <SidebarLink to="/invoices" :icon="faFileInvoiceDollar">Factures</SidebarLink>
              <SidebarLink v-if="hasPermission('Planification')" to="/budgets" :icon="faChartPie">Budgets</SidebarLink>
            </template>

            <template v-if="hasPermission('Patrimoine')">
              <SidebarSectionTitle label="Gestion financière"/>
              <SidebarLink to="/patrimoine" :icon="faSackDollar">Vue d'ensemble</SidebarLink>
              <SidebarLink to="/patrimoine/prediction" :icon="faChartArea">Prédiction</SidebarLink>
              <SidebarGroup label="Portfolio" :icon="faChartLine" :paths="['/portfolio']">
                <SidebarLink to="/portfolio" :icon="faLayerGroup">Liste des actifs</SidebarLink>
              </SidebarGroup>
              <SidebarGroup label="Marchés" :icon="faChartColumn" :paths="['/markets/analyse', '/markets/watchlist', '/markets/scan']">
                <SidebarLink to="/markets/analyse" :icon="faMagnifyingGlassChart">Analyse fondamentale</SidebarLink>
                <SidebarLink to="/markets/watchlist" :icon="faEye">Watchlist</SidebarLink>
                <SidebarLink to="/markets/scan" :icon="faSatelliteDish">Scanner</SidebarLink>
              </SidebarGroup>
            </template>

            <template v-if="hasPermission('Fiscalité')">
              <SidebarSectionTitle label="Gestion Fiscale"/>
              <SidebarLink to="/fiscalite" :icon="faScaleBalanced">Vue d'ensemble</SidebarLink>
              <SidebarLink to="/fiscalite/simulateur" :icon="faCalculator">Simulateur d'impôt</SidebarLink>
              <SidebarLink to="/fiscalite/regime" :icon="faFileContract">Régime fiscal</SidebarLink>
              <SidebarLink to="/fiscalite/foyer" :icon="faPeopleRoof">Foyer fiscal</SidebarLink>
              <SidebarLink to="/fiscalite/dossier" :icon="faFolderOpen">Dossier fiscal</SidebarLink>
            </template>

            <template v-if="hasPermission('Pilotage')">
              <SidebarSectionTitle label="Reporting"/>
              <SidebarLink to="/reports" :icon="faChartBar">Rapports prédéfinis</SidebarLink>
            </template>

            <template v-if="hasPermission('Réglages personnels')">
              <SidebarSectionTitle label="Paramètres"/>
              <SidebarLink to="/parametres" :icon="faGear">Paramétrage</SidebarLink>
            </template>

            <SidebarGroup v-if="hasPermission('Comptabilité')" label="Référentiels" :icon="faBook" :paths="['/categories', '/tags']">
              <SidebarLink to="/categories" :icon="faFolderTree">Catégories</SidebarLink>
              <SidebarLink to="/tags" :icon="faTag">Tags</SidebarLink>
            </SidebarGroup>
            <SidebarGroup v-if="isAdmin" label="Administration" :icon="faUserShield" :paths="['/admin/users', '/admin/roles', '/admin/backup']">
              <SidebarLink :icon="faUsers" to="/admin/users">Utilisateurs</SidebarLink>
              <SidebarLink :icon="faUserLock" to="/admin/roles">Rôles &amp; Permissions</SidebarLink>
              <SidebarLink :icon="faDatabase" to="/admin/backup">Sauvegarde</SidebarLink>
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