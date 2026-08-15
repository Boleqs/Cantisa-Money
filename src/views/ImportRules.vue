<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Règles apprises</h1>
        <p class="subtitle">
          Ces règles sont mémorisées automatiquement quand vous appliquez une catégorie ou une
          contrepartie à une transaction importée — elles ne sont ensuite que suggérées (jamais
          appliquées automatiquement) lors des imports/synchronisations suivants.
        </p>
      </div>
      <div class="header-actions">
        <div class="search-wrapper">
          <span class="search-icon">🔍</span>
          <input
            v-model="search"
            class="search-input"
            type="text"
            placeholder="Rechercher une règle (libellé, catégorie, compte)…"
          />
        </div>
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !rules.length" class="empty">Chargement…</div>
    <div v-else-if="!loading && !rules.length" class="empty">
      Aucune règle apprise pour l'instant — elles apparaissent ici dès que vous appliquez une
      catégorie ou une contrepartie suggérée (ou saisie manuellement) lors d'un import.
    </div>
    <div v-else-if="!filteredRules.length" class="empty">Aucune règle ne correspond à la recherche.</div>

    <div v-else class="rules-list">
      <div v-for="r in filteredRules" :key="r.id" class="rule-row">
        <div class="rule-main">
          <span class="rule-keyword">{{ r.keyword }}</span>
          <span class="rule-arrow">→</span>
          <select v-model="r._category_id" class="rule-select">
            <option :value="null">— Catégorie —</option>
            <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
          </select>
          <select v-model="r._opposing_account_id" class="rule-select">
            <option :value="null">— Contrepartie —</option>
            <option v-for="acc in accounts" :key="acc.id" :value="acc.id">{{ accountDisplayLabel(acc, accounts) }}</option>
          </select>
        </div>
        <div class="rule-meta muted">Mise à jour {{ fmtDate(r.updated_at) }}</div>
        <button
          v-if="isDirty(r)"
          class="btn-action btn-primary"
          title="Enregistrer les modifications"
          :disabled="r._saving"
          @click="saveRule(r)"
        >{{ r._saving ? '…' : '✓ Enregistrer' }}</button>
        <button class="btn-action btn-danger" title="Supprimer cette règle" @click="deleteRule(r)">✕</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { confirmDialog } from '@/utils/confirmDialog'
import { useToast } from '@/utils/toast'
import { normalizeSearch } from '@/utils/search.js'
import { formatDate } from '@/utils/dateFormat.js'
import { accountLabelById, accountDisplayLabel } from '@/utils/accountDisplay.js'

const toast = useToast()

const rules = ref([])
const categories = ref([])
const accounts = ref([])
const search = ref('')
const loading = ref(false)
const error = ref('')

function fmtDate(v) {
  return formatDate(v, { withTime: true })
}

function categoryNameById(id) {
  if (!id) return ''
  return categories.value.find(c => String(c.id) === String(id))?.name || ''
}

const filteredRules = computed(() => {
  const q = normalizeSearch(search.value)
  if (!q) return rules.value
  return rules.value.filter(r => {
    const blob = normalizeSearch([
      r.keyword,
      categoryNameById(r.category_id),
      accountLabelById(r.opposing_account_id, accounts.value),
    ].join(' '))
    return blob.includes(q)
  })
})

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [rulesRes, catRes, accRes] = await Promise.all([
      axios.get('/api/import/rules'),
      axios.get('/api/categories'),
      axios.get('/api/accounts'),
    ])
    const fetched = Array.isArray(rulesRes.data?.response_data) ? rulesRes.data.response_data : []
    // _category_id/_opposing_account_id sont des copies éditables : la modification ne part vers
    // le backend que sur clic explicite de "Enregistrer" (isDirty compare aux valeurs d'origine).
    rules.value = fetched.map(r => ({ ...r, _category_id: r.category_id, _opposing_account_id: r.opposing_account_id, _saving: false }))
    categories.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
    accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function isDirty(r) {
  return String(r._category_id || '') !== String(r.category_id || '')
    || String(r._opposing_account_id || '') !== String(r.opposing_account_id || '')
}

async function saveRule(r) {
  r._saving = true
  try {
    const { data } = await axios.patch(`/api/import/rules/${r.id}`, {
      category_id: r._category_id || null,
      opposing_account_id: r._opposing_account_id || null,
    })
    const updated = data?.response_data
    if (updated) {
      r.category_id = updated.category_id
      r.opposing_account_id = updated.opposing_account_id
      r.updated_at = updated.updated_at
    }
    toast.success('Règle mise à jour.')
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    r._saving = false
  }
}

async function deleteRule(r) {
  const ok = await confirmDialog({
    title: 'Supprimer la règle',
    message: `Supprimer la règle apprise pour « ${r.keyword} » ? Elle pourra se ré-apprendre au prochain import si vous appliquez à nouveau une catégorie/contrepartie à une transaction correspondante.`,
    confirmLabel: 'Supprimer',
    danger: true,
  })
  if (!ok) return
  try {
    await axios.delete(`/api/import/rules/${r.id}`)
    rules.value = rules.value.filter(x => x.id !== r.id)
    toast.success('Règle supprimée.')
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
.page-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; max-width: 60ch; }
.header-actions { display: flex; gap: 10px; align-items: center; }

.search-wrapper { position: relative; }
.search-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); opacity: 0.7; }
.search-input {
  padding: 10px 10px 10px 32px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  outline: none;
  width: 280px;
  max-width: 60vw;
}

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }

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
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.rule-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 14px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.5);
}
.rule-main {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}
.rule-keyword {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: #93c5fd;
  background: rgba(96, 165, 250, 0.08);
  border: 1px solid rgba(96, 165, 250, 0.2);
  border-radius: 6px;
  padding: 2px 8px;
}
.rule-arrow { color: #6b7280; }
.rule-select {
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 8px;
  color: #e5e7eb;
  font-size: 13px;
  padding: 5px 8px;
  max-width: 240px;
  outline: none;
}
.rule-select:focus { border-color: rgba(96, 165, 250, 0.5); }
.rule-meta { font-size: 12px; flex-shrink: 0; }
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
.btn-action:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-danger { border-color: rgba(239, 68, 68, 0.4); color: #fca5a5; }
.btn-danger:hover { background: rgba(239, 68, 68, 0.1); }
.btn-primary { border-color: rgba(96, 165, 250, 0.4); color: #93c5fd; white-space: nowrap; }
.btn-primary:hover { background: rgba(96, 165, 250, 0.1); }
</style>
