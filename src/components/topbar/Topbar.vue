<template>
  <header class="topbar" :style="{height: TOPBAR_HEIGHT, marginLeft: sidebarWidth}">
    <div class="topbar-left">
      <h1 class="topbar-title">Date du jour : </h1>
    </div>
    <div class="topbar-right">
      <!-- Zone d’actions : tu peux adapter -->
      <button class="topbar-btn" @click="$emit('refresh')">
        🔄 Rafraîchir
      </button>
      <button class="topbar-btn" @click="$emit('logout')">
        🚪 Déconnexion
      </button>
    </div>
  </header>
</template>

<script setup>
import { TOPBAR_HEIGHT } from './state.js'
import {sidebarWidth} from "@/components/sidebar/state.js";

</script>

<style scoped>
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 16px;
  background-color: #111827; /* fond sombre */
  color: #e5e7eb;
  border-bottom: 1px solid #1f2933;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2);
  transition: margin-left 0.5s;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.topbar-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.topbar-btn {
  border: 1px solid #374151;
  background: #111827;
  color: #e5e7eb;
  font-size: 13px;
  padding: 6px 10px;
  border-radius: 6px;
  cursor: pointer;
}
.topbar-btn:hover {
  background: #1f2937;
}
</style>