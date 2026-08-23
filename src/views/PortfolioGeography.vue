<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import WorldMap from '../components/graphs/WorldMap.vue'

const loading = ref(false)
const error = ref('')
const countries = ref([])
const unmappedPercent = ref(0)
const displayCurrency = ref('EUR')

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.get('/api/assets/geography')
    const rd = data?.response_data
    countries.value = Array.isArray(rd?.countries) ? rd.countries : []
    unmappedPercent.value = rd?.unmapped_percent ?? 0
    displayCurrency.value = rd?.display_currency || 'EUR'
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur lors du chargement de la répartition géographique'
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
        <h1>Répartition géographique</h1>
        <p class="subtitle">
          Pondération par pays de l'ensemble de votre patrimoine. Pour une action, le pays vient directement
          de l'émetteur (Yahoo Finance) ; pour un ETF, Yahoo Finance ne fournit jamais sa composition complète
          — seulement son <strong>top 10 des positions</strong>, dont on extrapole la répartition pays à la
          valeur totale du fonds (approximation, pas une composition exacte). Pour un actif physique
          (immobilier, véhicule…), le pays est celui renseigné manuellement sur la fiche de l'actif.
        </p>
      </div>
      <button class="btn" :disabled="loading" @click="reload">
        <span v-if="!loading">↻ Actualiser</span>
        <span v-else>Calcul…</span>
      </button>
    </header>

    <div v-if="error" class="alert">{{ error }}</div>

    <div class="card">
      <div class="card-title">Exposition par pays</div>
      <div v-if="loading && !countries.length" class="empty">Calcul en cours (interrogation de Yahoo Finance pour chaque ETF détenu)…</div>
      <div v-else-if="!countries.length" class="empty">Aucun actif avec un pays identifiable pour l'instant.</div>
      <WorldMap v-else :countries="countries" :unmapped-percent="unmappedPercent" />
    </div>
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
</style>
