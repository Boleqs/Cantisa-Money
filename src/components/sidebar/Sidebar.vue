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
    <div class="sidebar" :style="{ width: sidebarWidth}">
        <h1>
            <span class="sidebar-title" :class="{ schmall: collapsed, bwig: !collapsed }">Cantisa</span>
        </h1>
        <br>
        <SidebarLink to="/" iconUrl="https://cdn-icons-png.flaticon.com/512/1239/1239292.png">Accueil</SidebarLink>        
        <br>
        <SidebarLink to="/Dashboard" iconUrl="https://png.pngtree.com/png-vector/20230302/ourmid/pngtree-dashboard-line-icon-vector-png-image_6626604.png"> Dashboard</SidebarLink>
        <br>
        <SidebarLink to="/Accounts" iconUrl="https://pngimg.com/uploads/bank/bank_PNG13.png"> Accounts</SidebarLink>
        <br>
        <SidebarLink to="/Assets" iconUrl="https://png.pngtree.com/png-vector/20230326/ourmid/pngtree-asset-investment-icon-transparent-background-vector-png-image_6669561.png"> Assets</SidebarLink>
        <br>
        <SidebarLink to="/Budgets" iconUrl="https://png.pngtree.com/png-vector/20230225/ourmid/pngtree-budget-line-icon-png-image_6620500.png"> Budgets</SidebarLink>
        <br>
        <SidebarLink to="/Categories" iconUrl="https://cdn-icons-png.flaticon.com/512/2603/2603910.png"> Categories</SidebarLink>
        <br>
        <SidebarLink to="/Commodities" iconUrl="https://static.thenounproject.com/png/3961988-200.png"> Commodities</SidebarLink>
        <br>
        <SidebarLink to="/Splits" iconUrl="https://static.thenounproject.com/png/6624742-200.png"> Splits</SidebarLink>
        <br>
        <SidebarLink to="/Subscriptions" iconUrl="https://static.thenounproject.com/png/3967603-200.png"> Subscriptions</SidebarLink>
        <br>
        <SidebarLink to="/Tags" iconUrl="https://static.vecteezy.com/system/resources/previews/014/455/909/non_2x/illustration-of-tags-icon-on-transparent-background-free-png.png"> Tags</SidebarLink>
        <br>
        <SidebarLink to="/Transactions" iconUrl="https://cdn-icons-png.flaticon.com/512/2761/2761001.png"> Transactions</SidebarLink>
        <br>
        <SidebarLink to="/Users" iconUrl="https://cdn-icons-png.flaticon.com/512/3276/3276535.png"> Users</SidebarLink>
        <span 
            class="collapse-icon" 
            :class="{ 'rotate-180': collapsed}"
            @click="toggleSidebar"
        >
            <img class="collapse-icon-img" src="https://cdn-icons-png.flaticon.com/512/1828/1828769.png"></img>
        </span>
        <span>
            <img class="parameter" :class="{'parameter collapsed': collapsed}" src="https://cdn-icons-png.flaticon.com/512/25/25442.png"></img>
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

    transition: 0.3s ease;

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

    transition: 0.2s linear;
}

.collapse-icon-img {
    width: 25px;
    height: 25px;
}

.rotate-180 {
    transform: rotate(180deg);
    transition: 0.2 linear;
}
.parameter {
    cursor: pointer;
    position: absolute;
    bottom: 0.25em;
    right: 0.25em;
    padding: 0.5em;
    width: 50px;
    color: rgba(15, 6, 6, 0.7);

    transition: 0.2s linear;
}
.parameter.collapsed {
    bottom: 4em;
    right: 10px;
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