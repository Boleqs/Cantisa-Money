<script setup>
import Sidebar from './components/sidebar/Sidebar.vue'
import { sidebarWidth } from './components/sidebar/state'
import Topbar from "@/components/topbar/Topbar.vue";
import TopRightDisplay from "@/components/TopRightDisplay.vue";
import {ref, useTemplateRef} from "vue";

const topRightDisplayRef = useTemplateRef("showDiv")
const msgType = ref('info')
const msgContent = ref()
const showFullPage = ref(false)

async function showEvent (payload) {
  msgType.value = payload.type
  msgContent.value = payload.content
  topRightDisplayRef.value.showDiv()
}

async function FullPage (payload) {
  console.log(payload.value)
  showFullPage.value = payload.value
}
</script>

<template>
  <div class="app-root" v-if="!showFullPage">
    <!-- Sidebar fixe à gauche -->
    <Sidebar />
    <Topbar />
    <!-- Contenu principal, décalé grâce au padding-left -->
    <div class="app-main" :style="{ paddingLeft: sidebarWidth }">
      <main class="app-content">
        <TopRightDisplay :p-type="msgType" ref="showDiv">{{msgContent}}</TopRightDisplay>
        <!-- TODO: transition 5s pour correspondre avec la sidebar -->
        <router-view @msg-event="showEvent" @fullpage="FullPage" />
      </main>
    </div>
  </div>
  <div v-else><router-view @msg-event="showEvent"/></div>
</template>

<style>
html, body, #app {
  height: 100%;
  margin: 0;
}

/* important pour que le padding n'entraîne pas de débordement */
*, *::before, *::after {
  box-sizing: border-box;
}

.app-root {
  height: 100vh;
  overflow: hidden; /* pas de scroll horizontal global */
}

/* conteneur du contenu (hors sidebar) */
.app-main {
  height: 100%;
  display: flex;
  flex-direction: column;
  transition: padding-left 0.5s;
}

/* zone où s’affichent tes pages (avec le graphique etc.) */
.app-content {
  flex: 1;
  overflow: auto;
  padding: 16px;
}
</style>