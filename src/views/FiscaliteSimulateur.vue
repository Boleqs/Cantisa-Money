<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Simulateur d'impôt</h1>
        <p class="subtitle">Estimation de l'impôt sur le revenu à partir des données suivies dans l'app.</p>
      </div>
      <div class="header-actions">
        <label class="year-picker">Année
          <select v-model.number="selectedYear" @change="reload">
            <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}</option>
          </select>
        </label>
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Recalculer</span>
          <span v-else>Calcul…</span>
        </button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !result" class="empty">Calcul en cours…</div>

    <template v-else-if="result">
      <div v-if="!result.regime.is_verified" class="banner warn">
        ⚠️ Barème par défaut non vérifié — merci de contrôler les tranches dans
        <router-link to="/fiscalite/regime">Régime fiscal</router-link>.
      </div>
      <div v-if="result.household.profile_missing" class="banner info">
        ℹ️ Aucun profil de foyer pour {{ selectedYear }} — calcul avec 1 part par défaut.
        <router-link to="/fiscalite/foyer">Renseigner le foyer</router-link>.
      </div>

      <div class="kpi-row">
        <div class="kpi-card kpi-card--featured">
          <div class="kpi-label">IR net estimé</div>
          <div class="kpi-value">{{ fmtAmount(result.computation.net_tax_estimated) }}</div>
          <div class="kpi-sub">{{ result.regime.name }} — {{ selectedYear }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Revenu imposable total</div>
          <div class="kpi-value">{{ fmtAmount(result.income.taxable_income_total) }}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Parts fiscales</div>
          <div class="kpi-value">{{ result.household.parts.toFixed(1) }}</div>
          <div class="kpi-sub">{{ result.household.adults }} adulte(s), {{ result.household.dependents }} personne(s) à charge</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">Taux marginal</div>
          <div class="kpi-value">{{ (result.computation.marginal_rate * 100).toFixed(0) }} %</div>
        </div>
      </div>

      <div class="cols">
        <div class="card">
          <div class="card-title">Détail du revenu imposable</div>
          <table class="table">
            <tbody>
              <tr><td>Revenus imposables (catégories taguées)</td><td class="num pos">+ {{ fmtAmount(result.income.taxable_income_tracked) }}</td></tr>
              <tr><td>Charges déductibles</td><td class="num neg">− {{ fmtAmount(result.income.deductible_tracked) }}</td></tr>
              <tr><td>Revenu foncier net</td><td class="num">{{ fmtAmount(result.income.real_estate_net) }}</td></tr>
              <tr><td>Revenus supplémentaires du foyer</td><td class="num">{{ fmtAmount(result.income.extra_household_income) }}</td></tr>
              <tr class="total-row"><td>Total imposable</td><td class="num">{{ fmtAmount(result.income.taxable_income_total) }}</td></tr>
            </tbody>
          </table>
        </div>

        <div class="card">
          <div class="card-title">Détail du calcul</div>
          <table class="table">
            <tbody>
              <tr><td>Quotient (revenu / parts)</td><td class="num">{{ fmtAmount(result.computation.quotient) }}</td></tr>
              <tr><td>Impôt brut (avant plafonnement)</td><td class="num">{{ fmtAmount(result.computation.gross_tax_before_qf_cap) }}</td></tr>
              <tr v-if="result.computation.quotient_familial_cap_applied">
                <td>Plafonnement du quotient familial appliqué</td><td class="num warn-text">oui</td>
              </tr>
              <tr><td>Impôt brut retenu</td><td class="num">{{ fmtAmount(result.computation.gross_tax) }}</td></tr>
              <tr><td>Décote</td><td class="num neg">− {{ fmtAmount(result.computation.decote_amount) }}</td></tr>
              <tr class="total-row"><td>IR net estimé</td><td class="num">{{ fmtAmount(result.computation.net_tax_estimated) }}</td></tr>
            </tbody>
          </table>
        </div>

        <div class="card">
          <div class="card-title">Plus-values réalisées (PFU)</div>
          <div v-if="!result.capital_gains || result.capital_gains.disposal_count === 0" class="empty-note">
            Aucune cession réalisée sur {{ selectedYear }}.
          </div>
          <table v-else class="table">
            <tbody>
              <tr><td>Plus-value totale réalisée</td><td class="num">{{ fmtAmount(result.capital_gains.total_realized_gain) }}</td></tr>
              <tr><td>Part exonérée (PEA)</td><td class="num neg">− {{ fmtAmount(result.capital_gains.exempt_gain_pea) }}</td></tr>
              <tr><td>Base imposable</td><td class="num">{{ fmtAmount(result.capital_gains.taxable_gain) }}</td></tr>
              <tr><td>Impôt PFU ({{ (result.capital_gains.pfu_income_rate * 100).toFixed(1) }} %)</td><td class="num">{{ fmtAmount(result.capital_gains.pfu_income_tax_due) }}</td></tr>
              <tr><td>Prélèvements sociaux ({{ (result.capital_gains.pfu_social_rate * 100).toFixed(1) }} %)</td><td class="num">{{ fmtAmount(result.capital_gains.pfu_social_tax_due) }}</td></tr>
              <tr class="total-row"><td>Total dû</td><td class="num">{{ fmtAmount(result.capital_gains.pfu_total_due) }}</td></tr>
              <tr v-if="result.capital_gains.unknown_cost_basis_count">
                <td colspan="2" class="warn-text">
                  ⚠️ {{ result.capital_gains.unknown_cost_basis_count }} cession(s) sans coût d'achat connu, exclue(s) du calcul.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const currentYear = new Date().getFullYear()
const yearOptions = [currentYear - 1, currentYear, currentYear + 1]
const selectedYear = ref(currentYear)

const loading = ref(false)
const error = ref('')
const result = ref(null)

function fmtAmount(v) {
  const n = Number(v ?? 0)
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + ' ' + (result.value?.currency || '')
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get('/api/tax/simulate', { params: { year: selectedYear.value } })
    result.value = res.data?.response_data || null
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
.header-actions { display: flex; gap: 10px; align-items: center; }

.year-picker { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: #9ca3af; }
.year-picker select {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px;
  padding: 8px 10px;
  color: #e5e7eb;
}

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
.empty { font-size: 13px; color: #4b5563; }

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

.cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
@media (max-width: 800px) { .cols { grid-template-columns: 1fr; } }

.card {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 18px 20px;
}
.card-title { font-size: 13px; font-weight: 600; color: #cbd5e1; margin-bottom: 14px; }
.empty-note { font-size: 13px; color: #4b5563; }

.table { width: 100%; border-collapse: collapse; font-size: 13px; }
.table td { padding: 8px 0; border-bottom: 1px solid rgba(148,163,184,0.08); }
.table .num { text-align: right; font-variant-numeric: tabular-nums; }
.table .pos { color: #4ade80; }
.table .neg { color: #f87171; }
.table .warn-text { color: #fbbf24; }
.total-row td { border-top: 1px solid rgba(148,163,184,0.25); border-bottom: none; font-weight: 700; padding-top: 10px; }
</style>
