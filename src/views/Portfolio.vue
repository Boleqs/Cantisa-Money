<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Portfolio</h1>
        <p class="subtitle">Gérez vos actifs financiers et patrimoines.</p>
      </div>
      <div class="header-actions">
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn btn-primary" @click="openCreate">+ Nouvel actif</button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <!-- Summary cards by type -->
    <div v-if="assets.length" class="type-summary">
      <div v-for="(group, type) in byType" :key="type" class="type-card">
        <div class="type-label">{{ typeLabel(type) }}</div>
        <div class="type-count">{{ group.length }} actif{{ group.length > 1 ? 's' : '' }}</div>
        <div class="type-value">{{ fmtAmount(group.reduce((s, a) => s + a.total_value, 0)) }}</div>
      </div>
    </div>

    <div v-if="loading && !assets.length" class="empty">Chargement…</div>
    <div v-else-if="!loading && !assets.length" class="empty">Aucun actif enregistré.</div>

    <table v-else class="table">
      <thead>
        <tr>
          <th>Symbole</th>
          <th>Nom</th>
          <th>Type</th>
          <th>Secteur</th>
          <th>Valeur unitaire</th>
          <th>Quantité totale</th>
          <th>Valeur totale</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <template v-for="a in assets" :key="a.id">
          <tr class="asset-row" @click="toggleExpand(a.id)">
            <td class="symbol">{{ a.symbol }}</td>
            <td>{{ a.name }}</td>
            <td><span class="badge" :class="'badge-' + a.asset_type.toLowerCase()">{{ typeLabel(a.asset_type) }}</span></td>
            <td class="muted">{{ a.sector || '—' }}</td>
            <td>{{ fmtAmount(a.value_per_unit) }}</td>
            <td>{{ a.total_quantity }}</td>
            <td class="value">{{ fmtAmount(a.total_value) }}</td>
            <td class="actions" @click.stop>
              <button class="btn-action" @click="openEdit(a)">✎</button>
              <button class="btn-action" @click="openAddPossession(a)">+</button>
              <button class="btn-action btn-danger" @click="deleteAsset(a)">✕</button>
            </td>
          </tr>
          <!-- Possessions expandable -->
          <tr v-if="expanded.has(a.id) && a.possessions.length" class="possession-row">
            <td colspan="8">
              <table class="sub-table">
                <thead>
                  <tr><th>Compte</th><th>Quantité</th><th>Valeur</th><th></th></tr>
                </thead>
                <tbody>
                  <tr v-for="p in a.possessions" :key="p.id">
                    <td class="muted">{{ p.account_id }}</td>
                    <td>{{ p.quantity }}</td>
                    <td>{{ fmtAmount(p.quantity * a.value_per_unit) }}</td>
                    <td class="actions">
                      <button class="btn-action btn-danger" @click="deletePossession(p, a)">✕</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </td>
          </tr>
        </template>
      </tbody>
    </table>

    <!-- Modal asset -->
    <div v-if="showModal" class="modal-backdrop" @click.self="showModal = false">
      <div class="modal">
        <h2>{{ editTarget ? 'Modifier l\'actif' : 'Nouvel actif' }}</h2>
        <label>Symbole *
          <input v-model="form.symbol" placeholder="AAPL, AMZN…" />
        </label>
        <label>Nom *
          <input v-model="form.name" placeholder="Apple Inc." />
        </label>
        <label>Type *
          <select v-model="form.asset_type">
            <option v-for="t in assetTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </label>
        <label v-if="['Stock','ETF'].includes(form.asset_type)">Secteur
          <input v-model="form.sector" placeholder="Technology…" />
        </label>
        <label>Devise *
          <select v-model="form.commodity_id">
            <option v-for="c in commodities" :key="c.id" :value="c.id">{{ c.name }} ({{ c.short_name }})</option>
          </select>
        </label>
        <label>Valeur unitaire
          <input v-model.number="form.value_per_unit" type="number" step="0.01" min="0" />
        </label>
        <div class="modal-actions">
          <button class="btn" @click="showModal = false">Annuler</button>
          <button class="btn btn-primary" :disabled="!form.symbol.trim() || !form.name.trim()" @click="saveAsset">Enregistrer</button>
        </div>
      </div>
    </div>

    <!-- Modal possession -->
    <div v-if="showPossessionModal" class="modal-backdrop" @click.self="showPossessionModal = false">
      <div class="modal">
        <h2>Ajouter une position — {{ possessionTarget?.name }}</h2>
        <label>Compte *
          <select v-model="possessionForm.account_id">
            <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.name }}</option>
          </select>
        </label>
        <label>Quantité *
          <input v-model.number="possessionForm.quantity" type="number" min="0" />
        </label>
        <div class="modal-actions">
          <button class="btn" @click="showPossessionModal = false">Annuler</button>
          <button class="btn btn-primary" :disabled="!possessionForm.account_id || possessionForm.quantity < 1" @click="savePossession">Enregistrer</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const assets = ref([])
const commodities = ref([])
const accounts = ref([])
const loading = ref(false)
const error = ref('')
const showModal = ref(false)
const showPossessionModal = ref(false)
const editTarget = ref(null)
const possessionTarget = ref(null)
const expanded = ref(new Set())

const assetTypes = [
  { value: 'Stock', label: 'Action' },
  { value: 'ETF', label: 'ETF' },
  { value: 'RealEstate', label: 'Immobilier' },
  { value: 'Vehicle', label: 'Véhicule' },
  { value: 'Other', label: 'Autre' },
]

const form = ref({ symbol: '', name: '', asset_type: 'Stock', sector: '', commodity_id: '', value_per_unit: 0 })
const possessionForm = ref({ account_id: '', quantity: 1 })

function typeLabel(t) {
  return assetTypes.find(x => x.value === t)?.label || t
}

function fmtAmount(v) {
  return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'EUR', minimumFractionDigits: 2 }).format(v || 0)
}

const byType = computed(() => {
  const groups = {}
  for (const a of assets.value) {
    if (!groups[a.asset_type]) groups[a.asset_type] = []
    groups[a.asset_type].push(a)
  }
  return groups
})

function toggleExpand(id) {
  if (expanded.value.has(id)) expanded.value.delete(id)
  else expanded.value.add(id)
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [assetsRes, comRes, accRes] = await Promise.all([
      axios.get('/api/assets'),
      axios.get('/api/commodities'),
      axios.get('/api/accounts'),
    ])
    assets.value = Array.isArray(assetsRes.data?.response_data) ? assetsRes.data.response_data : []
    commodities.value = Array.isArray(comRes.data?.response_data) ? comRes.data.response_data : []
    accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  form.value = { symbol: '', name: '', asset_type: 'Stock', sector: '', commodity_id: commodities.value[0]?.id || '', value_per_unit: 0 }
  showModal.value = true
}

function openEdit(a) {
  editTarget.value = a
  form.value = { symbol: a.symbol, name: a.name, asset_type: a.asset_type, sector: a.sector || '', commodity_id: a.commodity_id, value_per_unit: a.value_per_unit }
  showModal.value = true
}

function openAddPossession(a) {
  possessionTarget.value = a
  possessionForm.value = { account_id: accounts.value[0]?.id || '', quantity: 1 }
  showPossessionModal.value = true
}

async function saveAsset() {
  try {
    const payload = {
      symbol: form.value.symbol,
      name: form.value.name,
      asset_type: form.value.asset_type,
      sector: ['Stock', 'ETF'].includes(form.value.asset_type) ? form.value.sector || null : null,
      commodity_id: form.value.commodity_id,
      value_per_unit: form.value.value_per_unit,
    }
    if (editTarget.value) {
      await axios.patch('/api/assets', { ...payload, asset_id: editTarget.value.id })
    } else {
      await axios.post('/api/assets', payload)
    }
    showModal.value = false
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function deleteAsset(a) {
  if (!confirm(`Supprimer l'actif « ${a.name} » et toutes ses positions ?`)) return
  try {
    await axios.delete('/api/assets', { params: { asset_id: a.id } })
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function savePossession() {
  try {
    await axios.post('/api/assets/possessions', {
      asset_id: possessionTarget.value.id,
      account_id: possessionForm.value.account_id,
      quantity: possessionForm.value.quantity,
    })
    showPossessionModal.value = false
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function deletePossession(p, a) {
  if (!confirm(`Supprimer cette position (${p.quantity} unités) ?`)) return
  try {
    await axios.delete('/api/assets/possessions', { params: { possession_id: p.id } })
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

.type-summary {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 20px;
}
.type-card {
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  padding: 14px 18px;
  min-width: 140px;
}
.type-label { font-size: 12px; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.05em; }
.type-count { font-size: 13px; color: #cbd5e1; margin: 4px 0; }
.type-value { font-size: 20px; font-weight: 600; color: #e5e7eb; }

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
.symbol { font-weight: 600; color: #60a5fa; font-family: monospace; }
.value { font-weight: 600; }
.actions { text-align: right; white-space: nowrap; }

.asset-row { cursor: pointer; }
.asset-row:hover td { background: rgba(148, 163, 184, 0.04); }

.possession-row td { background: rgba(15, 23, 42, 0.5); padding: 0; }
.sub-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.sub-table th { padding: 6px 24px; color: #6b7280; font-weight: 400; }
.sub-table td { padding: 6px 24px; border-bottom: 1px solid rgba(148,163,184,0.05); }

.badge {
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}
.badge-stock { background: rgba(59,130,246,0.2); color: #93c5fd; }
.badge-etf { background: rgba(139,92,246,0.2); color: #c4b5fd; }
.badge-realestate { background: rgba(16,185,129,0.2); color: #6ee7b7; }
.badge-vehicle { background: rgba(245,158,11,0.2); color: #fcd34d; }
.badge-other { background: rgba(148,163,184,0.15); color: #cbd5e1; }

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
  width: 420px;
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
