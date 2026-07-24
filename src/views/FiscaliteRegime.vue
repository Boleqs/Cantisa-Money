<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Régime fiscal</h1>
        <p class="subtitle">Barème d'imposition sur le revenu, décote et plafonnement du quotient familial.</p>
      </div>
      <div class="header-actions">
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn btn-primary" @click="openCreate">+ Nouveau régime</button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !regimes.length" class="empty">Chargement…</div>
    <div v-else-if="!loading && !regimes.length" class="empty">Aucun régime configuré.</div>

    <div v-else class="grid">
      <div v-for="r in regimes" :key="r.id" class="card">
        <div class="card-header">
          <div class="period">
            <span class="regime-name">{{ r.name }}</span>
            <span v-if="r.is_active" class="status-badge active">Actif</span>
            <span v-if="!r.is_verified" class="status-badge warn" title="Barème par défaut non vérifié — merci de contrôler ces chiffres">⚠️ Non vérifié</span>
          </div>
          <div class="date-range">{{ r.country_code }} — année fiscale {{ r.tax_year }}</div>
        </div>
        <div class="brackets-preview">
          <div v-for="(b, i) in r.config?.income_tax?.brackets || []" :key="i" class="bracket-row-preview">
            <span>{{ i === 0 ? '0' : fmtAmount(r.config.income_tax.brackets[i - 1].upper_bound) }} → {{ b.upper_bound !== null ? fmtAmount(b.upper_bound) : '∞' }}</span>
            <span class="rate">{{ (b.rate * 100).toFixed(1) }} %</span>
          </div>
        </div>
        <div class="card-actions">
          <button class="btn-action" @click="openEdit(r)">✎ Modifier</button>
          <button class="btn-action btn-danger" @click="deleteRegime(r)">✕ Supprimer</button>
        </div>
      </div>
    </div>

    <!-- Modal inline -->
    <div v-if="showModal" class="modal-backdrop" @click.self="showModal = false">
      <div class="modal">
        <h2>{{ editTarget ? 'Modifier le régime' : 'Nouveau régime' }}</h2>

        <label>Nom *
          <input v-model="form.name" placeholder="France 2026" />
        </label>
        <div class="field-row">
          <label>Pays
            <input v-model="form.country_code" maxlength="2" placeholder="FR" @input="form.country_code = form.country_code.toUpperCase()" />
          </label>
          <label>Année fiscale *
            <input v-model.number="form.tax_year" type="number" />
          </label>
        </div>
        <label class="checkbox-label">
          <input type="checkbox" v-model="form.is_active" />
          Régime actif (utilisé pour la simulation)
        </label>

        <h3>Tranches du barème</h3>
        <div class="bracket-editor">
          <div v-for="(b, i) in form.brackets" :key="i" class="bracket-row">
            <label class="bracket-field">
              <span class="bracket-label">Jusqu'à</span>
              <input
                v-if="i < form.brackets.length - 1"
                v-model.number="b.upper_bound"
                type="number"
                placeholder="Montant"
              />
              <span v-else class="infinity">∞ (dernière tranche)</span>
            </label>
            <label class="bracket-field bracket-rate">
              <span class="bracket-label">Taux %</span>
              <input v-model.number="b.ratePercent" type="number" step="0.1" min="0" max="100" />
            </label>
            <button type="button" class="btn-action btn-danger" :disabled="form.brackets.length <= 1" @click="removeBracket(i)">✕</button>
          </div>
          <button type="button" class="btn-normalize" @click="addBracket">+ Ajouter une tranche</button>
        </div>

        <h3>Décote</h3>
        <label class="checkbox-label">
          <input type="checkbox" v-model="form.decote.enabled" />
          Appliquer la décote
        </label>
        <div class="field-row" v-if="form.decote.enabled">
          <label>Seuil (célibataire)
            <input v-model.number="form.decote.threshold_single" type="number" />
          </label>
          <label>Seuil (couple)
            <input v-model.number="form.decote.threshold_couple" type="number" />
          </label>
          <label>Taux %
            <input v-model.number="form.decote.ratePercent" type="number" step="0.01" />
          </label>
        </div>

        <h3>Plafonnement du quotient familial</h3>
        <div class="field-row">
          <label>Plafond par demi-part
            <input v-model.number="form.quotient_familial.half_part_cap" type="number" />
          </label>
          <label>Plafond 2 premières demi-parts (parent isolé)
            <input v-model.number="form.quotient_familial.first_two_half_parts_cap" type="number" />
          </label>
        </div>

        <h3>Plus-values (PFU)</h3>
        <div class="field-row">
          <label>Taux impôt %
            <input v-model.number="form.capitalGains.pfuIncomeRatePercent" type="number" step="0.1" min="0" max="100" />
          </label>
          <label>Taux prélèvements sociaux %
            <input v-model.number="form.capitalGains.pfuSocialRatePercent" type="number" step="0.1" min="0" max="100" />
          </label>
          <label>Exonération PEA après (années)
            <input v-model.number="form.capitalGains.peaExemptAfterYears" type="number" step="1" min="0" />
          </label>
        </div>

        <div v-if="formError" class="alert">{{ formError }}</div>

        <div class="modal-actions">
          <button class="btn" @click="showModal = false">Annuler</button>
          <button class="btn btn-primary" :disabled="!form.name.trim() || saving" @click="save">
            {{ saving ? 'Enregistrement…' : 'Enregistrer' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const regimes = ref([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const formError = ref('')
const showModal = ref(false)
const editTarget = ref(null)

function emptyForm() {
  return {
    name: '', country_code: 'FR', tax_year: new Date().getFullYear(), is_active: false,
    brackets: [
      { upper_bound: 11497, ratePercent: 0 },
      { upper_bound: 29315, ratePercent: 11 },
      { upper_bound: 83823, ratePercent: 30 },
      { upper_bound: 180294, ratePercent: 41 },
      { upper_bound: null, ratePercent: 45 },
    ],
    decote: { enabled: true, threshold_single: 1929, threshold_couple: 3191, ratePercent: 45.25 },
    quotient_familial: { half_part_cap: 1791, first_two_half_parts_cap: 4224 },
    capitalGains: { pfuIncomeRatePercent: 12.8, pfuSocialRatePercent: 17.2, peaExemptAfterYears: 5 },
  }
}
const form = ref(emptyForm())

function fmtAmount(v) {
  if (v === null || v === undefined) return '∞'
  return new Intl.NumberFormat('fr-FR').format(v)
}

function addBracket() {
  // Insère juste avant la dernière tranche (qui reste toujours la tranche "infinie").
  form.value.brackets.splice(form.value.brackets.length - 1, 0, { upper_bound: 0, ratePercent: 0 })
}
function removeBracket(i) {
  form.value.brackets.splice(i, 1)
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get('/api/tax/regimes')
    regimes.value = Array.isArray(res.data?.response_data) ? res.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  form.value = emptyForm()
  formError.value = ''
  showModal.value = true
}

function openEdit(r) {
  editTarget.value = r
  const it = r.config?.income_tax || {}
  form.value = {
    name: r.name, country_code: r.country_code, tax_year: r.tax_year, is_active: r.is_active,
    brackets: (it.brackets || []).map(b => ({ upper_bound: b.upper_bound, ratePercent: b.rate * 100 })),
    decote: {
      enabled: it.decote?.enabled ?? true,
      threshold_single: it.decote?.threshold_single ?? 0,
      threshold_couple: it.decote?.threshold_couple ?? 0,
      ratePercent: (it.decote?.rate ?? 0) * 100,
    },
    quotient_familial: {
      half_part_cap: it.quotient_familial?.half_part_cap ?? 0,
      first_two_half_parts_cap: it.quotient_familial?.first_two_half_parts_cap ?? 0,
    },
    capitalGains: {
      pfuIncomeRatePercent: (r.config?.capital_gains?.pfu_income_rate ?? 0.128) * 100,
      pfuSocialRatePercent: (r.config?.capital_gains?.pfu_social_rate ?? 0.172) * 100,
      peaExemptAfterYears: r.config?.capital_gains?.pea_exempt_income_after_years ?? 5,
    },
  }
  formError.value = ''
  showModal.value = true
}

function buildConfig() {
  return {
    income_tax: {
      brackets: form.value.brackets.map(b => ({ upper_bound: b.upper_bound, rate: b.ratePercent / 100 })),
      decote: {
        enabled: form.value.decote.enabled,
        threshold_single: form.value.decote.threshold_single,
        threshold_couple: form.value.decote.threshold_couple,
        rate: form.value.decote.ratePercent / 100,
      },
      quotient_familial: {
        half_part_cap: form.value.quotient_familial.half_part_cap,
        first_two_half_parts_cap: form.value.quotient_familial.first_two_half_parts_cap,
      },
    },
    capital_gains: {
      mode: 'pfu',
      pfu_income_rate: form.value.capitalGains.pfuIncomeRatePercent / 100,
      pfu_social_rate: form.value.capitalGains.pfuSocialRatePercent / 100,
      pea_exempt_income_after_years: form.value.capitalGains.peaExemptAfterYears,
    },
  }
}

async function save() {
  formError.value = ''
  saving.value = true
  try {
    const payload = {
      name: form.value.name,
      country_code: form.value.country_code || 'FR',
      tax_year: form.value.tax_year,
      config: buildConfig(),
    }
    if (editTarget.value) {
      await axios.patch('/api/tax/regimes', { regime_id: editTarget.value.id, ...payload, is_active: form.value.is_active })
    } else {
      const res = await axios.post('/api/tax/regimes', payload)
      if (form.value.is_active && res.data?.response_data?.id) {
        await axios.patch('/api/tax/regimes', { regime_id: res.data.response_data.id, ...payload, is_active: true })
      }
    }
    showModal.value = false
    await reload()
  } catch (e) {
    formError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    saving.value = false
  }
}

async function deleteRegime(r) {
  if (!confirm(`Supprimer le régime « ${r.name} » ?`)) return
  try {
    await axios.delete('/api/tax/regimes', { params: { regime_id: r.id } })
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
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
}
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; }
.header-actions { display: flex; gap: 10px; align-items: center; }

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: linear-gradient(90deg, #2563eb, #4f46e5); border-color: transparent; color: #fff; }

.alert {
  border: 1px solid rgba(239, 68, 68, 0.5);
  background: rgba(239, 68, 68, 0.08);
  padding: 12px 14px;
  border-radius: 12px;
  margin-bottom: 16px;
  color: #fecaca;
}
.empty {
  padding: 18px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 14px;
  color: #cbd5e1;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}
.card {
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(2, 6, 23, 0.45);
  border-radius: 16px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card-header { display: flex; flex-direction: column; gap: 4px; }
.period { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.regime-name { font-size: 16px; font-weight: 700; color: #e5e7eb; }
.date-range { font-size: 12px; color: #6b7280; }

.status-badge { font-size: 11px; padding: 2px 8px; border-radius: 999px; }
.status-badge.active { background: rgba(34,197,94,0.12); border: 1px solid rgba(34,197,94,0.3); color: #86efac; }
.status-badge.warn { background: rgba(245,158,11,0.1); border: 1px solid rgba(245,158,11,0.3); color: #fde68a; }

.brackets-preview { display: flex; flex-direction: column; gap: 4px; }
.bracket-row-preview {
  display: flex; justify-content: space-between; font-size: 12px; color: #9ca3af;
  padding: 4px 8px; border-radius: 6px; background: rgba(148,163,184,0.06);
}
.bracket-row-preview .rate { color: #93c5fd; font-weight: 600; }

.card-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 4px; }
.btn-action {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
  padding: 5px 10px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
}
.btn-action:hover { background: rgba(148, 163, 184, 0.1); }
.btn-action:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-danger { border-color: rgba(239,68,68,0.4); color: #fca5a5; }
.btn-danger:hover { background: rgba(239,68,68,0.1); }

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 24px;
}
.modal {
  background: #1e293b;
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 16px;
  padding: 24px;
  width: 560px;
  max-width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.modal h2 { margin: 0; font-size: 18px; }
.modal h3 { margin: 8px 0 0; font-size: 13px; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.04em; }
.modal label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #9ca3af;
}
.modal input {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px;
  padding: 8px 10px;
  color: #e5e7eb;
  font-size: 14px;
}
.field-row { display: flex; gap: 12px; flex-wrap: wrap; }
.field-row label { flex: 1; min-width: 140px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 4px; }

.checkbox-label { flex-direction: row !important; align-items: center; gap: 8px !important; }
.checkbox-label input { margin-top: 0; accent-color: #2563eb; }

.bracket-editor { display: flex; flex-direction: column; gap: 8px; }
.bracket-row { display: flex; gap: 10px; align-items: flex-end; }
.bracket-field { flex: 1; }
.bracket-rate { max-width: 110px; }
.bracket-label { font-size: 11px; }
.infinity { font-size: 13px; color: #6b7280; padding: 8px 0; }
.btn-normalize {
  align-self: flex-start;
  background: transparent;
  border: 1px dashed rgba(148,163,184,0.3);
  color: #93c5fd;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
}
.btn-normalize:hover { background: rgba(148,163,184,0.08); }
</style>
