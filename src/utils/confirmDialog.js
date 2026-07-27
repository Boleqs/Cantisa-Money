import { reactive } from 'vue'

// Remplace window.confirm() par un modal stylé cohérent avec le reste de l'app (audit UX du
// 2026-07-27 : 21 occurrences de confirm() natif dans 15 fichiers, boîte système non brandée,
// bloquante, texte non stylable — problématique en particulier pour les suppressions
// irréversibles). Usage : `if (!(await confirmDialog({ message: '...' }))) return`.
const state = reactive({
  open: false,
  title: '',
  message: '',
  confirmLabel: 'Confirmer',
  cancelLabel: 'Annuler',
  danger: false,
  resolve: null,
})

export function confirmDialog({
  title = 'Confirmer',
  message,
  confirmLabel = 'Confirmer',
  cancelLabel = 'Annuler',
  danger = false,
} = {}) {
  return new Promise((resolve) => {
    // Si un dialogue était déjà ouvert (ne devrait pas arriver, un seul à la fois), on le résout
    // en "annulé" plutôt que de perdre silencieusement sa promesse en attente.
    if (state.resolve) state.resolve(false)
    state.title = title
    state.message = message
    state.confirmLabel = confirmLabel
    state.cancelLabel = cancelLabel
    state.danger = danger
    state.resolve = resolve
    state.open = true
  })
}

export function useConfirmDialogState() {
  return state
}

export function resolveConfirmDialog(value) {
  state.open = false
  if (state.resolve) {
    state.resolve(value)
    state.resolve = null
  }
}
