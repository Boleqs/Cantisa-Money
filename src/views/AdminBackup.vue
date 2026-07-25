<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Administration — Sauvegarde</h1>
        <p class="subtitle">
          Exportez l'intégralité de vos données (comptes, transactions, budgets, actifs…) ainsi que les
          justificatifs joints aux transactions dans une archive .zip, à conserver ou à réimporter — dans
          cette instance ou une autre. Les éléments déjà présents (même nom, mêmes montants et dates) sont
          automatiquement reconnus et ne sont jamais dupliqués. Les anciennes sauvegardes au format .json
          restent également réimportables.
        </p>
      </div>
    </header>

    <div class="settings-card">
      <h3 class="card-title">Exporter</h3>
      <div class="setting-row">
        <div class="setting-label">
          <span class="setting-name">Télécharger une sauvegarde complète</span>
          <span class="setting-desc">Archive .zip contenant toutes vos données actuelles et vos justificatifs.</span>
        </div>
        <button class="btn btn-primary" :disabled="exporting" @click="exportBackup">
          {{ exporting ? 'Export…' : 'Télécharger' }}
        </button>
      </div>
      <div v-if="exportError" class="modal-error">{{ exportError }}</div>
    </div>

    <div class="settings-card">
      <h3 class="card-title">Réimporter</h3>
      <div class="setting-row">
        <div class="setting-label">
          <span class="setting-name">Restaurer depuis un fichier de sauvegarde</span>
          <span class="setting-desc">Les données déjà présentes sont ignorées, seules les nouvelles sont ajoutées.</span>
        </div>
        <button class="btn btn-primary" :disabled="importing" @click="triggerImportPicker">
          {{ importing ? 'Import…' : 'Choisir un fichier…' }}
        </button>
        <input ref="importInput" type="file" accept="application/zip,.zip,application/json,.json" style="display: none" @change="onImportFileChosen" />
      </div>
      <div v-if="importError" class="modal-error">{{ importError }}</div>

      <div v-if="importReport" class="import-report">
        <div class="import-report-row" v-for="(v, k) in importReportEntries" :key="k">
          <span class="import-entity">{{ entityLabel(k) }}</span>
          <span class="import-counts">
            <span v-if="v.created" class="badge-created">+{{ v.created }}</span>
            <span v-if="v.matched" class="badge-matched">{{ v.matched }} déjà présent{{ v.matched > 1 ? 's' : '' }}</span>
            <span v-if="!v.created && !v.matched" class="muted">—</span>
          </span>
        </div>
        <p v-if="importReport.errors?.length" class="import-errors">
          <strong>{{ importReport.errors.length }} ligne(s) ignorée(s) :</strong>
          <span v-for="(e, i) in importReport.errors" :key="i">{{ e }}<br /></span>
        </p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import axios from 'axios'

const exporting     = ref(false)
const exportError   = ref('')
const importing     = ref(false)
const importError   = ref('')
const importReport  = ref(null)
const importInput   = ref(null)

const ENTITY_LABELS = {
  commodities: 'Devises', accounts: 'Comptes', categories: 'Catégories', tags: 'Tags',
  budgets: 'Budgets', budget_accounts: 'Budgets ↔ comptes', budget_categories: 'Budgets ↔ catégories',
  budget_tags: 'Budgets ↔ tags', subscriptions: 'Abonnements', assets: 'Actifs',
  asset_possessions: 'Possessions d\'actifs', asset_valuations: 'Valorisations d\'actifs',
  transactions: 'Transactions', splits: 'Répartitions (splits)', tags_on_split: 'Tags sur répartitions',
  transaction_documents: 'Justificatifs',
}
function entityLabel(k) { return ENTITY_LABELS[k] || k }
const importReportEntries = computed(() => {
  if (!importReport.value) return {}
  const { errors, user_settings, ...entries } = importReport.value
  return entries
})

async function exportBackup() {
  exporting.value = true
  exportError.value = ''
  try {
    const res = await axios.get('/api/backup/export', { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    const now = new Date()
    const stamp = now.toISOString().slice(0, 19).replace(/[:T]/g, '-')
    a.href = url
    a.download = `cantisa-backup-${stamp}.zip`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e) {
    exportError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    exporting.value = false
  }
}

function triggerImportPicker() {
  importError.value = ''
  importReport.value = null
  importInput.value?.click()
}

async function onImportFileChosen(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  importing.value = true
  importError.value = ''
  importReport.value = null
  try {
    const formData = new FormData()
    formData.append('file', file)
    const res = await axios.post('/api/backup/import', formData)
    importReport.value = res.data?.response_data || null
  } catch (e) {
    importError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.page {
  padding: 28px;
  color: #e5e7eb;
  background: #0b1220;
  min-height: 100vh;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 28px;
}
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; max-width: 720px; line-height: 1.6; }

.settings-card {
  background: #1e293b;
  border: 1px solid rgba(148,163,184,0.1);
  border-radius: 14px;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
}
.card-title { margin: 0; font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.07em; }

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 4px 0;
  border-bottom: 1px solid rgba(148,163,184,0.06);
}
.setting-row:last-child { border-bottom: none; }
.setting-label { display: flex; flex-direction: column; gap: 2px; flex: 1; }
.setting-name { font-size: 14px; color: #e5e7eb; }
.setting-desc { font-size: 12px; color: #6b7280; }

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2)); border-color: transparent; color: #fff; }

.modal-error {
  font-size: 13px;
  color: #fca5a5;
  background: rgba(239,68,68,0.08);
  border: 1px solid rgba(239,68,68,0.3);
  border-radius: 8px;
  padding: 8px 10px;
}

.import-report {
  margin-top: 4px;
  border-top: 1px solid rgba(148,163,184,0.1);
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.import-report-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13px;
}
.import-entity { color: #cbd5e1; }
.import-counts { display: flex; gap: 8px; align-items: center; }
.badge-created {
  background: rgba(74,222,128,0.12);
  color: #4ade80;
  border-radius: 6px;
  padding: 2px 8px;
  font-weight: 700;
  font-size: 12px;
}
.badge-matched {
  color: #64748b;
  font-size: 12px;
}
.muted { color: #9ca3af; }
.import-errors {
  margin: 8px 0 0;
  font-size: 12px;
  color: #fca5a5;
  line-height: 1.6;
}
</style>
