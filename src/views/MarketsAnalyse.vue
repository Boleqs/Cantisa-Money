<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Analyse fondamentale</h1>
        <p class="subtitle">Comparez les indicateurs clés d'une ou plusieurs actions en temps réel.</p>
      </div>
    </header>

    <!-- Barre de recherche -->
    <div class="search-bar">
      <div class="search-input-wrap">
        <input
          v-model="searchInput"
          @keydown.enter="addTicker"
          type="text"
          placeholder="Ticker (ex : AAPL, MC.PA, AIR.PA)..."
          class="search-input"
          :disabled="loading"
        />
        <button @click="addTicker" class="btn-search" :disabled="loading || !searchInput.trim()">
          {{ loading ? 'Chargement…' : 'Analyser' }}
        </button>
      </div>
      <p class="search-hint">
        Entrez un ticker boursier et appuyez sur Entrée ou cliquez sur Analyser.
        Vous pouvez comparer plusieurs actions simultanément.
      </p>
    </div>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <!-- Résultats -->
    <div v-if="results.length" class="results-section">

      <!-- Barre d'actions -->
      <div class="results-toolbar">
        <span class="results-count">{{ results.length }} action{{ results.length > 1 ? 's' : '' }} analysée{{ results.length > 1 ? 's' : '' }}</span>
        <button class="btn-export" @click="exportPdf" :disabled="exporting">
          {{ exporting ? 'Génération…' : '⬇ Exporter en PDF' }}
        </button>
      </div>
      <div v-if="exportError" class="error-banner">{{ exportError }}</div>

      <!-- Fiches individuelles -->
      <div class="cards-grid">
        <div v-for="stock in results" :key="stock.ticker" class="stock-card">

          <div class="card-header">
            <div class="card-title-group">
              <span class="ticker-badge">{{ stock.ticker }}</span>
              <span class="stock-name">{{ stock.name || '—' }}</span>
            </div>
            <div class="card-header-right">
              <div
                v-if="getScore(stock).score !== null"
                class="score-badge tip-wrap"
                :class="scoreClass(getScore(stock).score)"
                :data-tip="scoreDetail(stock)"
              >
                <span class="score-val">{{ getScore(stock).score }}</span>
                <span class="score-max">/10</span>
              </div>
              <button class="btn-remove" @click="removeResult(stock.ticker)" title="Retirer">✕</button>
            </div>
          </div>

          <div class="card-meta">
            <span v-if="stock.sector">{{ stock.sector }}</span>
            <span v-if="stock.sector && stock.industry"> · </span>
            <span v-if="stock.industry">{{ stock.industry }}</span>
            <span v-if="stock.country"> · {{ stock.country }}</span>
            <span v-if="stock.exchange" class="exchange-tag">{{ stock.exchange }}</span>
          </div>

          <!-- Prix -->
          <div class="card-section">
            <div class="section-label">Prix</div>
            <div class="price-row">
              <span class="price-main">
                {{ stock.current_price != null ? stock.current_price.toLocaleString('fr-FR') : '—' }}
                <span class="currency">{{ stock.currency || '' }}</span>
              </span>
              <span
                v-if="stock.day_change_pct != null"
                class="day-change"
                :class="stock.day_change_pct >= 0 ? 'positive' : 'negative'"
              >
                {{ stock.day_change_pct >= 0 ? '+' : '' }}{{ stock.day_change_pct }}%
              </span>
            </div>
            <div class="range-52w" v-if="stock.week_52_low != null && stock.week_52_high != null">
              <span class="tip-wrap" :data-tip="TIPS.week_52">
                <span class="range-label">52 sem.</span>
              </span>
              <span class="range-low">{{ stock.week_52_low }}</span>
              <div class="range-bar">
                <div class="range-fill" :style="{ left: rangePosition(stock) + '%' }"></div>
              </div>
              <span class="range-high">{{ stock.week_52_high }}</span>
            </div>
            <div class="metric-row" v-if="stock.market_cap">
              <span class="metric-label tip-wrap" :data-tip="TIPS.market_cap">Capitalisation</span>
              <span class="metric-value">{{ stock.market_cap }} {{ stock.currency || '' }}</span>
            </div>
          </div>

          <!-- Valorisation -->
          <div class="card-section">
            <div class="section-label">Valorisation</div>
            <div class="metrics-grid">
              <div class="metric-cell tip-wrap" :data-tip="TIPS.pe_trailing">
                <span class="metric-label">P/E trailing</span>
                <span class="metric-value" :class="ratingClass('pe', stock.pe_trailing)">{{ fmt(stock.pe_trailing) }}</span>
              </div>
              <div class="metric-cell tip-wrap" :data-tip="TIPS.pe_forward">
                <span class="metric-label">P/E forward</span>
                <span class="metric-value" :class="ratingClass('pe', stock.pe_forward)">{{ fmt(stock.pe_forward) }}</span>
              </div>
              <div class="metric-cell tip-wrap" :data-tip="TIPS.pb_ratio">
                <span class="metric-label">P/B</span>
                <span class="metric-value" :class="ratingClass('pb', stock.pb_ratio)">{{ fmt(stock.pb_ratio) }}</span>
              </div>
              <div class="metric-cell tip-wrap" :data-tip="TIPS.dividend_yield">
                <span class="metric-label">Dividende</span>
                <span class="metric-value positive">{{ stock.dividend_yield != null ? stock.dividend_yield + ' %' : '—' }}</span>
              </div>
            </div>
          </div>

          <!-- Rentabilité -->
          <div class="card-section">
            <div class="section-label">Rentabilité</div>
            <div class="metrics-grid">
              <div class="metric-cell tip-wrap" :data-tip="TIPS.roe">
                <span class="metric-label">ROE</span>
                <span class="metric-value" :class="ratingClass('roe', stock.roe)">{{ fmt(stock.roe, '%') }}</span>
              </div>
              <div class="metric-cell tip-wrap" :data-tip="TIPS.roa">
                <span class="metric-label">ROA</span>
                <span class="metric-value" :class="ratingClass('roa', stock.roa)">{{ fmt(stock.roa, '%') }}</span>
              </div>
              <div class="metric-cell tip-wrap" :data-tip="TIPS.net_margin">
                <span class="metric-label">Marge nette</span>
                <span class="metric-value" :class="ratingClass('margin', stock.net_margin)">{{ fmt(stock.net_margin, '%') }}</span>
              </div>
              <div class="metric-cell tip-wrap" :data-tip="TIPS.gross_margin">
                <span class="metric-label">Marge brute</span>
                <span class="metric-value" :class="ratingClass('margin', stock.gross_margin)">{{ fmt(stock.gross_margin, '%') }}</span>
              </div>
              <div class="metric-cell tip-wrap" :data-tip="TIPS.operating_margin">
                <span class="metric-label">Marge opérat.</span>
                <span class="metric-value" :class="ratingClass('margin', stock.operating_margin)">{{ fmt(stock.operating_margin, '%') }}</span>
              </div>
            </div>
          </div>

        </div>
      </div>

      <!-- Tableau comparatif (si 2+ tickers) -->
      <div v-if="results.length >= 2" class="compare-section">
        <h2 class="compare-title">Comparaison</h2>
        <div class="table-scroll">
          <table class="compare-table">
            <thead>
              <tr>
                <th>Métrique</th>
                <th v-for="s in results" :key="s.ticker">{{ s.ticker }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in compareRows" :key="row.key">
                <td class="row-label tip-wrap" :data-tip="TIPS[row.key]">{{ row.label }}</td>
                <td v-for="s in results" :key="s.ticker" :class="bestClass(row, s)">
                  {{ fmt(s[row.key], row.unit) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="compare-hint">La valeur la plus favorable est mise en évidence.</p>
      </div>
    </div>

    <!-- État vide -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-icon">📊</div>
      <h2>Analysez une action</h2>
      <p>Saisissez un ticker boursier pour obtenir les indicateurs fondamentaux.</p>
      <div class="ticker-examples">
        <span v-for="ex in examples" :key="ex" class="example-chip" @click="quickSearch(ex)">{{ ex }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { loadWeights, loadThresholds, computeScore, scoreClass } from '@/utils/marketScore.js'

// ── Score ─────────────────────────────────────────────────────────────────────
const weights    = ref({})
const thresholds = ref({})
onMounted(() => {
  weights.value    = loadWeights()
  thresholds.value = loadThresholds()
})

function getScore(stock) {
  return computeScore(stock, weights.value, thresholds.value)
}

function scoreDetail(stock) {
  const { detail } = getScore(stock)
  if (!detail.length) return 'Aucune métrique disponible'
  return detail.map(d => `${d.label} : ${d.note}/10 x ${d.weight}%`).join('\n')
}

// ── Recherche ─────────────────────────────────────────────────────────────────
const searchInput = ref('')
const loading     = ref(false)
const error       = ref(null)
const results     = ref([])
const exporting   = ref(false)
const exportError = ref(null)

const examples = ['AAPL', 'MC.PA', 'AIR.PA', 'MSFT', 'NVDA', 'TTE.PA']

// ── Textes des tooltips ───────────────────────────────────────────────────────
const TIPS = {
  pe_trailing:      'P/E trailing — Prix / Bénéfice net des 12 derniers mois. Combien tu paies pour 1 € de bénéfice déjà réalisé. Vert < 15 · Jaune 15–25 · Rouge > 25.',
  pe_forward:       'P/E forward — Prix / Bénéfice net estimé des 12 prochains mois. Plus prospectif que le trailing. Mêmes seuils.',
  pb_ratio:         'P/B (Price to Book) — Prix / Valeur comptable des actifs nets. < 1 : tu achètes sous la valeur des actifs. Vert < 1 · Jaune 1–3 · Rouge > 3.',
  dividend_yield:   'Rendement du dividende — Dividende annuel / Prix × 100. Revenu perçu chaque année pour chaque euro investi.',
  roe:              'ROE (Return on Equity) — Bénéfice net / Fonds propres. Mesure combien l\'entreprise génère pour chaque euro apporté par les actionnaires. Vert ≥ 15 % · Jaune 5–15 % · Rouge < 5 %.',
  roa:              'ROA (Return on Assets) — Bénéfice net / Total actifs. Efficacité globale à utiliser toutes ses ressources. Vert ≥ 15 % · Jaune 5–15 % · Rouge < 5 %.',
  net_margin:       'Marge nette — Bénéfice net / Chiffre d\'affaires. Ce qui reste après toutes les charges, impôts inclus. Vert ≥ 20 % · Jaune 5–20 % · Rouge < 5 %.',
  gross_margin:     'Marge brute — (CA − Coût des ventes) / CA. Rentabilité avant frais généraux et impôts. Vert ≥ 20 % · Jaune 5–20 % · Rouge < 5 %.',
  operating_margin: 'Marge opérationnelle — Résultat opérationnel / CA. Rentabilité après charges d\'exploitation mais avant intérêts et impôts. Vert ≥ 20 % · Jaune 5–20 % · Rouge < 5 %.',
  market_cap:       'Capitalisation boursière — Prix × nombre d\'actions. Valeur totale de l\'entreprise en bourse (T = billions, B = milliards, M = millions).',
  week_52:          'Fourchette 52 semaines — Plus bas et plus haut atteints sur les 12 derniers mois. Le point bleu indique où se situe le prix actuel.',
}

// ── Recherche ─────────────────────────────────────────────────────────────────
async function addTicker() {
  const ticker = searchInput.value.trim().toUpperCase()
  if (!ticker) return
  if (results.value.find(r => r.ticker === ticker)) {
    error.value = `${ticker} est déjà dans la liste.`
    return
  }
  error.value = null
  loading.value = true
  try {
    const res = await axios.get('/api/markets/analyse', { params: { ticker } })
    results.value.push(res.data.response_data)
    searchInput.value = ''
  } catch (err) {
    error.value = err.response?.data?.response_data || `Impossible de récupérer les données pour "${ticker}".`
  } finally {
    loading.value = false
  }
}

function quickSearch(ticker) {
  searchInput.value = ticker
  addTicker()
}

function removeResult(ticker) {
  results.value = results.value.filter(r => r.ticker !== ticker)
}

// ── Export PDF ────────────────────────────────────────────────────────────────
async function exportPdf() {
  exporting.value = true
  exportError.value = null
  try {
    const res = await axios.post('/api/markets/export-pdf', results.value, {
      responseType: 'blob',
    })
    const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url
    a.download = `cantisa_analyse_${new Date().toISOString().slice(0, 10)}.pdf`
    a.click()
    URL.revokeObjectURL(url)
  } catch (err) {
    const detail = err.response?.data?.response_data || err.message || 'Erreur inconnue'
    exportError.value = `Erreur PDF : ${detail}`
  } finally {
    exporting.value = false
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(value, unit = '') {
  if (value == null) return '—'
  return `${value}${unit}`
}

function rangePosition(stock) {
  const { current_price, week_52_low, week_52_high } = stock
  if (current_price == null || week_52_low == null || week_52_high == null) return 50
  const range = week_52_high - week_52_low
  if (range === 0) return 50
  return Math.round(((current_price - week_52_low) / range) * 100)
}

function ratingClass(type, value) {
  if (value == null) return ''
  if (type === 'pe') {
    if (value < 15) return 'positive'
    if (value < 25) return 'neutral'
    return 'negative'
  }
  if (type === 'pb') {
    if (value < 1) return 'positive'
    if (value < 3) return 'neutral'
    return 'negative'
  }
  if (type === 'roe' || type === 'roa') {
    if (value >= 15) return 'positive'
    if (value >= 5) return 'neutral'
    return 'negative'
  }
  if (type === 'margin') {
    if (value >= 20) return 'positive'
    if (value >= 5) return 'neutral'
    return 'negative'
  }
  return ''
}

const compareRows = [
  { key: 'pe_trailing',      label: 'P/E (trailing)',  unit: '',  best: 'min' },
  { key: 'pe_forward',       label: 'P/E (forward)',   unit: '',  best: 'min' },
  { key: 'pb_ratio',         label: 'P/B',             unit: '',  best: 'min' },
  { key: 'dividend_yield',   label: 'Dividende',       unit: '%', best: 'max' },
  { key: 'roe',              label: 'ROE',             unit: '%', best: 'max' },
  { key: 'roa',              label: 'ROA',             unit: '%', best: 'max' },
  { key: 'net_margin',       label: 'Marge nette',     unit: '%', best: 'max' },
  { key: 'gross_margin',     label: 'Marge brute',     unit: '%', best: 'max' },
  { key: 'operating_margin', label: 'Marge opérat.',   unit: '%', best: 'max' },
]

function bestClass(row, stock) {
  if (!row.best) return ''
  const values = results.value.map(s => s[row.key]).filter(v => v != null)
  if (values.length < 2) return ''
  const target = row.best === 'max' ? Math.max(...values) : Math.min(...values)
  return stock[row.key] === target ? 'best-cell' : ''
}
</script>

<style scoped>
.page {
  padding: 28px;
  color: #e5e7eb;
  background: #0b1220;
  min-height: 100vh;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}
.page-header { margin-bottom: 24px; }
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; }

/* Recherche */
.search-bar {
  background: #1e293b;
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 20px 24px;
  margin-bottom: 28px;
}
.search-input-wrap { display: flex; gap: 10px; }
.search-input {
  flex: 1;
  background: #0b1220;
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px;
  padding: 10px 14px;
  color: #e5e7eb;
  font-size: 15px;
  outline: none;
  transition: border-color 0.2s;
}
.search-input:focus { border-color: #3b82f6; }
.btn-search {
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 22px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}
.btn-search:hover:not(:disabled) { background: #2563eb; }
.btn-search:disabled { opacity: 0.5; cursor: not-allowed; }
.search-hint { margin: 10px 0 0; color: #6b7280; font-size: 12px; }

.error-banner {
  background: rgba(239,68,68,0.15);
  border: 1px solid rgba(239,68,68,0.4);
  border-radius: 8px;
  padding: 10px 16px;
  color: #fca5a5;
  font-size: 13px;
  margin-bottom: 20px;
}

/* Barre d'actions résultats */
.results-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.results-count { font-size: 13px; color: #64748b; }
.btn-export {
  background: #0f172a;
  color: #94a3b8;
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px;
  padding: 8px 16px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-export:hover:not(:disabled) { background: #1e293b; color: #e2e8f0; border-color: rgba(148,163,184,0.5); }
.btn-export:disabled { opacity: 0.5; cursor: not-allowed; }

/* Tooltips CSS */
.tip-wrap {
  position: relative;
  cursor: help;
}
.tip-wrap::after {
  content: attr(data-tip);
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: #0f172a;
  color: #e2e8f0;
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 400;
  line-height: 1.5;
  width: 260px;
  white-space: normal;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.15s;
  z-index: 200;
  box-shadow: 0 4px 20px rgba(0,0,0,0.5);
}
.tip-wrap:hover::after { opacity: 1; }

/* Cartes */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
}
.stock-card {
  background: #1e293b;
  border: 1px solid rgba(148,163,184,0.12);
  border-radius: 16px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.card-header-right { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }

/* Score badge */
.score-badge {
  display: flex;
  align-items: baseline;
  gap: 2px;
  border-radius: 8px;
  padding: 4px 10px;
  font-weight: 700;
  border: 1px solid currentColor;
}
.score-val { font-size: 18px; }
.score-max { font-size: 11px; opacity: 0.7; }
.score-good { color: #4ade80; background: rgba(74,222,128,0.1); border-color: rgba(74,222,128,0.3); }
.score-mid  { color: #facc15; background: rgba(250,204,21,0.1);  border-color: rgba(250,204,21,0.3); }
.score-bad  { color: #f87171; background: rgba(248,113,113,0.1); border-color: rgba(248,113,113,0.3); }
.card-title-group { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.ticker-badge {
  background: #3b82f6;
  color: #fff;
  border-radius: 6px;
  padding: 3px 10px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.05em;
}
.stock-name { font-size: 15px; font-weight: 600; color: #cbd5e1; }
.btn-remove {
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  font-size: 14px;
  padding: 2px 6px;
  border-radius: 4px;
  transition: color 0.2s, background 0.2s;
  flex-shrink: 0;
}
.btn-remove:hover { color: #ef4444; background: rgba(239,68,68,0.1); }
.card-meta { font-size: 12px; color: #6b7280; display: flex; align-items: center; flex-wrap: wrap; gap: 2px; }
.exchange-tag {
  margin-left: 6px;
  background: rgba(148,163,184,0.15);
  border-radius: 4px;
  padding: 1px 6px;
  font-size: 11px;
  color: #94a3b8;
}
.card-section { display: flex; flex-direction: column; gap: 10px; }
.section-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #475569;
  border-bottom: 1px solid rgba(148,163,184,0.1);
  padding-bottom: 4px;
}
.price-row { display: flex; align-items: baseline; gap: 10px; }
.price-main { font-size: 26px; font-weight: 700; color: #f1f5f9; }
.currency { font-size: 14px; color: #94a3b8; margin-left: 2px; }
.day-change { font-size: 14px; font-weight: 600; }
.range-52w { display: flex; align-items: center; gap: 8px; font-size: 12px; color: #6b7280; }
.range-label { font-size: 11px; color: #475569; }
.range-bar { flex: 1; height: 4px; background: rgba(148,163,184,0.2); border-radius: 2px; position: relative; }
.range-fill {
  position: absolute;
  top: -3px;
  width: 10px;
  height: 10px;
  background: #3b82f6;
  border-radius: 50%;
  transform: translateX(-50%);
}
.metric-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px; }
.metric-label { color: #94a3b8; font-size: 12px; }
.metric-value { font-weight: 600; font-size: 13px; }

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 10px;
}
.metric-cell {
  background: rgba(15,23,42,0.5);
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: background 0.15s;
}
.metric-cell:hover { background: rgba(30,41,59,0.9); }
.metric-cell .metric-label { font-size: 11px; color: #64748b; }
.metric-cell .metric-value { font-size: 15px; font-weight: 700; }

.positive { color: #4ade80; }
.neutral  { color: #facc15; }
.negative { color: #f87171; }

/* Tableau comparatif */
.compare-section { margin-top: 8px; }
.compare-title { font-size: 18px; font-weight: 700; margin: 0 0 14px; color: #cbd5e1; }
.table-scroll { overflow-x: auto; }
.compare-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 400px; }
.compare-table th {
  background: #1e293b;
  padding: 10px 14px;
  text-align: left;
  color: #94a3b8;
  font-weight: 600;
  border-bottom: 1px solid rgba(148,163,184,0.15);
}
.compare-table td {
  padding: 9px 14px;
  border-bottom: 1px solid rgba(148,163,184,0.07);
  color: #cbd5e1;
}
.compare-table tr:hover td { background: rgba(148,163,184,0.04); }
.row-label { color: #94a3b8; font-size: 12px; }
.best-cell { color: #4ade80 !important; font-weight: 700; }
.compare-hint { font-size: 11px; color: #475569; margin-top: 8px; }

/* État vide */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 64px 32px;
  border: 1px dashed rgba(148,163,184,0.2);
  border-radius: 16px;
  background: rgba(15,23,42,0.4);
  text-align: center;
}
.empty-icon { font-size: 56px; }
.empty-state h2 { margin: 0; font-size: 20px; color: #cbd5e1; }
.empty-state p { margin: 0; color: #6b7280; font-size: 14px; }
.ticker-examples { display: flex; gap: 8px; flex-wrap: wrap; justify-content: center; margin-top: 8px; }
.example-chip {
  background: #1e293b;
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 20px;
  padding: 5px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s;
}
.example-chip:hover { background: #3b82f6; border-color: #3b82f6; color: #fff; }
</style>
