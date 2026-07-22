<template>
  <div v-if="modelValue" class="modal-backdrop" @click.self="close">
    <div class="modal">
      <header class="modal-header">
        <div>
          <h2>Réviser le taux</h2>
          <p class="subtitle">Recalcule l'échéancier restant (échéances non payées) à partir de la date d'effet.</p>
        </div>
        <button class="icon-btn" type="button" @click="close">✕</button>
      </header>

      <form class="modal-body" @submit.prevent="onSubmit">
        <div v-if="formError" class="alert">{{ formError }}</div>

        <div class="field">
          <label>Date d'effet *</label>
          <input v-model="form.effective_date" type="date" required />
        </div>
        <div class="field">
          <label>Nouveau taux annuel (%) *</label>
          <input v-model.number="form.new_annual_rate" type="number" step="0.01" min="0" required />
        </div>
        <div class="field">
          <label>Mode de recalcul *</label>
          <label class="radio-item">
            <input type="radio" value="keep_term" v-model="form.recalc_mode" />
            Garder la durée restante (la mensualité est recalculée)
          </label>
          <label class="radio-item">
            <input type="radio" value="keep_payment" v-model="form.recalc_mode" />
            Garder la mensualité actuelle (la durée restante est recalculée)
          </label>
        </div>

        <footer class="modal-footer">
          <button type="button" class="btn" @click="close">Annuler</button>
          <button type="submit" class="btn btn-primary" :disabled="saving">
            {{ saving ? 'Enregistrement…' : 'Appliquer la révision' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import axios from 'axios'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  loanId: { type: String, default: null },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const saving = ref(false)
const formError = ref('')

const emptyForm = () => ({
  effective_date: new Date().toISOString().slice(0, 10),
  new_annual_rate: '',
  recalc_mode: 'keep_term',
})
const form = reactive(emptyForm())

watch(() => props.modelValue, (open) => {
  if (open) {
    formError.value = ''
    Object.assign(form, emptyForm())
  }
})

const close = () => emit('update:modelValue', false)

async function onSubmit() {
  formError.value = ''
  saving.value = true
  try {
    await axios.post('/api/loans/rate-revisions', {
      loan_id: props.loanId,
      effective_date: form.effective_date,
      new_annual_rate: form.new_annual_rate,
      recalc_mode: form.recalc_mode,
    })
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
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.75); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center; z-index: 100;
}
.modal {
  width: 440px; max-width: 96vw; background: #020617; border-radius: 16px; border: 1px solid #1f2937;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6); padding: 16px 18px 14px; color: #e5e7eb;
}
.modal-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; }
.subtitle { margin: 4px 0 0; font-size: 12px; color: #9ca3af; }
.modal-body { margin-top: 10px; display: flex; flex-direction: column; gap: 12px; }
.alert {
  border: 1px solid rgba(239, 68, 68, 0.5); background: rgba(239, 68, 68, 0.08);
  padding: 8px 10px; border-radius: 10px; color: #fecaca; font-size: 13px;
}
.field { display: flex; flex-direction: column; gap: 6px; }
.field label { font-size: 12px; color: #9ca3af; }
.field input[type="date"], .field input[type="number"] {
  background: #020617; border-radius: 8px; border: 1px solid #1f2937; padding: 6px 8px; color: #e5e7eb; font-size: 13px;
}
.radio-item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: #cbd5e1; font-weight: normal; margin-top: 4px; }
.radio-item input { accent-color: #2563eb; }
.modal-footer { margin-top: 4px; display: flex; justify-content: flex-end; gap: 8px; }
.btn {
  border-radius: 999px; border: 1px solid #374151; background: #111827; color: #e5e7eb;
  padding: 6px 12px; font-size: 13px; cursor: pointer;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: linear-gradient(90deg, #2563eb, #4f46e5); border-color: transparent; }
.icon-btn { border: none; background: transparent; color: #9ca3af; cursor: pointer; font-size: 16px; }
.icon-btn:hover { color: #e5e7eb; }
</style>
