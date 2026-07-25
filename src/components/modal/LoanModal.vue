<template>
  <div v-if="modelValue" class="modal-backdrop" @click.self="shake">
    <div class="modal" :class="{ 'modal-shake': shaking }">
      <header class="modal-header">
        <div>
          <h2>{{ isEdit ? 'Modifier le crédit' : 'Nouveau crédit' }}</h2>
          <p class="subtitle">
            Le capital, le taux, la durée et la date ne sont plus modifiables une fois le crédit créé —
            passez par une révision de taux depuis le détail du crédit pour changer le taux en cours de route.
          </p>
        </div>
        <button class="icon-btn" type="button" @click="close">✕</button>
      </header>

      <div v-if="loadingRef" class="hint">Chargement…</div>

      <form v-else class="modal-body" @submit.prevent="onSubmit">
        <div v-if="formError" class="alert">{{ formError }}</div>

        <div class="field">
          <label>Nom *</label>
          <input v-model="form.name" type="text" placeholder="Prêt immobilier, Crédit auto…" required />
        </div>

        <div class="field-row" v-if="!isEdit">
          <label class="checkbox-label">
            <input type="checkbox" v-model="form.is_existing_loan" />
            Ce crédit est déjà en cours (déjà débloqué avant l'usage de l'application)
          </label>
        </div>

        <div class="form-grid">
          <div class="field">
            <label>{{ form.is_existing_loan ? 'Capital restant dû aujourd\'hui *' : 'Montant emprunté *' }}</label>
            <input v-model.number="form.principal" type="number" step="0.01" min="0.01" :disabled="isEdit" required />
          </div>
          <div class="field">
            <label>Taux annuel (%) *</label>
            <input v-model.number="form.annual_rate" type="number" step="0.01" min="0" :disabled="isEdit" required />
          </div>
          <div class="field">
            <label>{{ form.is_existing_loan ? 'Échéances restantes *' : 'Durée totale (mois) *' }}</label>
            <input v-model.number="form.term_months" type="number" step="1" min="1" :disabled="isEdit" required />
          </div>
          <div class="field">
            <label>{{ form.is_existing_loan ? 'Date de la situation *' : 'Date de déblocage *' }}</label>
            <input v-model="form.start_date" type="date" :disabled="isEdit" required />
          </div>
          <div class="field">
            <label>Jour de prélèvement *</label>
            <input v-model.number="form.payment_day" type="number" min="1" max="31" :disabled="isEdit" required />
          </div>
        </div>

        <div class="section">
          <div class="section-title">Comptes</div>
          <div class="field">
            <label>Compte de prélèvement (Current) *</label>
            <select v-model="form.payment_account_id" required>
              <option value="">— Sélectionner —</option>
              <option v-for="a in currentAccounts" :key="a.id" :value="a.id">{{ a.name }}</option>
            </select>
            <p v-if="!currentAccounts.length" class="field-hint">Aucun compte de type Current — créez-en un d'abord.</p>
          </div>
          <div class="field">
            <label>Compte de dépense — intérêts (Expense) *</label>
            <select v-model="form.interest_expense_account_id" required>
              <option value="">— Sélectionner —</option>
              <option v-for="a in expenseAccounts" :key="a.id" :value="a.id">{{ a.name }}</option>
            </select>
            <p v-if="!expenseAccounts.length" class="field-hint">Aucun compte de type Expense — créez-en un d'abord.</p>
          </div>
          <div class="field">
            <label>Assurance emprunteur — mensualité (optionnel)</label>
            <input v-model.number="form.insurance_monthly_amount" type="number" step="0.01" min="0" placeholder="0" />
          </div>
          <div class="field" v-if="form.insurance_monthly_amount">
            <label>Compte de dépense — assurance (optionnel)</label>
            <select v-model="form.insurance_expense_account_id">
              <option value="">— Fondue dans les intérêts —</option>
              <option v-for="a in expenseAccounts" :key="a.id" :value="a.id">{{ a.name }}</option>
            </select>
            <p class="field-hint">Sans compte dédié, l'assurance est comptée avec les intérêts.</p>
          </div>
          <div class="field" v-if="form.is_existing_loan && !isEdit">
            <label>Compte d'ouverture (Equity) *</label>
            <select v-model="form.equity_opening_account_id" required>
              <option value="">— Sélectionner —</option>
              <option v-for="a in equityAccounts" :key="a.id" :value="a.id">{{ a.name }}</option>
            </select>
            <p class="field-hint">Contrepartie de l'écriture d'ouverture — le compte de prélèvement n'est pas crédité dans ce mode.</p>
            <p v-if="!equityAccounts.length" class="field-hint">Aucun compte de type Equity — créez-en un d'abord.</p>
          </div>
          <div class="field">
            <label>Catégorie (optionnel)</label>
            <select v-model="form.category_id">
              <option value="">— Aucune —</option>
              <option v-for="c in categories" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </div>
        </div>

        <label class="checkbox-label">
          <input type="checkbox" v-model="form.auto_debit" />
          Prélèvement automatique — sinon les échéances dues sont juste affichées (à confirmer manuellement, ou via l'import bancaire)
        </label>

        <footer class="modal-footer">
          <button type="button" class="btn" @click="close">Annuler</button>
          <button type="submit" class="btn btn-primary" :disabled="!canSubmit || saving">
            {{ saving ? 'Enregistrement…' : (isEdit ? 'Enregistrer' : 'Créer le crédit') }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import axios from 'axios'
import { useModalShake, useEscapeClose } from '@/utils/modalUX'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  editTarget: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const isEdit = computed(() => !!props.editTarget)

const accounts = ref([])
const categories = ref([])
const loadingRef = ref(false)
const saving = ref(false)
const formError = ref('')

const currentAccounts = computed(() => accounts.value.filter(a => a.account_type === 'Current'))
const expenseAccounts = computed(() => accounts.value.filter(a => a.account_type === 'Expense'))
const equityAccounts = computed(() => accounts.value.filter(a => a.account_type === 'Equity'))

async function loadReferentials() {
  loadingRef.value = true
  try {
    const [accRes, catRes] = await Promise.all([
      axios.get('/api/accounts'),
      axios.get('/api/categories'),
    ])
    accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
    categories.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
  } catch (e) {
    console.error('Erreur chargement des référentiels', e)
  } finally {
    loadingRef.value = false
  }
}

watch(() => props.modelValue, (open) => {
  if (open) loadReferentials()
}, { immediate: true })

const emptyForm = () => ({
  name: '',
  principal: '',
  annual_rate: '',
  term_months: '',
  start_date: new Date().toISOString().slice(0, 10),
  payment_day: 5,
  payment_account_id: '',
  interest_expense_account_id: '',
  insurance_monthly_amount: '',
  insurance_expense_account_id: '',
  category_id: '',
  auto_debit: false,
  is_existing_loan: false,
  equity_opening_account_id: '',
})

const form = reactive(emptyForm())

// Déclenché par l'ouverture du modal (modelValue), pas par l'identité de `editTarget` : en mode
// création, `editTarget` reste `null` d'une ouverture à l'autre donc un watch sur `editTarget`
// seul ne se redéclenche pas et laisse la saisie précédente dans le formulaire.
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    const l = props.editTarget
    formError.value = ''
    const base = emptyForm()
    if (l) {
      base.name = l.name ?? ''
      base.principal = l.principal ?? ''
      base.annual_rate = l.annual_rate ?? ''
      base.term_months = l.term_months ?? ''
      base.start_date = l.start_date ? l.start_date.slice(0, 10) : base.start_date
      base.payment_day = l.payment_day ?? 5
      base.payment_account_id = l.payment_account_id || ''
      base.interest_expense_account_id = l.interest_expense_account_id || ''
      base.insurance_monthly_amount = l.insurance_monthly_amount ?? ''
      base.insurance_expense_account_id = l.insurance_expense_account_id || ''
      base.category_id = l.category_id || ''
      base.auto_debit = !!l.auto_debit
      base.is_existing_loan = !!l.is_existing_loan
      base.equity_opening_account_id = l.equity_opening_account_id || ''
    }
    Object.assign(form, base)
  },
  { immediate: true }
)

const canSubmit = computed(() => {
  if (!form.name.trim() || !form.payment_account_id || !form.interest_expense_account_id) return false
  if (!isEdit.value) {
    if (!form.principal || form.annual_rate === '' || !form.term_months || !form.start_date || !form.payment_day) return false
    if (form.is_existing_loan && !form.equity_opening_account_id) return false
  }
  return true
})

const close = () => {
  formError.value = ''
  emit('update:modelValue', false)
}

const { shaking, shake } = useModalShake()
useEscapeClose(() => { if (props.modelValue) close() })

async function onSubmit() {
  formError.value = ''
  saving.value = true
  try {
    if (isEdit.value) {
      const payload = {
        loan_id: props.editTarget.id,
        name: form.name,
        payment_account_id: form.payment_account_id,
        interest_expense_account_id: form.interest_expense_account_id,
        insurance_expense_account_id: form.insurance_expense_account_id || null,
        insurance_monthly_amount: form.insurance_monthly_amount === '' ? null : form.insurance_monthly_amount,
        category_id: form.category_id || null,
        auto_debit: form.auto_debit,
      }
      await axios.patch('/api/loans', payload)
    } else {
      const payload = {
        name: form.name,
        principal: form.principal,
        annual_rate: form.annual_rate,
        term_months: form.term_months,
        start_date: form.start_date,
        payment_day: form.payment_day,
        payment_account_id: form.payment_account_id,
        interest_expense_account_id: form.interest_expense_account_id,
        insurance_expense_account_id: form.insurance_expense_account_id || null,
        insurance_monthly_amount: form.insurance_monthly_amount === '' ? null : form.insurance_monthly_amount,
        category_id: form.category_id || null,
        auto_debit: form.auto_debit,
        is_existing_loan: form.is_existing_loan,
        equity_opening_account_id: form.is_existing_loan ? form.equity_opening_account_id : null,
      }
      await axios.post('/api/loans', payload)
    }
    emit('saved')
    emit('update:modelValue', false)
  } catch (e) {
    formError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    saving.value = false
  }
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
  width: 620px;
  max-width: 96vw;
  max-height: 90vh;
  overflow-y: auto;
  background: #020617;
  border-radius: 16px;
  border: 1px solid #1f2937;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
  padding: 16px 18px 14px;
  color: #e5e7eb;
}

.modal-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.subtitle { margin: 4px 0 0; font-size: 12px; color: #9ca3af; }

.modal-body { margin-top: 10px; display: flex; flex-direction: column; gap: 14px; }

.alert {
  border: 1px solid rgba(239, 68, 68, 0.5);
  background: rgba(239, 68, 68, 0.08);
  padding: 8px 10px;
  border-radius: 10px;
  color: #fecaca;
  font-size: 13px;
}

.field-row { display: flex; }

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 12px;
}

.field { display: flex; flex-direction: column; gap: 4px; }
.field label { font-size: 12px; color: #9ca3af; }
.field input, .field select {
  background: #020617;
  border-radius: 8px;
  border: 1px solid #1f2937;
  padding: 6px 8px;
  color: #e5e7eb;
  font-size: 13px;
}
.field input:focus, .field select:focus { outline: none; border-color: #2563eb; }
.field input:disabled, .field select:disabled { opacity: 0.5; cursor: not-allowed; }
.field-hint { margin: 0; font-size: 11px; color: #6b7280; }

.section { border: 1px solid #1f2937; border-radius: 12px; padding: 12px; display: flex; flex-direction: column; gap: 10px; }
.section-title { font-size: 13px; font-weight: 600; color: #cbd5e1; }

.checkbox-label {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  color: #cbd5e1;
}
.checkbox-label input { margin-top: 2px; accent-color: #2563eb; }

.hint { font-size: 12px; color: #6b7280; padding: 4px 0; }

.modal-footer { margin-top: 4px; display: flex; justify-content: flex-end; gap: 8px; }

.btn {
  border-radius: 999px;
  border: 1px solid #374151;
  background: #111827;
  color: #e5e7eb;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: linear-gradient(90deg, #2563eb, #4f46e5); border-color: transparent; }
.btn:hover { opacity: 0.92; }

.icon-btn { border: none; background: transparent; color: #9ca3af; cursor: pointer; font-size: 16px; }
.icon-btn:hover { color: #e5e7eb; }
</style>
