<script>
import SidebarLink from './SidebarLink.vue';
import { collapsed, toggleSidebar, sidebarWidth } from './state';
import Settings from '../modal/settings.vue';
import MyAccount from '../modal/MyAccount.vue'; 

export default {
    props: {},
    components: { SidebarLink, Settings, MyAccount },
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
        return { collapsed, toggleSidebar, sidebarWidth }
    }
}

</script>

<template>
    <div class="sidebar" :style="{ width: sidebarWidth}">
        <h1>
            <span class="sidebar-title" :class="{ schmall: collapsed, bwig: !collapsed }">CMM</span>
        </h1>
        <br>
        <SidebarLink to="/" iconFile="Accueil.png">Accueil</SidebarLink>        
        <br>
        <SidebarLink to="/Dashboard" iconFile="Dashboard.png">Dashboard</SidebarLink>
        <br>
        <SidebarLink to="/Accounts" iconFile="Accounts.png">Accounts</SidebarLink>
        <br>
        <SidebarLink to="/Assets" iconFile="Assets.png">Assets</SidebarLink>
        <br>
        <SidebarLink to="/Budgets" iconFile="Budgets.png">Budgets</SidebarLink>
        <br>
        <SidebarLink to="/Categories" iconFile="Categories.png">Categories</SidebarLink>
        <br>
        <SidebarLink to="/Commodities" iconFile="Commodities.png">Commodities</SidebarLink>
        <br>
        <SidebarLink to="/Splits" iconFile="Splits.png">Splits</SidebarLink>
        <br>
        <SidebarLink to="/Subscriptions" iconFile="Subscriptions.png">Subscriptions</SidebarLink>
        <br>
        <SidebarLink to="/Tags" iconFile="Tags.png">Tags</SidebarLink>
        <br>
        <SidebarLink to="/Transactions" iconFile="Transactions.png">Transactions</SidebarLink>
        <br>
        <SidebarLink to="/Users" iconFile="Users.png">Users</SidebarLink>
        <span>
            <span class="collapse-icon" @click="toggleSidebar">
                <img class="collapse-icon-img" :class="{ 'collapse-icon-img collapsed': collapsed}" src="../icons/double_fleche.png"></img>
            </span>
            <span>
                <img 
                    class="icon_account" 
                    :class="{'icon_account collapsed': collapsed, 'logo disabled': showMyAccount || showSettings}" 
                    src="../icons/Users.png" 
                    @click="openMyAccount"
                />
                <MyAccount v-if="showMyAccount" @close="showMyAccount = false"/>
            </span>
            <span>
                <img 
                    class="parameter" 
                    :class="{'parameter collapsed': collapsed, 'logo disabled': showMyAccount || showSettings}" 
                    src="../icons/Cog.png" 
                    @click="openSettings"
                />
                <Settings v-if="showSettings" @close="showSettings = false"/>
            </span>
        </span>
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

    float: left;
    position: fixed;
    z-index: 0;
    top: 0;
    left: 0;
    bottom: 0;
    padding: 0.5em;

    transition: 0.5s ease;

    display: flex;
    flex-direction: column;
}

.sidebar-title {
    display: flex;
    justify-content: center; /* Center horizontally */
    align-items: center; /* Center vertically */
    width: 100%;
    height: 100px; /* Adjust the height as needed */
}
.collapse-icon {
    cursor: pointer;
    position: absolute;
    bottom: 0;
    padding: 1em;
    color: rgba(255, 255, 255, 0.7);
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
    position: absolute;
    bottom: 0.75em;
    left: 8em;
    padding: 0.5em;
    width: 50px;
    transition: 0.3s ease-in-out;
}
.parameter.collapsed {
    bottom: 8em;
    left: 0.8em;
}
.logo.disabled {
    cursor: default;
}
.icon_account {
    cursor: pointer;
    position: absolute;
    bottom: 0.75em;
    left: 4.25em;
    padding: 0.5em;
    width: 50px;

    transition: 0.3s ease-in-out;
}
.icon_account.collapsed {
    bottom: 4em;
    left: 0.8em;
}
.schmall {
    font-size: 0.50em; /* Adjust the size as needed */
    transition: 0.3s ease;
}
.bwig {
    font-size: 1.10em; /* Adjust the size as needed */
    transition: 0.3s ease;
}

</style>