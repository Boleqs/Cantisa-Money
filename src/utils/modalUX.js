import { onMounted, onUnmounted, ref, watch } from 'vue'

// Clic sur le fond d'un modal : au lieu de fermer (perte de saisie accidentelle),
// on secoue la boîte pour signaler qu'il faut passer par Annuler/✕/Echap.
export function useModalShake() {
  const shaking = ref(false)
  let timeout = null

  function shake() {
    if (timeout) clearTimeout(timeout)
    shaking.value = false
    requestAnimationFrame(() => {
      shaking.value = true
      timeout = setTimeout(() => { shaking.value = false }, 300)
    })
  }

  onUnmounted(() => { if (timeout) clearTimeout(timeout) })

  return { shaking, shake }
}

// Touche Echap : sortie rapide au clavier tant que rien n'a été saisi. Dès qu'un champ du modal a
// été modifié, Echap secoue au lieu de fermer (même garde-fou que le clic sur le fond, cf.
// useModalShake ci-dessus) — avant ce correctif, Echap fermait TOUJOURS immédiatement, contournant
// la protection anti-perte de saisie mise en place pour le clic extérieur (audit UX du 2026-07-27).
// `shake` et `isOpen` sont optionnels : sans eux, Echap referme toujours (comportement d'origine),
// utile pour des modals sans formulaire (ex. panneaux de simple confirmation).
export function useEscapeClose(close, shake, isOpen) {
  const touched = ref(false)

  if (isOpen) {
    watch(isOpen, (open) => { if (open) touched.value = false })
  }

  function onFieldChange() { touched.value = true }

  function onKeydown(e) {
    if (e.key !== 'Escape') return
    if (touched.value && shake) shake()
    else close()
  }

  onMounted(() => {
    document.addEventListener('keydown', onKeydown)
    // Capture (3e argument true) : un input à l'intérieur du modal suffit à le marquer "modifié",
    // qu'il s'agisse d'un <input>, <select> ou <textarea> — pas besoin d'écouter chaque champ un
    // par un, le backdrop bloque toute interaction avec le reste de la page pendant que le modal
    // est ouvert donc tout input/change capté ici lui appartient forcément.
    document.addEventListener('input', onFieldChange, true)
    document.addEventListener('change', onFieldChange, true)
  })
  onUnmounted(() => {
    document.removeEventListener('keydown', onKeydown)
    document.removeEventListener('input', onFieldChange, true)
    document.removeEventListener('change', onFieldChange, true)
  })

  return { touched }
}
