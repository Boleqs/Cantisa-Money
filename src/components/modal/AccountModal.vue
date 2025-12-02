<template>
  <div v-if="modelValue" class="modal-backdrop" @click.self="close">
    <div class="modal">
      <header class="modal-header">
        <div>
          <h2>{{ isEdit ? 'Modifier le compte' : 'Nouveau compte' }}</h2>
          <p class="subtitle">
            Définissez les informations du compte et ses soldes.
          </p>
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
            <label>Type</label>
            <select v-model="form.type">
              <option value="bank">Bank account</option>
              <option value="investment">Investment account</option>
            </select>
          </div>

          <div class="field">
            <label>Institution</label>
            <input
              v-model="form.institution"
              placeholder="Banque, courtier…"
            />
          </div>

          <div class="field">
            <label>Devise</label>
            <input v-model="form.currency" placeholder="EUR, USD…" />
          </div>

          <div class="field">
            <label>Bank balance</label>
            <input
              v-model.number="form.bank_balance"
              type="number"
              step="0.01"
            />
          </div>

          <div class="field">
            <label>Adj. balance</label>
            <input
              v-model.number="form.adjusted_balance"
              type="number"
              step="0.01"
            />
          </div>

          <div class="field">
            <label>Code interne</label>
            <input v-model="form.code" placeholder="CCP-BRS…" />
          </div>

          <div class="field">
            <label>Dernière mise à jour</label>
            <input v-model="form.last_updated" type="date" />
          </div>

          <div class="field field-full toggles">
            <label>
              <input type="checkbox" v-model="form.is_archived" />
              Compte archivé
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
  modelValue: { type: Boolean, required: true }, // v-model:visible
  mode: { type: String, default: 'create' },     // 'create' | 'edit'
  account: { type: Object, default: null }       // compte à éditer
})

const emit = defineEmits(['update:modelValue', 'save', 'cancel'])

const isEdit = computed(() => props.mode === 'edit')

const emptyForm = () => ({
  id: null,
  name: '',
  type: 'bank',
  institution: '',
  currency: 'EUR',
  bank_balance: 0,
  adjusted_balance: 0,
  last_updated: new Date().toISOString().slice(0, 10),
  code: '',
  is_archived: false
})

const form = reactive(emptyForm())

// quand on ouvre en mode édition, on copie les valeurs du compte
watch(
  () => props.account,
  (acc) => {
    Object.assign(
      form,
      emptyForm(),
      acc ? { ...acc } : {}
    )
  },
  { immediate: true }
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
  width: 520px;
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

/* boutons */
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
