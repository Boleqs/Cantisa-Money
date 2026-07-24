<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Gestion Fiscale</h1>
        <p class="subtitle">Centre fiscal — vue d'ensemble de votre situation.</p>
      </div>
      <button class="btn" :disabled="loading" @click="reload">
        <span v-if="!loading">↻ Rafraîchir</span>
        <span v-else>Chargement…</span>
      </button>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <template v-if="result">
      <div v-if="!result.regime.is_verified" class="banner warn">
        ⚠️ Barème par défaut non vérifié pour « {{ result.regime.name }} » — merci de contrôler les tranches.
        <router-link to="/fiscalite/regime">Vérifier le régime</router-link>
      </div>
      <div v-if="result.household.profile_missing" class="banner info">
        ℹ️ Aucun profil de foyer pour {{ currentYear }} — le calcul suppose 1 part.
        <router-link to="/fiscalite/foyer">Renseigner le foyer</router-link>
      </div>

      <div class="kpi-row">
        <div class="kpi-card kpi-card--featured">
          <div class="kpi-label">IR net estimé — {{ currentYear }}</div>
          <div class="kpi-value">{{ fmtAmount(result.computation.net_tax_estimated) }}</div>
          <div class="kpi-sub">Régime « {{ result.regime.name }} »</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Revenu imposable</div>
          <div class="kpi-value">{{ fmtAmount(result.income.taxable_income_total) }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Parts fiscales</div>
          <div class="kpi-value">{{ result.household.parts.toFixed(1) }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Catégories taguées fiscalement</div>
          <div class="kpi-value">{{ taggedCategoriesCount }} / {{ totalCategoriesCount }}</div>
          <div class="kpi-sub"><router-link to="/categories">Gérer les catégories</router-link></div>
        </div>
      </div>
    </template>

    <div class="nav-grid">
      <router-link to="/fiscalite/simulateur" class="nav-card">
        <div class="nav-icon">📊</div>
        <div class="nav-title">Simulateur d'impôt</div>
        <div class="nav-desc">Détail complet du calcul de l'IR, année par année.</div>
      </router-link>
      <router-link to="/fiscalite/regime" class="nav-card">
        <div class="nav-icon">⚖️</div>
        <div class="nav-title">Régime fiscal</div>
        <div class="nav-desc">Barème, tranches, décote et plafonnement du quotient familial.</div>
      </router-link>
      <router-link to="/fiscalite/foyer" class="nav-card">
        <div class="nav-icon">🏠</div>
        <div class="nav-title">Foyer fiscal</div>
        <div class="nav-desc">Parts, personnes à charge, revenus du conjoint.</div>
      </router-link>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const currentYear = new Date().getFullYear()
const loading = ref(false)
const error = ref('')
const result = ref(null)
const taggedCategoriesCount = ref(0)
const totalCategoriesCount = ref(0)

function fmtAmount(v) {
  const n = Number(v ?? 0)
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + ' ' + (result.value?.currency || '')
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [simRes, catRes] = await Promise.all([
      axios.get('/api/tax/simulate', { params: { year: currentYear } }),
      axios.get('/api/categories'),
    ])
    result.value = simRes.data?.response_data || null
    const cats = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
    totalCategoriesCount.value = cats.length
    taggedCategoriesCount.value = cats.filter(c => c.tax_treatment).length
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

onMounted(() => reload())
</script>

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
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; }

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 8px 14px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
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

.banner {
  padding: 12px 16px;
  border-radius: 12px;
  font-size: 13px;
}
.banner.warn { background: rgba(245,158,11,0.08); border: 1px solid rgba(245,158,11,0.3); color: #fde68a; }
.banner.info { background: rgba(96,165,250,0.08); border: 1px solid rgba(96,165,250,0.3); color: #93c5fd; }
.banner a { color: inherit; font-weight: 600; text-decoration: underline; margin-left: 4px; }

.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
@media (max-width: 900px) { .kpi-row { grid-template-columns: repeat(2, 1fr); } }
.kpi-card {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 18px 20px;
}
.kpi-card--featured { border-color: rgba(37,99,235,0.35); background: rgba(37,99,235,0.06); }
.kpi-label { font-size: 12px; color: #9ca3af; margin-bottom: 6px; }
.kpi-value { font-size: 22px; font-weight: 700; font-variant-numeric: tabular-nums; }
.kpi-sub { font-size: 11px; color: #4b5563; margin-top: 4px; }
.kpi-sub a { color: #60a5fa; text-decoration: none; }
.kpi-sub a:hover { text-decoration: underline; }

.nav-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
@media (max-width: 800px) { .nav-grid { grid-template-columns: 1fr; } }
.nav-card {
  display: block;
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 20px;
  text-decoration: none;
  color: inherit;
  transition: border-color 0.15s, background 0.15s;
}
.nav-card:hover { border-color: rgba(96,165,250,0.4); background: rgba(37,99,235,0.06); }
.nav-icon { font-size: 24px; margin-bottom: 8px; }
.nav-title { font-size: 15px; font-weight: 700; margin-bottom: 4px; }
.nav-desc { font-size: 12px; color: #9ca3af; }
</style>
