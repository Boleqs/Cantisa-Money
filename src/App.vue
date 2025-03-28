<script>
import Sidebar from './components/sidebar/Sidebar.vue'
import { sidebarWidth } from './components/sidebar/state'
export default {
  components: { Sidebar },
  setup() {
    return { sidebarWidth }
  }
}
</script>
<template>
  <Sidebar />
  <div class="smooch" :style="{ 'margin-left': sidebarWidth }">
    <router-view />
  </div>
</template>

<style>
.smooch {
  transition: margin-left 0.5s;
}

</style>