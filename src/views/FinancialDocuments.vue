<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Dossier financier</h1>
        <p class="subtitle">Tous vos documents importants — assurances, actes, avis d'imposition, contrats — rangés au même endroit.</p>
      </div>
      <div class="header-actions">
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <div class="export-menu">
          <button class="btn export-trigger" @click="showExportMenu = !showExportMenu">↓ Exporter <span class="caret">▾</span></button>
          <div v-if="showExportMenu" class="export-dropdown" @click.self="showExportMenu = false">
            <div class="export-dropdown-label">Tout le dossier</div>
            <button class="export-item" @click="exportZip(null)">📦 Toutes les catégories (.zip)</button>
            <template v-if="categories.length">
              <div class="export-dropdown-label">Par catégorie</div>
              <button v-for="c in categories" :key="c.name" class="export-item" @click="exportZip(c.name)">
                <span class="tag-dot" :class="'tag-' + c.color"></span> {{ c.name }}
              </button>
            </template>
          </div>
        </div>
        <button class="btn btn-primary" @click="openAdd">+ Ajouter un document</button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <section class="stats">
      <div class="stat-card">
        <div class="stat-label">Documents</div>
        <div class="stat-value">{{ documents.length }}</div>
        <div class="stat-hint">{{ usedCategoryCount }} catégorie{{ usedCategoryCount > 1 ? 's' : '' }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Espace utilisé</div>
        <div class="stat-value">{{ fmtSize(totalSize) }}</div>
        <div class="stat-hint">sur ce compte</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Ajouté récemment</div>
        <div class="stat-value">{{ recentCount }}</div>
        <div class="stat-hint">sur les 30 derniers jours</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Dernier ajout</div>
        <div class="stat-value stat-value-text">{{ lastDoc ? lastDoc.original_filename : '—' }}</div>
        <div class="stat-hint">{{ lastDoc ? relativeDate(lastDoc.uploaded_at) : '' }}</div>
      </div>
    </section>

    <div class="filter-bar">
      <div class="search-wrapper">
        <span class="search-icon">🔍</span>
        <input v-model="search" class="search-input" type="text" placeholder="Rechercher un nom, une catégorie, ou un mot dans le contenu…" />
      </div>
    </div>
    <p class="search-hint">La recherche porte aussi sur le texte des documents (PDF et images scannées).</p>

    <div class="chip-row">
      <span class="chip all" :class="{ active: activeCategory === null }" @click="activeCategory = null">
        Tous <span class="count">{{ documents.length }}</span>
      </span>
      <span
        v-for="c in ALL_CATEGORIES" :key="c.name"
        class="chip" :class="['c-' + c.color, { active: activeCategory === c.name }]"
        @click="activeCategory = c.name"
      >
        {{ c.name }} <span class="count">{{ categoryCounts[c.name] || 0 }}</span>
      </span>
    </div>

    <div v-if="loading && !documents.length" class="empty">Chargement…</div>
    <div v-else class="doc-grid">
      <div class="doc-card upload-tile" @click="openAdd">
        <div class="up-icon">+</div>
        <div class="up-title">Ajouter un document</div>
        <div class="up-sub">Cliquez pour parcourir</div>
      </div>

      <div v-for="d in displayedDocuments" :key="d.id" class="doc-card">
        <div class="doc-top">
          <div class="doc-icon" :class="iconClass(d)">{{ iconGlyph(d) }}</div>
          <div class="doc-meta">
            <div class="doc-name" :title="d.original_filename">{{ d.original_filename }}</div>
            <div class="doc-sub">{{ fmtSize(d.file_size) }} · ajouté le {{ fmtDate(d.uploaded_at) }}</div>
          </div>
        </div>
        <div class="doc-tags">
          <span class="tag" :class="'tag-' + categoryColor(d.category)">{{ d.category }}</span>
        </div>
        <div v-if="linkLabel(d)" class="doc-link"><span class="ic">↗</span> {{ linkLabel(d) }}</div>
        <div class="doc-actions">
          <button class="btn-action" @click="openDocument(d)">Ouvrir</button>
          <button class="btn-action" @click="openEdit(d)">✎</button>
          <button class="btn-action" @click="deleteDocument(d)">✕</button>
        </div>
      </div>

      <div v-if="!loading && !displayedDocuments.length" class="empty-grid">
        Aucun document{{ search || activeCategory ? ' ne correspond à ces filtres' : '' }}.
      </div>
    </div>

    <!-- Modal ajout/édition -->
    <div v-if="showModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>{{ editTarget ? 'Modifier le document' : 'Ajouter un document' }}</h2>

        <template v-if="!editTarget">
          <div
            class="drop-zone" :class="{ 'drop-zone--over': dragging }"
            @dragover.prevent="dragging = true"
            @dragleave="dragging = false"
            @drop.prevent="onDrop"
            @click="fileInput.click()"
          >
            <input ref="fileInput" type="file" accept="image/jpeg,image/png,image/webp,application/pdf" hidden @change="onFileChange" />
            <span v-if="!form.file">📎 Glisse un fichier ici, ou clique pour parcourir</span>
            <span v-else class="file-name">📄 {{ form.file.name }}</span>
          </div>
        </template>
        <p v-else class="hint-text">Le fichier ne peut pas être remplacé — supprime ce document et ré-ajoute-le si besoin.</p>

        <label>Catégorie *
          <select v-model="form.category">
            <option v-for="c in ALL_CATEGORIES" :key="c.name" :value="c.name">{{ c.name }}</option>
          </select>
        </label>
        <label>Description (facultatif)
          <textarea v-model="form.description" rows="2" placeholder="Note libre..."></textarea>
        </label>
        <label>Lié à… (facultatif)
          <select v-model="form.linkedType">
            <option value="none">Aucun</option>
            <option value="account">Un compte</option>
            <option value="asset">Un actif</option>
            <option value="loan">Un prêt</option>
          </select>
        </label>
        <label v-if="form.linkedType === 'account'">Compte
          <select v-model="form.linkedId">
            <option v-for="a in accounts" :key="a.id" :value="a.id">{{ accountDisplayLabel(a, accounts) }}</option>
          </select>
        </label>
        <label v-if="form.linkedType === 'asset'">Actif
          <select v-model="form.linkedId">
            <option v-for="a in assets" :key="a.id" :value="a.id">{{ a.name }} ({{ a.symbol }})</option>
          </select>
        </label>
        <label v-if="form.linkedType === 'loan'">Prêt
          <select v-model="form.linkedId">
            <option v-for="l in loans" :key="l.id" :value="l.id">{{ l.name }}</option>
          </select>
        </label>

        <div class="modal-actions">
          <button class="btn" @click="showModal = false">Annuler</button>
          <button
            class="btn btn-primary"
            :disabled="actionPending || !form.category || (!editTarget && !form.file)"
            @click="saveDocument"
          >{{ actionPending ? 'Enregistrement…' : 'Enregistrer' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import axios from 'axios'
import { useModalShake, useEscapeClose } from '@/utils/modalUX'
import { confirmDialog } from '@/utils/confirmDialog'
import { useToast } from '@/utils/toast'
import { accountDisplayLabel } from '@/utils/accountDisplay.js'

const toast = useToast()

// Couleur -> classes CSS tag-*/chip c-*, alignées sur la maquette validée.
const ALL_CATEGORIES = [
  { name: 'Banque', color: 'blue' },
  { name: 'Immobilier', color: 'amber' },
  { name: 'Assurance', color: 'teal' },
  { name: 'Fiscal', color: 'purple' },
  { name: 'Crédits', color: 'red' },
  { name: 'Retraite & épargne', color: 'green' },
  { name: 'Juridique', color: 'slate' },
]
const COLOR_BY_CATEGORY = Object.fromEntries(ALL_CATEGORIES.map(c => [c.name, c.color]))
function categoryColor(name) {
  return COLOR_BY_CATEGORY[name] || 'slate'
}

const documents = ref([])
const accounts = ref([])
const assets = ref([])
const loans = ref([])
const loading = ref(false)
const error = ref('')
const search = ref('')
const activeCategory = ref(null)
const showExportMenu = ref(false)
const actionPending = ref(false)

const showModal = ref(false)
const editTarget = ref(null)
const dragging = ref(false)
const fileInput = ref(null)
const form = ref({ file: null, category: 'Banque', description: '', linkedType: 'none', linkedId: null })

const { shaking, shake } = useModalShake()
useEscapeClose(() => { showModal.value = false }, shake, showModal)

// Catégories effectivement utilisées (pour le menu d'export "par catégorie" — inutile de proposer
// une catégorie sans aucun document).
const categories = computed(() => ALL_CATEGORIES.filter(c => categoryCounts.value[c.name]))

const categoryCounts = computed(() => {
  const counts = {}
  for (const d of documents.value) counts[d.category] = (counts[d.category] || 0) + 1
  return counts
})
const usedCategoryCount = computed(() => Object.keys(categoryCounts.value).length)
const totalSize = computed(() => documents.value.reduce((s, d) => s + (d.file_size || 0), 0))
const recentCount = computed(() => {
  const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000
  return documents.value.filter(d => d.uploaded_at && new Date(d.uploaded_at).getTime() >= cutoff).length
})
const lastDoc = computed(() => documents.value[0] || null) // déjà trié par uploaded_at desc côté backend

// La recherche porte aussi sur extracted_text (OCR), jamais renvoyé par l'API (uniquement utilisé
// côté serveur pour le ILIKE) — un filtrage purement client sur `documents` ne pourrait donc jamais
// retrouver un document par son contenu. La liste affichée est donc récupérée séparément, filtrée
// côté serveur (?category=&q=), pendant que `documents` (non filtré) reste la source des stats et
// des compteurs par catégorie toujours visibles dans les chips.
const displayedDocuments = ref([])
async function loadFiltered() {
  try {
    const res = await axios.get('/api/financial-documents', {
      params: {
        category: activeCategory.value || undefined,
        q: search.value.trim() || undefined,
      },
    })
    displayedDocuments.value = Array.isArray(res.data?.response_data) ? res.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}
let searchDebounce = null
watch(search, () => {
  clearTimeout(searchDebounce)
  searchDebounce = setTimeout(loadFiltered, 300)
})
watch(activeCategory, loadFiltered)

function fmtDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('fr-FR')
}
function relativeDate(iso) {
  if (!iso) return ''
  const days = Math.round((Date.now() - new Date(iso).getTime()) / 86400000)
  if (days <= 0) return "aujourd'hui"
  if (days === 1) return 'il y a 1 jour'
  return `il y a ${days} jours`
}
function fmtSize(bytes) {
  if (!bytes) return '0 Ko'
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} Ko`
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`
}
function iconClass(d) {
  return d.mime_type === 'application/pdf' ? 'pdf' : 'img'
}
function iconGlyph(d) {
  return d.mime_type === 'application/pdf' ? '📄' : '🖼'
}
function linkLabel(d) {
  if (d.linked_account_id) {
    const a = accounts.value.find(x => x.id === d.linked_account_id)
    return a ? `Lié au compte « ${accountDisplayLabel(a, accounts.value)} »` : null
  }
  if (d.linked_asset_id) {
    const a = assets.value.find(x => x.id === d.linked_asset_id)
    return a ? `Lié à l'actif « ${a.name} »` : null
  }
  if (d.linked_loan_id) {
    const l = loans.value.find(x => x.id === d.linked_loan_id)
    return l ? `Lié au prêt « ${l.name} »` : null
  }
  return null
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [docsRes, accRes, assetsRes, loansRes] = await Promise.all([
      axios.get('/api/financial-documents'),
      axios.get('/api/accounts'),
      axios.get('/api/assets'),
      axios.get('/api/loans'),
    ])
    documents.value = Array.isArray(docsRes.data?.response_data) ? docsRes.data.response_data : []
    displayedDocuments.value = documents.value
    accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
    assets.value = Array.isArray(assetsRes.data?.response_data) ? assetsRes.data.response_data : []
    loans.value = Array.isArray(loansRes.data?.response_data) ? loansRes.data.response_data : []
    if (activeCategory.value || search.value.trim()) await loadFiltered()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function openAdd() {
  editTarget.value = null
  form.value = { file: null, category: 'Banque', description: '', linkedType: 'none', linkedId: null }
  showModal.value = true
}

function openEdit(d) {
  editTarget.value = d
  let linkedType = 'none', linkedId = null
  if (d.linked_account_id) { linkedType = 'account'; linkedId = d.linked_account_id }
  else if (d.linked_asset_id) { linkedType = 'asset'; linkedId = d.linked_asset_id }
  else if (d.linked_loan_id) { linkedType = 'loan'; linkedId = d.linked_loan_id }
  form.value = { file: null, category: d.category, description: d.description || '', linkedType, linkedId }
  showModal.value = true
}

function setFile(f) { form.value.file = f }
function onDrop(e) {
  dragging.value = false
  const f = e.dataTransfer.files[0]
  if (f) setFile(f)
}
function onFileChange(e) {
  const f = e.target.files[0]
  if (f) setFile(f)
}

function linkFields() {
  return {
    linked_account_id: form.value.linkedType === 'account' ? form.value.linkedId : null,
    linked_asset_id: form.value.linkedType === 'asset' ? form.value.linkedId : null,
    linked_loan_id: form.value.linkedType === 'loan' ? form.value.linkedId : null,
  }
}

async function saveDocument() {
  if (actionPending.value) return
  actionPending.value = true
  try {
    if (editTarget.value) {
      await axios.patch('/api/financial-documents', {
        document_id: editTarget.value.id,
        category: form.value.category,
        description: form.value.description || null,
        ...linkFields(),
      })
    } else {
      const fd = new FormData()
      fd.append('file', form.value.file)
      fd.append('category', form.value.category)
      if (form.value.description) fd.append('description', form.value.description)
      const links = linkFields()
      if (links.linked_account_id) fd.append('linked_account_id', links.linked_account_id)
      if (links.linked_asset_id) fd.append('linked_asset_id', links.linked_asset_id)
      if (links.linked_loan_id) fd.append('linked_loan_id', links.linked_loan_id)
      await axios.post('/api/financial-documents', fd)
    }
    showModal.value = false
    await reload()
    toast.success(editTarget.value ? 'Document modifié.' : 'Document ajouté.')
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    actionPending.value = false
  }
}

async function deleteDocument(d) {
  const ok = await confirmDialog({
    title: 'Supprimer le document',
    message: `Supprimer « ${d.original_filename} » ?`,
    confirmLabel: 'Supprimer',
    danger: true,
  })
  if (!ok) return
  try {
    await axios.delete('/api/financial-documents/' + d.id)
    await reload()
    toast.success('Document supprimé.')
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function openDocument(d) {
  try {
    const res = await axios.get('/api/financial-documents/' + d.id, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([res.data], { type: d.mime_type }))
    window.open(url, '_blank')
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function exportZip(category) {
  showExportMenu.value = false
  try {
    const res = await axios.get('/api/financial-documents/export', {
      params: category ? { category } : {},
      responseType: 'blob',
    })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')
    a.href = url
    a.download = `dossier-financier${category ? '-' + category : ''}-${stamp}.zip`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

onMounted(() => reload())
</script>

<style scoped>
.page {
  padding: 28px;
  color: #e5e7eb;
  background: #0b1220;
  min-height: 100vh;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}
.page-header { display: flex; align-items: flex-end; justify-content: space-between; gap: 16px; margin-bottom: 22px; flex-wrap: wrap; }
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; max-width: 46ch; }
.header-actions { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13.5px;
  cursor: pointer;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2)); border-color: transparent; color: #fff; font-weight: 600; }

.export-menu { position: relative; }
.export-trigger .caret { font-size: 10px; opacity: 0.7; margin-left: 2px; }
.export-dropdown {
  position: absolute; top: calc(100% + 8px); left: 0; z-index: 20;
  background: #17213b; border: 1px solid rgba(148,163,184,0.25); border-radius: 12px;
  padding: 8px; width: 232px; box-shadow: 0 12px 32px rgba(0,0,0,0.45);
  display: flex; flex-direction: column; gap: 1px;
}
.export-dropdown-label { font-size: 10.5px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #6b7280; padding: 8px 10px 4px; }
.export-item {
  display: flex; align-items: center; gap: 8px; text-align: left;
  background: transparent; border: none; color: #e5e7eb; font-family: inherit;
  font-size: 13px; padding: 8px 10px; border-radius: 8px; cursor: pointer;
}
.export-item:hover { background: rgba(148, 163, 184, 0.1); }
.tag-dot { width: 8px; height: 8px; padding: 0; border-radius: 50%; display: inline-block; border-width: 1px; }

.alert { border: 1px solid rgba(239, 68, 68, 0.5); background: rgba(239, 68, 68, 0.08); padding: 12px 14px; border-radius: 12px; margin-bottom: 16px; color: #fecaca; }
.empty { padding: 18px; border: 1px solid rgba(148, 163, 184, 0.18); background: rgba(15, 23, 42, 0.55); border-radius: 14px; color: #cbd5e1; }
.empty-grid { grid-column: 1 / -1; padding: 24px; text-align: center; color: #6b7280; }

.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
.stat-card { background: rgba(2, 6, 23, 0.45); border: 1px solid rgba(148, 163, 184, 0.16); border-radius: 14px; padding: 16px 18px; }
.stat-label { font-size: 11.5px; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.06em; }
.stat-value { font-size: 22px; font-weight: 700; margin-top: 6px; }
.stat-value-text { font-size: 16px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stat-hint { font-size: 12px; color: #6b7280; margin-top: 3px; }

.filter-bar { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; flex-wrap: wrap; }
.search-hint { margin: 0 0 16px; font-size: 11.5px; color: #6b7280; }
.search-wrapper { position: relative; flex: 1 1 260px; max-width: 420px; }
.search-icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); opacity: 0.6; font-size: 13px; }
.search-input {
  width: 100%; padding: 10px 12px 10px 34px; border-radius: 10px;
  border: 1px solid rgba(148,163,184,0.25); background: rgba(15,23,42,0.7); color: #e5e7eb; font-size: 13.5px;
}

.chip-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 22px; }
.chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 13px; border-radius: 999px; font-size: 12.5px; font-weight: 600;
  border: 1px solid rgba(148,163,184,0.25); color: #9ca3af; background: rgba(15,23,42,0.7);
  cursor: pointer; user-select: none;
}
.chip .count { opacity: 0.65; font-weight: 500; }
.chip.active { color: #fff; border-color: transparent; }
.chip.all.active { background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2)); }
.chip.c-blue.active { background: linear-gradient(90deg,#3b82f6,#60a5fa); }
.chip.c-amber.active { background: linear-gradient(90deg,#f59e0b,#fbbf24); }
.chip.c-teal.active { background: linear-gradient(90deg,#14b8a6,#2dd4bf); }
.chip.c-purple.active { background: linear-gradient(90deg,#a855f7,#c084fc); }
.chip.c-red.active { background: linear-gradient(90deg,#ef4444,#f87171); }
.chip.c-green.active { background: linear-gradient(90deg,#22c55e,#4ade80); }
.chip.c-slate.active { background: linear-gradient(90deg,#64748b,#94a3b8); }

.doc-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(255px, 1fr)); gap: 14px; }
.doc-card { background: rgba(2, 6, 23, 0.45); border: 1px solid rgba(148, 163, 184, 0.16); border-radius: 14px; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.doc-top { display: flex; align-items: flex-start; gap: 12px; }
.doc-icon {
  width: 42px; height: 42px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; font-size: 18px;
  background: rgba(148, 163, 184, 0.08); border: 1px solid rgba(148, 163, 184, 0.16);
}
.doc-icon.pdf { color: #f87171; }
.doc-icon.img { color: #60a5fa; }
.doc-meta { min-width: 0; flex: 1; }
.doc-name { font-size: 13.5px; font-weight: 600; line-height: 1.35; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.doc-sub { font-size: 11.5px; color: #6b7280; margin-top: 4px; }

.doc-tags { display: flex; gap: 6px; flex-wrap: wrap; }
.tag { font-size: 11px; font-weight: 600; padding: 3px 9px; border-radius: 999px; border: 1px solid; }
.tag-blue { background: rgba(59, 130, 246, 0.12); color: #93c5fd; border-color: rgba(59, 130, 246, 0.3); }
.tag-amber { background: rgba(245, 158, 11, 0.1); color: #fde68a; border-color: rgba(245, 158, 11, 0.3); }
.tag-teal { background: rgba(20, 184, 166, 0.1); color: #5eead4; border-color: rgba(20, 184, 166, 0.3); }
.tag-purple { background: rgba(168, 85, 247, 0.1); color: #d8b4fe; border-color: rgba(168, 85, 247, 0.3); }
.tag-red { background: rgba(239, 68, 68, 0.1); color: #fca5a5; border-color: rgba(239, 68, 68, 0.3); }
.tag-green { background: rgba(34, 197, 94, 0.1); color: #86efac; border-color: rgba(34, 197, 94, 0.3); }
.tag-slate { background: rgba(148, 163, 184, 0.1); color: #cbd5e1; border-color: rgba(148, 163, 184, 0.28); }

.doc-link { font-size: 11.5px; color: #9ca3af; display: flex; align-items: center; gap: 5px; }
.doc-link .ic { opacity: 0.7; }

.doc-actions { display: flex; gap: 6px; padding-top: 10px; margin-top: auto; border-top: 1px solid rgba(148, 163, 184, 0.16); }
.doc-actions .btn-action {
  flex: 1; text-align: center; background: transparent; border: 1px solid rgba(148,163,184,0.25);
  color: #9ca3af; padding: 6px 8px; border-radius: 8px; font-size: 11.5px; cursor: pointer;
}
.doc-actions .btn-action:hover { background: rgba(148, 163, 184, 0.1); }

.doc-card.upload-tile {
  align-items: center; justify-content: center; text-align: center;
  border-style: dashed; border-color: rgba(148,163,184,0.25); background: transparent;
  gap: 8px; min-height: 140px; cursor: pointer;
}
.doc-card.upload-tile:hover { border-color: #3b82f6; background: rgba(59, 130, 246, 0.06); }
.upload-tile .up-icon {
  width: 42px; height: 42px; border-radius: 10px;
  background: linear-gradient(135deg, rgba(37,99,235,0.18), rgba(79,70,229,0.18));
  display: flex; align-items: center; justify-content: center; font-size: 18px; color: #93c5fd;
  border: 1px solid rgba(59, 130, 246, 0.3);
}
.upload-tile .up-title { font-size: 13.5px; font-weight: 600; }
.upload-tile .up-sub { font-size: 11.5px; color: #6b7280; max-width: 20ch; }

.modal-backdrop { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #1e293b; border: 1px solid rgba(148,163,184,0.2); border-radius: 16px; padding: 24px; width: 440px; max-height: 90vh; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; }
.modal h2 { margin: 0; font-size: 18px; }
.modal label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #9ca3af; }
.modal input, .modal select, .modal textarea {
  background: rgba(15,23,42,0.7); border: 1px solid rgba(148,163,184,0.25); border-radius: 8px;
  padding: 8px 10px; color: #e5e7eb; font-size: 14px; font-family: inherit; resize: vertical;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 4px; }
.hint-text { font-size: 11px; color: #64748b; margin: -6px 0 0; }

.drop-zone {
  border: 2px dashed rgba(96, 165, 250, 0.35);
  border-radius: 12px;
  padding: 28px;
  text-align: center;
  color: #9ca3af;
  cursor: pointer;
  display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap;
}
.drop-zone:hover, .drop-zone--over { border-color: #3b82f6; background: rgba(59, 130, 246, 0.06); color: #93c5fd; }
.file-name { color: #93c5fd; font-weight: 500; display: flex; align-items: center; gap: 8px; }
</style>
