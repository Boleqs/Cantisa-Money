<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Tags</h1>
        <p class="subtitle">Étiquetez vos opérations pour un filtrage avancé.</p>
      </div>
      <div class="header-actions">
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn btn-primary" @click="openCreate">+ Nouveau tag</button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !tags.length" class="empty">Chargement…</div>
    <div v-else-if="!loading && !tags.length" class="empty">Aucun tag.</div>

    <div v-else class="chips-list">
      <div v-for="t in tags" :key="t.id" class="chip-row">
        <span class="color-dot" :style="{ background: colorHex(t.color) }"></span>
        <span class="chip-name">{{ t.name }}</span>
        <span class="chip-color muted">{{ t.color }}</span>
        <span v-if="t.tax_treatment" class="chip-tax-badge">{{ taxTreatmentLabel(t.tax_treatment) }}</span>
        <span class="chip-actions">
          <button class="btn-action" @click="openEdit(t)">✎</button>
          <button class="btn-action btn-danger" @click="deleteTag(t)">✕</button>
        </span>
      </div>
    </div>

    <!-- Modal inline -->
    <div v-if="showModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>{{ editTarget ? 'Modifier le tag' : 'Nouveau tag' }}</h2>
        <label>Nom *
          <input v-model="form.name" placeholder="Voyage, Loisirs…" />
        </label>
        <label>Couleur
          <select v-model="form.color">
            <option v-for="c in COLORS" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <div class="color-preview" :style="{ background: colorHex(form.color) }"></div>
        <label>Ligne fiscale
          <select v-model="form.tax_treatment">
            <option :value="null">— Non fiscal —</option>
            <option v-for="t in TAX_TREATMENTS" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </label>
        <span class="hint">Tout split portant ce tag compte comme fiscal, quelle que soit sa catégorie.</span>
        <div class="modal-actions">
          <button class="btn" @click="showModal = false">Annuler</button>
          <button class="btn btn-primary" :disabled="!form.name.trim()" @click="save">Enregistrer</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useModalShake, useEscapeClose } from '@/utils/modalUX'

const COLORS = ['green', 'red', 'blue', 'white', 'black', 'yellow', 'purple']
const COLOR_MAP = {
  green: '#22c55e', red: '#ef4444', blue: '#3b82f6',
  white: '#f1f5f9', black: '#1e293b', yellow: '#eab308', purple: '#a855f7',
}
// Tenu synchronisé avec TAX_TREATMENT_VALUES dans rt_tags.py.
const TAX_TREATMENTS = [
  { value: 'taxable_income', label: 'Revenu imposable' },
  { value: 'deductible', label: 'Charge déductible' },
  { value: 'real_estate_income', label: 'Revenu foncier' },
  { value: 'real_estate_expense', label: 'Charge foncière' },
]

const tags = ref([])
const loading = ref(false)
const error = ref('')
const showModal = ref(false)
const editTarget = ref(null)
const form = ref({ name: '', color: 'green', tax_treatment: null })

const { shaking, shake } = useModalShake()
useEscapeClose(() => { if (showModal.value) showModal.value = false })

function colorHex(c) { return COLOR_MAP[c] || '#6b7280' }
function taxTreatmentLabel(v) { return TAX_TREATMENTS.find(t => t.value === v)?.label || v }

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get('/api/tags')
    tags.value = Array.isArray(res.data?.response_data) ? res.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  form.value = { name: '', color: 'green', tax_treatment: null }
  showModal.value = true
}

function openEdit(t) {
  editTarget.value = t
  form.value = { name: t.name, color: t.color, tax_treatment: t.tax_treatment || null }
  showModal.value = true
}

async function save() {
  try {
    if (editTarget.value) {
      await axios.patch('/api/tags', {
        tag_id: editTarget.value.id,
        name: form.value.name,
        color: form.value.color,
        tax_treatment: form.value.tax_treatment || null,
      })
    } else {
      await axios.post('/api/tags', {
        name: form.value.name,
        color: form.value.color,
        tax_treatment: form.value.tax_treatment || null,
      })
    }
    showModal.value = false
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function deleteTag(t) {
  if (!confirm(`Supprimer le tag « ${t.name} » ?`)) return
  try {
    await axios.delete('/api/tags', { params: { tag_id: t.id } })
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

.chips-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.chip-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border: 1px solid rgba(148,163,184,0.12);
  border-radius: 10px;
  background: rgba(15,23,42,0.5);
}
.color-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  flex-shrink: 0;
}
.chip-name { font-weight: 500; flex: 1; }
.chip-color { font-size: 12px; }
.chip-tax-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(96,165,250,0.4);
  background: rgba(96,165,250,0.1);
  color: #93c5fd;
}
.muted { color: #9ca3af; }
.chip-actions { display: flex; gap: 6px; }

.btn-action {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}
.btn-action:hover { background: rgba(148, 163, 184, 0.1); }
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
}
.modal {
  background: #1e293b;
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 16px;
  padding: 24px;
  width: 380px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.modal h2 { margin: 0; font-size: 18px; }
.modal label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #9ca3af;
}
.modal input, .modal select {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px;
  padding: 8px 10px;
  color: #e5e7eb;
  font-size: 14px;
}
.hint {
  font-size: 11px;
  color: #6b7280;
}
.color-preview {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 2px solid rgba(255,255,255,0.15);
}
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 4px; }
</style>