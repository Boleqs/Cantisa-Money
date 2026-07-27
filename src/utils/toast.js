import { reactive } from 'vue'

// Singleton partagé (pas de provide/inject nécessaire) : importable depuis n'importe quel écran
// ou modal sans passer par des emits remontant jusqu'à App.vue (contrairement à l'ancien
// TopRightDisplay/msg-event, qui ne fonctionnait qu'en émettant depuis un composant routé
// directement — inutilisable depuis un modal sans re-émettre à chaque niveau).
const toasts = reactive([])
let nextId = 1

function push(type, message, duration = 4000) {
  const id = nextId++
  toasts.push({ id, type, message })
  setTimeout(() => dismiss(id), duration)
  return id
}

function dismiss(id) {
  const i = toasts.findIndex(t => t.id === id)
  if (i !== -1) toasts.splice(i, 1)
}

export function useToast() {
  return {
    toasts,
    dismiss,
    success: (message, duration) => push('success', message, duration),
    error: (message, duration) => push('error', message, duration ?? 6000),
    info: (message, duration) => push('info', message, duration),
  }
}
