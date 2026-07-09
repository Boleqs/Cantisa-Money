<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Scanner de marchés</h1>
        <p class="subtitle">Identifiez les actions qui correspondent à vos critères en un clic.</p>
      </div>
    </header>

    <!-- Panneau de configuration -->
    <div class="config-panel">
      <!-- Sélection indice -->
      <div class="config-row">
        <label class="config-label">
          Indice / liste
          <span v-if="indicesLoading" class="loading-dot">chargement…</span>
        </label>
        <div class="index-pills">
          <button
            v-for="(count, name) in availableIndices"
            :key="name"
            class="pill"
            :class="{ active: selectedIndex === name }"
            @click="selectIndex(name)"
          >
            {{ name }}
            <span class="pill-count">{{ count }}</span>
          </button>
          <button
            class="pill"
            :class="{ active: selectedIndex === 'custom' }"
            @click="selectIndex('custom')"
          >Personnalisé</button>
        </div>
      </div>

      <!-- Tickers personnalisés -->
      <div v-if="selectedIndex === 'custom'" class="config-row">
        <label class="config-label">Tickers (séparés par virgule ou espace)</label>
        <textarea
          v-model="customTickers"
          class="ticker-textarea"
          placeholder="AAPL, MSFT, MC.PA, AIR.PA..."
          rows="3"
        />
      </div>

      <!-- Aperçu de la liste -->
      <div v-if="tickerList.length" class="config-row">
        <label class="config-label">
          Tickers à scanner —
          <span class="ticker-count-inline">{{ tickerList.length }} ticker{{ tickerList.length > 1 ? 's' : '' }}</span>
          <span v-if="estimatedSeconds > 0" class="eta">· ~{{ estimatedSeconds }}s estimées</span>
        </label>
        <div class="ticker-preview">
          <span v-for="t in tickerList.slice(0, 60)" :key="t" class="ticker-chip">{{ t }}</span>
          <span v-if="tickerList.length > 60" class="ticker-chip more">+{{ tickerList.length - 60 }} autres</span>
        </div>
      </div>

      <!-- Filtres -->
      <div class="config-filters">
        <div class="filter-block">
          <label class="config-label">Score minimum</label>
          <div class="score-slider-wrap">
            <input type="range" min="0" max="10" step="0.5" v-model.number="minScore" class="slider" />
            <span class="score-value" :class="scoreClass(minScore)">{{ minScore }}/10</span>
          </div>
        </div>
        <div class="filter-block">
          <label class="config-label">Secteur</label>
          <select v-model="filterSector" class="sector-select">
            <option value="">Tous les secteurs</option>
            <option v-for="s in sectors" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div class="filter-block">
          <label class="config-label">Trier par</label>
          <select v-model="sortBy" class="sector-select">
            <option value="score">Score</option>
            <option value="day_change_pct">Variation jour</option>
            <option value="pe_trailing">P/E</option>
            <option value="roe">ROE</option>
            <option value="net_margin">Marge nette</option>
            <option value="dividend_yield">Dividende</option>
          </select>
        </div>
      </div>

      <div class="config-actions">
        <button class="btn-scan" :disabled="scanning || !tickerList.length" @click="runScan">
          <span v-if="scanning" class="spinner"></span>
          {{ scanning ? `Analyse en cours… (${scanProgress}/${tickerList.length})` : 'Lancer le scan' }}
        </button>
        <span v-if="lastScanAt" class="last-scan">Dernier scan : {{ lastScanAt }}</span>
      </div>

      <div v-if="scanError" class="error-banner">{{ scanError }}</div>
    </div>

    <!-- Résultats -->
    <div v-if="filteredResults.length" class="results-section">
      <div class="results-meta">
        <span>{{ filteredResults.length }} action{{ filteredResults.length > 1 ? 's' : '' }} trouvée{{ filteredResults.length > 1 ? 's' : '' }}</span>
        <span v-if="rawResults.length !== filteredResults.length" class="filter-note">
          ({{ rawResults.length }} total, filtrées par secteur)
        </span>
      </div>

      <div class="table-scroll">
        <table class="scan-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Nom</th>
              <th>Secteur</th>
              <th>Prix</th>
              <th>Variation</th>
              <th class="sortable" @click="setSortBy('pe_trailing')">
                P/E <span class="sort-arrow">{{ sortBy === 'pe_trailing' ? '↓' : '' }}</span>
              </th>
              <th class="sortable" @click="setSortBy('roe')">
                ROE <span class="sort-arrow">{{ sortBy === 'roe' ? '↓' : '' }}</span>
              </th>
              <th class="sortable" @click="setSortBy('net_margin')">
                Marge nette <span class="sort-arrow">{{ sortBy === 'net_margin' ? '↓' : '' }}</span>
              </th>
              <th class="sortable" @click="setSortBy('dividend_yield')">
                Dividende <span class="sort-arrow">{{ sortBy === 'dividend_yield' ? '↓' : '' }}</span>
              </th>
              <th class="sortable" @click="setSortBy('score')">
                Score <span class="sort-arrow">{{ sortBy === 'score' ? '↓' : '' }}</span>
              </th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in filteredResults" :key="s.ticker">
              <td><span class="ticker-badge">{{ s.ticker }}</span></td>
              <td class="col-name">{{ s.name || '—' }}</td>
              <td class="col-meta">{{ s.sector || '—' }}</td>
              <td class="col-price">
                {{ s.current_price != null ? s.current_price : '—' }}
                <span class="col-currency">{{ s.currency }}</span>
              </td>
              <td>
                <span
                  v-if="s.day_change_pct != null"
                  class="change-pill"
                  :class="s.day_change_pct >= 0 ? 'positive' : 'negative'"
                >{{ s.day_change_pct >= 0 ? '+' : '' }}{{ s.day_change_pct }}%</span>
                <span v-else class="col-meta">—</span>
              </td>
              <td :class="ratingClass('pe', s.pe_trailing)">{{ fmt(s.pe_trailing) }}</td>
              <td :class="ratingClass('roe', s.roe)">{{ fmt(s.roe, '%') }}</td>
              <td :class="ratingClass('margin', s.net_margin)">{{ fmt(s.net_margin, '%') }}</td>
              <td class="positive">{{ fmt(s.dividend_yield, '%') }}</td>
              <td>
                <span
                  v-if="s.score != null"
                  class="score-badge"
                  :class="scoreClass(s.score)"
                >{{ s.score }}/10</span>
                <span v-else class="col-meta">—</span>
              </td>
              <td>
                <button
                  class="btn-add"
                  title="Ajouter à la watchlist"
                  :disabled="watchlistTickers.has(s.ticker)"
                  @click="addToWatchlist(s)"
                >{{ watchlistTickers.has(s.ticker) ? '✓' : '+' }}</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- État vide post-scan -->
    <div v-else-if="scanned && !scanning" class="empty-state">
      <div class="empty-icon">🔍</div>
      <h2>Aucun résultat</h2>
      <p>Aucune action ne dépasse le score de {{ minScore }}/10 avec les paramètres actuels.<br>Essayez d'abaisser le score minimum ou de modifier vos poids dans les <router-link to="/parametres" class="link">Paramètres</router-link>.</p>
    </div>

    <!-- État initial -->
    <div v-else-if="!scanning" class="empty-state">
      <div class="empty-icon">📡</div>
      <h2>Prêt à scanner</h2>
      <p>Choisissez un indice, définissez votre score minimum, puis lancez le scan.</p>
      <p class="hint">Les poids utilisés sont ceux configurés dans <router-link to="/parametres" class="link">Paramètres → Marchés</router-link>.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { loadWeights, loadThresholds, scoreClass } from '@/utils/marketScore.js'

// ── Config ────────────────────────────────────────────────────────────────────
// availableIndices : { "S&P 500": 500, "CAC 40": 40, ... }  (count par indice)
const availableIndices  = ref({})
const indicesLoading    = ref(false)
// indexTickersCache : { "S&P 500": [...tickers], ... }  (chargé à la demande)
const indexTickersCache = ref({})
const selectedIndex     = ref('')
const customTickers     = ref('')
const minScore          = ref(6)
const filterSector      = ref('')
const sortBy            = ref('score')

// ── État du scan ─────────────────────────────────────────────────────────────
const scanning     = ref(false)
const scanProgress = ref(0)
const scanError    = ref(null)
const scanned      = ref(false)
const lastScanAt   = ref(null)
const rawResults   = ref([])

// ── Watchlist locale (pour afficher le ✓) ────────────────────────────────────
const watchlistTickers = ref(new Set())

// ── Computed ──────────────────────────────────────────────────────────────────
const tickerList = computed(() => {
  if (selectedIndex.value === 'custom') {
    return customTickers.value
      .split(/[\s,;]+/)
      .map(t => t.trim().toUpperCase())
      .filter(Boolean)
  }
  return indexTickersCache.value[selectedIndex.value] || []
})

// Durée estimée : 10 workers, ~0.6s par ticker
const estimatedSeconds = computed(() => {
  const n = tickerList.value.length
  if (!n) return 0
  return Math.round(n * 0.6 / 10)
})

const sectors = computed(() => {
  const s = new Set(rawResults.value.map(r => r.sector).filter(Boolean))
  return [...s].sort()
})

const filteredResults = computed(() => {
  let list = [...rawResults.value]
  if (filterSector.value) list = list.filter(r => r.sector === filterSector.value)
  list.sort((a, b) => {
    const va = a[sortBy.value] ?? -Infinity
    const vb = b[sortBy.value] ?? -Infinity
    return vb - va
  })
  return list
})

// ── Montage ───────────────────────────────────────────────────────────────────
onMounted(async () => {
  indicesLoading.value = true
  try {
    // Premier appel : peut être lent (scraping Wikipedia côté serveur)
    const res = await axios.get('/api/markets/scan/indices')
    availableIndices.value = res.data.response_data
    const firstIndex = Object.keys(availableIndices.value)[0]
    if (firstIndex) {
      selectedIndex.value = firstIndex
      await loadIndexTickers(firstIndex)
    }
  } catch {} finally {
    indicesLoading.value = false
  }
  try {
    const wl = await axios.get('/api/markets/watchlist')
    watchlistTickers.value = new Set(wl.data.response_data.map(s => s.ticker))
  } catch {}
})

// ── Actions ───────────────────────────────────────────────────────────────────
async function loadIndexTickers(name) {
  if (indexTickersCache.value[name]) return
  try {
    const res = await axios.get('/api/markets/scan/index-tickers', { params: { index: name } })
    indexTickersCache.value = { ...indexTickersCache.value, [name]: res.data.response_data }
  } catch {}
}

async function selectIndex(name) {
  selectedIndex.value = name
  if (name !== 'custom') await loadIndexTickers(name)
}

function setSortBy(col) {
  sortBy.value = col
}

async function runScan() {
  const tickers = tickerList.value
  if (!tickers.length) return
  scanning.value     = true
  scanError.value    = null
  scanned.value      = false
  rawResults.value   = []
  scanProgress.value = 0

  // Progression simulée : les 10 workers traitent ~10 tickers/s
  const total    = tickers.length
  const ticksPerSec = 10
  const interval = setInterval(() => {
    if (scanProgress.value < total - ticksPerSec) scanProgress.value += ticksPerSec
  }, 1000)

  try {
    const res = await axios.post('/api/markets/scan', {
      tickers,
      weights:    loadWeights(),
      thresholds: loadThresholds(),
      min_score:  minScore.value,
    }, { timeout: 300_000 })   // 5 min max pour les gros indices
    rawResults.value   = res.data.response_data
    scanProgress.value = total
    scanned.value      = true
    lastScanAt.value   = new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  } catch (err) {
    scanError.value = err.response?.data?.response_data || 'Erreur lors du scan.'
  } finally {
    clearInterval(interval)
    scanning.value = false
  }
}

async function addToWatchlist(stock) {
  try {
    await axios.post('/api/markets/watchlist', { ticker: stock.ticker })
    watchlistTickers.value = new Set([...watchlistTickers.value, stock.ticker])
  } catch {}
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(value, unit = '') {
  if (value == null) return '—'
  return `${value}${unit}`
}

function ratingClass(type, value) {
  if (value == null) return ''
  if (type === 'pe') {
    if (value < 15) return 'positive'
    if (value < 25) return 'neutral'
    return 'negative'
  }
  if (type === 'roe') {
    if (value >= 15) return 'positive'
    if (value >= 5)  return 'neutral'
    return 'negative'
  }
  if (type === 'margin') {
    if (value >= 20) return 'positive'
    if (value >= 5)  return 'neutral'
    return 'negative'
  }
  return ''
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

/* ── Config panel ── */
.config-panel {
  background: #1e293b;
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 24px;
  margin-bottom: 28px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.config-row { display: flex; flex-direction: column; gap: 8px; }
.config-label { font-size: 12px; font-weight: 600; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }

.index-pills { display: flex; flex-wrap: wrap; gap: 8px; }
.pill {
  background: rgba(148,163,184,0.08);
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 20px;
  padding: 5px 16px;
  font-size: 13px;
  font-weight: 600;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.2s;
}
.pill:hover  { background: rgba(59,130,246,0.15); border-color: #3b82f6; color: #93c5fd; }
.pill.active { background: #3b82f6; border-color: #3b82f6; color: #fff; }
.pill-count {
  display: inline-block;
  background: rgba(255,255,255,0.15);
  border-radius: 10px;
  padding: 0 6px;
  font-size: 10px;
  font-weight: 700;
  margin-left: 5px;
  vertical-align: middle;
}

.ticker-textarea {
  background: #0b1220;
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px;
  padding: 10px 14px;
  color: #e5e7eb;
  font-size: 14px;
  resize: vertical;
  font-family: ui-monospace, monospace;
  outline: none;
  transition: border-color 0.2s;
}
.ticker-textarea:focus { border-color: #3b82f6; }

.ticker-preview { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; max-height: 120px; overflow-y: auto; }
.ticker-chip {
  background: rgba(59,130,246,0.12);
  border: 1px solid rgba(59,130,246,0.3);
  border-radius: 6px;
  padding: 2px 8px;
  font-size: 11px;
  font-weight: 700;
  color: #93c5fd;
  letter-spacing: 0.04em;
}
.ticker-chip.more {
  background: rgba(100,116,139,0.15);
  border-color: rgba(100,116,139,0.3);
  color: #64748b;
}
.ticker-count-inline { font-size: 12px; color: #3b82f6; font-weight: 700; }
.eta { font-size: 12px; color: #475569; }
.loading-dot { font-size: 11px; color: #3b82f6; font-weight: 400; margin-left: 6px; }

/* ── Filtres ── */
.config-filters { display: flex; gap: 24px; flex-wrap: wrap; }
.filter-block { display: flex; flex-direction: column; gap: 8px; min-width: 180px; }

.score-slider-wrap { display: flex; align-items: center; gap: 12px; }
.slider {
  -webkit-appearance: none;
  width: 180px;
  height: 4px;
  border-radius: 2px;
  background: rgba(148,163,184,0.2);
  outline: none;
}
.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 16px; height: 16px;
  border-radius: 50%;
  background: #3b82f6;
  cursor: pointer;
}
.score-value {
  font-size: 15px;
  font-weight: 700;
  min-width: 50px;
}

.sector-select {
  background: #0b1220;
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px;
  padding: 7px 12px;
  color: #e5e7eb;
  font-size: 13px;
  outline: none;
  cursor: pointer;
}

/* ── Actions ── */
.config-actions { display: flex; align-items: center; gap: 16px; padding-top: 4px; }
.btn-scan {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 11px 28px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.2s;
  white-space: nowrap;
}
.btn-scan:hover:not(:disabled) { background: #2563eb; }
.btn-scan:disabled { opacity: 0.5; cursor: not-allowed; }

.spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }

.last-scan { font-size: 12px; color: #475569; }

.error-banner {
  background: rgba(239,68,68,0.15);
  border: 1px solid rgba(239,68,68,0.4);
  border-radius: 8px;
  padding: 10px 16px;
  color: #fca5a5;
  font-size: 13px;
}

/* ── Résultats ── */
.results-section { display: flex; flex-direction: column; gap: 12px; }
.results-meta { font-size: 13px; color: #64748b; }
.filter-note { margin-left: 6px; color: #475569; }

.table-scroll { overflow-x: auto; }
.scan-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 800px; }
.scan-table th {
  background: #1e293b;
  padding: 10px 14px;
  text-align: left;
  color: #94a3b8;
  font-weight: 600;
  border-bottom: 1px solid rgba(148,163,184,0.15);
  white-space: nowrap;
}
.scan-table th.sortable { cursor: pointer; user-select: none; }
.scan-table th.sortable:hover { color: #e2e8f0; }
.sort-arrow { color: #3b82f6; margin-left: 2px; }
.scan-table td {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(148,163,184,0.07);
  white-space: nowrap;
  font-weight: 600;
}
.scan-table tr:hover td { background: rgba(148,163,184,0.04); }

.ticker-badge {
  background: #3b82f6;
  color: #fff;
  border-radius: 6px;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
}
.col-name     { color: #cbd5e1; font-weight: 400; }
.col-meta     { color: #64748b; font-weight: 400; }
.col-price    { color: #f1f5f9; }
.col-currency { color: #64748b; font-size: 11px; margin-left: 3px; font-weight: 400; }

.change-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
}
.change-pill.positive { background: rgba(74,222,128,0.12); color: #4ade80; }
.change-pill.negative { background: rgba(248,113,113,0.12); color: #f87171; }

.positive { color: #4ade80; }
.neutral  { color: #facc15; }
.negative { color: #f87171; }

.score-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
}
.score-good { color: #4ade80; background: rgba(74,222,128,0.12); }
.score-mid  { color: #facc15; background: rgba(250,204,21,0.12);  }
.score-bad  { color: #f87171; background: rgba(248,113,113,0.12); }

.btn-add {
  background: rgba(74,222,128,0.1);
  border: 1px solid rgba(74,222,128,0.3);
  color: #4ade80;
  border-radius: 6px;
  width: 28px; height: 28px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.btn-add:hover:not(:disabled) { background: rgba(74,222,128,0.2); }
.btn-add:disabled { opacity: 0.4; cursor: default; color: #4ade80; }

/* ── États vides ── */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 64px 32px;
  border: 1px dashed rgba(148,163,184,0.2);
  border-radius: 16px;
  background: rgba(15,23,42,0.4);
  text-align: center;
}
.empty-icon { font-size: 52px; }
.empty-state h2 { margin: 0; font-size: 20px; color: #cbd5e1; }
.empty-state p { margin: 0; color: #6b7280; font-size: 14px; line-height: 1.6; }
.hint { font-size: 12px !important; color: #475569 !important; margin-top: 4px !important; }
.link { color: #60a5fa; text-decoration: none; }
.link:hover { text-decoration: underline; }
</style>
