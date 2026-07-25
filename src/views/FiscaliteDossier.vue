<template>
  <div class="page">
    <header class="page-header no-print">
      <div class="title-block">
        <h1>Dossier fiscal</h1>
        <p class="subtitle">Document récapitulatif imprimable pour l'année fiscale sélectionnée.</p>
      </div>
      <div class="header-actions">
        <label class="year-picker">Année
          <select v-model.number="selectedYear" @change="reload">
            <option v-for="y in yearOptions" :key="y" :value="y">{{ y }}</option>
          </select>
        </label>
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn btn-primary" :disabled="loading || !simulate" @click="print">🖨 Imprimer / Exporter PDF</button>
      </div>
    </header>

    <div v-if="error" class="alert no-print"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !simulate" class="empty no-print">Chargement…</div>

    <div v-else-if="simulate" class="dossier">
      <div class="dossier-header">
        <div>
          <h2>Dossier fiscal — {{ selectedYear }}</h2>
          <p class="dossier-sub">{{ simulate.regime.name }} — généré le {{ generatedAtLabel }}</p>
        </div>
        <div class="dossier-total-box">
          <div class="dossier-total-label">Total estimé dû (IR + PFU)</div>
          <div class="dossier-total-value">{{ fmtAmount(totalDue) }}</div>
        </div>
      </div>

      <div class="banner warn" v-if="!simulate.regime.is_verified">
        ⚠️ Le barème utilisé est une valeur par défaut non vérifiée — merci de contrôler les tranches dans « Régime fiscal » avant toute utilisation officielle.
      </div>
      <div class="banner info" v-if="simulate.household.profile_missing">
        ℹ️ Aucun profil de foyer renseigné pour {{ selectedYear }} — ce dossier utilise 1 part par défaut.
      </div>
      <div class="banner warn" v-if="simulate.regime.year_mismatch">
        ⚠️ Le régime actif ({{ simulate.regime.tax_year }}) ne correspond pas à l'année sélectionnée ({{ selectedYear }}).
      </div>

      <section class="dossier-section">
        <h3>Foyer fiscal</h3>
        <table class="dossier-table">
          <tbody>
            <tr><td>Composition</td><td class="num">{{ simulate.household.adults }} adulte(s), {{ simulate.household.dependents }} personne(s) à charge{{ household.dependents_disabled ? ` (dont ${household.dependents_disabled} en situation de handicap)` : '' }}</td></tr>
            <tr><td>Parent isolé</td><td class="num">{{ household.parent_isole ? 'Oui' : 'Non' }}</td></tr>
            <tr><td>Parts fiscales</td><td class="num">{{ simulate.household.parts.toFixed(1) }} (référence {{ simulate.household.reference_parts.toFixed(1) }})</td></tr>
            <tr v-if="household.notes"><td>Notes</td><td class="num">{{ household.notes }}</td></tr>
          </tbody>
        </table>

        <template v-if="household.incomes && household.incomes.length">
          <h4>Revenus supplémentaires du foyer</h4>
          <table class="dossier-table">
            <thead><tr><th>Libellé</th><th>Type</th><th class="num">Montant</th></tr></thead>
            <tbody>
              <tr v-for="inc in household.incomes" :key="inc.id">
                <td>{{ inc.label }}</td>
                <td>{{ incomeTypeLabel(inc.income_type) }}</td>
                <td class="num">{{ fmtAmount(inc.amount) }}</td>
              </tr>
            </tbody>
          </table>
        </template>
      </section>

      <section class="dossier-section">
        <h3>Détail du revenu imposable</h3>
        <table class="dossier-table">
          <tbody>
            <tr><td>Revenus imposables (catégories taguées)</td><td class="num">+ {{ fmtAmount(simulate.income.taxable_income_tracked) }}</td></tr>
            <tr><td>Charges déductibles</td><td class="num">− {{ fmtAmount(simulate.income.deductible_tracked) }}</td></tr>
            <tr><td>Revenu foncier net</td><td class="num">{{ fmtAmount(simulate.income.real_estate_net) }}</td></tr>
            <tr><td>Revenus supplémentaires du foyer</td><td class="num">{{ fmtAmount(simulate.income.extra_household_income) }}</td></tr>
            <tr class="total-row"><td>Total imposable</td><td class="num">{{ fmtAmount(simulate.income.taxable_income_total) }}</td></tr>
          </tbody>
        </table>
      </section>

      <section class="dossier-section" v-if="activeRegime">
        <h3>Régime fiscal utilisé — {{ activeRegime.name }} ({{ activeRegime.country_code }}, {{ activeRegime.tax_year }})</h3>
        <table class="dossier-table">
          <thead><tr><th>Jusqu'à</th><th class="num">Taux</th></tr></thead>
          <tbody>
            <tr v-for="(b, i) in activeRegime.config.income_tax.brackets" :key="i">
              <td>{{ i === 0 ? '0' : fmtAmount(activeRegime.config.income_tax.brackets[i - 1].upper_bound) }} → {{ b.upper_bound !== null ? fmtAmount(b.upper_bound) : '∞' }}</td>
              <td class="num">{{ (b.rate * 100).toFixed(1) }} %</td>
            </tr>
          </tbody>
        </table>
        <table class="dossier-table">
          <tbody>
            <tr><td>Décote appliquée</td><td class="num">{{ activeRegime.config.income_tax.decote.enabled ? 'Oui' : 'Non' }}</td></tr>
            <tr v-if="activeRegime.config.income_tax.decote.enabled">
              <td>Seuils décote (célibataire / couple)</td>
              <td class="num">{{ fmtAmount(activeRegime.config.income_tax.decote.threshold_single) }} / {{ fmtAmount(activeRegime.config.income_tax.decote.threshold_couple) }}</td>
            </tr>
            <tr><td>Plafond par demi-part (quotient familial)</td><td class="num">{{ fmtAmount(activeRegime.config.income_tax.quotient_familial.half_part_cap) }}</td></tr>
          </tbody>
        </table>
      </section>

      <section class="dossier-section">
        <h3>Calcul de l'impôt sur le revenu</h3>
        <table class="dossier-table">
          <tbody>
            <tr><td>Quotient familial (revenu / parts)</td><td class="num">{{ fmtAmount(simulate.computation.quotient) }}</td></tr>
            <tr><td>Taux marginal</td><td class="num">{{ (simulate.computation.marginal_rate * 100).toFixed(0) }} %</td></tr>
            <tr><td>Impôt brut (avant plafonnement)</td><td class="num">{{ fmtAmount(simulate.computation.gross_tax_before_qf_cap) }}</td></tr>
            <tr v-if="simulate.computation.quotient_familial_cap_applied">
              <td>Plafonnement du quotient familial appliqué</td><td class="num">oui</td>
            </tr>
            <tr><td>Impôt brut retenu</td><td class="num">{{ fmtAmount(simulate.computation.gross_tax) }}</td></tr>
            <tr><td>Décote</td><td class="num">− {{ fmtAmount(simulate.computation.decote_amount) }}</td></tr>
            <tr class="total-row"><td>IR net estimé</td><td class="num">{{ fmtAmount(simulate.computation.net_tax_estimated) }}</td></tr>
          </tbody>
        </table>
      </section>

      <section class="dossier-section">
        <h3>Plus-values réalisées (PFU)</h3>
        <p v-if="!simulate.capital_gains || simulate.capital_gains.disposal_count === 0" class="hint">
          Aucune cession réalisée sur {{ selectedYear }}.
        </p>
        <table v-else class="dossier-table">
          <tbody>
            <tr><td>Plus-value totale réalisée</td><td class="num">{{ fmtAmount(simulate.capital_gains.total_realized_gain) }}</td></tr>
            <tr><td>Part exonérée (PEA)</td><td class="num">− {{ fmtAmount(simulate.capital_gains.exempt_gain_pea) }}</td></tr>
            <tr><td>Base imposable</td><td class="num">{{ fmtAmount(simulate.capital_gains.taxable_gain) }}</td></tr>
            <tr><td>Impôt PFU ({{ (simulate.capital_gains.pfu_income_rate * 100).toFixed(1) }} %)</td><td class="num">{{ fmtAmount(simulate.capital_gains.pfu_income_tax_due) }}</td></tr>
            <tr><td>Prélèvements sociaux ({{ (simulate.capital_gains.pfu_social_rate * 100).toFixed(1) }} %)</td><td class="num">{{ fmtAmount(simulate.capital_gains.pfu_social_tax_due) }}</td></tr>
            <tr class="total-row"><td>Total dû</td><td class="num">{{ fmtAmount(simulate.capital_gains.pfu_total_due) }}</td></tr>
            <tr v-if="simulate.capital_gains.unknown_cost_basis_count">
              <td colspan="2" class="warn-text">
                ⚠️ {{ simulate.capital_gains.unknown_cost_basis_count }} cession(s) sans coût d'achat connu, exclue(s) du calcul.
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <p class="disclaimer">
        Document généré automatiquement par Cantisa Money à partir des données saisies dans l'application. Il s'agit
        d'une estimation indicative, non contractuelle — à vérifier avant toute déclaration officielle.
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const currentYear = new Date().getFullYear()
const yearOptions = [currentYear - 1, currentYear, currentYear + 1]
const selectedYear = ref(currentYear)

const loading = ref(false)
const error = ref('')
const simulate = ref(null)
const household = ref({ adults: 1, dependents: 0, dependents_disabled: 0, parent_isole: false, notes: '', incomes: [] })
const regimes = ref([])
const generatedAt = ref(null)

const incomeTypeLabels = { salary: 'Salaire', pension: 'Pension / retraite', rental: 'Revenu locatif', other: 'Autre' }
function incomeTypeLabel(t) {
  return incomeTypeLabels[t] || t
}

const activeRegime = computed(() => regimes.value.find(r => r.id === simulate.value?.regime?.id) || null)

const totalDue = computed(() => {
  if (!simulate.value) return 0
  const ir = simulate.value.computation?.net_tax_estimated || 0
  const pfu = simulate.value.capital_gains?.pfu_total_due || 0
  return ir + pfu
})

const generatedAtLabel = computed(() => generatedAt.value ? generatedAt.value.toLocaleString('fr-FR') : '')

function fmtAmount(v) {
  const n = Number(v ?? 0)
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n) + ' ' + (simulate.value?.currency || '')
}

function print() {
  window.print()
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [simRes, houseRes, regimesRes] = await Promise.all([
      axios.get('/api/tax/simulate', { params: { year: selectedYear.value } }),
      axios.get('/api/tax/household', { params: { year: selectedYear.value } }),
      axios.get('/api/tax/regimes'),
    ])
    simulate.value = simRes.data?.response_data || null
    household.value = houseRes.data?.response_data || household.value
    regimes.value = Array.isArray(regimesRes.data?.response_data) ? regimesRes.data.response_data : []
    generatedAt.value = new Date()
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
.btn-primary { background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2)); border-color: transparent; color: #fff; }

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

.dossier {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.15);
  border-radius: 14px;
  padding: 28px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}
.dossier-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.dossier-header h2 { margin: 0; font-size: 22px; }
.dossier-sub { margin: 4px 0 0; font-size: 12px; color: #9ca3af; }
.dossier-total-box { text-align: right; }
.dossier-total-label { font-size: 11px; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.04em; }
.dossier-total-value { font-size: 24px; font-weight: 700; color: #93c5fd; }

.dossier-section { display: flex; flex-direction: column; gap: 8px; }
.dossier-section h3 { margin: 0; font-size: 14px; font-weight: 700; color: #e5e7eb; border-bottom: 1px solid rgba(148,163,184,0.15); padding-bottom: 6px; }
.dossier-section h4 { margin: 8px 0 0; font-size: 12px; font-weight: 600; color: #9ca3af; }

.dossier-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.dossier-table th { text-align: left; padding: 6px 0; color: #6b7280; font-weight: 500; border-bottom: 1px solid rgba(148,163,184,0.15); }
.dossier-table td { padding: 6px 0; border-bottom: 1px solid rgba(148,163,184,0.08); }
.dossier-table .num { text-align: right; font-variant-numeric: tabular-nums; }
.dossier-table .warn-text { color: #fbbf24; text-align: left; }
.total-row td { border-top: 1px solid rgba(148,163,184,0.25); border-bottom: none; font-weight: 700; padding-top: 10px; }
.hint { font-size: 12px; color: #6b7280; margin: 0; }

.disclaimer { font-size: 11px; color: #6b7280; margin: 12px 0 0; border-top: 1px solid rgba(148,163,184,0.1); padding-top: 12px; }

@media print {
  .no-print { display: none !important; }
  .page { padding: 0; background: #fff; color: #111827; min-height: 0; }
  .dossier { background: #fff; border: none; border-radius: 0; padding: 0; color: #111827; }
  .dossier-sub, .hint, .dossier-total-label { color: #4b5563; }
  .dossier-total-value { color: #111827; }
  .dossier-section h3, .dossier-section h4 { color: #111827; border-bottom-color: #d1d5db; }
  .dossier-table th { color: #4b5563; border-bottom-color: #d1d5db; }
  .dossier-table td { border-bottom-color: #e5e7eb; }
  .total-row td { border-top-color: #9ca3af; }
  .banner.warn { background: #fff7ed; border-color: #fdba74; color: #9a3412; }
  .banner.info { background: #eff6ff; border-color: #93c5fd; color: #1e3a8a; }
  .disclaimer { color: #6b7280; border-top-color: #e5e7eb; }
}
</style>
