<script setup>
import { collapsed } from './state'

const props = defineProps({
  label: {
    type: String,
    required: true
  }
})
</script>

<template>
  <div class="sidebar-section" :class="{ collapsed }">
    <!-- on cache le texte quand c'est collapsé, mais on garde la hauteur -->
    <span v-if="!collapsed" class="sidebar-section__label">
      {{ label }}
    </span>
  </div>
</template>

<style scoped>
.sidebar-section {
  padding: 12px 18px 4px 6px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: rgba(255, 255, 255, 0.5);
}

/* quand la sidebar est repliée, on réduit un peu le padding pour juste un petit espace */
.sidebar-section.collapsed {
  padding: 8px 0 4px 0;
}
</style>