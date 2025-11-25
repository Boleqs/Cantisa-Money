<script>
import Sidebar from './components/sidebar/Sidebar.vue'
import { sidebarWidth } from './components/sidebar/state'
import Topbar from "@/components/topbar/Topbar.vue";
import TopRightDisplay from "@/components/TopRightDisplay.vue";
export default {
  components: {TopRightDisplay, Topbar, Sidebar },
  setup() {
    return { sidebarWidth }
  }
}
</script>
<template>
  <Sidebar />
  <Topbar/>
  <div class="smooch" :style="{ 'margin-left': sidebarWidth}">
    <div v-show=false><TopRightDisplay p-type="error">Maud pète !!!</TopRightDisplay></div>
    <router-view />
  </div>
</template>

<style>
.smooch {
  position: fixed;
  transition: margin-left 0.5s;
  background: #051122;
  box-sizing: border-box;
  height: 100%;
  width: 100%;
}
</style>