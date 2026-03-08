<template>
  <div v-if="modelValue" class="modal-backdrop" @click.self="close">
    <div class="modal">
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
            <label>Description *</label>
            <input v-model="form.description" required />
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
            <label>Compte parent</label>
            <select v-model="form.parent_id">
              <option :value="null">Aucun</option>
              <option v-for="a in parentAccounts" :key="a.id" :value="a.id">
                {{ a.name }}
              </option>
            </select>
          </div>

          <div class="field">
            <label>Type</label>
            <select v-model="form.account_type">
              <option value="">— Aucun —</option>
              <option value="Current">Current</option>
              <option value="Assets">Assets</option>
              <option value="Equity">Equity</option>
              <option value="Income">Income</option>
              <option value="Expense">Expense</option>
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
import { computed, reactive, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  mode: { type: String, default: 'create' },
  account: { type: Object, default: null },
  commodities: { type: Array, default: () => [] },
  parentAccounts: { type: Array, default: () => [] },
})

const emit = defineEmits(['update:modelValue', 'save', 'cancel'])

const isEdit = computed(() => props.mode === 'edit')
const isEquity = computed(() => form.account_type === 'Equity')

const emptyForm = () => ({
  id: null,
  name: '',
  description: '',
  currency_id: '',
  parent_id: null,
  account_type: 'Current',
  account_subtype: '',
  is_hidden: false,
  is_virtual: false,
  code: '',
})

const form = reactive(emptyForm())

watch(
  () => props.account,
  (acc) => {
    Object.assign(form, emptyForm(), acc ? { ...acc } : {})
  },
  { immediate: true }
)

// Réinitialise le sous-type si on quitte le type Equity
watch(
  () => form.account_type,
  (type) => {
    if (type !== 'Equity') form.account_subtype = ''
  }
)

const close = () => {
  emit('update:modelValue', false)
  emit('cancel')
}

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
  background: linear-gradient(90deg, #2563eb, #4f46e5);
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
