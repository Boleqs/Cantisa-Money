<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Foyer fiscal</h1>
        <p class="subtitle">Parts, personnes à charge et revenus non suivis dans l'app (conjoint, etc.).</p>
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
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading" class="empty">Chargement…</div>
    <template v-else>
      <div class="card">
        <div class="card-title">Composition du foyer — {{ selectedYear }}</div>
        <div class="field-row">
          <label>Adultes
            <select v-model.number="form.adults">
              <option :value="1">1 (personne seule)</option>
              <option :value="2">2 (couple)</option>
            </select>
          </label>
          <label>Personnes à charge
            <input v-model.number="form.dependents" type="number" min="0" />
          </label>
          <label>Dont en situation de handicap
            <input v-model.number="form.dependents_disabled" type="number" min="0" />
          </label>
        </div>
        <label class="checkbox-label">
          <input type="checkbox" v-model="form.parent_isole" />
          Parent isolé (majoration d'une demi-part)
        </label>
        <label>Notes
          <input v-model="form.notes" placeholder="Optionnel" />
        </label>
        <div class="parts-preview">
          Parts calculées : <strong>{{ computedParts.toFixed(1) }}</strong>
          <span class="muted">({{ partsFormula }})</span>
        </div>
      </div>

      <div class="card">
        <div class="card-title">Revenus supplémentaires du foyer</div>
        <p class="hint">Revenus non suivis dans l'app (salaire du conjoint, revenus fonciers externes, etc.) — s'ajoutent au revenu imposable tracké dans le simulateur.</p>
        <div class="incomes-editor">
          <div v-for="(inc, i) in form.incomes" :key="i" class="income-row">
            <input v-model="inc.label" placeholder="Libellé (ex: Salaire conjoint)" class="income-label" />
            <input v-model.number="inc.amount" type="number" placeholder="Montant" class="income-amount" />
            <select v-model="inc.income_type" class="income-type">
              <option value="salary">Salaire</option>
              <option value="pension">Pension / retraite</option>
              <option value="rental">Revenu locatif</option>
              <option value="other">Autre</option>
            </select>
            <button type="button" class="btn-action btn-danger" @click="removeIncome(i)">✕</button>
          </div>
          <button type="button" class="btn-normalize" @click="addIncome">+ Ajouter un revenu</button>
        </div>
        <div class="incomes-total">Total : {{ fmtAmount(incomesTotal) }}</div>
      </div>

      <div class="actions-row">
        <button class="btn btn-primary" :disabled="saving" @click="save">
          {{ saving ? 'Enregistrement…' : 'Enregistrer le profil' }}
        </button>
        <span v-if="saved" class="saved-hint">✓ Enregistré</span>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const currentYear = new Date().getFullYear()
const yearOptions = [currentYear - 1, currentYear, currentYear + 1]
const selectedYear = ref(currentYear)

const loading = ref(false)
const saving = ref(false)
const saved = ref(false)
const error = ref('')

function emptyForm() {
  return { adults: 1, dependents: 0, dependents_disabled: 0, parent_isole: false, notes: '', incomes: [] }
}
const form = ref(emptyForm())

const computedParts = computed(() => {
  const base = form.value.adults === 2 ? 2 : 1
  const dep = form.value.dependents
  const depParts = Math.min(dep, 2) * 0.5 + Math.max(0, dep - 2) * 1
  const isoleBonus = (form.value.parent_isole && dep >= 1) ? 0.5 : 0
  const disabledBonus = 0.5 * form.value.dependents_disabled
  return base + depParts + isoleBonus + disabledBonus
})

const partsFormula = computed(() => {
  const parts = []
  parts.push(form.value.adults === 2 ? '2 (couple)' : '1 (seul)')
  if (form.value.dependents > 0) parts.push(`+ ${(Math.min(form.value.dependents, 2) * 0.5 + Math.max(0, form.value.dependents - 2) * 1).toFixed(1)} (${form.value.dependents} enfant${form.value.dependents > 1 ? 's' : ''})`)
  if (form.value.parent_isole && form.value.dependents >= 1) parts.push('+ 0.5 (parent isolé)')
  if (form.value.dependents_disabled > 0) parts.push(`+ ${(0.5 * form.value.dependents_disabled).toFixed(1)} (handicap)`)
  return parts.join(' ')
})

const incomesTotal = computed(() => form.value.incomes.reduce((s, i) => s + (Number(i.amount) || 0), 0))

function fmtAmount(v) {
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(v || 0)
}

function addIncome() {
  form.value.incomes.push({ label: '', amount: 0, income_type: 'salary' })
}
function removeIncome(i) {
  form.value.incomes.splice(i, 1)
}

async function reload() {
  loading.value = true
  error.value = ''
  saved.value = false
  try {
    const res = await axios.get('/api/tax/household', { params: { year: selectedYear.value } })
    const d = res.data?.response_data || {}
    form.value = {
      adults: d.adults ?? 1,
      dependents: d.dependents ?? 0,
      dependents_disabled: d.dependents_disabled ?? 0,
      parent_isole: !!d.parent_isole,
      notes: d.notes || '',
      incomes: (d.incomes || []).map(i => ({ label: i.label, amount: i.amount, income_type: i.income_type })),
    }
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  error.value = ''
  saved.value = false
  try {
    await axios.put('/api/tax/household', {
      tax_year: selectedYear.value,
      adults: form.value.adults,
      dependents: form.value.dependents,
      dependents_disabled: form.value.dependents_disabled,
      parent_isole: form.value.parent_isole,
      notes: form.value.notes || null,
      incomes: form.value.incomes.filter(i => i.label.trim()),
    })
    saved.value = true
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    saving.value = false
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
  gap: 16px;
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
  color: #fecaca;
}
.empty {
  padding: 18px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 14px;
  color: #cbd5e1;
}

.card {
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(2, 6, 23, 0.45);
  border-radius: 16px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.card-title { font-size: 14px; font-weight: 700; color: #e5e7eb; }
.hint { font-size: 12px; color: #6b7280; margin: -6px 0 0; }

.field-row { display: flex; gap: 12px; flex-wrap: wrap; }
.field-row label { flex: 1; min-width: 160px; }

label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #9ca3af; }
input, select {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px;
  padding: 8px 10px;
  color: #e5e7eb;
  font-size: 14px;
}

.checkbox-label { flex-direction: row !important; align-items: center; gap: 8px !important; }
.checkbox-label input { margin-top: 0; accent-color: #2563eb; }

.parts-preview { font-size: 13px; color: #cbd5e1; }
.parts-preview .muted { color: #6b7280; font-size: 12px; }

.incomes-editor { display: flex; flex-direction: column; gap: 8px; }
.income-row { display: flex; gap: 10px; align-items: center; }
.income-label { flex: 2; }
.income-amount { flex: 1; max-width: 140px; }
.income-type { flex: 1; max-width: 160px; }

.incomes-total { font-size: 13px; color: #93c5fd; font-weight: 600; text-align: right; }

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

.btn-action {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
}
.btn-danger { border-color: rgba(239,68,68,0.4); color: #fca5a5; }
.btn-danger:hover { background: rgba(239,68,68,0.1); }

.actions-row { display: flex; align-items: center; gap: 12px; }
.saved-hint { color: #4ade80; font-size: 13px; }
</style>
