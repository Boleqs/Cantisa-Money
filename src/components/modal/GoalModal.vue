<template>
  <div v-if="modelValue" class="modal-backdrop" @click.self="shake">
    <div class="modal" :class="{ 'modal-shake': shaking }">
      <header class="modal-header">
        <div>
          <h2>{{ isEdit ? "Modifier l'objectif" : 'Nouvel objectif' }}</h2>
          <p class="subtitle">Un besoin ponctuel (apport, achat...) ou un train de vie récurrent à confronter à votre projection de patrimoine.</p>
        </div>
        <button class="icon-btn" type="button" @click="close">✕</button>
      </header>

      <form class="modal-body" @submit.prevent="onSubmit">
        <div class="form-grid">
          <div class="field field-full">
            <label>Nom *</label>
            <input v-model="form.name" type="text" placeholder="Apport immobilier, études des enfants, retraite…" required />
          </div>

          <div class="field field-full">
            <label>Type</label>
            <div class="pill-row">
              <button type="button" class="pill" :class="{ active: form.goal_type === 'one_time' }" @click="form.goal_type = 'one_time'">
                Ponctuel
              </button>
              <button type="button" class="pill" :class="{ active: form.goal_type === 'recurring' }" @click="form.goal_type = 'recurring'">
                Récurrent (mensuel)
              </button>
            </div>
          </div>

          <div class="field">
            <label>{{ form.goal_type === 'recurring' ? 'Montant mensuel *' : 'Montant *' }}</label>
            <input v-model.number="form.target_amount" type="number" step="0.01" min="0.01" required />
          </div>

          <div class="field">
            <label>{{ form.goal_type === 'recurring' ? 'Date de début *' : 'Date *' }}</label>
            <input v-model="form.target_date" type="date" required />
          </div>

          <div v-if="form.goal_type === 'recurring'" class="field field-full">
            <label>Date de fin (optionnel)</label>
            <input v-model="form.end_date" type="date" />
            <p class="section-hint" style="margin:2px 0 0">Laissez vide pour un besoin jusqu'à la fin de l'horizon simulé (ex. retraite).</p>
          </div>
        </div>

        <footer class="modal-footer">
          <button type="button" class="btn" @click="close">Annuler</button>
          <button type="submit" class="btn btn-primary">
            {{ isEdit ? 'Enregistrer' : "Créer l'objectif" }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch } from 'vue'
import { useModalShake, useEscapeClose } from '@/utils/modalUX'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  mode: { type: String, default: 'create' },
  goal: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'save', 'cancel'])

const isEdit = computed(() => props.mode === 'edit')

const emptyForm = () => ({
  id: null,
  name: '',
  goal_type: 'one_time',
  target_amount: null,
  target_date: new Date().toISOString().slice(0, 10),
  end_date: '',
})

const form = reactive(emptyForm())

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    const g = props.goal
    const base = emptyForm()
    if (g) {
      base.id = g.id
      base.name = g.name ?? ''
      base.goal_type = g.goal_type ?? 'one_time'
      base.target_amount = g.target_amount ?? null
      base.target_date = g.target_date ? g.target_date.slice(0, 10) : base.target_date
      base.end_date = g.end_date ? g.end_date.slice(0, 10) : ''
    }
    Object.assign(form, base)
  },
  { immediate: true }
)

const close = () => {
  emit('update:modelValue', false)
  emit('cancel')
}

const { shaking, shake } = useModalShake()
useEscapeClose(() => { if (props.modelValue) close() }, shake, () => props.modelValue)

const onSubmit = () => {
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
  width: 480px;
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

.field { display: flex; flex-direction: column; gap: 4px; }
.field-full { grid-column: 1 / -1; }
.field label { font-size: 12px; color: #9ca3af; }

.field input {
  background: #020617;
  border-radius: 8px;
  border: 1px solid #1f2937;
  padding: 6px 8px;
  color: #e5e7eb;
  font-size: 13px;
}

.field input:focus { outline: none; border-color: #2563eb; }

.section-hint { font-size: 12px; color: #6b7280; }

.pill-row { display: flex; gap: 6px; flex-wrap: wrap; }
.pill {
  border: 1px solid rgba(148,163,184,0.25);
  background: rgba(2,6,23,0.6);
  color: #cbd5e1;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 12.5px;
  cursor: pointer;
}
.pill:hover { border-color: rgba(148,163,184,0.4); }
.pill.active { border-color: #2563eb; background: rgba(59,130,246,0.15); color: #fff; }

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

.btn-primary {
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
  border-color: transparent;
}

.btn:hover { opacity: 0.92; }

.icon-btn {
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  font-size: 16px;
}

.icon-btn:hover { color: #e5e7eb; }
</style>
