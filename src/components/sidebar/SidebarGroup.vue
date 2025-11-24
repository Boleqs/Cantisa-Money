<script>
import { ref, computed } from 'vue'
import { collapsed } from './state'

export default {
  name: 'SidebarGroup',
  props: {
    label: { type: String, required: true },
    iconFile: { type: String, default: null } // icon is optional
  },
  setup (props) {
    const isOpen = ref(false)

    const toggleOpen = () => {
      // même si la sidebar est globalement collapsée,
      // on garde quand même l’état du groupe
      isOpen.value = !isOpen.value
    }

    const iconSrc = computed(() => {
      if (!props.iconFile) return null
      return new URL(`../icons/${props.iconFile}`, import.meta.url).href
    })

    return {
      collapsed,
      isOpen,
      toggleOpen,
      iconSrc
    }
  }
}
</script>

<template>
  <div class="sidebar-group" :class="{ collapsed }">
    <!-- Barre de titre / séparateur -->
    <div class="sidebar-group-header" @click="toggleOpen">
      <div class="left">
        <img v-if="iconSrc" :src="iconSrc" class="icon" alt="" />
        <span v-if="!collapsed" class="label">{{ label }}</span>
      </div>
      <span v-if="!collapsed" class="chevron">
        <!-- petit indicateur d’ouverture/fermeture -->
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

/* Ligne de titre / séparateur */
.sidebar-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  padding: 0.4em 0.4em;
  letter-spacing: 0.05em;
  opacity: 0.85;
  border-top: 1px solid rgba(255,255,255,0.2);
  font-weight: 400;
  color: white;
}

.sidebar-group-header:hover {
  background-color: var(--sidebar-item-hover);
}

.left {
  display: flex;
  align-items: center;
  gap: 0.5em;
}

.icon {
  flex-shrink: 0;
  width: 25px;
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