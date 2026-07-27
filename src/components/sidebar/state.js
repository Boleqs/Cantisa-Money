import { ref, computed, watch } from 'vue'

const STORAGE_KEY = 'cmm_sidebar_collapsed'

function readStored() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored !== null) return stored === 'true'
  } catch { /* localStorage indisponible : on retombe sur la détection de largeur ci-dessous */ }
  // Pas de préférence explicite encore enregistrée : sur un écran étroit (tablette/mobile), la
  // sidebar dépliée (180px) mange une part disproportionnée de la largeur utile — repliée par
  // défaut dans ce cas plutôt que dépliée comme sur desktop (audit UX du 2026-07-27 : aucun
  // breakpoint responsive sur la sidebar).
  try { return window.matchMedia('(max-width: 900px)').matches } catch { return false }
}

export const collapsed = ref(readStored())

export const toggleSidebar = () => (collapsed.value = !collapsed.value)

// Persist toute modification
watch(collapsed, v => {
  try { localStorage.setItem(STORAGE_KEY, String(v)) } catch {}
})

export const SIDEBAR_WIDTH = 180
export const SIDEBAR_WIDTH_COLLAPSED = 70
export const sidebarWidth = computed(
  () => `${collapsed.value ? SIDEBAR_WIDTH_COLLAPSED : SIDEBAR_WIDTH}px`
)
