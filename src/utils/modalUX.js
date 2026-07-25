import { onMounted, onUnmounted, ref } from 'vue'

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

// Touche Echap : sortie rapide au clavier, seul raccourci restant pour fermer
// sans passer par un bouton depuis qu'on ne ferme plus au clic extérieur.
export function useEscapeClose(close) {
  function onKeydown(e) {
    if (e.key === 'Escape') close()
  }
  onMounted(() => document.addEventListener('keydown', onKeydown))
  onUnmounted(() => document.removeEventListener('keydown', onKeydown))
}
