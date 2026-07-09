/**
 * Calcul du score pondéré d'une action à partir des poids configurés.
 * Utilisé par MarketsAnalyse.vue et potentiellement d'autres vues.
 */

const KEY_WEIGHTS     = 'cmm_market_score_weights'
const KEY_THRESHOLDS  = 'cmm_market_score_thresholds'

export const DEFAULT_METRICS = [
  { key: 'pe_trailing',      label: 'P/E (trailing)',   direction: 'lower', great: 10,  bad: 35  },
  { key: 'pe_forward',       label: 'P/E (forward)',    direction: 'lower', great: 10,  bad: 35  },
  { key: 'pb_ratio',         label: 'P/B',              direction: 'lower', great: 1,   bad: 5   },
  { key: 'dividend_yield',   label: 'Dividende',        direction: 'higher', great: 5,  bad: 0   },
  { key: 'roe',              label: 'ROE',              direction: 'higher', great: 20, bad: 0   },
  { key: 'roa',              label: 'ROA',              direction: 'higher', great: 15, bad: 0   },
  { key: 'net_margin',       label: 'Marge nette',      direction: 'higher', great: 25, bad: 0   },
  { key: 'gross_margin',     label: 'Marge brute',      direction: 'higher', great: 60, bad: 10  },
  { key: 'operating_margin', label: 'Marge opérat.',    direction: 'higher', great: 25, bad: 0   },
]

/** Charge les poids depuis le localStorage. */
export function loadWeights() {
  try {
    const raw = localStorage.getItem(KEY_WEIGHTS)
    if (raw) return JSON.parse(raw)
  } catch {}
  // Valeurs par défaut : tout activé, poids égaux
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

/** Sauvegarde les poids dans le localStorage. */
export function saveWeights(weights) {
  try {
    localStorage.setItem(KEY_WEIGHTS, JSON.stringify(weights))
  } catch {}
}

/** Charge les seuils personnalisés depuis le localStorage. */
export function loadThresholds() {
  try {
    const raw = localStorage.getItem(KEY_THRESHOLDS)
    if (raw) {
      const stored = JSON.parse(raw)
      // Fusionne avec les défauts pour les métriques éventuellement absentes
      const result = {}
      DEFAULT_METRICS.forEach(m => {
        result[m.key] = stored[m.key] ?? { great: m.great, bad: m.bad }
      })
      return result
    }
  } catch {}
  const result = {}
  DEFAULT_METRICS.forEach(m => { result[m.key] = { great: m.great, bad: m.bad } })
  return result
}

/** Sauvegarde les seuils dans le localStorage. */
export function saveThresholds(thresholds) {
  try {
    localStorage.setItem(KEY_THRESHOLDS, JSON.stringify(thresholds))
  } catch {}
}

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
