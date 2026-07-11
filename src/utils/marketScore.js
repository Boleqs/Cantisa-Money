/**
 * Calcul du score pondéré d'une action à partir des poids configurés.
 * Utilisé par MarketsAnalyse.vue et potentiellement d'autres vues.
 */

export { DEFAULT_METRICS } from './marketScoreMetrics.js'

// Persistance (désormais en base via user_settings, cf. settings.js) — mêmes signatures
// synchrones qu'auparavant, ré-exportées ici pour ne rien changer aux vues consommatrices.
export { loadWeights, saveWeights, loadThresholds, saveThresholds } from './settings.js'

import { DEFAULT_METRICS } from './marketScoreMetrics.js'

/** Normalise une valeur sur 0–10 selon la direction et les bornes. */
function normalize(val, direction, great, bad) {
  if (val == null || isNaN(val)) return null
  if (direction === 'lower') {
    if (val <= great) return 10
    if (val >= bad)   return 0
    return 10 * (bad - val) / (bad - great)
  } else {
    if (val >= great) return 10
    if (val <= bad)   return 0
    return 10 * (val - bad) / (great - bad)
  }
}

/**
 * Calcule le score global d'un stock selon les poids et seuils fournis.
 * @param {object} stock       - données de l'action
 * @param {object} weights     - { [key]: { enabled, weight } }
 * @param {object} thresholds  - { [key]: { great, bad } } — si null, utilise les défauts
 * @returns { score: number|null, detail: [{label, rawVal, note, weight}] }
 */
export function computeScore(stock, weights, thresholds = null) {
  let totalWeight = 0
  let weightedSum = 0
  const detail = []

  for (const metric of DEFAULT_METRICS) {
    const cfg = weights[metric.key]
    if (!cfg?.enabled || !cfg.weight) continue

    const rawVal = stock[metric.key]
    const t = thresholds?.[metric.key] ?? { great: metric.great, bad: metric.bad }
    const note = normalize(rawVal, metric.direction, t.great, t.bad)
    if (note === null) continue   // valeur absente → on ignore

    const w = cfg.weight
    weightedSum += note * w
    totalWeight += w
    detail.push({ label: metric.label, rawVal, note: Math.round(note * 10) / 10, weight: w })
  }

  if (totalWeight === 0) return { score: null, detail: [] }

  const score = Math.round((weightedSum / totalWeight) * 10) / 10
  return { score, detail }
}

/** Classe CSS selon le score (0–10). */
export function scoreClass(score) {
  if (score == null) return ''
  if (score >= 7)  return 'score-good'
  if (score >= 4)  return 'score-mid'
  return 'score-bad'
}
