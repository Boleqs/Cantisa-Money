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

    <!-- ── Step 0 : Scanner (upload + révision, composant partagé) ── -->
    <ReceiptOcrReview v-if="step === 0" @confirmed="onConfirmed" />

    <!-- ── Step 1 : Résultat ──────────────────────────────────── -->
    <section v-if="step === 1" class="card result-card">
      <div class="result-icon">✅</div>
      <h2>Transaction créée</h2>
      <p class="result-text">Le ticket a été enregistré avec {{ resultLineCount }} ligne(s).</p>
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
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import ReceiptOcrReview from '@/components/ReceiptOcrReview.vue'

const router = useRouter()

const activeTab = ref('list')

const documents = ref([])
const docsLoading = ref(false)
const docsError = ref('')

const steps = ['Scanner un ticket', 'Résultat']
const step = ref(0)
const resultLineCount = ref(0)

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

function onConfirmed(tx) {
  resultLineCount.value = Math.max((tx?.splits?.length || 1) - 1, 0)
  step.value = 1
}

function reset() {
  step.value = 0
}

onMounted(() => {
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
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
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
.btn-primary { background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2)); border-color: transparent; color: #fff; }
.btn-primary:not(:disabled):hover { background: linear-gradient(90deg, #1d4ed8, #4338ca); }
.btn-sm { padding: 6px 12px; font-size: 12px; }

.result-card { text-align: center; padding: 48px 24px; }
.result-icon { font-size: 48px; margin-bottom: 12px; }
.result-text { color: #9ca3af; font-size: 15px; margin: 8px 0 0; line-height: 1.7; }
.result-actions { justify-content: center; margin-top: 28px; }
</style>
