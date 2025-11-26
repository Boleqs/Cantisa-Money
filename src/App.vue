<script setup>
import Sidebar from './components/sidebar/Sidebar.vue'
import { sidebarWidth } from './components/sidebar/state'
import Topbar from "@/components/topbar/Topbar.vue";
import TopRightDisplay from "@/components/TopRightDisplay.vue";
import {ref, useTemplateRef} from "vue";

const topRightDisplayRef = useTemplateRef("showDiv")
const msgType = ref('info')
const msgContent = ref()

async function showEvent (payload) {
  msgType.value = payload.type
  msgContent.value = payload.content
  topRightDisplayRef.value.showDiv()
}
</script>

<template>
  <Topbar/>
  <div class="smooch" :style="{ 'margin-left': sidebarWidth}">
    <TopRightDisplay :p-type="msgType" ref="showDiv">{{msgContent}}</TopRightDisplay>
    <router-view @msg-event="showEvent" />
  </div>
  <Sidebar />
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