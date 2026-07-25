<script>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { collapsed } from './state'

export default {
  name: 'SidebarGroup',
  props: {
    label: { type: String, required: true },
    icon: { type: [Object, Array], default: null },
    paths: { type: Array, default: () => [] },
  },
  setup (props) {
    const route = useRoute()

    const isChildActive = (path) => props.paths.includes(path)
    const isOpen = ref(isChildActive(route.path))

    // Auto-ouvrir quand on navigue vers une route du groupe
    watch(() => route.path, (path) => {
      if (isChildActive(path)) isOpen.value = true
    })

    const toggleOpen = () => {
      isOpen.value = !isOpen.value
    }

    return {
      collapsed,
      isOpen,
      toggleOpen
    }
  }
}
</script>

<template>
  <div class="sidebar-group" :class="{ collapsed }">
    <!-- Barre de titre / séparateur -->
    <div class="sidebar-group-header" @click="toggleOpen">
      <div class="left">
        <font-awesome-icon v-if="icon" class="icon" :icon="icon" fixed-width />
        <span v-if="!collapsed" class="label">{{ label }}</span>
      </div>
      <span v-if="!collapsed" class="chevron">
        <!-- petit indicateur d'ouverture/fermeture -->
        {{ isOpen ? '⮟' : '⮞' }}
      </span>
    </div>

    <!-- Liens enfants -->
    <transition name="collapse">
      <div
        v-show="isOpen && !collapsed"
        class="sidebar-group-children"
      >
        <slot />
      </div>
    </transition>
  </div>
</template>

<style scoped>
.sidebar-group {
  margin-top: 0em;
}

/* Ligne de titre — même apparence que les liens simples (SidebarLink) */
.sidebar-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
  margin: 0.7em 0;
  padding: 0.4em;
  border-radius: 0.25em;
  font-weight: 400;
  color: white;
  transition: 0.4s ease;
}

.sidebar-group-header:hover {
  background-color: var(--sidebar-item-hover);
  padding: 1em;
}

.left {
  display: flex;
  align-items: center;
  gap: 0.5em;
}

.icon {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  margin-right: 5px;
}

.label {
  white-space: nowrap;
}
/* Chevron ('⮟' : '⮞') size */
.chevron {
  font-size: 0.7em;
  margin-left: 5px;
}

/* conteneur des liens enfants */
.sidebar-group-children {
  display: flex;
  flex-direction: column;
  margin-left: 15px;
}

/* petite anim de collapse vertical */
.collapse-enter-active,
.collapse-leave-active {
  transition: max-height 0.2s ease, opacity 0.2s ease;
}
.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
}
.collapse-enter-to,
.collapse-leave-from {
  max-height: 500px;
  opacity: 1;
}

/* quand la sidebar entière est collapsée */
.sidebar-group.collapsed .sidebar-group-header {
  justify-content: center;
  padding-left: 0.2em;
  padding-right: 0.6em;
}
</style>