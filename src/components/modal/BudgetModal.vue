<template>
  <div v-if="modelValue" class="modal-backdrop" @click.self="shake">
    <div class="modal" :class="{ 'modal-shake': shaking }">
      <header class="modal-header">
        <div>
          <h2>{{ isEdit ? 'Modifier le budget' : 'Nouveau budget' }}</h2>
          <p class="subtitle">Définissez la période, le montant et les comptes, catégories ou tags associés.</p>
        </div>
        <button class="icon-btn" type="button" @click="close">✕</button>
      </header>

      <form class="modal-body" @submit.prevent="onSubmit">
        <div class="form-grid">
          <div class="field field-full">
            <label>Nom *</label>
            <input v-model="form.name" type="text" placeholder="Budget alimentation mars…" required />
          </div>

          <div class="field">
            <label>Début de période *</label>
            <input v-model="form.start_date" type="date" required />
          </div>

          <div class="field">
            <label>Fin de période *</label>
            <input v-model="form.end_date" type="date" required />
          </div>

          <div class="field field-full">
            <label>Montant alloué *</label>
            <input v-model.number="form.amount_allocated" type="number" step="0.01" min="0" required />
          </div>

          <div class="field field-full">
            <label>Reconduction automatique</label>
            <select v-model="form.renew_period">
              <option :value="null">Aucune — budget ponctuel</option>
              <option value="monthly">Mensuelle</option>
              <option value="quarterly">Trimestrielle</option>
              <option value="yearly">Annuelle</option>
            </select>
            <p class="section-hint" style="margin:2px 0 0">
              Un nouveau budget identique (même montant, mêmes comptes/catégories/tags) sera créé automatiquement à la fin de chaque période.
            </p>
          </div>
        </div>

        <!-- Comptes associés -->
        <div class="section">
          <div class="section-title">Comptes suivis</div>
          <p class="section-hint">Les dépenses sur ces comptes seront comptabilisées dans ce budget.</p>
          <div v-if="loadingRef" class="hint">Chargement…</div>
          <div v-else class="checkbox-list">
            <label v-for="acc in accounts" :key="acc.id" class="checkbox-item">
              <input type="checkbox" :value="acc.id" v-model="form.account_ids" />
              <span>{{ acc.name }}</span>
              <span v-if="acc.account_type" class="chip">{{ acc.account_type }}</span>
            </label>
            <div v-if="!accounts.length" class="hint">Aucun compte disponible.</div>
          </div>
        </div>

        <!-- Catégories associées -->
        <div class="section">
          <div class="section-title">Catégories suivies</div>
          <p class="section-hint">Les transactions classées dans ces catégories seront comptabilisées dans ce budget.</p>
          <div v-if="loadingRef" class="hint">Chargement…</div>
          <div v-else class="checkbox-list">
            <label v-for="cat in categories" :key="cat.id" class="checkbox-item">
              <input type="checkbox" :value="cat.id" v-model="form.category_ids" />
              <span>{{ cat.name }}</span>
            </label>
            <div v-if="!categories.length" class="hint">Aucune catégorie disponible.</div>
          </div>
        </div>

        <!-- Tags associés -->
        <div class="section">
          <div class="section-title">Tags suivis</div>
          <p class="section-hint">Les splits portant ces tags seront comptabilisés dans ce budget.</p>
          <div v-if="loadingRef" class="hint">Chargement…</div>
          <div v-else class="checkbox-list">
            <label v-for="tag in tags" :key="tag.id" class="checkbox-item">
              <input type="checkbox" :value="tag.id" v-model="form.tag_ids" />
              <span>{{ tag.name }}</span>
            </label>
            <div v-if="!tags.length" class="hint">Aucun tag disponible.</div>
          </div>
        </div>

        <footer class="modal-footer">
          <button type="button" class="btn" @click="close">Annuler</button>
          <button type="submit" class="btn btn-primary">
            {{ isEdit ? 'Enregistrer' : 'Créer le budget' }}
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
  mode: { type: String, default: 'create' },
  budget: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'save', 'cancel'])

const isEdit = computed(() => props.mode === 'edit')

const accounts = ref([])
const categories = ref([])
const tags = ref([])
const loadingRef = ref(false)

async function loadReferentials() {
  loadingRef.value = true
  try {
    const [accRes, catRes, tagRes] = await Promise.all([
      axios.get('/api/accounts'),
      axios.get('/api/categories'),
      axios.get('/api/tags'),
    ])
    accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
    categories.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
    tags.value = Array.isArray(tagRes.data?.response_data) ? tagRes.data.response_data : []
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
  id: null,
  name: '',
  amount_allocated: 0,
  start_date: new Date().toISOString().slice(0, 7) + '-01',
  end_date: new Date().toISOString().slice(0, 7) + '-' + new Date(new Date().getFullYear(), new Date().getMonth() + 1, 0).getDate(),
  account_ids: [],
  category_ids: [],
  tag_ids: [],
  renew_period: null,
})

const form = reactive(emptyForm())

// Déclenché par l'ouverture du modal (modelValue), pas par l'identité de `budget` : en mode
// création, `budget` reste `null` d'une ouverture à l'autre donc un watch sur `budget` seul ne se
// redéclenche pas et laisse la saisie précédente dans le formulaire.
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    const b = props.budget
    const base = emptyForm()
    if (b) {
      base.id = b.id
      base.name = b.name ?? ''
      base.amount_allocated = b.amount_allocated ?? 0
      base.start_date = b.start_date ? b.start_date.slice(0, 10) : base.start_date
      base.end_date = b.end_date ? b.end_date.slice(0, 10) : base.end_date
      base.account_ids = Array.isArray(b.account_ids) ? [...b.account_ids] : []
      base.category_ids = Array.isArray(b.category_ids) ? [...b.category_ids] : []
      base.tag_ids = Array.isArray(b.tag_ids) ? [...b.tag_ids] : []
      base.renew_period = b.renew_period ?? null
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
  width: 560px;
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

/* Section comptes */
.section {
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 12px;
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: #cbd5e1;
  margin-bottom: 4px;
}

.section-hint {
  font-size: 12px;
  color: #6b7280;
  margin: 0 0 10px;
}

.checkbox-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 200px;
  overflow-y: auto;
}

.checkbox-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #cbd5e1;
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 6px;
}

.checkbox-item:hover {
  background: rgba(148, 163, 184, 0.06);
}

.checkbox-item input[type="checkbox"] {
  accent-color: #2563eb;
}

.chip {
  margin-left: auto;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  color: #9ca3af;
}

.hint {
  font-size: 12px;
  color: #6b7280;
  padding: 4px 0;
}

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