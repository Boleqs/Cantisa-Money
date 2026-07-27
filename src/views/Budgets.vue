<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Budgets</h1>
        <p class="subtitle">Suivez vos dépenses par rapport à vos budgets alloués.</p>
      </div>
      <div class="header-actions">
        <div class="search-wrapper">
          <span class="search-icon">🔍</span>
          <input
            v-model="search"
            class="search-input"
            type="text"
            placeholder="Rechercher un budget (nom, compte, catégorie, tag)…"
          />
        </div>
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn btn-primary" @click="openCreate">+ Nouveau budget</button>
      </div>
    </header>

    <div v-if="error" class="alert">
      <strong>Erreur :</strong> {{ error }}
    </div>

    <div v-if="loading && !budgets.length" class="empty">Chargement des budgets…</div>
    <div v-else-if="!loading && !budgets.length" class="empty">Aucun budget configuré.</div>
    <div v-else-if="!filteredBudgets.length" class="empty">Aucun budget ne correspond à « {{ search }} ».</div>

    <div v-else class="grid">
      <div v-for="b in filteredBudgets" :key="b.id" class="card">
        <!-- En-tête -->
        <div class="card-header">
          <div class="period">
            <span class="budget-name">{{ b.name }}</span>
            <span :class="['status-badge', statusClass(b)]">{{ statusLabel(b) }}</span>
            <span
              v-if="b.amount_spent_incomplete"
              class="status-badge warn"
              title="Conversion de devise incomplète — total possiblement sous-estimé"
            >⚠️ Devise incomplète</span>
            <span v-if="b.renew_period" class="status-badge renew" :title="`Un nouveau budget identique sera créé automatiquement à la fin de la période`">
              🔁 {{ renewLabel(b.renew_period) }}
            </span>
          </div>
          <div class="date-range">{{ fmtDate(b.start_date) }} → {{ fmtDate(b.end_date) }}</div>
        </div>

        <!-- Barre de progression -->
        <div class="progress-block">
          <div class="amounts">
            <span class="spent">{{ fmtAmount(b.amount_spent) }}</span>
            <span class="sep">/</span>
            <span class="allocated">{{ fmtAmount(b.amount_allocated) }}</span>
          </div>
          <div class="progress-bar-bg">
            <div
              class="progress-bar-fill"
              :class="{ danger: pct(b) >= 100, warn: pct(b) >= 80 && pct(b) < 100 }"
              :style="{ width: Math.min(pct(b), 100) + '%' }"
            ></div>
          </div>
          <div class="pct-label">{{ pct(b).toFixed(0) }}%</div>
        </div>

        <!-- Restant -->
        <div class="remaining" :class="{ negative: b.amount_spent > b.amount_allocated }">
          {{ b.amount_spent > b.amount_allocated ? 'Dépassement' : 'Restant' }} :
          {{ fmtAmount(Math.abs(b.amount_allocated - b.amount_spent)) }}
        </div>

        <!-- Comptes / catégories / tags associés -->
        <div v-if="b.account_ids && b.account_ids.length" class="accounts-section">
          <span class="accounts-label">Comptes :</span>
          <span v-for="id in b.account_ids" :key="id" class="account-chip">
            {{ accountName(id) }}
          </span>
        </div>
        <div v-if="b.category_ids && b.category_ids.length" class="accounts-section">
          <span class="accounts-label">Catégories :</span>
          <span v-for="id in b.category_ids" :key="id" class="account-chip chip-category">
            {{ categoryName(id) }}
          </span>
        </div>
        <div v-if="b.tag_ids && b.tag_ids.length" class="accounts-section">
          <span class="accounts-label">Tags :</span>
          <span v-for="id in b.tag_ids" :key="id" class="account-chip chip-tag">
            {{ tagName(id) }}
          </span>
        </div>

        <div class="card-actions">
          <button class="btn-action" @click="openEdit(b)">✎ Modifier</button>
          <button class="btn-action btn-danger" @click="deleteBudget(b)">✕ Supprimer</button>
        </div>
      </div>
    </div>
  </div>

  <BudgetModal
    v-model="showModal"
    :mode="modalMode"
    :budget="selectedBudget"
    @save="handleSave"
  />
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { currency } from '@/utils/settings.js'
import BudgetModal from '@/components/modal/BudgetModal.vue'
import { confirmDialog } from '@/utils/confirmDialog'
import { useToast } from '@/utils/toast'

const toast = useToast()

const budgets = ref([])
const accounts = ref([])
const categories = ref([])
const tags = ref([])
const search = ref('')

function normalizeText(v) {
  return (v ?? '').toString().toLowerCase().trim()
}

// Recherche côté client (pas de pagination serveur sur cet écran, contrairement à Transactions) :
// nom du budget, mais aussi les comptes/catégories/tags qui lui sont associés — un budget "Loisirs"
// lié au tag "sorties" doit ressortir en tapant "sorties", pas seulement en tapant "Loisirs".
const filteredBudgets = computed(() => {
  const q = normalizeText(search.value)
  if (!q) return budgets.value
  return budgets.value.filter((b) => {
    if (normalizeText(b.name).includes(q)) return true
    if ((b.account_ids || []).some((id) => normalizeText(accountName(id)).includes(q))) return true
    if ((b.category_ids || []).some((id) => normalizeText(categoryName(id)).includes(q))) return true
    if ((b.tag_ids || []).some((id) => normalizeText(tagName(id)).includes(q))) return true
    return false
  })
})

const showModal = ref(false)
const modalMode = ref('create')
const selectedBudget = ref(null)
const loading = ref(false)
const error = ref('')

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtDate(v) {
  if (!v) return '—'
  const d = new Date(v)
  if (Number.isNaN(d.getTime())) return String(v)
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
}

function fmtAmount(v) {
  const n = Number(v ?? 0)
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(n) + ' ' + currency.value
}

function pct(b) {
  if (!b.amount_allocated) return 0
  return (b.amount_spent / b.amount_allocated) * 100
}

function statusClass(b) {
  const p = pct(b)
  const now = new Date()
  const end = new Date(b.end_date)
  if (p >= 100) return 'danger'
  if (p >= 80) return 'warn'
  if (end < now) return 'closed'
  return 'active'
}

function statusLabel(b) {
  const p = pct(b)
  const now = new Date()
  const end = new Date(b.end_date)
  if (p >= 100) return 'Dépassé'
  if (end < now) return 'Terminé'
  const start = new Date(b.start_date)
  if (start > now) return 'À venir'
  return 'En cours'
}

const RENEW_LABELS = { monthly: 'Mensuel', quarterly: 'Trimestriel', yearly: 'Annuel' }
function renewLabel(period) {
  return RENEW_LABELS[period] || period
}

function accountName(id) {
  const a = accounts.value.find(a => String(a.id) === String(id))
  return a ? a.name : id
}

function categoryName(id) {
  const c = categories.value.find(c => String(c.id) === String(id))
  return c ? c.name : id
}

function tagName(id) {
  const t = tags.value.find(t => String(t.id) === String(id))
  return t ? t.name : id
}

// ── data fetching ─────────────────────────────────────────────────────────────

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [budgetRes, accountRes, catRes, tagRes] = await Promise.all([
      axios.get('/api/budgets'),
      axios.get('/api/accounts'),
      axios.get('/api/categories'),
      axios.get('/api/tags'),
    ])
    budgets.value = Array.isArray(budgetRes.data?.response_data) ? budgetRes.data.response_data : []
    accounts.value = Array.isArray(accountRes.data?.response_data) ? accountRes.data.response_data : []
    categories.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
    tags.value = Array.isArray(tagRes.data?.response_data) ? tagRes.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

// ── modal ─────────────────────────────────────────────────────────────────────

function openCreate() {
  selectedBudget.value = null
  modalMode.value = 'create'
  showModal.value = true
}

function openEdit(b) {
  selectedBudget.value = { ...b }
  modalMode.value = 'edit'
  showModal.value = true
}

async function handleSave(form) {
  try {
    if (modalMode.value === 'create') {
      await axios.post('/api/budgets', {
        name: form.name,
        amount_allocated: form.amount_allocated,
        start_date: form.start_date,
        end_date: form.end_date,
        account_ids: form.account_ids,
        category_ids: form.category_ids,
        tag_ids: form.tag_ids,
        renew_period: form.renew_period,
      })
    } else {
      await axios.patch('/api/budgets', {
        budget_id: form.id,
        name: form.name,
        amount_allocated: form.amount_allocated,
        start_date: form.start_date,
        end_date: form.end_date,
        account_ids: form.account_ids,
        category_ids: form.category_ids,
        tag_ids: form.tag_ids,
        renew_period: form.renew_period,
      })
    }
    await reload()
    toast.success(modalMode.value === 'create' ? `Budget « ${form.name} » créé.` : `Budget « ${form.name} » mis à jour.`)
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function deleteBudget(b) {
  const ok = await confirmDialog({
    title: 'Supprimer le budget',
    message: `Supprimer le budget « ${b.name} » ?`,
    confirmLabel: 'Supprimer',
    danger: true,
  })
  if (!ok) return
  try {
    await axios.delete('/api/budgets', { params: { budget_id: b.id } })
    await reload()
    toast.success(`Budget « ${b.name} » supprimé.`)
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

.header-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

.search-wrapper { position: relative; }
.search-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); opacity: 0.7; }
.search-input {
  padding: 10px 10px 10px 32px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  outline: none;
  width: 280px;
  max-width: 70vw;
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

/* Grid */
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

/* Header */
.card-header { display: flex; flex-direction: column; gap: 4px; }
.period { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.budget-name { font-size: 16px; font-weight: 700; color: #e5e7eb; }
.date-range { font-size: 12px; color: #6b7280; }

.status-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
}
.status-badge.active  { background: var(--color-success-soft); border: 1px solid var(--color-success-border); color: var(--color-success-text); }
.status-badge.warn    { background: var(--color-warning-soft); border: 1px solid var(--color-warning-border); color: var(--color-warning-text); }
.status-badge.danger  { background: var(--color-danger-soft);  border: 1px solid var(--color-danger-border);  color: var(--color-danger-text); }
.status-badge.closed  { background: rgba(148,163,184,0.1); border: 1px solid rgba(148,163,184,0.2); color: #9ca3af; }
.status-badge.renew   { background: rgba(96,165,250,0.1);  border: 1px solid rgba(96,165,250,0.3);  color: #93c5fd; }

/* Progress */
.progress-block { display: flex; flex-direction: column; gap: 6px; }

.amounts { display: flex; align-items: baseline; gap: 4px; font-variant-numeric: tabular-nums; }
.spent { font-size: 20px; font-weight: 700; color: #e5e7eb; }
.sep { color: #6b7280; font-size: 16px; }
.allocated { font-size: 14px; color: #9ca3af; }

.progress-bar-bg {
  height: 8px;
  background: rgba(148, 163, 184, 0.15);
  border-radius: 999px;
  overflow: hidden;
}
.progress-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
  border-radius: 999px;
  transition: width 0.4s ease;
}
.progress-bar-fill.warn   { background: linear-gradient(90deg, #d97706, #f59e0b); }
.progress-bar-fill.danger { background: linear-gradient(90deg, #dc2626, #ef4444); }

.pct-label { font-size: 12px; color: #9ca3af; text-align: right; }

/* Remaining */
.remaining { font-size: 13px; color: var(--color-success-text); }
.remaining.negative { color: var(--color-danger-text); }

/* Accounts */
.accounts-section { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.accounts-label { font-size: 12px; color: #6b7280; }
.account-chip {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(96,165,250,0.25);
  background: rgba(96,165,250,0.1);
  color: #93c5fd;
}
.chip-category {
  border-color: rgba(168,85,247,0.3);
  background: rgba(168,85,247,0.1);
  color: #d8b4fe;
}
.chip-tag {
  border-color: rgba(34,197,94,0.3);
  background: rgba(34,197,94,0.1);
  color: #86efac;
}

/* Actions */
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
.btn-danger { border-color: var(--color-danger-border); color: var(--color-danger-text); }
.btn-danger:hover { background: var(--color-danger-soft); }
</style>