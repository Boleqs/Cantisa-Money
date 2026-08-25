<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import WorldMap from '../components/graphs/WorldMap.vue'

const loading = ref(false)
const error = ref('')

// Répartition géographique (carte) : périmètre portefeuille (financier + physique) — /assets/geography.
const countries = ref([])
const unmappedPercent = ref(0)

// Portail de diversification (patrimoine global : cash + portefeuille + physique) — /assets/diversification.
const diversification = ref(null)
const displayCurrency = ref('EUR')

// Palette catégorielle (skill dataviz, référence dark) — ordre fixe, jamais réassigné par valeur.
const SERIES_COLORS = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767']
function seriesColor(i) {
  return SERIES_COLORS[i % SERIES_COLORS.length]
}

function scoreTier(score) {
  if (score == null) return { label: 'N/A', color: '#6b7280' }
  if (score < 40) return { label: 'Faible', color: '#d03b3b' }
  if (score < 65) return { label: 'Modérée', color: '#fab219' }
  if (score < 85) return { label: 'Bonne', color: '#0ca30c' }
  return { label: 'Excellente', color: '#0ca30c' }
}

const globalTier = computed(() => scoreTier(diversification.value?.global_score))

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [geoRes, divRes] = await Promise.all([
      axios.get('/api/assets/geography'),
      axios.get('/api/assets/diversification'),
    ])
    const geoData = geoRes.data?.response_data
    countries.value = Array.isArray(geoData?.countries) ? geoData.countries : []
    unmappedPercent.value = geoData?.unmapped_percent ?? 0

    diversification.value = divRes.data?.response_data ?? null
    displayCurrency.value = diversification.value?.display_currency || 'EUR'
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur lors du chargement de la diversification'
  } finally {
    loading.value = false
  }
}

onMounted(() => reload())
</script>

<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Diversification du patrimoine</h1>
        <p class="subtitle">
          Vue consolidée de la diversification par classe d'actif, secteur et pays, sur l'ensemble de votre
          patrimoine (liquidités, portefeuille et actifs physiques) — pas seulement le portefeuille financier.
          Pour une action, le secteur/pays vient directement de Yahoo Finance ; pour un ETF, du top 10 des
          positions extrapolé à la valeur totale (Yahoo ne fournit jamais la composition complète d'un fonds) ;
          pour un actif physique, du pays renseigné manuellement.
        </p>
      </div>
      <button class="btn" :disabled="loading" @click="reload">
        <span v-if="!loading">↻ Actualiser</span>
        <span v-else>Calcul…</span>
      </button>
    </header>

    <div v-if="error" class="alert">{{ error }}</div>

    <div v-if="loading && !diversification" class="empty card">
      Calcul en cours (interrogation de Yahoo Finance pour chaque action/ETF détenu)…
    </div>

    <template v-else-if="diversification">
      <div class="card score-card">
        <div class="score-ring" :style="{ '--ring-color': globalTier.color }">
          <span class="score-value">{{ diversification.global_score ?? '—' }}</span>
          <span class="score-max">/100</span>
        </div>
        <div class="score-text">
          <div class="score-title">Note globale de diversification</div>
          <div class="score-tier" :style="{ color: globalTier.color }">{{ globalTier.label }}</div>
          <p class="score-hint">
            Moyenne des scores classe d'actif / secteur / pays ci-dessous, chacun basé sur l'indice de
            Herfindahl-Hirschman (concentration des parts) — 100 = très étalé sur de nombreuses parts égales,
            0 = tout concentré sur une seule. Patrimoine total considéré :
            <strong>{{ new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 0, maximumFractionDigits: 0 }).format(diversification.total_patrimoine) }} {{ displayCurrency }}</strong>.
          </p>
        </div>
      </div>

      <div class="dim-grid">
        <div class="card">
          <div class="dim-header">
            <div class="card-title">Classe d'actif</div>
            <div class="dim-score" :style="{ color: scoreTier(diversification.asset_class.score).color }">
              {{ diversification.asset_class.score ?? '—' }}<span class="dim-score-max">/100</span>
            </div>
          </div>
          <div v-if="!diversification.asset_class.buckets.length" class="empty">Aucune donnée.</div>
          <div v-else class="bars">
            <div v-for="(b, i) in diversification.asset_class.buckets" :key="b.label" class="bar-row">
              <div class="bar-label">{{ b.label }}</div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: b.percent + '%', background: seriesColor(i) }"></div>
              </div>
              <div class="bar-percent">{{ b.percent }}%</div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="dim-header">
            <div class="card-title">Secteur (actions/ETF)</div>
            <div class="dim-score" :style="{ color: scoreTier(diversification.sector.score).color }">
              {{ diversification.sector.score ?? '—' }}<span class="dim-score-max">/100</span>
            </div>
          </div>
          <div v-if="!diversification.sector.buckets.length" class="empty">Aucune donnée.</div>
          <div v-else class="bars">
            <div v-for="(b, i) in diversification.sector.buckets" :key="b.label" class="bar-row">
              <div class="bar-label">{{ b.label }}</div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: b.percent + '%', background: seriesColor(i) }"></div>
              </div>
              <div class="bar-percent">{{ b.percent }}%</div>
            </div>
          </div>
        </div>

        <div class="card">
          <div class="dim-header">
            <div class="card-title">Répartition géographique</div>
            <div class="dim-score" :style="{ color: scoreTier(diversification.geography.score).color }">
              {{ diversification.geography.score ?? '—' }}<span class="dim-score-max">/100</span>
            </div>
          </div>
          <div v-if="!diversification.geography.buckets.length" class="empty">Aucune donnée.</div>
          <div v-else class="bars">
            <div v-for="(b, i) in diversification.geography.buckets" :key="b.label" class="bar-row">
              <div class="bar-label">{{ b.label }}</div>
              <div class="bar-track">
                <div class="bar-fill" :style="{ width: b.percent + '%', background: seriesColor(i) }"></div>
              </div>
              <div class="bar-percent">{{ b.percent }}%</div>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Exposition par pays — portefeuille (financier + physique)</div>
        <div v-if="!countries.length" class="empty">Aucun actif avec un pays identifiable pour l'instant.</div>
        <WorldMap v-else :countries="countries" :unmapped-percent="unmappedPercent" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.page {
  padding: 28px;
  color: #e5e7eb;
  background: #0b1220;
  min-height: 100vh;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.page-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; font-size: 13px; color: #9ca3af; max-width: 80ch; line-height: 1.6; }

.btn {
  border: 1px solid rgba(148,163,184,0.25);
  background: rgba(15,23,42,0.7);
  color: #e5e7eb;
  padding: 8px 14px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  flex-shrink: 0;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }

.alert {
  border: 1px solid rgba(239,68,68,0.4);
  background: rgba(239,68,68,0.08);
  padding: 10px 14px;
  border-radius: 10px;
  color: #fca5a5;
  font-size: 13px;
}

.card {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 18px 20px;
}
.card-title { font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 14px; }

.empty { font-size: 13px; color: #6b7280; }

.score-card {
  display: flex;
  align-items: center;
  gap: 28px;
}
.score-ring {
  flex-shrink: 0;
  width: 108px;
  height: 108px;
  border-radius: 50%;
  border: 6px solid var(--ring-color);
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 2px;
}
.score-value { font-size: 32px; font-weight: 700; color: #f1f5f9; font-variant-numeric: tabular-nums; }
.score-max { font-size: 13px; color: #6b7280; }
.score-title { font-size: 15px; font-weight: 600; color: #f1f5f9; }
.score-tier { font-size: 13px; font-weight: 600; margin-top: 2px; }
.score-hint { margin: 8px 0 0; font-size: 12.5px; color: #9ca3af; line-height: 1.6; max-width: 70ch; }

.dim-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
}
@media (max-width: 1100px) {
  .dim-grid { grid-template-columns: 1fr; }
}

.dim-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 14px; }
.dim-header .card-title { margin-bottom: 0; }
.dim-score { font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; }
.dim-score-max { font-size: 11px; font-weight: 400; color: #6b7280; }

.bars { display: flex; flex-direction: column; gap: 10px; }
.bar-row { display: grid; grid-template-columns: 1fr 2fr auto; align-items: center; gap: 10px; }
.bar-label {
  font-size: 12.5px;
  color: #cbd5e1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.bar-track {
  height: 8px;
  border-radius: 4px;
  background: #1e293b;
  overflow: hidden;
}
.bar-fill { height: 100%; border-radius: 4px; }
.bar-percent { font-size: 12px; color: #9ca3af; font-variant-numeric: tabular-nums; text-align: right; min-width: 42px; }
</style>
