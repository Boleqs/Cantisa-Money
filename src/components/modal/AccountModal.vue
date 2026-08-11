<template>
  <div v-if="modelValue" class="modal-backdrop" @click.self="shake">
    <div class="modal" :class="{ 'modal-shake': shaking }">
      <header class="modal-header">
        <div>
          <h2>{{ isEdit ? 'Modifier le compte' : 'Nouveau compte' }}</h2>
          <p class="subtitle">Définissez les informations du compte.</p>
        </div>
        <button class="icon-btn" type="button" @click="close">✕</button>
      </header>

      <form class="modal-body" @submit.prevent="onSubmit">
        <div class="form-grid">
          <div class="field">
            <label>Nom du compte *</label>
            <input v-model="form.name" required />
          </div>

          <div class="field">
            <label>Code interne</label>
            <input v-model="form.code" placeholder="CCP-BRS…" />
          </div>

          <div class="field field-full">
            <label>Description</label>
            <input v-model="form.description" />
          </div>

          <div class="field">
            <label>Devise *</label>
            <select v-model="form.currency_id" required :disabled="!!selectedParentCurrency">
              <option value="" disabled>Sélectionner…</option>
              <option v-for="c in commodities" :key="c.id" :value="c.id">
                {{ c.name }} ({{ c.short_name?.toUpperCase() }})
              </option>
            </select>
            <span v-if="selectedParentCurrency" class="hint">Devise héritée du compte parent.</span>
          </div>

          <div class="field">
            <label>Compte parent</label>
            <select v-model="form.parent_id">
              <option :value="null">Aucun</option>
              <option v-for="a in parentAccounts" :key="a.id" :value="a.id">
                {{ accountDisplayLabel(a, parentAccounts) }}
              </option>
            </select>
          </div>

          <div class="field">
            <label>Institution bancaire</label>
            <div class="inline-add">
              <template v-if="addingInstitution">
                <input
                  v-model="newInstitutionName"
                  class="inline-input"
                  placeholder="Nom de la banque…"
                  autofocus
                  @keyup.enter="createInstitution"
                  @keyup.esc="addingInstitution = false"
                />
                <button type="button" class="icon-btn-sm" :disabled="!newInstitutionName?.trim() || creatingInstitution" @click="createInstitution">✓</button>
                <button type="button" class="icon-btn-sm" @click="addingInstitution = false">✕</button>
              </template>
              <template v-else>
                <select v-model="form.institution_id">
                  <option :value="null">Aucune</option>
                  <option v-for="i in institutions" :key="i.id" :value="i.id">{{ i.name }}</option>
                </select>
                <button type="button" class="icon-btn-sm" title="Nouvelle institution" @click="addingInstitution = true; newInstitutionName = ''">+</button>
              </template>
            </div>
          </div>

          <div class="field">
            <label>Type</label>
            <select v-model="form.account_type">
              <option value="">— Aucun —</option>
              <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </div>

          <div class="field" v-if="isEquity">
            <label>Sous-type (Equity)</label>
            <select v-model="form.account_subtype">
              <option value="">— Aucun —</option>
              <option value="fr_PEA">fr_PEA</option>
              <option value="Other">Other</option>
            </select>
          </div>
          <div class="field" v-else></div>

          <div class="field">
            <label>Ligne fiscale</label>
            <select v-model="form.tax_treatment">
              <option :value="null">— Non fiscal —</option>
              <option v-for="t in TAX_TREATMENTS" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
            <span class="hint">Tout mouvement sur ce compte compte comme fiscal, quelle que soit sa catégorie.</span>
          </div>

          <div class="field field-full toggles">
            <label>
              <input type="checkbox" v-model="form.is_hidden" />
              Compte caché
            </label>
            <label>
              <input type="checkbox" v-model="form.is_virtual" />
              Compte virtuel
            </label>
          </div>

          <template v-if="!isEdit && canHaveOpeningBalance">
            <div class="field">
              <label>Solde initial</label>
              <input v-model="form.opening_balance" type="number" step="0.01" placeholder="Optionnel" />
              <span class="hint">Si l'historique des transactions de ce compte a été perdu lors de son intégration.</span>
            </div>
            <div class="field">
              <label>À la date du</label>
              <input v-model="form.opening_balance_date" type="date" :disabled="!form.opening_balance" />
            </div>
          </template>
        </div>

        <footer class="modal-footer">
          <button type="button" class="btn" @click="close">Annuler</button>
          <button type="submit" class="btn btn-primary">
            {{ isEdit ? 'Enregistrer' : 'Créer le compte' }}
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
import { accountDisplayLabel } from '@/utils/accountDisplay.js'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  mode: { type: String, default: 'create' },
  account: { type: Object, default: null },
  commodities: { type: Array, default: () => [] },
  parentAccounts: { type: Array, default: () => [] },
  institutions: { type: Array, default: () => [] },
  // Restreint le select "Type" (ex: page Comptes de revenus et dépenses -> Income/Expense
  // uniquement) ; par défaut les 5 types utilisables depuis la page Comptes classique.
  typeOptions: {
    type: Array,
    default: () => [
      { value: 'Current', label: 'Current' },
      { value: 'Assets', label: 'Assets' },
      { value: 'Equity', label: 'Equity' },
      { value: 'Income', label: 'Income' },
      { value: 'Expense', label: 'Expense' },
    ],
  },
  defaultAccountType: { type: String, default: 'Current' },
})

const emit = defineEmits(['update:modelValue', 'save', 'cancel', 'institution-created'])

const isEdit = computed(() => props.mode === 'edit')
const isEquity = computed(() => form.account_type === 'Equity')
// Pas de sens pour Income/Expense (contreparties de catégorisation, pas de l'argent réel) —
// même règle côté backend, voir set_opening_balance() dans rt_accounts.py.
const canHaveOpeningBalance = computed(() => !['Income', 'Expense'].includes(form.account_type))

// Tenu synchronisé avec TAX_TREATMENT_VALUES dans rt_accounts.py.
const TAX_TREATMENTS = [
  { value: 'taxable_income', label: 'Revenu imposable' },
  { value: 'deductible', label: 'Charge déductible' },
  { value: 'real_estate_income', label: 'Revenu foncier' },
  { value: 'real_estate_expense', label: 'Charge foncière' },
]

const emptyForm = () => ({
  id: null,
  name: '',
  description: '',
  currency_id: '',
  parent_id: null,
  institution_id: null,
  account_type: props.defaultAccountType,
  account_subtype: '',
  is_hidden: false,
  is_virtual: false,
  code: '',
  tax_treatment: null,
  opening_balance: '',
  opening_balance_date: '',
})

const form = reactive(emptyForm())

// Création d'institution à la volée sans quitter le formulaire — même pattern que la création
// de catégorie pendant la révision d'import (Import.vue).
const addingInstitution = ref(false)
const newInstitutionName = ref('')
const creatingInstitution = ref(false)

async function createInstitution() {
  const name = (newInstitutionName.value || '').trim()
  if (!name) return
  creatingInstitution.value = true
  try {
    const existing = props.institutions.find(i => i.name.toLowerCase() === name.toLowerCase())
    if (existing) {
      form.institution_id = existing.id
    } else {
      const { data } = await axios.post('/api/institutions', { name })
      const created = data?.response_data
      if (created) {
        emit('institution-created', created)
        form.institution_id = created.id
      }
    }
    addingInstitution.value = false
  } catch (e) {
    // Erreur silencieuse ici (ex. nom déjà pris par une course) : le select repasse visible,
    // l'utilisateur peut réessayer ou choisir une institution existante.
  } finally {
    creatingInstitution.value = false
  }
}

// Déclenché par l'ouverture du modal (modelValue), pas par l'identité de `account` : en mode
// création, `account` reste `null` d'une ouverture à l'autre donc un watch sur `account` seul ne
// se redéclenche pas et laisse la saisie précédente dans le formulaire.
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    Object.assign(form, emptyForm(), props.account ? { ...props.account } : {})
  },
  { immediate: true }
)

// Réinitialise le sous-type si on quitte le type Equity
watch(
  () => form.account_type,
  (type) => {
    if (type !== 'Equity') form.account_subtype = ''
    if (['Income', 'Expense'].includes(type)) {
      form.opening_balance = ''
      form.opening_balance_date = ''
    }
  }
)

// Un compte enfant doit avoir la même devise que son parent (sinon les totaux consolidés,
// additionnés sans conversion, deviennent faux — cf. rt_accounts.py) : on la verrouille dès
// qu'un parent est choisi, plutôt que de laisser l'utilisateur se heurter à l'erreur 400.
const selectedParentCurrency = computed(() => {
  const p = props.parentAccounts.find(a => String(a.id) === String(form.parent_id))
  return p ? p.currency_id : null
})
watch(
  () => form.parent_id,
  (parentId) => {
    const p = props.parentAccounts.find(a => String(a.id) === String(parentId))
    if (p) form.currency_id = p.currency_id
  }
)

const close = () => {
  emit('update:modelValue', false)
  emit('cancel')
}

const { shaking, shake } = useModalShake()
useEscapeClose(() => { if (props.modelValue) close() }, shake, () => props.modelValue)

const onSubmit = () => {
  if (!form.name.trim()) return
  emit('save', { ...form })
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
  width: 540px;
  max-width: 100%;
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
  gap: 12px;
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

.hint {
  font-size: 11px;
  color: #6b7280;
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

.field select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.inline-add {
  display: flex;
  gap: 6px;
  align-items: center;
}
.inline-add select,
.inline-add .inline-input {
  flex: 1;
  min-width: 0;
}

.icon-btn-sm {
  flex-shrink: 0;
  border: 1px solid #374151;
  background: #111827;
  color: #e5e7eb;
  border-radius: 8px;
  padding: 5px 9px;
  font-size: 12px;
  cursor: pointer;
}
.icon-btn-sm:hover {
  opacity: 0.9;
}
.icon-btn-sm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toggles {
  flex-direction: row;
  justify-content: flex-start;
  gap: 16px;
  align-items: center;
}

.modal-footer {
  margin-top: 10px;
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
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.btn-primary {
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
  border-color: transparent;
}

.btn:hover {
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
