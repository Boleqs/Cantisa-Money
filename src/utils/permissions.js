/**
 * Permissions de l'utilisateur connecté (groupes fonctionnels définis côté serveur dans
 * backend/config.py::VAR_PERMISSIONS_LIST), utilisées pour masquer les sections de l'UI
 * auxquelles l'utilisateur n'a pas accès. Le backend reste la seule source de vérité pour
 * l'autorisation réelle — ce cache ne sert qu'à l'affichage.
 */
import { ref } from 'vue'
import axios from 'axios'

export const permissions = ref(new Set())

let loadPromise = null

/** Charge les permissions depuis le serveur une seule fois (appels concurrents partagent la même requête). */
export function ensurePermissionsLoaded() {
  if (!loadPromise) {
    loadPromise = axios.get('/api/user/me/permissions')
      .then(res => {
        const names = Array.isArray(res.data?.response_data) ? res.data.response_data : []
        permissions.value = new Set(names)
      })
      .catch(() => {})
  }
  return loadPromise
}

/** À appeler à la déconnexion pour ne pas garder les permissions du précédent utilisateur en cache. */
export function clearPermissions() {
  permissions.value = new Set()
  loadPromise = null
}

export function hasPermission(name) {
  return permissions.value.has(name)
}
