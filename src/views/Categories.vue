<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Catégories</h1>
        <p class="subtitle">Organisez vos transactions par catégorie.</p>
      </div>
      <div class="header-actions">
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn btn-primary" @click="openCreate">+ Nouvelle catégorie</button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !categories.length" class="empty">Chargement…</div>
    <div v-else-if="!loading && !categories.length" class="empty">Aucune catégorie.</div>

    <table v-else class="table">
      <thead>
        <tr>
          <th>Nom</th>
          <th>Description</th>
          <th>Ligne fiscale</th>
          <th>Créée le</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in categories" :key="c.id">
          <td>{{ c.name }}</td>
          <td class="muted">{{ c.description || '—' }}</td>
          <td class="muted">{{ taxTreatmentLabel(c.tax_treatment) }}</td>
          <td class="muted">{{ fmtDate(c.created_at) }}</td>
          <td class="actions">
            <button class="btn-action" @click="openEdit(c)">✎</button>
            <button class="btn-action btn-danger" @click="deleteCategory(c)">✕</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Modal inline -->
    <div v-if="showModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>{{ editTarget ? 'Modifier' : 'Nouvelle catégorie' }}</h2>
        <label>Nom *
          <input v-model="form.name" placeholder="Alimentation…" />
        </label>
        <label>Description
          <input v-model="form.description" placeholder="Optionnel" />
        </label>
        <label>Ligne fiscale
          <select v-model="form.tax_treatment">
            <option :value="null">— Non fiscal —</option>
            <option v-for="t in TAX_TREATMENTS" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </label>
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

const categories = ref([])
const loading = ref(false)
const error = ref('')
const showModal = ref(false)
const editTarget = ref(null)
const form = ref({ name: '', description: '', tax_treatment: null })

const { shaking, shake } = useModalShake()
useEscapeClose(() => { if (showModal.value) showModal.value = false })

const TAX_TREATMENTS = [
  { value: 'taxable_income', label: 'Revenu imposable' },
  { value: 'deductible', label: 'Charge déductible' },
  { value: 'real_estate_income', label: 'Revenu foncier' },
  { value: 'real_estate_expense', label: 'Charge foncière' },
]

function taxTreatmentLabel(v) {
  return TAX_TREATMENTS.find(t => t.value === v)?.label || '—'
}

function fmtDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get('/api/categories')
    categories.value = Array.isArray(res.data?.response_data) ? res.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  form.value = { name: '', description: '', tax_treatment: null }
  showModal.value = true
}

function openEdit(c) {
  editTarget.value = c
  form.value = { name: c.name, description: c.description || '', tax_treatment: c.tax_treatment || null }
  showModal.value = true
}

async function save() {
  try {
    if (editTarget.value) {
      await axios.patch('/api/categories', {
        category_id: editTarget.value.id,
        name: form.value.name,
        description: form.value.description || null,
        tax_treatment: form.value.tax_treatment || null,
      })
    } else {
      await axios.post('/api/categories', {
        name: form.value.name,
        description: form.value.description || null,
        tax_treatment: form.value.tax_treatment || null,
      })
    }
    showModal.value = false
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function deleteCategory(c) {
  if (!confirm(`Supprimer la catégorie « ${c.name} » ?`)) return
  try {
    await axios.delete('/api/categories', { params: { category_id: c.id } })
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

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.table th {
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
  color: #9ca3af;
  font-weight: 500;
}
.table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}
.muted { color: #9ca3af; }
.actions { text-align: right; white-space: nowrap; }

.btn-action {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  margin-left: 4px;
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
  width: 400px;
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
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 4px; }
</style>