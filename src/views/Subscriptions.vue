<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Abonnements</h1>
        <p class="subtitle">Gérez vos dépenses récurrentes.</p>
      </div>
      <div class="header-actions">
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn btn-primary" @click="openCreate">+ Nouvel abonnement</button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !subscriptions.length" class="empty">Chargement…</div>
    <div v-else-if="!loading && !subscriptions.length" class="empty">Aucun abonnement.</div>

    <table v-else class="table">
      <thead>
        <tr>
          <th>Nom</th>
          <th>Montant</th>
          <th>Planification</th>
          <th>Prochaine échéance</th>
          <th>Dernière exéc.</th>
          <th>Compte débit</th>
          <th>Compte crédit</th>
          <th>Catégorie</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in subscriptions" :key="s.id" :class="{ 'row-overdue': s.is_overdue }">
          <td>
            {{ s.name }}
            <span v-if="s.is_forecast_only" class="badge-forecast" title="Ne crée pas de transaction automatiquement">Prévisionnel</span>
            <span v-else-if="s.is_overdue" class="badge-overdue">En retard</span>
          </td>
          <td>{{ fmtAmount(s.amount, s.from_account_id) }}</td>
          <td class="muted">{{ scheduleLabel(s) }}</td>
          <td :class="s.is_overdue ? 'overdue' : 'muted'">{{ fmtDate(s.next_due_at) }}</td>
          <td class="muted">{{ s.last_executed_at ? fmtDate(s.last_executed_at) : '—' }}</td>
          <td class="muted">{{ accountName(s.from_account_id) }}</td>
          <td class="muted">{{ accountName(s.to_account_id) }}</td>
          <td class="muted">{{ categoryName(s.category_id) }}</td>
          <td class="actions">
            <button class="btn-action btn-execute" :disabled="s.executing" @click="executeSubscription(s)" title="Exécuter maintenant">
              <span v-if="s.executing">…</span>
              <span v-else>▶</span>
            </button>
            <button class="btn-action" @click="openEdit(s)">✎</button>
            <button class="btn-action btn-danger" @click="deleteSubscription(s)">✕</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Modal inline -->
    <div v-if="showModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>{{ editTarget ? 'Modifier' : 'Nouvel abonnement' }}</h2>
        <label>Nom *
          <input v-model="form.name" placeholder="Netflix, Loyer…" />
        </label>
        <label>Montant *
          <input v-model.number="form.amount" type="number" step="0.01" placeholder="9.99" />
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
        <label>Compte débit *
          <select v-model="form.from_account_id">
            <option value="">— Sélectionner —</option>
            <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.name }}</option>
          </select>
        </label>
        <label>Compte crédit *
          <select v-model="form.to_account_id">
            <option value="">— Sélectionner —</option>
            <option v-for="a in accounts" :key="a.id" :value="a.id">{{ a.name }}</option>
          </select>
        </label>
        <label>Catégorie
          <select v-model="form.category_id">
            <option value="">— Aucune —</option>
            <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
          </select>
        </label>
        <label class="checkbox-label">
          <input type="checkbox" v-model="form.is_forecast_only" />
          Prévisionnel uniquement (ne crée pas de transaction automatiquement — utile si vous importez vos relevés bancaires, pour éviter les doublons)
        </label>
        <div class="modal-actions">
          <button class="btn" @click="showModal = false">Annuler</button>
          <button
            class="btn btn-primary"
            :disabled="!form.name.trim() || !form.amount || !form.from_account_id || !form.to_account_id || !scheduleValid"
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

const MONTH_NAMES = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]
const WEEKDAY_NAMES = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

const subscriptions = ref([])
const accounts = ref([])
const categories = ref([])
const commodities = ref([])
const loading = ref(false)
const error = ref('')
const showModal = ref(false)
const editTarget = ref(null)
const form = ref({
  name: '', amount: '',
  schedule_type: 'monthly', day_of_month: 1, month_of_year: 1, weekdays: [],
  from_account_id: '', to_account_id: '', category_id: '', is_forecast_only: false,
})

const { shaking, shake } = useModalShake()
useEscapeClose(() => { if (showModal.value) showModal.value = false })

const scheduleValid = computed(() => {
  if (form.value.schedule_type === 'monthly') return form.value.day_of_month >= 1 && form.value.day_of_month <= 31
  if (form.value.schedule_type === 'yearly') return form.value.day_of_month >= 1 && form.value.day_of_month <= 31 && form.value.month_of_year >= 1
  if (form.value.schedule_type === 'weekly') return form.value.weekdays.length > 0
  return false
})

function toggleWeekday(day) {
  const i = form.value.weekdays.indexOf(day)
  if (i === -1) form.value.weekdays.push(day)
  else form.value.weekdays.splice(i, 1)
}

function scheduleLabel(s) {
  if (s.schedule_type === 'monthly') return `Le ${s.day_of_month} de chaque mois`
  if (s.schedule_type === 'yearly') return `Le ${s.day_of_month} ${MONTH_NAMES[s.month_of_year - 1]}`
  if (s.schedule_type === 'weekly') return (s.weekdays || []).map(d => WEEKDAY_NAMES[d - 1]).join(', ') || '—'
  return '—'
}

// Un abonnement n'a pas de devise propre : le montant est implicitement dans celle du compte
// débité (from_account_id), voir le même commentaire côté backend (rt_reports.py) — jamais
// converti vers la devise par défaut, donc on affiche sa devise native plutôt que globale.
function currencyShort(id) {
  const c = commodities.value.find(c => String(c.id) === String(id))
  return c?.short_name?.toUpperCase?.() || '—'
}
function fmtAmount(v, accountId) {
  const a = accounts.value.find(a => String(a.id) === String(accountId))
  const short = a ? currencyShort(a.currency_id) : '—'
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(Number(v ?? 0)) + ' ' + short
}

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
}
function accountName(id) {
  const a = accounts.value.find(a => String(a.id) === String(id))
  return a ? a.name : id || '—'
}
function categoryName(id) {
  if (!id) return '—'
  const c = categories.value.find(c => String(c.id) === String(id))
  return c ? c.name : id
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [subRes, accRes, catRes, comRes] = await Promise.all([
      axios.get('/api/subscriptions'),
      axios.get('/api/accounts'),
      axios.get('/api/categories'),
      axios.get('/api/commodities'),
    ])
    subscriptions.value = (Array.isArray(subRes.data?.response_data) ? subRes.data.response_data : [])
      .map(s => ({ ...s, executing: false }))
    accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
    commodities.value = Array.isArray(comRes.data?.response_data) ? comRes.data.response_data : []
    categories.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function emptyForm() {
  return {
    name: '', amount: '',
    schedule_type: 'monthly', day_of_month: 1, month_of_year: 1, weekdays: [],
    from_account_id: '', to_account_id: '', category_id: '', is_forecast_only: false,
  }
}

function openCreate() {
  editTarget.value = null
  form.value = emptyForm()
  showModal.value = true
}

function openEdit(s) {
  editTarget.value = s
  form.value = {
    name: s.name,
    amount: s.amount,
    schedule_type: s.schedule_type,
    day_of_month: s.day_of_month || 1,
    month_of_year: s.month_of_year || 1,
    weekdays: [...(s.weekdays || [])],
    from_account_id: s.from_account_id || '',
    to_account_id: s.to_account_id || '',
    category_id: s.category_id || '',
    is_forecast_only: !!s.is_forecast_only,
  }
  showModal.value = true
}

async function save() {
  const payload = {
    name: form.value.name,
    amount: form.value.amount,
    schedule_type: form.value.schedule_type,
    day_of_month: form.value.day_of_month,
    month_of_year: form.value.month_of_year,
    weekdays: form.value.weekdays,
    from_account_id: form.value.from_account_id,
    to_account_id: form.value.to_account_id,
    category_id: form.value.category_id || null,
    is_forecast_only: form.value.is_forecast_only,
  }
  try {
    if (editTarget.value) {
      await axios.patch('/api/subscriptions', { subscription_id: editTarget.value.id, ...payload })
    } else {
      await axios.post('/api/subscriptions', payload)
    }
    showModal.value = false
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function executeSubscription(s) {
  s.executing = true
  error.value = ''
  try {
    const { data } = await axios.post('/api/subscriptions/execute', { subscription_id: s.id })
    Object.assign(s, data.response_data, { executing: false })
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de l\'exécution'
    s.executing = false
  }
}

async function deleteSubscription(s) {
  if (!confirm(`Supprimer l'abonnement « ${s.name} » ?`)) return
  try {
    await axios.delete('/api/subscriptions', { params: { subscription_id: s.id } })
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
  background: linear-gradient(90deg, #2563eb, #4f46e5);
  border-color: transparent;
  color: #fff;
}
</style>