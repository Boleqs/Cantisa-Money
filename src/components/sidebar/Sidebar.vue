<script>
import SidebarLink from './SidebarLink.vue';
import { collapsed, toggleSidebar, sidebarWidth } from './state';
export default {
    props: {},
    components: { SidebarLink },
    setup() {
        return { collapsed, toggleSidebar, sidebarWidth }
    }
}</script>

<template>
    <div class="sidebar" :style ="{ width: sidebarWidth}">
        <img src="@/assets/home.png" alt="Cantisa Logo" width="50" height="50">
        <h1>
            <span :class="{ schmall: collapsed, bwig: !collapsed }">Cantisa</span>
        </h1>
        <br>
        <SidebarLink to="/" icon="A"> Accueil</SidebarLink>
        <br>
        
        <SidebarLink to="/Dashboard" icon="DA"> Dashboard</SidebarLink>
        <br>

        <SidebarLink to="/Accounts" icon="AC"> Accounts</SidebarLink>
        <br>

        <SidebarLink to="/Assets" icon="AS"> Assets</SidebarLink>
        <br>

        <SidebarLink to="/Budgets" icon="BU"> Budgets</SidebarLink>
        <br>

        <SidebarLink to="/Categories" icon="CA"> Categories</SidebarLink>
        <br>

        <SidebarLink to="/Commodities" icon="CO"> Commodities</SidebarLink>
        <br>

        <SidebarLink to="/Splits" icon="SP"> Splits</SidebarLink>
        <br>

        <SidebarLink to="/Subscriptions" icon="SU"> Subscriptions</SidebarLink>
        <br>

        <SidebarLink to="/Tags" icon="TA"> Tags</SidebarLink>
        <br>

        <SidebarLink to="/Transactions" icon="TR"> Transactions</SidebarLink>
        <br>

        <SidebarLink to="/Users" icon="US"> Users</SidebarLink>



        <span 
            class="collapse-icon" 
            :class="{ 'rotate-180': collapsed}"
            @click="toggleSidebar"
        >
            <p><<</p>
        </span>
    </div>
</template>


<style>
:root {
    --sidebar-bg-color: #2f855a;
    --sidebar-item-hover: #38a169;
    --sidebar-item-active: #2f855a;
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

    transition: 0.3s ease;

    display: flex;
    flex-direction: column;
}

.collapse-icon {
    cursor: pointer;
    position: absolute;
    bottom: 0;
    padding: 0.75em;

    color: rgba(255, 255, 255, 0.7);

    transition: 0.2s linear;
}

.rotate-180 {
    transform: rotate(180deg);
    transition: 0.2 linear;
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