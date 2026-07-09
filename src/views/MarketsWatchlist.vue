<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Watchlist</h1>
        <p class="subtitle">Suivez les actions qui vous intéressent en un coup d'œil.</p>
      </div>
    </header>

    <!-- Barre d'ajout -->
    <div class="search-bar">
      <div class="search-input-wrap">
        <input
          v-model="watchlistInput"
          @keydown.enter="addToWatchlist"
          type="text"
          placeholder="Ticker (ex : AAPL, MC.PA, AIR.PA)..."
          class="search-input"
          :disabled="wlLoading"
        />
        <button @click="addToWatchlist" class="btn-search" :disabled="wlLoading || !watchlistInput.trim()">
          {{ wlLoading ? 'Chargement…' : 'Ajouter' }}
        </button>
      </div>
      <p class="search-hint">Ajoutez des tickers pour les retrouver ici à chaque visite.</p>
    </div>

    <div v-if="wlError" class="error-banner">{{ wlError }}</div>

    <!-- Tableau watchlist -->
    <div v-if="watchlist.length" class="watchlist-section">
      <div class="watchlist-meta">
        {{ watchlist.length }} action{{ watchlist.length > 1 ? 's' : '' }} suivie{{ watchlist.length > 1 ? 's' : '' }}
      </div>
      <div class="table-scroll">
        <table class="wl-table">
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Nom</th>
              <th>Secteur</th>
              <th>Prix</th>
              <th>Variation</th>
              <th>P/E</th>
              <th>ROE</th>
              <th>Marge nette</th>
              <th>Dividende</th>
              <th>Score</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in watchlist" :key="s.ticker">
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
                >
                  {{ s.day_change_pct >= 0 ? '+' : '' }}{{ s.day_change_pct }}%
                </span>
                <span v-else class="col-meta">—</span>
              </td>
              <td :class="ratingClass('pe', s.pe_trailing)">{{ fmt(s.pe_trailing) }}</td>
              <td :class="ratingClass('roe', s.roe)">{{ fmt(s.roe, '%') }}</td>
              <td :class="ratingClass('margin', s.net_margin)">{{ fmt(s.net_margin, '%') }}</td>
              <td class="positive">{{ fmt(s.dividend_yield, '%') }}</td>
              <td>
                <span
                  v-if="getScore(s).score !== null"
                  class="score-badge"
                  :class="scoreClass(getScore(s).score)"
                >{{ getScore(s).score }}/10</span>
                <span v-else class="col-meta">—</span>
              </td>
              <td>
                <button class="btn-remove" @click="removeFromWatchlist(s.ticker)" title="Retirer">✕</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- État vide -->
    <div v-else-if="!wlLoading" class="empty-state">
      <div class="empty-icon">👁</div>
      <h2>Votre watchlist est vide</h2>
      <p>Ajoutez des actions à surveiller pour les retrouver ici rapidement.</p>
      <div class="ticker-examples">
        <span v-for="ex in examples" :key="ex" class="example-chip" @click="quickAdd(ex)">{{ ex }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { loadWeights, loadThresholds, computeScore, scoreClass } from '@/utils/marketScore.js'

const weights    = ref({})
const thresholds = ref({})

function getScore(stock) { return computeScore(stock, weights.value, thresholds.value) }

const watchlistInput = ref('')
const wlLoading = ref(false)
const wlError = ref(null)
const watchlist = ref([])

const examples = ['AAPL', 'MC.PA', 'AIR.PA', 'MSFT', 'NVDA', 'TTE.PA']

onMounted(async () => {
  weights.value    = loadWeights()
  thresholds.value = loadThresholds()
  await fetchWatchlist()
})

async function fetchWatchlist() {
  wlLoading.value = true
  wlError.value = null
  try {
    const res = await axios.get('/api/markets/watchlist')
    watchlist.value = res.data.response_data
  } catch (err) {
    wlError.value = err.response?.data?.response_data || 'Impossible de charger la watchlist.'
  } finally {
    wlLoading.value = false
  }
}

async function addToWatchlist() {
  const ticker = watchlistInput.value.trim().toUpperCase()
  if (!ticker) return
  if (watchlist.value.find(r => r.ticker === ticker)) {
    wlError.value = `${ticker} est déjà dans la watchlist.`
    return
  }
  wlError.value = null
  wlLoading.value = true
  try {
    await axios.post('/api/markets/watchlist', { ticker })
    const res = await axios.get('/api/markets/analyse', { params: { ticker } })
    watchlist.value.push(res.data.response_data)
    watchlistInput.value = ''
  } catch (err) {
    wlError.value = err.response?.data?.response_data || `Impossible d'ajouter "${ticker}".`
  } finally {
    wlLoading.value = false
  }
}

function quickAdd(ticker) {
  watchlistInput.value = ticker
  addToWatchlist()
}

async function removeFromWatchlist(ticker) {
  try {
    await axios.delete(`/api/markets/watchlist/${ticker}`)
    watchlist.value = watchlist.value.filter(r => r.ticker !== ticker)
  } catch (err) {
    wlError.value = err.response?.data?.response_data || `Impossible de retirer "${ticker}".`
  }
}

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

.watchlist-section { display: flex; flex-direction: column; gap: 12px; }
.watchlist-meta { font-size: 13px; color: #64748b; }

.table-scroll { overflow-x: auto; }
.wl-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 700px; }
.wl-table th {
  background: #1e293b;
  padding: 10px 14px;
  text-align: left;
  color: #94a3b8;
  font-weight: 600;
  border-bottom: 1px solid rgba(148,163,184,0.15);
  white-space: nowrap;
}
.wl-table td {
  padding: 10px 14px;
  border-bottom: 1px solid rgba(148,163,184,0.07);
  white-space: nowrap;
  font-weight: 600;
}
.wl-table tr:hover td { background: rgba(148,163,184,0.04); }

.ticker-badge {
  background: #3b82f6;
  color: #fff;
  border-radius: 6px;
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.05em;
}
.col-name { color: #cbd5e1; font-weight: 400; }
.col-meta { color: #64748b; font-weight: 400; }
.col-price { color: #f1f5f9; }
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
  white-space: nowrap;
}
.score-good { color: #4ade80; background: rgba(74,222,128,0.12); }
.score-mid  { color: #facc15; background: rgba(250,204,21,0.12);  }
.score-bad  { color: #f87171; background: rgba(248,113,113,0.12); }

.btn-remove {
  background: none;
  border: none;
  color: #475569;
  cursor: pointer;
  font-size: 13px;
  padding: 2px 6px;
  border-radius: 4px;
  transition: color 0.2s, background 0.2s;
}
.btn-remove:hover { color: #ef4444; background: rgba(239,68,68,0.1); }

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
