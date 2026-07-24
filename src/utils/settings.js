/**
 * Paramètres fonctionnels de l'utilisateur (devise, format de date, score de marché),
 * persistés côté serveur (table user_settings) — contrairement aux préférences purement
 * graphiques (sidebar), qui restent en localStorage (cf. src/components/sidebar/state.js).
 */
import { ref } from 'vue'
import axios from 'axios'

export const currency = ref('EUR')
export const dateFormat = ref('fr-FR')
export const onboardingCompleted = ref(false)

let weightsCache = null
let thresholdsCache = null
let loadPromise = null

/** Charge les paramètres depuis le serveur une seule fois (appels concurrents partagent la même requête). */
export function ensureSettingsLoaded() {
  if (!loadPromise) {
    loadPromise = axios.get('/api/settings')
      .then(res => {
        const d = res.data?.response_data || {}
        currency.value = d.currency || 'EUR'
        dateFormat.value = d.date_format || 'fr-FR'
        onboardingCompleted.value = !!d.onboarding_completed
        weightsCache = d.market_score_weights || null
        thresholdsCache = d.market_score_thresholds || null
      })
      .catch(() => {})
  }
  return loadPromise
}

/** Force un rechargement des paramètres (ex: juste après avoir terminé l'onboarding) — le
 * `loadPromise` mémoïsé par ensureSettingsLoaded() est déjà résolu et ne referait pas de requête
 * sinon. */
export function refreshSettings() {
  loadPromise = null
  return ensureSettingsLoaded()
}

/** Réinitialise le cache local au logout — sans ça, un deuxième utilisateur se connectant dans le
 * même onglet hériterait de la devise/onboardingCompleted du précédent jusqu'à un rechargement
 * complet de la page (ensureSettingsLoaded() ne refait rien tant que loadPromise est résolu). */
export function clearSettings() {
  currency.value = 'EUR'
  dateFormat.value = 'fr-FR'
  onboardingCompleted.value = false
  weightsCache = null
  thresholdsCache = null
  loadPromise = null
}

/** Envoie l'état courant au serveur et met à jour le cache local avec la réponse. */
async function saveSettings(partial) {
  const payload = {
    currency: partial.currency ?? currency.value,
    date_format: partial.dateFormat ?? dateFormat.value,
    market_score_weights: partial.weights !== undefined ? partial.weights : weightsCache,
    market_score_thresholds: partial.thresholds !== undefined ? partial.thresholds : thresholdsCache,
  }
  const res = await axios.put('/api/settings', payload)
  const d = res.data?.response_data || {}
  currency.value = d.currency || 'EUR'
  dateFormat.value = d.date_format || 'fr-FR'
  weightsCache = d.market_score_weights || null
  thresholdsCache = d.market_score_thresholds || null
}

export { saveSettings }

// ── Score de marché : mêmes signatures synchrones qu'auparavant (localStorage), maintenant
// adossées au cache peuplé par ensureSettingsLoaded() — aucun changement requis dans les vues
// consommatrices (MarketsScan.vue, MarketsAnalyse.vue, MarketsWatchlist.vue, Parametres.vue).

import { DEFAULT_METRICS } from './marketScoreMetrics.js' // fichier séparé pour éviter un import circulaire avec marketScore.js

export function loadWeights() {
  if (weightsCache) return weightsCache
  const equal = Math.round(100 / DEFAULT_METRICS.length)
  const weights = {}
  DEFAULT_METRICS.forEach((m, i) => {
    weights[m.key] = {
      enabled: true,
      weight: i < DEFAULT_METRICS.length - 1 ? equal : 100 - equal * (DEFAULT_METRICS.length - 1),
    }
  })
  return weights
}

export function saveWeights(weights) {
  weightsCache = weights
  saveSettings({ weights })
}

export function loadThresholds() {
  const result = {}
  DEFAULT_METRICS.forEach(m => {
    result[m.key] = thresholdsCache?.[m.key] ?? { great: m.great, bad: m.bad }
  })
  return result
}

export function saveThresholds(thresholds) {
  thresholdsCache = thresholds
  saveSettings({ thresholds })
}
