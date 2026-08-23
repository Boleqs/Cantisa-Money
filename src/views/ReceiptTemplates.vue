<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Gabarits de tickets</h1>
        <p class="subtitle">
          Un gabarit mémorise, pour un marchand donné, où lire le marchand/la date/le total/les articles sur son
          ticket — au prochain ticket du même marchand, l'OCR recadre et lit spécifiquement ces zones au lieu
          d'une lecture pleine page. Créés depuis l'écran de scan d'un ticket, ou depuis cette page.
        </p>
      </div>
      <div class="header-actions">
        <input ref="newFileInput" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="onNewFile" />
        <button class="btn btn-primary" @click="newFileInput.click()">+ Nouveau gabarit</button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !templates.length" class="empty">Chargement…</div>
    <div v-else-if="!loading && !templates.length" class="empty">
      Aucun gabarit pour l'instant — scanne un ticket (Factures ou depuis une transaction) et propose-le en
      gabarit, ou clique « + Nouveau gabarit » ci-dessus avec une photo sous la main.
    </div>

    <div v-else class="template-list">
      <div v-for="t in templates" :key="t.id" class="template-row">
        <div class="template-main">
          <span class="template-name">{{ t.merchant_name }}</span>
          <div class="template-zones">
            <span v-for="z in zoneCounts(t)" :key="z.label" class="zone-chip" :class="z.label">
              <span class="dot"></span>{{ z.label === 'articles' ? 'Zone articles' : zoneLabelName(z.label) }}
            </span>
          </div>
        </div>
        <div class="template-meta muted">Mis à jour {{ fmtDate(t.updated_at) }}</div>
        <input :ref="el => setEditInput(t.id, el)" type="file" accept="image/jpeg,image/png,image/webp" hidden @change="e => onEditFile(e, t)" />
        <button class="btn-action" title="Modifier (avec une nouvelle photo du ticket)" @click="editInputs[t.id]?.click()">✎</button>
        <button class="btn-action btn-danger" title="Supprimer" @click="deleteTemplate(t)">✕</button>
      </div>
    </div>

    <ReceiptTemplateEditor
      v-if="showEditor"
      :image-url="editorImageUrl"
      :merchant-name="editorMerchantName"
      :existing-template="editorTarget"
      @saved="onSaved"
      @cancel="closeEditor"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import axios from 'axios'
import { confirmDialog } from '@/utils/confirmDialog'
import { useToast } from '@/utils/toast'
import { formatDate } from '@/utils/dateFormat.js'
import ReceiptTemplateEditor from '../components/ReceiptTemplateEditor.vue'

const toast = useToast()

const templates = ref([])
const loading = ref(false)
const error = ref('')

const newFileInput = ref(null)
const editInputs = ref({})
function setEditInput(id, el) {
  if (el) editInputs.value[id] = el
}

const showEditor = ref(false)
const editorImageUrl = ref(null)
const editorMerchantName = ref('')
const editorTarget = ref(null)

const ZONE_LABEL_NAMES = { marchand: 'Marchand', date: 'Date', total: 'Total', articles: 'Zone articles' }
function zoneLabelName(key) { return ZONE_LABEL_NAMES[key] || key }
function zoneCounts(t) {
  const seen = new Set()
  return (t.zones || []).filter(z => {
    if (seen.has(z.label)) return false
    seen.add(z.label)
    return true
  })
}

function fmtDate(v) {
  return formatDate(v, { withTime: true })
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const { data } = await axios.get('/api/receipt-templates')
    templates.value = Array.isArray(data?.response_data) ? data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function openEditorWithFile(file, target) {
  if (editorImageUrl.value) URL.revokeObjectURL(editorImageUrl.value)
  editorImageUrl.value = URL.createObjectURL(file)
  editorTarget.value = target
  editorMerchantName.value = target?.merchant_name || ''
  showEditor.value = true
}

function onNewFile(e) {
  const f = e.target.files[0]
  if (f) openEditorWithFile(f, null)
  e.target.value = ''
}

function onEditFile(e, t) {
  const f = e.target.files[0]
  if (f) openEditorWithFile(f, t)
  e.target.value = ''
}

function closeEditor() {
  showEditor.value = false
  if (editorImageUrl.value) URL.revokeObjectURL(editorImageUrl.value)
  editorImageUrl.value = null
  editorTarget.value = null
}

function onSaved(template) {
  const idx = templates.value.findIndex(t => t.id === template.id)
  if (idx >= 0) templates.value[idx] = template
  else templates.value.push(template)
  toast.success(`Gabarit « ${template.merchant_name} » enregistré.`)
  closeEditor()
}

async function deleteTemplate(t) {
  const ok = await confirmDialog({
    title: 'Supprimer le gabarit',
    message: `Supprimer le gabarit « ${t.merchant_name} » ? Les prochains tickets de ce marchand repasseront par la lecture OCR pleine page standard.`,
    confirmLabel: 'Supprimer',
    danger: true,
  })
  if (!ok) return
  try {
    await axios.delete('/api/receipt-templates', { params: { template_id: t.id } })
    templates.value = templates.value.filter(x => x.id !== t.id)
    toast.success('Gabarit supprimé.')
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

onMounted(() => reload())
onBeforeUnmount(() => {
  if (editorImageUrl.value) URL.revokeObjectURL(editorImageUrl.value)
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
.page-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 18px; flex-wrap: wrap; }
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; max-width: 70ch; line-height: 1.6; }
.header-actions { display: flex; gap: 10px; align-items: center; }

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 16px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
}
.btn-primary { background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2)); border-color: transparent; color: #fff; }

.alert {
  border: 1px solid rgba(239, 68, 68, 0.5);
  background: rgba(239, 68, 68, 0.08);
  padding: 12px 14px;
  border-radius: 12px;
  margin-bottom: 16px;
  color: #fecaca;
}
.empty {
  padding: 18px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 14px;
  color: #cbd5e1;
  line-height: 1.6;
}

.template-list { display: flex; flex-direction: column; gap: 6px; }
.template-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.5);
}
.template-main { flex: 1; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; min-width: 0; }
.template-name { font-weight: 600; font-size: 14px; }
.template-zones { display: flex; gap: 6px; flex-wrap: wrap; }
.zone-chip {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 11px; font-weight: 600; color: #9ca3af;
  border: 1px solid rgba(148, 163, 184, 0.25); border-radius: 999px; padding: 3px 9px;
}
.zone-chip .dot { width: 7px; height: 7px; border-radius: 50%; }
.zone-chip.marchand .dot { background: #a78bfa; }
.zone-chip.date .dot { background: #fbbf24; }
.zone-chip.total .dot { background: #34d399; }
.zone-chip.articles .dot { background: #60a5fa; }

.template-meta { font-size: 12px; flex-shrink: 0; }
.muted { color: #9ca3af; }

.btn-action {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
  padding: 5px 10px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
  flex-shrink: 0;
}
.btn-action:hover { background: rgba(148, 163, 184, 0.1); }
.btn-danger { border-color: rgba(239, 68, 68, 0.4); color: #fca5a5; }
.btn-danger:hover { background: rgba(239, 68, 68, 0.1); }
</style>
