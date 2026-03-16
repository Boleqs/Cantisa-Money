<template>
  <div v-if="modelValue" class="modal-backdrop" @click.self="close">
    <div class="modal">
      <header class="modal-header">
        <div>
          <h2>{{ isEdit ? 'Modifier la transaction' : 'Nouvelle transaction' }}</h2>
          <p class="subtitle">Renseignez les informations et les splits.</p>
        </div>
        <button class="icon-btn" type="button" @click="close">✕</button>
      </header>

      <form class="modal-body" @submit.prevent="onSubmit">
        <!-- Champs principaux -->
        <div class="form-grid">
          <div class="field field-full">
            <label>Description</label>
            <input v-model="form.description" placeholder="Libellé de la transaction…" />
          </div>

          <div class="field">
            <label>Date comptable *</label>
            <input v-model="form.post_date" type="date" required />
          </div>

          <div class="field">
            <label>Date effective</label>
            <input v-model="form.effective_date" type="date" />
          </div>

          <div class="field">
            <label>Devise *</label>
            <select v-model="form.currency_id" required>
              <option value="" disabled>Sélectionner…</option>
              <option v-for="c in commodities" :key="c.id" :value="c.id">
                {{ c.name }} ({{ c.short_name?.toUpperCase() }})
              </option>
            </select>
          </div>

          <div class="field">
            <label>Catégorie</label>
            <select v-model="form.category_id">
              <option value="">— Aucune —</option>
              <option v-for="c in categories" :key="c.id" :value="c.id">
                {{ c.name }}
              </option>
            </select>
          </div>

          <div class="field toggles">
            <label>
              <input type="checkbox" v-model="form.is_cleared" />
              Pointé / Rapproché
            </label>
          </div>
        </div>

        <!-- Splits -->
        <div class="splits-section">
          <div class="splits-header">
            <span class="splits-title">Splits</span>
            <span :class="['balance-badge', balanceOk ? 'ok' : 'warn']">
              Balance : {{ fmtBalance }}
            </span>
          </div>

          <div class="split-row" v-for="(split, i) in form.splits" :key="i">
            <select v-model="split.account_id" required>
              <option value="" disabled>Compte…</option>
              <option v-for="a in accounts" :key="a.id" :value="a.id">
                {{ a.name }}
              </option>
            </select>
            <input
              v-model.number="split.quantity"
              type="number"
              step="0.01"
              placeholder="Montant (+/-)"
              required
            />
            <button
              type="button"
              class="remove-btn"
              :disabled="form.splits.length <= 2"
              @click="removeSplit(i)"
            >✕</button>
          </div>

          <button type="button" class="btn add-split-btn" @click="addSplit">
            + Ajouter un split
          </button>
        </div>

        <footer class="modal-footer">
          <button type="button" class="btn" @click="close">Annuler</button>
          <button type="submit" class="btn btn-primary" :disabled="!balanceOk">
            {{ isEdit ? 'Enregistrer' : 'Créer la transaction' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch, ref } from 'vue'
import axios from 'axios'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  mode: { type: String, default: 'create' },
  transaction: { type: Object, default: null },
})

// Le modal charge ses propres données au moment de l'ouverture
const commodities = ref([])
const accounts = ref([])
const categories = ref([])

async function loadReferenceData() {
  try {
    const [comRes, accRes, catRes] = await Promise.all([
      axios.get('/api/commodities'),
      axios.get('/api/accounts'),
      axios.get('/api/categories'),
    ])
    commodities.value = Array.isArray(comRes.data?.response_data) ? comRes.data.response_data : []
    accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
    categories.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
  } catch (e) {
    console.error('Erreur chargement données du modal', e)
  }
}

watch(() => props.modelValue, (open) => {
  if (open) loadReferenceData()
}, { immediate: true })

const emit = defineEmits(['update:modelValue', 'save', 'cancel'])

const isEdit = computed(() => props.mode === 'edit')

const emptyForm = () => ({
  id: null,
  description: '',
  post_date: new Date().toISOString().slice(0, 10),
  effective_date: '',
  currency_id: '',
  category_id: '',
  is_cleared: false,
  splits: [
    { account_id: '', quantity: 0 },
    { account_id: '', quantity: 0 },
  ],
})

const form = reactive(emptyForm())

watch(
  () => props.transaction,
  (tx) => {
    const base = emptyForm()
    if (tx) {
      base.id = tx.id
      base.description = tx.description || ''
      base.post_date = tx.post_date ? tx.post_date.slice(0, 10) : base.post_date
      base.effective_date = tx.effective_date ? tx.effective_date.slice(0, 10) : ''
      base.currency_id = tx.currency_id || ''
      base.category_id = tx.category_id || ''
      base.is_cleared = tx.is_cleared || false
      base.splits = (tx.splits && tx.splits.length)
        ? tx.splits.map(s => ({ account_id: s.account_id, quantity: s.quantity }))
        : [{ account_id: '', quantity: 0 }, { account_id: '', quantity: 0 }]
    }
    Object.assign(form, base)
  },
  { immediate: true }
)

const balance = computed(() =>
  form.splits.reduce((sum, s) => sum + (Number(s.quantity) || 0), 0)
)
const balanceOk = computed(() => Math.abs(balance.value) < 0.001)
const fmtBalance = computed(() => {
  const n = balance.value
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2, signDisplay: 'always' }).format(n)
})

function addSplit() {
  form.splits.push({ account_id: '', quantity: 0 })
}

function removeSplit(i) {
  if (form.splits.length > 2) form.splits.splice(i, 1)
}

const close = () => {
  emit('update:modelValue', false)
  emit('cancel')
}

const onSubmit = () => {
  if (!balanceOk.value) return
  emit('save', {
    id: form.id,
    description: form.description,
    post_date: form.post_date,
    effective_date: form.effective_date || null,
    currency_id: form.currency_id,
    category_id: form.category_id || null,
    is_cleared: form.is_cleared,
    splits: form.splits.map(s => ({ account_id: s.account_id, quantity: Number(s.quantity) })),
  })
  emit('update:modelValue', false)
}
</script>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.75);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal {
  width: 600px;
  max-width: 96vw;
  max-height: 90vh;
  overflow-y: auto;
  background: #020617;
  border-radius: 16px;
  border: 1px solid #1f2937;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
  padding: 16px 18px 14px;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
}

.subtitle {
  margin: 2px 0 0;
  font-size: 12px;
  color: #9ca3af;
}

.modal-body {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 12px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-full {
  grid-column: 1 / -1;
}

.field label {
  font-size: 12px;
  color: #9ca3af;
}

.field input,
.field select {
  background: #020617;
  border-radius: 8px;
  border: 1px solid #1f2937;
  padding: 6px 8px;
  color: #e5e7eb;
  font-size: 13px;
}

.field input:focus,
.field select:focus {
  outline: none;
  border-color: #2563eb;
}

.toggles {
  flex-direction: row;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #cbd5e1;
}

/* Splits */
.splits-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 12px;
}

.splits-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.splits-title {
  font-size: 13px;
  font-weight: 600;
  color: #cbd5e1;
}

.balance-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
}

.balance-badge.ok {
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.3);
  color: #86efac;
}

.balance-badge.warn {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
}

.split-row {
  display: grid;
  grid-template-columns: 1fr 130px 30px;
  gap: 8px;
  align-items: center;
}

.split-row select,
.split-row input {
  background: #020617;
  border-radius: 8px;
  border: 1px solid #1f2937;
  padding: 6px 8px;
  color: #e5e7eb;
  font-size: 13px;
}

.split-row select:focus,
.split-row input:focus {
  outline: none;
  border-color: #2563eb;
}

.remove-btn {
  background: transparent;
  border: none;
  color: #6b7280;
  cursor: pointer;
  font-size: 14px;
  padding: 0;
}

.remove-btn:hover:not(:disabled) {
  color: #fca5a5;
}

.remove-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.add-split-btn {
  align-self: flex-start;
  font-size: 12px;
  padding: 4px 10px;
}

/* Footer */
.modal-footer {
  margin-top: 4px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.btn {
  border-radius: 999px;
  border: 1px solid #374151;
  background: #111827;
  color: #e5e7eb;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: linear-gradient(90deg, #2563eb, #4f46e5);
  border-color: transparent;
}

.btn:hover:not(:disabled) {
  opacity: 0.92;
}

.icon-btn {
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  font-size: 16px;
}

.icon-btn:hover {
  color: #e5e7eb;
}
</style>
