import { ref, computed, watch } from 'vue'

const STORAGE_KEY = 'cmm_sidebar_collapsed'

function readStored() {
  try { return localStorage.getItem(STORAGE_KEY) === 'true' } catch { return false }
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
