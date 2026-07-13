<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Factures</h1>
        <p class="subtitle">Justificatifs liés à tes transactions — scanne un ticket de caisse ou une facture pour en créer une automatiquement.</p>
      </div>
    </header>

    <!-- Onglets -->
    <div class="tabs">
      <button class="tab" :class="{ active: activeTab === 'list' }" @click="switchTab('list')">Mes justificatifs</button>
      <button class="tab" :class="{ active: activeTab === 'add' }" @click="switchTab('add')">+ Ajouter un ticket</button>
    </div>

    <!-- ══════════════ Onglet Liste ══════════════ -->
    <section v-if="activeTab === 'list'" class="card">
      <div v-if="docsError" class="alert">{{ docsError }}</div>

      <div v-if="docsLoading" class="hint">Chargement…</div>
      <div v-else-if="!documents.length" class="empty-state">
        <div class="placeholder-icon">🧾</div>
        <p>Aucun justificatif pour l'instant.</p>
        <button class="btn btn-primary" @click="switchTab('add')">+ Ajouter un ticket</button>
      </div>

      <div v-else class="table-scroll">
        <table class="tx-table">
          <thead>
            <tr>
              <th>Fichier</th>
              <th>Ajouté le</th>
              <th>Transaction liée</th>
              <th class="amount-col">Montant</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="doc in documents" :key="doc.id">
              <td class="desc-cell">📎 {{ doc.original_filename }}</td>
              <td>{{ fmtDate(doc.uploaded_at) }}</td>
              <td class="desc-cell">
                <span v-if="doc.transaction">{{ doc.transaction.description || '—' }} ({{ fmtDate(doc.transaction.post_date) }})</span>
                <span v-else class="hint">Transaction supprimée</span>
              </td>
              <td class="amount-col">{{ doc.transaction ? fmtAmount(doc.transaction.amount) : '—' }}</td>
              <td class="doc-actions">
                <button class="btn btn-sm" @click="viewDocument(doc)">Voir</button>
                <button v-if="doc.transaction" class="btn btn-sm" @click="goToTransaction(doc)">Voir la transaction</button>
                <button class="btn btn-sm" @click="removeDocument(doc)">✕</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ══════════════ Onglet Ajout (flux OCR existant) ══════════════ -->
    <template v-if="activeTab === 'add'">
    <!-- Stepper -->
    <div class="stepper">
      <div v-for="(s, i) in steps" :key="i" class="step" :class="{ active: step === i, done: step > i }">
        <div class="step-dot">{{ step > i ? '✓' : i + 1 }}</div>
        <span class="step-label">{{ s }}</span>
      </div>
    </div>

    <div v-if="error" class="alert">{{ error }}</div>

    <!-- ── Step 0 : Charger le document ───────────────────────── -->
    <section v-if="step === 0" class="card">
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
        <button class="btn btn-primary" :disabled="!file || parsing" @click="parse">
          <span v-if="parsing">Lecture OCR…</span>
          <span v-else>Analyser →</span>
        </button>
      </div>
    </section>

    <!-- ── Step 1 : Réviser ───────────────────────────────────── -->
    <section v-if="step === 1" class="card">
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
            <option v-for="acc in accounts" :key="acc.id" :value="acc.id">{{ acc.name }} ({{ acc.account_type }})</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Compte de dépense</label>
          <select v-model="form.expense_account_id" class="form-select">
            <option value="">— Sélectionner —</option>
            <option v-for="acc in accounts" :key="acc.id" :value="acc.id">{{ acc.name }} ({{ acc.account_type }})</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Catégorie (pour toute la transaction)</label>
          <select v-model="form.category_id" class="form-select">
            <option :value="null">—</option>
            <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
          </select>
        </div>
      </div>

      <div class="review-controls">
        <button class="btn btn-sm" @click="addLine">+ Ajouter une ligne</button>
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
                  <option v-for="tag in tags" :key="tag.id" :value="tag.id">{{ tag.name }}</option>
                </select>
              </td>
              <td><button class="btn btn-sm" @click="lines.splice(i, 1)">✕</button></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="totals-row">
        <span>Total des lignes : <strong>{{ fmtAmount(linesTotal) }}</strong></span>
        <span v-if="detectedTotal !== null">Total lu sur le ticket : <strong>{{ fmtAmount(detectedTotal) }}</strong></span>
      </div>

      <div class="step-actions">
        <button class="btn" @click="backToUpload">← Retour</button>
        <button
          class="btn btn-primary"
          :disabled="confirming || !form.account_id || !form.expense_account_id || lines.length === 0"
          @click="confirm"
        >
          <span v-if="confirming">Création…</span>
          <span v-else>Créer la transaction →</span>
        </button>
      </div>
    </section>

    <!-- ── Step 2 : Résultat ──────────────────────────────────── -->
    <section v-if="step === 2" class="card result-card">
      <div class="result-icon">✅</div>
      <h2>Transaction créée</h2>
      <p class="result-text">Le ticket a été enregistré avec {{ lines.length }} ligne(s).</p>
      <div class="step-actions result-actions">
        <button class="btn" @click="reset">Nouveau ticket</button>
        <button class="btn" @click="switchTab('list')">Voir mes justificatifs</button>
        <button class="btn btn-primary" @click="router.push('/transactions')">Voir les transactions →</button>
      </div>
    </section>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()

const activeTab = ref('list')

const documents = ref([])
const docsLoading = ref(false)
const docsError = ref('')

const steps = ['Document', 'Révision', 'Résultat']
const step = ref(0)

const file = ref(null)
const fileInput = ref(null)
const dragging = ref(false)
const error = ref('')
const parsing = ref(false)
const confirming = ref(false)

const accounts = ref([])
const categories = ref([])
const tags = ref([])

const documentId = ref(null)
const detectedTotal = ref(null)
const warnings = ref([])
const lines = ref([])

const form = ref({
  description: '',
  post_date: new Date().toISOString().slice(0, 10),
  account_id: '',
  expense_account_id: '',
  category_id: null,
})

const linesTotal = computed(() => lines.value.reduce((sum, l) => sum + (Number(l.amount) || 0), 0))

function fmtAmount(v) {
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v || 0)
}

function fmtDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString('fr-FR')
}

function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'list') loadDocuments()
}

async function loadDocuments() {
  docsLoading.value = true
  docsError.value = ''
  try {
    const { data } = await axios.get('/api/documents')
    documents.value = Array.isArray(data?.response_data) ? data.response_data : []
  } catch (e) {
    docsError.value = e?.response?.data?.response_data || e?.message || 'Erreur lors du chargement'
  } finally {
    docsLoading.value = false
  }
}

async function viewDocument(doc) {
  try {
    const { data } = await axios.get(`/api/documents/${doc.id}`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([data], { type: doc.mime_type }))
    window.open(url, '_blank')
  } catch (e) {
    docsError.value = "Erreur lors de l'ouverture du document"
  }
}

function goToTransaction(doc) {
  router.push({ path: '/transactions', query: { tx_id: doc.transaction.id } })
}

async function removeDocument(doc) {
  try {
    await axios.delete(`/api/documents/${doc.id}`)
    documents.value = documents.value.filter(d => d.id !== doc.id)
  } catch (e) {
    docsError.value = 'Erreur lors de la suppression'
  }
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

    step.value = 1
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || "Erreur lors de l'analyse OCR"
  } finally {
    parsing.value = false
  }
}

async function confirm() {
  confirming.value = true
  error.value = ''
  try {
    await axios.post('/api/documents/confirm', {
      document_id: documentId.value,
      account_id: form.value.account_id,
      expense_account_id: form.value.expense_account_id,
      category_id: form.value.category_id,
      description: form.value.description,
      post_date: form.value.post_date,
      lines: lines.value,
    })
    step.value = 2
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
  step.value = 0
}

function reset() {
  step.value = 0
  file.value = null
  documentId.value = null
  detectedTotal.value = null
  warnings.value = []
  lines.value = []
  form.value = {
    description: '',
    post_date: new Date().toISOString().slice(0, 10),
    account_id: '',
    expense_account_id: '',
    category_id: null,
  }
  if (fileInput.value) fileInput.value.value = ''
}

async function loadReferentials() {
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
    error.value = e?.message || 'Impossible de charger les comptes/catégories/tags'
  }
}

onMounted(() => {
  loadReferentials()
  loadDocuments()
})
</script>

<style scoped>
.page {
  padding: 28px;
  color: #e5e7eb;
  background: #0b1220;
  min-height: 100vh;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}

.page-header { margin-bottom: 24px; }
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; }

.tabs { display: flex; gap: 8px; margin-bottom: 20px; }
.tab {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.5);
  color: #9ca3af;
  padding: 8px 16px;
  border-radius: 999px;
  cursor: pointer;
  font-size: 13px;
  transition: 0.15s;
}
.tab:hover { color: #cbd5e1; }
.tab.active {
  background: linear-gradient(90deg, #2563eb, #4f46e5);
  border-color: transparent;
  color: #fff;
}

.hint { font-size: 13px; color: #9ca3af; }

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 24px;
  text-align: center;
  color: #9ca3af;
}
.empty-state .placeholder-icon { font-size: 40px; }

.doc-actions { display: flex; gap: 6px; white-space: nowrap; }

.stepper { display: flex; margin-bottom: 28px; position: relative; }
.stepper::before {
  content: '';
  position: absolute;
  top: 16px; left: 16px; right: 16px;
  height: 2px;
  background: rgba(148, 163, 184, 0.2);
  z-index: 0;
}
.step { display: flex; flex-direction: column; align-items: center; flex: 1; gap: 6px; position: relative; z-index: 1; }
.step-dot {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 600;
  border: 2px solid rgba(148, 163, 184, 0.3);
  background: #0b1220; color: #9ca3af;
  transition: 0.2s;
}
.step.active .step-dot { border-color: #3b82f6; background: #1e3a5f; color: #93c5fd; }
.step.done .step-dot { border-color: #10b981; background: #064e3b; color: #6ee7b7; }
.step-label { font-size: 12px; color: #9ca3af; }
.step.active .step-label { color: #93c5fd; }
.step.done .step-label { color: #6ee7b7; }

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

.result-card { text-align: center; padding: 48px 24px; }
.result-icon { font-size: 48px; margin-bottom: 12px; }
.result-text { color: #9ca3af; font-size: 15px; margin: 8px 0 0; line-height: 1.7; }
.result-actions { justify-content: center; margin-top: 28px; }
</style>
