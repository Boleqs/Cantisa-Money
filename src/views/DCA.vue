<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Investissement programmé (DCA)</h1>
        <p class="subtitle">Planifiez des achats récurrents d'un actif pour un montant fixe.</p>
      </div>
      <div class="header-actions">
        <div class="search-wrapper">
          <span class="search-icon">🔍</span>
          <input
            v-model="search"
            class="search-input"
            type="text"
            placeholder="Rechercher un plan (nom, actif, compte)…"
          />
        </div>
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn btn-primary" @click="openCreate">+ Nouveau plan</button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !plans.length" class="empty">Chargement…</div>
    <div v-else-if="!loading && !plans.length" class="empty">Aucun plan DCA.</div>
    <div v-else-if="!filteredPlans.length" class="empty">Aucun plan ne correspond à « {{ search }} ».</div>

    <table v-else class="table">
      <thead>
        <tr>
          <th>Nom</th>
          <th>Actif</th>
          <th>Montant</th>
          <th>Planification</th>
          <th>Prochaine échéance</th>
          <th>Investi total</th>
          <th>Valeur actuelle</th>
          <th>Plus-value</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="p in filteredPlans" :key="p.id" :class="{ 'row-overdue': p.is_overdue }">
          <td>
            {{ p.name }}
            <span v-if="p.is_forecast_only" class="badge-forecast" title="Ne crée pas de position automatiquement">Prévisionnel</span>
            <span v-else-if="p.is_overdue" class="badge-overdue">En retard</span>
            <span v-if="p.is_ended" class="badge-ended">Terminé</span>
          </td>
          <td class="muted">{{ assetSymbol(p.asset_id) }}</td>
          <td>{{ fmtAmount(p.amount, p.source_account_id) }}</td>
          <td class="muted">{{ scheduleLabel(p) }}</td>
          <td :class="p.is_overdue ? 'overdue' : 'muted'">{{ p.next_due_at ? fmtDate(p.next_due_at) : '—' }}</td>
          <td class="muted">{{ fmtConverted(p.total_invested) }}</td>
          <td class="muted">{{ fmtConverted(p.current_value) }}</td>
          <td :class="p.gain_abs != null ? (p.gain_abs >= 0 ? 'gain-positive' : 'gain-negative') : 'muted'">
            <template v-if="p.gain_abs != null">
              {{ fmtConverted(p.gain_abs) }}
              <span v-if="p.gain_pct != null">({{ p.gain_pct >= 0 ? '+' : '' }}{{ p.gain_pct.toFixed(1) }}%)</span>
            </template>
            <template v-else>—</template>
          </td>
          <td class="actions">
            <button
              class="btn-action btn-execute"
              :disabled="p.executing || p.is_ended"
              @click="executeDcaPlan(p)"
              title="Exécuter maintenant"
            >
              <span v-if="p.executing">…</span>
              <span v-else>▶</span>
            </button>
            <button class="btn-action" @click="openEdit(p)">✎</button>
            <button class="btn-action btn-danger" @click="deleteDcaPlan(p)">✕</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Modal inline -->
    <div v-if="showModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>{{ editTarget ? 'Modifier' : 'Nouveau plan DCA' }}</h2>
        <label>Nom *
          <input v-model="form.name" placeholder="PEA MSCI World…" />
        </label>
        <label>Actif *
          <select v-model="form.asset_id">
            <option value="">— Sélectionner —</option>
            <option v-for="a in assets" :key="a.id" :value="a.id">{{ a.symbol }} — {{ a.name }}</option>
          </select>
        </label>
        <label>Montant par échéance *
          <input v-model.number="form.amount" type="number" step="0.01" min="0.01" placeholder="200" />
        </label>
        <label>Planification *
          <select v-model="form.schedule_type">
            <option value="monthly">Mensuelle (un jour du mois)</option>
            <option value="yearly">Annuelle (un jour précis)</option>
            <option value="weekly">Hebdomadaire (jour(s) de la semaine)</option>
          </select>
        </label>

        <label v-if="form.schedule_type === 'monthly'">Jour du mois *
          <input v-model.number="form.day_of_month" type="number" min="1" max="31" placeholder="6" />
        </label>

        <template v-if="form.schedule_type === 'yearly'">
          <label>Jour *
            <input v-model.number="form.day_of_month" type="number" min="1" max="31" placeholder="5" />
          </label>
          <label>Mois *
            <select v-model.number="form.month_of_year">
              <option v-for="(m, i) in MONTH_NAMES" :key="i" :value="i + 1">{{ m }}</option>
            </select>
          </label>
        </template>

        <label v-if="form.schedule_type === 'weekly'">Jour(s) de la semaine *
          <div class="weekday-picker">
            <button
              v-for="(d, i) in WEEKDAY_NAMES"
              :key="i"
              type="button"
              class="weekday-chip"
              :class="{ on: form.weekdays.includes(i + 1) }"
              @click="toggleWeekday(i + 1)"
            >{{ d.slice(0, 3) }}</button>
          </div>
        </label>
        <label>Compte débité *
          <select v-model="form.source_account_id">
            <option value="">— Sélectionner —</option>
            <option v-for="a in debitableAccounts" :key="a.id" :value="a.id">{{ a.name }}</option>
          </select>
        </label>
        <label>Compte de portefeuille *
          <select v-model="form.dest_account_id">
            <option value="">— Sélectionner —</option>
            <option v-for="a in investmentAccounts" :key="a.id" :value="a.id">{{ a.name }}</option>
          </select>
        </label>
        <label>Date de début *
          <input v-model="form.start_date" type="date" />
        </label>
        <label>Date de fin (facultatif)
          <input v-model="form.end_date" type="date" />
        </label>
        <label class="checkbox-label">
          <input type="checkbox" v-model="form.is_forecast_only" />
          Prévisionnel uniquement (ne crée pas de position automatiquement — échéance affichée seulement)
        </label>
        <div class="modal-actions">
          <button class="btn" @click="showModal = false">Annuler</button>
          <button
            class="btn btn-primary"
            :disabled="!formValid"
            @click="save"
          >Enregistrer</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { useModalShake, useEscapeClose } from '@/utils/modalUX'
import { confirmDialog } from '@/utils/confirmDialog'
import { useToast } from '@/utils/toast'
import { normalizeSearch } from '@/utils/search.js'
import { formatDate } from '@/utils/dateFormat.js'
import { currency } from '@/utils/settings.js'

const toast = useToast()

const MONTH_NAMES = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]
const WEEKDAY_NAMES = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

const plans = ref([])
const assets = ref([])
const accounts = ref([])
const commodities = ref([])
const loading = ref(false)
const error = ref('')
const search = ref('')
const showModal = ref(false)
const editTarget = ref(null)
const form = ref(emptyForm())

function emptyForm() {
  return {
    name: '', asset_id: '', amount: '',
    schedule_type: 'monthly', day_of_month: 1, month_of_year: 1, weekdays: [],
    source_account_id: '', dest_account_id: '',
    start_date: new Date().toISOString().slice(0, 10), end_date: '',
    is_forecast_only: false,
  }
}

const { shaking, shake } = useModalShake()
useEscapeClose(() => { if (showModal.value) showModal.value = false }, shake, () => showModal.value)

const scheduleValid = computed(() => {
  if (form.value.schedule_type === 'monthly') return form.value.day_of_month >= 1 && form.value.day_of_month <= 31
  if (form.value.schedule_type === 'yearly') return form.value.day_of_month >= 1 && form.value.day_of_month <= 31 && form.value.month_of_year >= 1
  if (form.value.schedule_type === 'weekly') return form.value.weekdays.length > 0
  return false
})

const formValid = computed(() =>
  form.value.name.trim() && form.value.asset_id && form.value.amount > 0 &&
  form.value.source_account_id && form.value.dest_account_id && form.value.start_date && scheduleValid.value
)

function toggleWeekday(day) {
  const i = form.value.weekdays.indexOf(day)
  if (i === -1) form.value.weekdays.push(day)
  else form.value.weekdays.splice(i, 1)
}

function scheduleLabel(p) {
  if (p.schedule_type === 'monthly') return `Le ${p.day_of_month} de chaque mois`
  if (p.schedule_type === 'yearly') return `Le ${p.day_of_month} ${MONTH_NAMES[p.month_of_year - 1]}`
  if (p.schedule_type === 'weekly') return (p.weekdays || []).map(d => WEEKDAY_NAMES[d - 1]).join(', ') || '—'
  return '—'
}

const investmentAccounts = computed(() => accounts.value.filter(a => ['Assets', 'Equity'].includes(a.account_type)))
const debitableAccounts = computed(() => accounts.value.filter(a => ['Current', 'Assets', 'Equity'].includes(a.account_type)))

function accountName(id) {
  const a = accounts.value.find(a => String(a.id) === String(id))
  return a ? a.name : id || '—'
}
function assetSymbol(id) {
  const a = assets.value.find(a => String(a.id) === String(id))
  return a ? a.symbol : '—'
}

// Le montant par échéance n'a pas de devise propre : il est implicitement dans celle du compte
// débité (source_account_id), même convention que Subscriptions.amount — jamais converti, donc
// affiché dans sa devise native plutôt que la devise par défaut globale.
function currencyShort(id) {
  const c = commodities.value.find(c => String(c.id) === String(id))
  return c?.short_name?.toUpperCase?.() || '—'
}
function fmtAmount(v, accountId) {
  const a = accounts.value.find(a => String(a.id) === String(accountId))
  const short = a ? currencyShort(a.currency_id) : '—'
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(Number(v ?? 0)) + ' ' + short
}
// Agrégats (investi total, valeur actuelle, plus-value) déjà convertis côté backend dans la devise
// par défaut de l'utilisateur (voir get_dca_plan_breakdown) — même convention que Dashboard/Budgets.
function fmtConverted(v) {
  if (v == null) return '—'
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(Number(v)) + ' ' + currency.value
}

const fmtDate = formatDate

const normalizeText = normalizeSearch

const filteredPlans = computed(() => {
  const q = normalizeText(search.value)
  if (!q) return plans.value
  return plans.value.filter((p) =>
    normalizeText(p.name).includes(q) ||
    normalizeText(assetSymbol(p.asset_id)).includes(q) ||
    normalizeText(accountName(p.source_account_id)).includes(q) ||
    normalizeText(accountName(p.dest_account_id)).includes(q)
  )
})

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [dcaRes, assetsRes, accRes, comRes] = await Promise.all([
      axios.get('/api/dca'),
      axios.get('/api/assets'),
      axios.get('/api/accounts'),
      axios.get('/api/commodities'),
    ])
    plans.value = (Array.isArray(dcaRes.data?.response_data) ? dcaRes.data.response_data : [])
      .map(p => ({ ...p, executing: false }))
    assets.value = Array.isArray(assetsRes.data?.response_data) ? assetsRes.data.response_data : []
    accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
    commodities.value = Array.isArray(comRes.data?.response_data) ? comRes.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  form.value = emptyForm()
  showModal.value = true
}

function openEdit(p) {
  editTarget.value = p
  form.value = {
    name: p.name,
    asset_id: p.asset_id,
    amount: p.amount,
    schedule_type: p.schedule_type,
    day_of_month: p.day_of_month || 1,
    month_of_year: p.month_of_year || 1,
    weekdays: [...(p.weekdays || [])],
    source_account_id: p.source_account_id || '',
    dest_account_id: p.dest_account_id || '',
    start_date: p.start_date || '',
    end_date: p.end_date || '',
    is_forecast_only: !!p.is_forecast_only,
  }
  showModal.value = true
}

async function save() {
  const payload = {
    name: form.value.name,
    asset_id: form.value.asset_id,
    amount: form.value.amount,
    schedule_type: form.value.schedule_type,
    day_of_month: form.value.day_of_month,
    month_of_year: form.value.month_of_year,
    weekdays: form.value.weekdays,
    source_account_id: form.value.source_account_id,
    dest_account_id: form.value.dest_account_id,
    start_date: form.value.start_date,
    end_date: form.value.end_date || null,
    is_forecast_only: form.value.is_forecast_only,
  }
  try {
    if (editTarget.value) {
      await axios.patch('/api/dca', { plan_id: editTarget.value.id, ...payload })
    } else {
      await axios.post('/api/dca', payload)
    }
    showModal.value = false
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function executeDcaPlan(p) {
  p.executing = true
  error.value = ''
  try {
    const { data } = await axios.post('/api/dca/execute', { plan_id: p.id })
    Object.assign(p, data.response_data, { executing: false })
    toast.success(`Contribution exécutée pour « ${p.name} ».`)
  } catch (e) {
    // Contrairement aux abonnements (qui ne peuvent pas échouer), une exécution DCA peut échouer
    // (prix ou taux de change indisponible) — l'erreur backend doit être visible, pas juste
    // silencieusement retentée à la prochaine passe horaire.
    error.value = e?.response?.data?.response_data || e?.message || "Erreur lors de l'exécution"
    p.executing = false
  }
}

async function deleteDcaPlan(p) {
  const ok = await confirmDialog({
    title: 'Supprimer le plan DCA',
    message: `Supprimer le plan « ${p.name} » ? Les positions déjà achetées restent en portefeuille.`,
    confirmLabel: 'Supprimer',
    danger: true,
  })
  if (!ok) return
  try {
    await axios.delete('/api/dca', { params: { plan_id: p.id } })
    await reload()
    toast.success(`Plan « ${p.name} » supprimé.`)
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
.btn-execute { border-color: rgba(16,185,129,0.4); color: #6ee7b7; }
.btn-execute:hover { background: rgba(16,185,129,0.1); }
.btn-execute:disabled { opacity: 0.5; cursor: not-allowed; }

.row-overdue td { background: rgba(245, 158, 11, 0.04); }
.overdue { color: #fde68a !important; font-weight: 600; }
.badge-overdue {
  display: inline-block;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid rgba(245,158,11,0.4);
  background: rgba(245,158,11,0.1);
  color: #fde68a;
  margin-left: 6px;
  vertical-align: middle;
}
.badge-forecast {
  display: inline-block;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid rgba(96,165,250,0.4);
  background: rgba(96,165,250,0.1);
  color: #93c5fd;
  margin-left: 6px;
  vertical-align: middle;
}
.badge-ended {
  display: inline-block;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 999px;
  border: 1px solid rgba(148,163,184,0.3);
  background: rgba(148,163,184,0.1);
  color: #cbd5e1;
  margin-left: 6px;
  vertical-align: middle;
}

.gain-positive { color: #4ade80; font-weight: 600; }
.gain-negative { color: #f87171; font-weight: 600; }

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
  max-height: 90vh;
  overflow-y: auto;
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

.checkbox-label {
  flex-direction: row !important;
  align-items: flex-start;
  gap: 8px !important;
}
.checkbox-label input { margin-top: 2px; accent-color: #2563eb; }

.weekday-picker { display: flex; gap: 6px; flex-wrap: wrap; }
.weekday-chip {
  border: 1px solid rgba(148,163,184,0.25);
  background: rgba(15,23,42,0.7);
  color: #9ca3af;
  padding: 6px 10px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
  transition: 0.15s;
}
.weekday-chip:hover { color: #cbd5e1; }
.weekday-chip.on {
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
  border-color: transparent;
  color: #fff;
}
</style>
