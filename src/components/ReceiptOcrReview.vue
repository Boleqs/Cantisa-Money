<template>
  <div class="ocr-review">
    <div v-if="error" class="alert">{{ error }}</div>

    <!-- Step 0 : charger le document -->
    <section v-if="localStep === 0" class="card">
      <h2>Charger le document</h2>

      <div
        class="drop-zone"
        :class="{ 'drop-zone--over': dragging }"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="onDrop"
        @click="fileInput.click()"
      >
        <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp,application/pdf" hidden @change="onFileChange" />
        <span v-if="!file">🧾 Glisse une photo de ticket ou un PDF ici, ou clique pour parcourir</span>
        <span v-else class="file-name">📄 {{ file.name }}</span>
      </div>

      <div class="info-banner">
        Lecture par OCR local (Tesseract), sans IA. Le résultat est toujours à vérifier à l'étape suivante avant validation.
      </div>

      <div class="step-actions">
        <button v-if="existingTxId" type="button" class="btn" @click="emit('cancelled')">Annuler</button>
        <button type="button" class="btn btn-primary" :disabled="!file || parsing" @click="parse">
          <span v-if="parsing">Lecture OCR…</span>
          <span v-else>Analyser →</span>
        </button>
      </div>
    </section>

    <!-- Step 1 : réviser -->
    <section v-if="localStep === 1" class="card">
      <h2>Réviser les lignes détectées</h2>

      <div v-if="warnings.length" class="alert alert-warn">
        <div v-for="(w, i) in warnings" :key="i">{{ w }}</div>
      </div>

      <div class="config-grid">
        <div class="form-group">
          <label class="form-label">Commerçant / description</label>
          <input type="text" v-model="form.description" class="form-input" placeholder="ex: Carrefour" />
        </div>
        <div class="form-group">
          <label class="form-label">Date</label>
          <input type="date" v-model="form.post_date" class="form-input" />
        </div>
        <div class="form-group">
          <label class="form-label">Compte payeur</label>
          <select v-model="form.account_id" class="form-select">
            <option value="">— Sélectionner —</option>
            <option v-for="acc in accountsList" :key="acc.id" :value="acc.id">{{ acc.name }} ({{ acc.account_type }})</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Compte de dépense</label>
          <select v-model="form.expense_account_id" class="form-select">
            <option value="">— Sélectionner —</option>
            <option v-for="acc in accountsList" :key="acc.id" :value="acc.id">{{ acc.name }} ({{ acc.account_type }})</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Catégorie (pour toute la transaction)</label>
          <select v-model="form.category_id" class="form-select">
            <option :value="null">—</option>
            <option v-for="cat in categoriesList" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
          </select>
        </div>
      </div>

      <div class="review-controls">
        <button type="button" class="btn btn-sm" @click="addLine">+ Ajouter une ligne</button>
      </div>

      <div class="table-scroll">
        <table class="tx-table">
          <thead>
            <tr>
              <th>Libellé</th>
              <th class="amount-col">Montant</th>
              <th>Tag</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(line, i) in lines" :key="i">
              <td class="desc-cell"><input type="text" v-model="line.label" class="form-input" /></td>
              <td class="amount-col"><input type="number" step="0.01" v-model.number="line.amount" class="form-input amount-input" /></td>
              <td>
                <select v-model="line.tag_id" class="cat-select">
                  <option :value="null">—</option>
                  <option v-for="tag in tagsList" :key="tag.id" :value="tag.id">{{ tag.name }}</option>
                </select>
              </td>
              <td><button type="button" class="btn btn-sm" @click="lines.splice(i, 1)">✕</button></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="totals-row">
        <span>Total des lignes : <strong>{{ fmtAmount(linesTotal) }}</strong></span>
        <span v-if="detectedTotal !== null">Total lu sur le ticket : <strong>{{ fmtAmount(detectedTotal) }}</strong></span>
      </div>

      <div class="step-actions">
        <button type="button" class="btn" @click="backToUpload">← Retour</button>
        <button
          type="button"
          class="btn btn-primary"
          :disabled="confirming || !form.account_id || !form.expense_account_id || lines.length === 0"
          @click="doConfirm"
        >
          <span v-if="confirming">{{ existingTxId ? 'Mise à jour…' : 'Création…' }}</span>
          <span v-else>{{ existingTxId ? 'Mettre à jour les splits →' : 'Créer la transaction →' }}</span>
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'

const props = defineProps({
  existingTxId: { type: String, default: null },
  existingSplitsCount: { type: Number, default: 0 },
  existingSplits: { type: Array, default: () => [] },
  existingCategoryId: { type: String, default: null },
  accounts: { type: Array, default: null },
  categories: { type: Array, default: null },
  tags: { type: Array, default: null },
})
const emit = defineEmits(['confirmed', 'cancelled'])

const localStep = ref(0)
const file = ref(null)
const fileInput = ref(null)
const dragging = ref(false)
const error = ref('')
const parsing = ref(false)
const confirming = ref(false)

const accountsList = ref(props.accounts || [])
const categoriesList = ref(props.categories || [])
const tagsList = ref(props.tags || [])

const documentId = ref(null)
const detectedTotal = ref(null)
const warnings = ref([])
const lines = ref([])

// Sur une transaction existante, préremplit compte payeur/dépense avec ceux déjà utilisés
// (le split le plus négatif = payeur, le split de type Expense — ou le plus positif à défaut —
// = dépense) plutôt que de forcer un nouveau choix à chaque scan.
function defaultAccountIds() {
  if (!props.existingSplits.length) return { account_id: '', expense_account_id: '' }
  const sorted = [...props.existingSplits].sort((a, b) => a.quantity - b.quantity)
  const payer = sorted[0]
  const expenseCandidate = props.existingSplits.find(s =>
    s.account_id !== payer.account_id &&
    (props.accounts || []).find(a => a.id === s.account_id)?.account_type === 'Expense'
  )
  const fallback = sorted[sorted.length - 1]
  return {
    account_id: payer?.account_id || '',
    expense_account_id: (expenseCandidate || fallback)?.account_id || '',
  }
}

const form = ref({
  description: '',
  post_date: new Date().toISOString().slice(0, 10),
  category_id: props.existingCategoryId || null,
  ...defaultAccountIds(),
})

const linesTotal = computed(() => lines.value.reduce((sum, l) => sum + (Number(l.amount) || 0), 0))

function fmtAmount(v) {
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v || 0)
}

function onDrop(e) {
  dragging.value = false
  const f = e.dataTransfer.files[0]
  if (f) setFile(f)
}

function onFileChange(e) {
  const f = e.target.files[0]
  if (f) setFile(f)
}

function setFile(f) {
  file.value = f
  error.value = ''
}

function addLine() {
  lines.value.push({ label: '', amount: 0, tag_id: null })
}

async function parse() {
  parsing.value = true
  error.value = ''
  try {
    const fd = new FormData()
    fd.append('file', file.value)
    const { data } = await axios.post('/api/documents/parse', fd)
    const res = data.response_data

    documentId.value = res.document_id
    detectedTotal.value = res.total
    warnings.value = res.warnings || []
    lines.value = (res.lines || []).map(l => ({ label: l.label, amount: l.amount, tag_id: l.suggested_tag_id || null }))
    form.value.description = res.merchant || ''
    form.value.post_date = res.date || new Date().toISOString().slice(0, 10)

    localStep.value = 1
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || "Erreur lors de l'analyse OCR"
  } finally {
    parsing.value = false
  }
}

async function doConfirm() {
  if (props.existingTxId && props.existingSplitsCount > 0) {
    const ok = confirm(`Cette transaction a déjà ${props.existingSplitsCount} ligne(s) — les remplacer par celles du ticket ?`)
    if (!ok) return
  }
  confirming.value = true
  error.value = ''
  try {
    const { data } = await axios.post('/api/documents/confirm', {
      document_id: documentId.value,
      account_id: form.value.account_id,
      expense_account_id: form.value.expense_account_id,
      category_id: form.value.category_id,
      description: form.value.description,
      post_date: form.value.post_date,
      lines: lines.value,
      tx_id: props.existingTxId || undefined,
    })
    emit('confirmed', data.response_data)
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la création'
  } finally {
    confirming.value = false
  }
}

async function backToUpload() {
  if (documentId.value) {
    try {
      await axios.delete(`/api/documents/${documentId.value}`)
    } catch (e) {
      // document déjà nettoyé côté serveur, sans conséquence
    }
  }
  documentId.value = null
  localStep.value = 0
}

async function loadReferentials() {
  try {
    const [accRes, catRes, tagRes] = await Promise.all([
      axios.get('/api/accounts'),
      axios.get('/api/categories'),
      axios.get('/api/tags'),
    ])
    accountsList.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
    categoriesList.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
    tagsList.value = Array.isArray(tagRes.data?.response_data) ? tagRes.data.response_data : []
  } catch (e) {
    error.value = e?.message || 'Impossible de charger les comptes/catégories/tags'
  }
}

onMounted(() => {
  if (!props.accounts) loadReferentials()
})
</script>

<style scoped>
.card {
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 16px;
}
.card h2 { margin: 0 0 20px; font-size: 18px; color: #e5e7eb; }

.alert {
  border: 1px solid rgba(239, 68, 68, 0.5);
  background: rgba(239, 68, 68, 0.08);
  padding: 12px 14px;
  border-radius: 12px;
  margin-bottom: 16px;
  color: #fecaca;
  font-size: 14px;
}
.alert-warn {
  border-color: rgba(245, 158, 11, 0.4);
  background: rgba(245, 158, 11, 0.08);
  color: #fde68a;
}

.info-banner {
  border: 1px solid rgba(96, 165, 250, 0.3);
  background: rgba(96, 165, 250, 0.07);
  border-radius: 10px;
  padding: 12px 14px;
  color: #93c5fd;
  font-size: 13px;
  margin-bottom: 16px;
}

.drop-zone {
  border: 2px dashed rgba(96, 165, 250, 0.35);
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  color: #9ca3af;
  transition: 0.2s;
  margin-bottom: 20px;
  display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap;
}
.drop-zone:hover, .drop-zone--over { border-color: #3b82f6; background: rgba(59, 130, 246, 0.06); color: #93c5fd; }
.file-name { color: #93c5fd; font-weight: 500; display: flex; align-items: center; gap: 8px; }

.form-label { display: block; font-size: 13px; color: #9ca3af; margin-bottom: 6px; }
.form-select, .form-input {
  width: 100%;
  padding: 9px 12px;
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 14px;
  outline: none;
  box-sizing: border-box;
}
.form-select:focus, .form-input:focus { border-color: rgba(96, 165, 250, 0.5); }

.config-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px 20px; margin-bottom: 20px; }
@media (max-width: 640px) { .config-grid { grid-template-columns: 1fr; } }

.review-controls { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }

.table-scroll { overflow-x: auto; border-radius: 10px; border: 1px solid rgba(148, 163, 184, 0.15); }
.tx-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.tx-table th {
  background: rgba(15, 23, 42, 0.8);
  color: #9ca3af;
  font-weight: 600;
  padding: 10px 12px;
  text-align: left;
  white-space: nowrap;
}
.tx-table td { padding: 8px 12px; border-top: 1px solid rgba(148, 163, 184, 0.1); color: #e5e7eb; }
.desc-cell { min-width: 220px; }
.amount-col { text-align: right; font-variant-numeric: tabular-nums; }
.amount-input { text-align: right; max-width: 110px; }

.cat-select {
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 6px;
  color: #e5e7eb;
  font-size: 12px;
  padding: 5px 6px;
  max-width: 160px;
  outline: none;
}

.totals-row {
  display: flex;
  gap: 24px;
  margin-top: 14px;
  font-size: 13px;
  color: #9ca3af;
}
.totals-row strong { color: #e5e7eb; }

.step-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 16px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  transition: 0.15s;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn:not(:disabled):hover { background: rgba(148, 163, 184, 0.1); }
.btn-primary { background: linear-gradient(90deg, #2563eb, #4f46e5); border-color: transparent; color: #fff; }
.btn-primary:not(:disabled):hover { background: linear-gradient(90deg, #1d4ed8, #4338ca); }
.btn-sm { padding: 6px 12px; font-size: 12px; }
</style>
