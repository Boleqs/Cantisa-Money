import { ref } from 'vue'
import axios from 'axios'

// Cache partagé (même pattern que settings.js pour la devise par défaut) : plusieurs vues/modales
// ont besoin de la liste des institutions juste pour désambiguïser des noms de comptes identiques
// (voir accountDisplay.js) — évite de refaire un GET /api/institutions dans chacune.
export const institutions = ref([])
let loaded = false
let loadingPromise = null

export async function ensureInstitutionsLoaded() {
  if (loaded) return institutions.value
  if (loadingPromise) return loadingPromise
  loadingPromise = axios
    .get('/api/institutions')
    .then(({ data }) => {
      institutions.value = Array.isArray(data?.response_data) ? data.response_data : []
      loaded = true
      return institutions.value
    })
    .catch(() => {
      // Utilisateur sans permission Comptabilité, ou backend indisponible : pas d'institutions,
      // les libellés de compte retombent simplement sur le nom + chaîne de parents.
      institutions.value = []
      loaded = true
      return institutions.value
    })
    .finally(() => {
      loadingPromise = null
    })
  return loadingPromise
}

// Utile après une création/modification d'institution ailleurs dans l'app, pour forcer un refetch
// au prochain ensureInstitutionsLoaded() plutôt que de servir un cache périmé indéfiniment.
export function invalidateInstitutionsCache() {
  loaded = false
}
