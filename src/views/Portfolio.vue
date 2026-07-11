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
        <div class="type-value">{{ typeSummaryValue(group) }}</div>
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
          <th>Plus-value</th>
          <th>MAJ</th>
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
            <td>{{ fmtAmount(a.value_per_unit, commodityCode(a.commodity_id)) }}</td>
            <td>{{ a.total_quantity }}</td>
            <td class="value">{{ fmtAmount(a.total_value, commodityCode(a.commodity_id)) }}</td>
            <td :class="gainLoss(a) ? (gainLoss(a).abs >= 0 ? 'gain-positive' : 'gain-negative') : 'muted'">
              <template v-if="gainLoss(a)">
                {{ fmtAmount(gainLoss(a).abs, commodityCode(a.commodity_id)) }}
                <span v-if="gainLoss(a).pct != null">({{ gainLoss(a).pct >= 0 ? '+' : '' }}{{ gainLoss(a).pct.toFixed(1) }}%)</span>
              </template>
              <template v-else>—</template>
            </td>
            <td class="muted">{{ lastUpdatedLabel(a) }}</td>
            <td class="actions" @click.stop>
              <button v-if="a.track_live_price" class="btn-action" :disabled="refreshingIds.has(a.id)" @click="refreshPrice(a)">⟳</button>
              <button class="btn-action" @click="openEdit(a)">✎</button>
              <button class="btn-action" @click="openAddPossession(a)">+</button>
              <button class="btn-action btn-danger" @click="deleteAsset(a)">✕</button>
            </td>
          </tr>
          <!-- Possessions expandable -->
          <tr v-if="expanded.has(a.id) && a.possessions.length" class="possession-row">
            <td colspan="10">
              <table class="sub-table">
                <thead>
                  <tr><th>Compte</th><th>Quantité</th><th>Prix d'achat</th><th>Date d'achat</th><th>Valeur</th><th>Plus-value</th><th></th></tr>
                </thead>
                <tbody>
                  <tr v-for="p in a.possessions" :key="p.id">
                    <td class="muted">{{ p.account_id }}</td>
                    <td>{{ p.quantity }}</td>
                    <td class="muted">{{ p.purchase_price != null ? fmtAmount(p.purchase_price, commodityCode(a.commodity_id)) : '—' }}</td>
                    <td class="muted">{{ p.purchase_date ? p.purchase_date.slice(0, 10) : '—' }}</td>
                    <td>{{ fmtAmount(p.quantity * a.value_per_unit, commodityCode(a.commodity_id)) }}</td>
                    <td :class="possessionGain(p, a) ? (possessionGain(p, a).abs >= 0 ? 'gain-positive' : 'gain-negative') : 'muted'">
                      <template v-if="possessionGain(p, a)">
                        {{ fmtAmount(possessionGain(p, a).abs, commodityCode(a.commodity_id)) }}
                        <span v-if="possessionGain(p, a).pct != null">({{ possessionGain(p, a).pct >= 0 ? '+' : '' }}{{ possessionGain(p, a).pct.toFixed(1) }}%)</span>
                      </template>
                      <template v-else>—</template>
                    </td>
                    <td class="actions">
                      <button class="btn-action" @click="openEditPossession(p, a)">✎</button>
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
          <input v-model="form.symbol" placeholder="AAPL, AMZN…" @blur="validateSymbol" />
        </label>
        <label>Nom *
          <input v-model="form.name" placeholder="Apple Inc." />
        </label>
        <label>Type *
          <select v-model="form.asset_type" @change="validateSymbol">
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
        <label v-if="['Stock','ETF'].includes(form.asset_type)" class="checkbox-label">
          <input type="checkbox" v-model="form.track_live_price" @change="validateSymbol" />
          Suivre le prix en temps réel (marché)
        </label>
        <template v-if="form.track_live_price">
          <div class="symbol-status">
            <span v-if="validatingSymbol" class="muted">Vérification du symbole…</span>
            <span v-else-if="symbolValidationError" class="error-text">{{ symbolValidationError }}</span>
            <span v-else-if="fetchedPrice != null" class="ok-text">✓ Prix trouvé : {{ fetchedPrice }} {{ fetchedCurrency }}</span>
          </div>
          <label>Valeur de marché (devise du titre — sera convertie en {{ commodities.find(c => c.id === form.commodity_id)?.short_name || '…' }})
            <input :value="fetchedPrice != null ? `${fetchedPrice} ${fetchedCurrency || ''}` : '—'" disabled />
          </label>
        </template>
        <label v-else>Valeur unitaire
          <input v-model.number="form.value_per_unit" type="number" step="0.01" min="0" />
        </label>
        <p class="hint-text">Le prix d'achat se renseigne par position (bouton "+"), pas ici — un même actif peut avoir plusieurs lots achetés à des prix différents.</p>
        <div class="modal-actions">
          <button class="btn" @click="showModal = false">Annuler</button>
          <button
            class="btn btn-primary"
            :disabled="!form.symbol.trim() || !form.name.trim() || (form.track_live_price && (validatingSymbol || fetchedPrice == null))"
            @click="saveAsset"
          >Enregistrer</button>
        </div>
      </div>
    </div>

    <!-- Modal possession -->
    <div v-if="showPossessionModal" class="modal-backdrop" @click.self="showPossessionModal = false">
      <div class="modal">
        <h2>{{ possessionEditTarget ? 'Modifier la position' : 'Ajouter une position' }} — {{ possessionTarget?.name }}</h2>
        <label>Compte *
          <select v-model="possessionForm.account_id" :disabled="!!possessionEditTarget">
            <option v-for="a in investmentAccounts" :key="a.id" :value="a.id">{{ a.name }}</option>
          </select>
        </label>
        <label>Compte débité (facultatif)
          <select v-model="possessionForm.source_account_id" :disabled="!!possessionEditTarget">
            <option :value="null">Aucun — saisie manuelle</option>
            <option v-for="a in debitableAccounts" :key="a.id" :value="a.id">{{ a.name }}</option>
          </select>
        </label>
        <label>Quantité *
          <input v-model.number="possessionForm.quantity" type="number" min="0" />
        </label>
        <label>Prix d'achat unitaire *{{ possessionTarget?.track_live_price ? ` (devise native du titre)` : '' }}
          <input
            v-model.number="possessionForm.purchase_price"
            type="number" step="0.01" min="0"
            :placeholder="possessionTarget?.track_live_price ? 'Dans la devise native du titre' : 'Montant payé'"
          />
        </label>
        <label>Date d'achat *
          <input v-model="possessionForm.purchase_date" type="date" />
        </label>
        <div class="modal-actions">
          <button class="btn" @click="showPossessionModal = false">Annuler</button>
          <button
            class="btn btn-primary"
            :disabled="!possessionForm.account_id || possessionForm.quantity < 1 || possessionForm.purchase_price == null || !possessionForm.purchase_date"
            @click="savePossession"
          >Enregistrer</button>
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
const possessionEditTarget = ref(null)
const expanded = ref(new Set())

const assetTypes = [
  { value: 'Stock', label: 'Action' },
  { value: 'ETF', label: 'ETF' },
  { value: 'RealEstate', label: 'Immobilier' },
  { value: 'Vehicle', label: 'Véhicule' },
  { value: 'Other', label: 'Autre' },
]

const form = ref({ symbol: '', name: '', asset_type: 'Stock', sector: '', commodity_id: '', value_per_unit: 0, track_live_price: false })
const possessionForm = ref({ account_id: '', source_account_id: null, quantity: 1, purchase_price: null, purchase_date: null })

const investmentAccounts = computed(() => accounts.value.filter(a => ['Assets', 'Equity'].includes(a.account_type)))
const debitableAccounts = computed(() => accounts.value.filter(a => ['Current', 'Assets', 'Equity'].includes(a.account_type)))

const validatingSymbol = ref(false)
const symbolValidationError = ref('')
const fetchedPrice = ref(null)
const fetchedCurrency = ref(null)
const refreshingIds = ref(new Set())

function typeLabel(t) {
  return assetTypes.find(x => x.value === t)?.label || t
}

function commodityCode(id) {
  return commodities.value.find(c => c.id === id)?.short_name || 'EUR'
}

function fmtAmount(v, currency = 'EUR') {
  try {
    return new Intl.NumberFormat('fr-FR', { style: 'currency', currency, minimumFractionDigits: 2 }).format(v || 0)
  } catch {
    return `${new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2 }).format(v || 0)} ${currency}`
  }
}

function typeSummaryValue(group) {
  const total = group.reduce((s, a) => s + a.total_value, 0)
  const codes = new Set(group.map(a => commodityCode(a.commodity_id)))
  if (codes.size === 1) return fmtAmount(total, [...codes][0])
  return `${total.toFixed(2)} (devises mixtes)`
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
  form.value = { symbol: '', name: '', asset_type: 'Stock', sector: '', commodity_id: commodities.value[0]?.id || '', value_per_unit: 0, track_live_price: false }
  fetchedPrice.value = null
  fetchedCurrency.value = null
  symbolValidationError.value = ''
  showModal.value = true
}

function openEdit(a) {
  editTarget.value = a
  form.value = {
    symbol: a.symbol, name: a.name, asset_type: a.asset_type, sector: a.sector || '',
    commodity_id: a.commodity_id, value_per_unit: a.value_per_unit,
    track_live_price: a.track_live_price,
  }
  fetchedPrice.value = null
  fetchedCurrency.value = null
  symbolValidationError.value = ''
  showModal.value = true
  if (a.track_live_price) validateSymbol()
}

async function validateSymbol() {
  if (!form.value.track_live_price || !form.value.symbol.trim()) {
    fetchedPrice.value = null
    fetchedCurrency.value = null
    symbolValidationError.value = ''
    return
  }
  validatingSymbol.value = true
  symbolValidationError.value = ''
  try {
    const res = await axios.get('/api/markets/analyse', { params: { ticker: form.value.symbol.trim() } })
    fetchedPrice.value = res.data?.response_data?.current_price ?? null
    fetchedCurrency.value = res.data?.response_data?.currency ?? null
    if (fetchedPrice.value == null) symbolValidationError.value = 'Prix indisponible pour ce symbole.'
  } catch (e) {
    fetchedPrice.value = null
    fetchedCurrency.value = null
    symbolValidationError.value = e?.response?.data?.response_data || 'Symbole introuvable.'
  } finally {
    validatingSymbol.value = false
  }
}

function openAddPossession(a) {
  possessionTarget.value = a
  possessionEditTarget.value = null
  possessionForm.value = {
    account_id: investmentAccounts.value[0]?.id || '',
    source_account_id: null,
    quantity: 1, purchase_price: null, purchase_date: null,
  }
  showPossessionModal.value = true
}

function openEditPossession(p, a) {
  possessionTarget.value = a
  possessionEditTarget.value = p
  possessionForm.value = {
    account_id: p.account_id,
    source_account_id: p.source_account_id || null,
    quantity: p.quantity,
    purchase_price: p.purchase_price_native != null ? p.purchase_price_native : p.purchase_price,
    purchase_date: p.purchase_date ? p.purchase_date.slice(0, 10) : null,
  }
  showPossessionModal.value = true
}

async function saveAsset() {
  if (form.value.track_live_price && fetchedPrice.value == null) {
    await validateSymbol()
    if (fetchedPrice.value == null) return
  }
  try {
    const payload = {
      symbol: form.value.symbol,
      name: form.value.name,
      asset_type: form.value.asset_type,
      sector: ['Stock', 'ETF'].includes(form.value.asset_type) ? form.value.sector || null : null,
      commodity_id: form.value.commodity_id,
      value_per_unit: form.value.value_per_unit,
      track_live_price: form.value.track_live_price,
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
    if (possessionEditTarget.value) {
      await axios.patch('/api/assets/possessions', {
        possession_id: possessionEditTarget.value.id,
        quantity: possessionForm.value.quantity,
        purchase_price: possessionForm.value.purchase_price,
        purchase_date: possessionForm.value.purchase_date,
      })
    } else {
      await axios.post('/api/assets/possessions', {
        asset_id: possessionTarget.value.id,
        account_id: possessionForm.value.account_id,
        source_account_id: possessionForm.value.source_account_id || null,
        quantity: possessionForm.value.quantity,
        purchase_price: possessionForm.value.purchase_price,
        purchase_date: possessionForm.value.purchase_date,
      })
    }
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

async function refreshPrice(a) {
  refreshingIds.value.add(a.id)
  try {
    await axios.post('/api/assets/refresh-price', { asset_id: a.id })
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    refreshingIds.value.delete(a.id)
  }
}

function possessionGain(p, a) {
  if (p.purchase_price == null) return null
  const abs = (a.value_per_unit - p.purchase_price) * p.quantity
  const purchaseValue = p.purchase_price * p.quantity
  const pct = purchaseValue !== 0 ? (abs / purchaseValue) * 100 : null
  return { abs, pct }
}

function gainLoss(a) {
  const priced = (a.possessions || []).filter(p => p.purchase_price != null)
  if (!priced.length) return null
  const currentValue = priced.reduce((s, p) => s + p.quantity * a.value_per_unit, 0)
  const purchaseValue = priced.reduce((s, p) => s + p.quantity * p.purchase_price, 0)
  const abs = currentValue - purchaseValue
  const pct = purchaseValue !== 0 ? (abs / purchaseValue) * 100 : null
  return { abs, pct }
}

function lastUpdatedLabel(a) {
  if (!a.track_live_price) return 'manuel'
  if (!a.last_price_updated_at) return '—'
  const diffMin = Math.round((Date.now() - new Date(a.last_price_updated_at).getTime()) / 60000)
  if (diffMin < 1) return 'à l\'instant'
  if (diffMin < 60) return `il y a ${diffMin} min`
  const diffH = Math.round(diffMin / 60)
  if (diffH < 24) return `il y a ${diffH} h`
  return new Date(a.last_price_updated_at).toLocaleDateString('fr-FR')
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

.checkbox-label { flex-direction: row !important; align-items: center; gap: 8px !important; font-size: 14px; color: #e5e7eb; }
.checkbox-label input[type="checkbox"] { width: 16px; height: 16px; cursor: pointer; }
.symbol-status { font-size: 12px; margin-top: -6px; }
.error-text { color: #fca5a5; }
.ok-text { color: #6ee7b7; }
.hint-text { font-size: 11px; color: #64748b; margin: -6px 0 0; }
.modal input:disabled, .modal select:disabled { opacity: 0.6; cursor: not-allowed; }

.gain-positive { color: #4ade80; font-weight: 600; }
.gain-negative { color: #f87171; font-weight: 600; }
</style>
