<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Institutions bancaires</h1>
        <p class="subtitle">Les banques auxquelles rattacher vos comptes.</p>
      </div>
      <div class="header-actions">
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn btn-primary" @click="openCreate">+ Nouvelle institution</button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !institutions.length" class="empty">Chargement…</div>
    <div v-else-if="!loading && !institutions.length" class="empty">Aucune institution.</div>

    <table v-else class="table">
      <thead>
        <tr>
          <th></th>
          <th>Nom</th>
          <th>BIC</th>
          <th>Site web</th>
          <th>Notes</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="i in institutions" :key="i.id">
          <td><span class="color-dot" :style="{ background: colorHex(i.color) }"></span></td>
          <td>{{ i.name }}</td>
          <td class="muted">{{ i.bic || '—' }}</td>
          <td class="muted">{{ i.website || '—' }}</td>
          <td class="muted">{{ i.notes || '—' }}</td>
          <td class="actions">
            <button class="btn-action" @click="openEdit(i)">✎</button>
            <button class="btn-action btn-danger" @click="deleteInstitution(i)">✕</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Modal inline -->
    <div v-if="showModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>{{ editTarget ? 'Modifier' : 'Nouvelle institution' }}</h2>
        <label>Nom *
          <input v-model="form.name" placeholder="Banque Populaire…" />
        </label>
        <label>Couleur
          <select v-model="form.color">
            <option v-for="c in COLORS" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <div class="color-preview" :style="{ background: colorHex(form.color) }"></div>
        <label>BIC
          <input v-model="form.bic" placeholder="Optionnel" />
        </label>
        <label>Site web
          <input v-model="form.website" placeholder="Optionnel" />
        </label>
        <label>Notes
          <input v-model="form.notes" placeholder="Optionnel" />
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
import { confirmDialog } from '@/utils/confirmDialog'
import { useToast } from '@/utils/toast'

const toast = useToast()

// Palette tenue synchronisée avec Tags.vue / rt_tags.py (même 7 valeurs, pas de color-picker
// libre dans l'app).
const COLORS = ['green', 'red', 'blue', 'white', 'black', 'yellow', 'purple']
const COLOR_MAP = {
  green: '#22c55e', red: '#ef4444', blue: '#3b82f6',
  white: '#f1f5f9', black: '#1e293b', yellow: '#eab308', purple: '#a855f7',
}
function colorHex(c) { return COLOR_MAP[c] || '#6b7280' }

const institutions = ref([])
const loading = ref(false)
const error = ref('')
const showModal = ref(false)
const editTarget = ref(null)
const form = ref({ name: '', bic: '', website: '', notes: '', color: 'blue' })

const { shaking, shake } = useModalShake()
useEscapeClose(() => { if (showModal.value) showModal.value = false }, shake, () => showModal.value)

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const res = await axios.get('/api/institutions')
    institutions.value = Array.isArray(res.data?.response_data) ? res.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  form.value = { name: '', bic: '', website: '', notes: '', color: 'blue' }
  showModal.value = true
}

function openEdit(i) {
  editTarget.value = i
  form.value = { name: i.name, bic: i.bic || '', website: i.website || '', notes: i.notes || '', color: i.color || 'blue' }
  showModal.value = true
}

async function save() {
  try {
    if (editTarget.value) {
      await axios.patch('/api/institutions', {
        institution_id: editTarget.value.id,
        name: form.value.name,
        bic: form.value.bic || null,
        website: form.value.website || null,
        notes: form.value.notes || null,
        color: form.value.color,
      })
    } else {
      await axios.post('/api/institutions', {
        name: form.value.name,
        bic: form.value.bic || null,
        website: form.value.website || null,
        notes: form.value.notes || null,
        color: form.value.color,
      })
    }
    showModal.value = false
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function deleteInstitution(i) {
  const ok = await confirmDialog({
    title: 'Supprimer l’institution',
    message: `Supprimer « ${i.name} » ? Les comptes rattachés seront simplement détachés.`,
    confirmLabel: 'Supprimer',
    danger: true,
  })
  if (!ok) return
  try {
    await axios.delete('/api/institutions', { params: { institution_id: i.id } })
    await reload()
    toast.success(`Institution « ${i.name} » supprimée.`)
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
.btn-primary { background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2)); border-color: transparent; color: #fff; }

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

.color-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  display: inline-block;
}

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
.color-preview {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 2px solid rgba(255,255,255,0.15);
}
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 4px; }
</style>
