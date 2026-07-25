<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Importer des données</h1>
        <p class="subtitle">Importez des transactions depuis un fichier bancaire (CSV ou QIF).</p>
      </div>
    </header>

    <!-- Stepper -->
    <div class="stepper">
      <div v-for="(s, i) in steps" :key="i" class="step" :class="{ active: step === i, done: step > i }">
        <div class="step-dot">{{ step > i ? '✓' : i + 1 }}</div>
        <span class="step-label">{{ s }}</span>
      </div>
    </div>

    <div v-if="error" class="alert">{{ error }}</div>

    <!-- ── Step 0 : Charger le fichier ───────────────────────── -->
    <section v-if="step === 0" class="card">
      <h2>Charger le fichier</h2>

      <div
        class="drop-zone"
        :class="{ 'drop-zone--over': dragging }"
        @dragover.prevent="dragging = true"
        @dragleave="dragging = false"
        @drop.prevent="onDrop"
        @click="fileInput.click()"
      >
        <input ref="fileInput" type="file" accept=".csv,.txt,.qif" hidden @change="onFileChange" />
        <span v-if="!file">📂 Glissez un fichier ici (CSV ou QIF), ou cliquez pour parcourir</span>
        <span v-else class="file-name">
          📄 {{ file.name }}
          <span class="format-badge" :class="detectedFormat">{{ detectedFormat.toUpperCase() }}</span>
        </span>
      </div>

      <!-- CSV-only options -->
      <template v-if="detectedFormat === 'csv'">
        <div class="form-row">
          <label class="form-label">Séparateur</label>
          <select v-model="config.delimiter" class="form-select">
            <option value=";">Point-virgule ( ; )</option>
            <option value=",">Virgule ( , )</option>
            <option value="\t">Tabulation</option>
          </select>
        </div>
        <div class="form-row">
          <label class="toggle">
            <input type="checkbox" v-model="config.has_header" />
            <span>Première ligne = en-têtes</span>
          </label>
        </div>
      </template>

      <!-- QIF info banner -->
      <div v-if="detectedFormat === 'qif'" class="info-banner">
        Format QIF détecté — les champs (date, montant, libellé) sont extraits automatiquement.
      </div>

      <div class="step-actions">
        <button class="btn btn-primary" :disabled="!file" @click="goToConfig">Suivant →</button>
      </div>
    </section>

    <!-- ── Step 1 : Configurer ───────────────────────────────── -->
    <section v-if="step === 1" class="card">
      <h2>
        Configurer
        <span class="format-badge" :class="detectedFormat">{{ detectedFormat.toUpperCase() }}</span>
      </h2>

      <!-- CSV raw preview -->
      <div v-if="detectedFormat === 'csv' && rawPreview.length" class="preview-wrap">
        <p class="hint">Aperçu du fichier (premières lignes) :</p>
        <div class="table-scroll">
          <table class="preview-table">
            <thead>
              <tr>
                <th v-for="(h, i) in previewHeaders" :key="i" class="col-header">
                  {{ h }}<br /><small class="col-idx">col {{ i }}</small>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(row, ri) in rawPreview" :key="ri">
                <td v-for="(cell, ci) in row" :key="ci">{{ cell }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="config-grid">
        <!-- Date format (both formats) -->
        <div class="form-group">
          <label class="form-label">Format de date</label>
          <select v-model="config.date_format" class="form-select">
            <option value="%d/%m/%Y">JJ/MM/AAAA</option>
            <option value="%m/%d/%Y">MM/JJ/AAAA (US)</option>
            <option value="%Y-%m-%d">AAAA-MM-JJ</option>
            <option value="%d-%m-%Y">JJ-MM-AAAA</option>
            <option value="%d/%m/%y">JJ/MM/AA</option>
            <option value="%m/%d/%y">MM/JJ/AA (US)</option>
          </select>
        </div>

        <!-- Decimal sep (both formats) -->
        <div class="form-group">
          <label class="form-label">Séparateur décimal</label>
          <select v-model="config.decimal_sep" class="form-select">
            <option value=",">Virgule — 1 234,56 (FR)</option>
            <option value=".">Point — 1,234.56 (US/QIF)</option>
          </select>
        </div>

        <!-- CSV-only: column mapping -->
        <template v-if="detectedFormat === 'csv'">
          <div class="form-group">
            <label class="form-label">Colonne Date (n°)</label>
            <input type="number" v-model.number="config.date_col" class="form-input" min="0" />
          </div>
          <div class="form-group">
            <label class="form-label">Colonne Libellé (n°)</label>
            <input type="number" v-model.number="config.desc_col" class="form-input" min="0" />
          </div>
          <div class="form-group">
            <label class="form-label">Mode montant</label>
            <select v-model="config.amount_mode" class="form-select">
              <option value="single">Colonne unique (+ / -)</option>
              <option value="debit_credit">Débit + Crédit séparés</option>
            </select>
          </div>
          <template v-if="config.amount_mode === 'single'">
            <div class="form-group">
              <label class="form-label">Colonne Montant (n°)</label>
              <input type="number" v-model.number="config.amount_col" class="form-input" min="0" />
            </div>
          </template>
          <template v-else>
            <div class="form-group">
              <label class="form-label">Colonne Débit (n°)</label>
              <input type="number" v-model.number="config.debit_col" class="form-input" min="0" />
            </div>
            <div class="form-group">
              <label class="form-label">Colonne Crédit (n°)</label>
              <input type="number" v-model.number="config.credit_col" class="form-input" min="0" />
            </div>
          </template>
        </template>

        <!-- Accounts & currency (both formats) -->
        <div class="form-group">
          <label class="form-label">Compte cible (compte bancaire)</label>
          <select v-model="config.account_id" class="form-select">
            <option value="">— Sélectionner —</option>
            <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
              {{ acc.name }} ({{ acc.account_type }})
            </option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Compte de contrepartie — Dépenses</label>
          <select v-model="config.expense_opposing_account_id" class="form-select">
            <option value="">— Sélectionner —</option>
            <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
              {{ acc.name }} ({{ acc.account_type }})
            </option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Compte de contrepartie — Recettes</label>
          <select v-model="config.income_opposing_account_id" class="form-select">
            <option value="">— Sélectionner —</option>
            <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
              {{ acc.name }} ({{ acc.account_type }})
            </option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Devise</label>
          <select v-model="config.currency_id" class="form-select">
            <option value="">— Sélectionner —</option>
            <option v-for="c in commodities" :key="c.id" :value="c.id">
              {{ c.name }} ({{ c.short_name }})
            </option>
          </select>
        </div>
      </div>

      <div class="step-actions">
        <button class="btn" @click="step = 0">← Retour</button>
        <button
          class="btn btn-primary"
          :disabled="parsing || !config.account_id || !config.expense_opposing_account_id || !config.income_opposing_account_id || !config.currency_id"
          @click="parse"
        >
          <span v-if="parsing">Analyse…</span>
          <span v-else>Analyser le fichier →</span>
        </button>
      </div>
    </section>

    <!-- ── Step 2 : Réviser et importer ─────────────────────── -->
    <section v-if="step === 2" class="card">
      <h2>Réviser les transactions</h2>

      <!-- Comptes détectés (QIF uniquement) -->
      <div v-if="accountsFound.length" class="accounts-found">
        <div class="accounts-found-header" @click="showAccountsFound = !showAccountsFound">
          <span>
            📁 {{ accountsFound.length }} compte(s) détecté(s) dans le fichier
            <span v-if="accountsFound.some(a => !a.created && !a.skipped)" class="badge warn">À traiter</span>
            <span v-else class="badge ok">Traités</span>
          </span>
          <span class="chevron">{{ showAccountsFound ? '▾' : '▸' }}</span>
        </div>

        <div v-if="showAccountsFound" class="accounts-found-body">
          <p class="hint">Ces comptes sont définis dans le fichier QIF. Créez-les dans Cantisa ou ignorez-les.</p>
          <table class="acc-table">
            <thead>
              <tr>
                <th>Nom</th>
                <th>Type QIF</th>
                <th>Type Cantisa</th>
                <th>Description</th>
                <th>Statut</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="acc in accountsFound" :key="acc.name" :class="{ 'row-done': acc.created || acc.skipped }">
                <td class="acc-name">{{ acc.name }}</td>
                <td><span class="badge">{{ acc.qif_type || '—' }}</span></td>
                <td><span class="badge ok">{{ acc.cantisa_type }}</span></td>
                <td class="desc-cell">{{ acc.description || '—' }}</td>
                <td>
                  <span v-if="acc.created" class="badge ok">Créé</span>
                  <span v-else-if="acc.existing" class="badge">Existant</span>
                  <span v-else-if="acc.skipped" class="badge muted">Ignoré</span>
                  <span v-else class="badge warn">À créer</span>
                </td>
                <td class="acc-actions">
                  <template v-if="!acc.created && !acc.existing && !acc.skipped">
                    <button class="btn btn-sm btn-primary" :disabled="acc.creating" @click="createAccount(acc)">
                      <span v-if="acc.creating">…</span>
                      <span v-else>Créer</span>
                    </button>
                    <button class="btn btn-sm" @click="acc.skipped = true">Ignorer</button>
                  </template>
                  <span v-else-if="acc.existing" class="muted-text">Déjà présent</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="import-stats">
        <div class="stat">
          <span class="stat-val">{{ transactions.length }}</span>
          <span class="stat-lbl">trouvées</span>
        </div>
        <div class="stat">
          <span class="stat-val">{{ selectedCount }}</span>
          <span class="stat-lbl">sélectionnées</span>
        </div>
        <div class="stat warn">
          <span class="stat-val">{{ duplicateCount }}</span>
          <span class="stat-lbl">doublons</span>
        </div>
        <div class="stat danger" v-if="parseErrors.length">
          <span class="stat-val">{{ parseErrors.length }}</span>
          <span class="stat-lbl">erreurs</span>
        </div>
      </div>

      <div class="review-controls">
        <button class="btn btn-sm" @click="selectAll(true)">Tout sélectionner</button>
        <button class="btn btn-sm" @click="selectAll(false)">Tout désélectionner</button>
        <button class="btn btn-sm" @click="selectNonDuplicates">Ignorer les doublons</button>
        <button class="btn btn-sm btn-ai" :disabled="aiLoading" @click="categorizeWithAI">
          <span v-if="aiLoading">🤖 Analyse…</span>
          <span v-else>🤖 Catégoriser avec l'IA</span>
        </button>
      </div>

      <div v-if="aiError" class="alert">{{ aiError }}</div>

      <div class="table-scroll">
        <table class="tx-table">
          <thead>
            <tr>
              <th></th>
              <th>Date</th>
              <th>Libellé</th>
              <th class="amount-col">Montant</th>
              <th>Catégorie</th>
              <th>Contrepartie</th>
              <th>Statut</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="tx in transactions"
              :key="tx.row"
              :class="{ 'row-dup': tx.is_duplicate, 'row-deselected': !tx.selected }"
            >
              <td><input type="checkbox" v-model="tx.selected" /></td>
              <td>{{ tx.date }}</td>
              <td class="desc-cell">{{ tx.description }}</td>
              <td class="amount-col" :class="tx.amount >= 0 ? 'pos' : 'neg'">
                {{ fmtAmount(tx.amount) }}
              </td>
              <td class="cat-cell">
                <span v-if="tx.aiSuggested && tx.category_id" class="ai-dot" title="Suggéré par l'IA">🤖</span>
                <select v-model="tx.category_id" class="cat-select" @change="tx.aiSuggested = false">
                  <option :value="null">—</option>
                  <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
                </select>
              </td>
              <td class="opp-cell">
                <span v-if="tx.aiSuggested && tx.opposing_account_id" class="ai-dot" title="Suggéré par l'IA">🤖</span>
                <!-- Compte existant suggéré ou choix manuel -->
                <select v-if="!tx.newAccountSuggestion || tx.opposing_account_id" v-model="tx.opposing_account_id" class="cat-select" @change="tx.newAccountSuggestion = null; tx.aiSuggested = false">
                  <option :value="null">— (défaut)</option>
                  <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
                    {{ acc.name }}
                  </option>
                </select>
                <!-- Nouveau compte proposé par l'IA -->
                <template v-if="tx.newAccountSuggestion && !tx.opposing_account_id">
                  <span class="new-acc-label" :title="tx.newAccountSuggestion.cantisa_type">
                    🤖 {{ tx.newAccountSuggestion.name }}
                  </span>
                  <button class="btn btn-sm btn-ai" style="padding:2px 8px;font-size:11px" :disabled="tx.creatingAccount" @click="createAccountFromTx(tx)">
                    <span v-if="tx.creatingAccount">…</span>
                    <span v-else>Créer</span>
                  </button>
                  <button class="btn btn-sm" style="padding:2px 6px;font-size:11px" @click="tx.newAccountSuggestion = null">✕</button>
                </template>
              </td>
              <td>
                <span v-if="tx.is_duplicate" class="badge warn">Doublon</span>
                <span v-else class="badge ok">Nouveau</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="parseErrors.length" class="errors-box">
        <p class="errors-title">Lignes ignorées ({{ parseErrors.length }}) :</p>
        <div v-for="e in parseErrors" :key="e.row" class="error-line">
          Ligne {{ e.row + 1 }} : {{ e.error }}
        </div>
      </div>

      <div class="step-actions">
        <button class="btn" @click="step = 1">← Retour</button>
        <button
          class="btn btn-primary"
          :disabled="importing || selectedCount === 0"
          @click="confirm"
        >
          <span v-if="importing">Import en cours…</span>
          <span v-else>Importer {{ selectedCount }} transaction(s) →</span>
        </button>
      </div>
    </section>

    <!-- ── Step 3 : Résultat ─────────────────────────────────── -->
    <section v-if="step === 3" class="card result-card">
      <div class="result-icon">✅</div>
      <h2>Import terminé</h2>
      <p class="result-text">
        <strong>{{ result.created }}</strong> transaction(s) importée(s).<br />
        <span v-if="result.skipped">{{ result.skipped }} ignorée(s) (non sélectionnées).</span>
      </p>
      <div class="step-actions result-actions">
        <button class="btn" @click="reset">Nouvel import</button>
        <button class="btn btn-primary" @click="router.push('/transactions')">
          Voir les transactions →
        </button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const router = useRouter()

const steps = ['Fichier', 'Configuration', 'Révision', 'Résultat']
const step = ref(0)

const file = ref(null)
const fileInput = ref(null)
const dragging = ref(false)
const error = ref('')
const parsing = ref(false)
const importing = ref(false)
const detectedFormat = ref('csv')

const accounts = ref([])
const commodities = ref([])

const rawPreview = ref([])
const previewHeaders = ref([])
const transactions = ref([])
const parseErrors = ref([])
const accountsFound = ref([])
const showAccountsFound = ref(true)
const result = ref({ created: 0, skipped: 0 })
const categories = ref([])
const aiLoading = ref(false)
const aiError = ref('')

const config = ref({
  delimiter: ';',
  has_header: true,
  date_col: 0,
  desc_col: 1,
  date_format: '%d/%m/%Y',
  decimal_sep: ',',
  amount_mode: 'single',
  amount_col: 2,
  debit_col: 2,
  credit_col: 3,
  account_id: '',
  expense_opposing_account_id: '',
  income_opposing_account_id: '',
  currency_id: '',
})

const selectedCount = computed(() => transactions.value.filter(t => t.selected).length)
const duplicateCount = computed(() => transactions.value.filter(t => t.is_duplicate).length)

function fmtAmount(v) {
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v)
}

function detectFormatFromFile(f) {
  const ext = f.name.split('.').pop().toLowerCase()
  if (ext === 'qif') return 'qif'
  return 'csv'
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
  detectedFormat.value = detectFormatFromFile(f)
  // QIF default: US decimal separator
  if (detectedFormat.value === 'qif') {
    config.value.decimal_sep = '.'
    config.value.date_format = '%m/%d/%Y'
  } else {
    config.value.decimal_sep = ','
    config.value.date_format = '%d/%m/%Y'
  }
}

async function goToConfig() {
  error.value = ''
  if (detectedFormat.value === 'csv') {
    // Build local preview from file
    const text = await file.value.text()
    const delim = config.value.delimiter === '\\t' ? '\t' : config.value.delimiter
    const lines = text.replace(/\r/g, '').split('\n').filter(l => l.trim())

    const splitRow = (line) => {
      const res = []
      let cur = '', inQuote = false
      for (const ch of line) {
        if (ch === '"') { inQuote = !inQuote }
        else if (ch === delim && !inQuote) { res.push(cur); cur = '' }
        else { cur += ch }
      }
      res.push(cur)
      return res
    }

    const allRows = lines.map(splitRow)
    if (config.value.has_header && allRows.length) {
      previewHeaders.value = allRows[0]
      rawPreview.value = allRows.slice(1, 6)
    } else {
      previewHeaders.value = allRows[0]?.map((_, i) => `Colonne ${i}`) || []
      rawPreview.value = allRows.slice(0, 5)
    }
  }
  step.value = 1
}

async function parse() {
  parsing.value = true
  error.value = ''
  try {
    const fd = new FormData()
    fd.append('file', file.value)
    fd.append('format', detectedFormat.value)
    fd.append('date_format', config.value.date_format)
    fd.append('decimal_sep', config.value.decimal_sep)
    fd.append('account_id', config.value.account_id)

    if (detectedFormat.value === 'csv') {
      fd.append('delimiter', config.value.delimiter)
      fd.append('has_header', config.value.has_header)
      fd.append('date_col', config.value.date_col)
      fd.append('desc_col', config.value.desc_col)
      if (config.value.amount_mode === 'single') {
        fd.append('amount_col', config.value.amount_col)
      } else {
        fd.append('debit_col', config.value.debit_col)
        fd.append('credit_col', config.value.credit_col)
      }
    }

    const { data } = await axios.post('/api/import/parse', fd)
    const res = data.response_data
    transactions.value = res.transactions.map(t => ({
      ...t,
      category_id: t.category_id ?? null,
      opposing_account_id: (Number(t.amount) < 0
        ? config.value.expense_opposing_account_id
        : config.value.income_opposing_account_id) || null,
      newAccountSuggestion: null,
      aiSuggested: false,
      creatingAccount: false,
    }))
    parseErrors.value = res.errors

    // Enrich accounts_found: mark those that already exist by name
    const existingNames = new Set(accounts.value.map(a => a.name.toLowerCase()))
    accountsFound.value = (res.accounts_found || []).map(a => ({
      ...a,
      existing: existingNames.has(a.name.toLowerCase()),
      created: false,
      skipped: false,
      creating: false,
    }))
    showAccountsFound.value = accountsFound.value.length > 0

    step.value = 2
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || "Erreur lors de l'analyse"
  } finally {
    parsing.value = false
  }
}

async function confirm() {
  importing.value = true
  error.value = ''
  try {
    const { data } = await axios.post('/api/import/confirm', {
      account_id: config.value.account_id,
      expense_opposing_account_id: config.value.expense_opposing_account_id,
      income_opposing_account_id: config.value.income_opposing_account_id,
      currency_id: config.value.currency_id,
      transactions: transactions.value,
    })
    result.value = data.response_data
    step.value = 3
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || "Erreur lors de l'import"
  } finally {
    importing.value = false
  }
}

function selectAll(val) {
  transactions.value.forEach(t => (t.selected = val))
}

function selectNonDuplicates() {
  transactions.value.forEach(t => (t.selected = !t.is_duplicate))
}

async function categorizeWithAI() {
  aiLoading.value = true
  aiError.value = ''
  try {
    const descriptions = transactions.value.map(t => t.description || '')
    const { data } = await axios.post('/api/ai/categorize', { descriptions })
    const suggestions = data.response_data?.suggestions || []
    suggestions.forEach(s => {
      const tx = transactions.value[s.index]
      if (!tx) return
      if (s.category_id) tx.category_id = s.category_id
      if (s.opposing_account_id) {
        tx.opposing_account_id = s.opposing_account_id
        tx.newAccountSuggestion = null
      } else if (s.new_account) {
        tx.opposing_account_id = null
        tx.newAccountSuggestion = s.new_account
      }
      if (s.category_id || s.opposing_account_id || s.new_account) tx.aiSuggested = true
    })
  } catch (e) {
    aiError.value = e?.response?.data?.response_data || e?.message || "Erreur lors de la catégorisation IA"
  } finally {
    aiLoading.value = false
  }
}

async function createAccountFromTx(tx) {
  tx.creatingAccount = true
  try {
    const { data } = await axios.post('/api/accounts', {
      name: tx.newAccountSuggestion.name,
      account_type: tx.newAccountSuggestion.cantisa_type,
      currency_id: config.value.currency_id,
    })
    const created = data?.response_data
    if (created) {
      accounts.value.push(created)
      tx.opposing_account_id = created.id
      tx.newAccountSuggestion = null
    }
  } catch (e) {
    aiError.value = e?.response?.data?.response_data || e?.message || 'Erreur création compte'
  } finally {
    tx.creatingAccount = false
  }
}

async function createAccount(acc) {
  acc.creating = true
  try {
    const { data } = await axios.post('/api/accounts', {
      name: acc.name,
      description: acc.description || undefined,
      currency_id: config.value.currency_id,
      account_type: acc.cantisa_type,
    })
    acc.created = true
    // Add the new account to the local list so it appears in selectors
    const created = data?.response_data
    if (created) accounts.value.push(created)
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la création du compte'
  } finally {
    acc.creating = false
  }
}

function reset() {
  step.value = 0
  file.value = null
  detectedFormat.value = 'csv'
  transactions.value = []
  parseErrors.value = []
  accountsFound.value = []
  aiError.value = ''
  error.value = ''
  result.value = { created: 0, skipped: 0 }
  if (fileInput.value) fileInput.value.value = ''
}

async function loadReferentials() {
  try {
    const [accRes, comRes, catRes] = await Promise.all([
      axios.get('/api/accounts'),
      axios.get('/api/commodities'),
      axios.get('/api/categories'),
    ])
    accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
    commodities.value = Array.isArray(comRes.data?.response_data) ? comRes.data.response_data : []
    categories.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
    if (commodities.value.length === 1) {
      config.value.currency_id = commodities.value[0].id
    }
  } catch (e) {
    error.value = e?.message || 'Impossible de charger les comptes/devises'
  }
}

onMounted(() => {
  loadReferentials()
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

/* Stepper */
.stepper {
  display: flex;
  margin-bottom: 28px;
  position: relative;
}

.stepper::before {
  content: '';
  position: absolute;
  top: 16px;
  left: 16px;
  right: 16px;
  height: 2px;
  background: rgba(148, 163, 184, 0.2);
  z-index: 0;
}

.step {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  gap: 6px;
  position: relative;
  z-index: 1;
}

.step-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  border: 2px solid rgba(148, 163, 184, 0.3);
  background: #0b1220;
  color: #9ca3af;
  transition: 0.2s;
}

.step.active .step-dot { border-color: #3b82f6; background: #1e3a5f; color: #93c5fd; }
.step.done .step-dot { border-color: #10b981; background: #064e3b; color: #6ee7b7; }
.step-label { font-size: 12px; color: #9ca3af; }
.step.active .step-label { color: #93c5fd; }
.step.done .step-label { color: #6ee7b7; }

/* Card */
.card {
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 16px;
}

.card h2 {
  margin: 0 0 20px;
  font-size: 18px;
  color: #e5e7eb;
  display: flex;
  align-items: center;
  gap: 10px;
}

/* Alert */
.alert {
  border: 1px solid rgba(239, 68, 68, 0.5);
  background: rgba(239, 68, 68, 0.08);
  padding: 12px 14px;
  border-radius: 12px;
  margin-bottom: 16px;
  color: #fecaca;
  font-size: 14px;
}

/* Info banner */
.info-banner {
  border: 1px solid rgba(96, 165, 250, 0.3);
  background: rgba(96, 165, 250, 0.07);
  border-radius: 10px;
  padding: 12px 14px;
  color: #93c5fd;
  font-size: 13px;
  margin-bottom: 16px;
}

/* Format badge */
.format-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  letter-spacing: 0.5px;
}

.format-badge.csv {
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.35);
  color: #6ee7b7;
}

.format-badge.qif {
  background: rgba(139, 92, 246, 0.15);
  border: 1px solid rgba(139, 92, 246, 0.35);
  color: #c4b5fd;
}

/* Drop zone */
.drop-zone {
  border: 2px dashed rgba(96, 165, 250, 0.35);
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  color: #9ca3af;
  transition: 0.2s;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
}

.drop-zone:hover,
.drop-zone--over {
  border-color: #3b82f6;
  background: rgba(59, 130, 246, 0.06);
  color: #93c5fd;
}

.file-name { color: #93c5fd; font-weight: 500; display: flex; align-items: center; gap: 8px; }

/* Form */
.form-row { margin-bottom: 14px; }

.form-label {
  display: block;
  font-size: 13px;
  color: #9ca3af;
  margin-bottom: 6px;
}

.form-select,
.form-input {
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

.form-select:focus,
.form-input:focus { border-color: rgba(96, 165, 250, 0.5); }

.toggle {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: #cbd5e1;
  cursor: pointer;
}

.toggle input { accent-color: #60a5fa; }

/* Config grid */
.config-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px 20px;
  margin-bottom: 20px;
}

@media (max-width: 640px) { .config-grid { grid-template-columns: 1fr; } }

/* Preview table */
.preview-wrap { margin-bottom: 20px; }
.hint { font-size: 13px; color: #9ca3af; margin: 0 0 8px; }

.table-scroll {
  overflow-x: auto;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.15);
}

.preview-table,
.tx-table { width: 100%; border-collapse: collapse; font-size: 13px; }

.preview-table th,
.tx-table th {
  background: rgba(15, 23, 42, 0.8);
  color: #9ca3af;
  font-weight: 600;
  padding: 10px 12px;
  text-align: left;
  white-space: nowrap;
}

.preview-table td,
.tx-table td {
  padding: 8px 12px;
  border-top: 1px solid rgba(148, 163, 184, 0.1);
  color: #e5e7eb;
  white-space: nowrap;
}

.col-header { text-align: center !important; }
.col-idx { color: #60a5fa; font-weight: normal; }

/* Accounts found */
.accounts-found {
  border: 1px solid rgba(139, 92, 246, 0.3);
  background: rgba(139, 92, 246, 0.05);
  border-radius: 12px;
  margin-bottom: 20px;
  overflow: hidden;
}

.accounts-found-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  cursor: pointer;
  font-size: 14px;
  color: #c4b5fd;
  font-weight: 500;
}

.accounts-found-header:hover { background: rgba(139, 92, 246, 0.08); }
.chevron { font-size: 13px; color: #9ca3af; }

.accounts-found-body { padding: 0 16px 16px; }

.acc-table { width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 8px; }

.acc-table th {
  color: #9ca3af;
  font-weight: 600;
  padding: 8px 10px;
  text-align: left;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
  white-space: nowrap;
}

.acc-table td {
  padding: 8px 10px;
  border-top: 1px solid rgba(148, 163, 184, 0.08);
  color: #e5e7eb;
  vertical-align: middle;
}

.acc-name { font-weight: 500; }
.acc-actions { display: flex; gap: 6px; }
.row-done td { opacity: 0.5; }

.badge.muted {
  border-color: rgba(148, 163, 184, 0.2);
  background: rgba(148, 163, 184, 0.06);
  color: #9ca3af;
}

.muted-text { font-size: 12px; color: #6b7280; font-style: italic; }

/* Stats */
.import-stats { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }

.stat {
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.5);
  border-radius: 10px;
  padding: 10px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 80px;
}

.stat-val { font-size: 22px; font-weight: 700; color: #e5e7eb; }
.stat-lbl { font-size: 12px; color: #9ca3af; }
.stat.warn .stat-val { color: #fde68a; }
.stat.danger .stat-val { color: #fca5a5; }

/* Review controls */
.review-controls { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }

.row-dup td { color: #9ca3af; }
.row-deselected td { opacity: 0.45; }
.desc-cell { max-width: 260px; overflow: hidden; text-overflow: ellipsis; }
.amount-col { text-align: right; font-variant-numeric: tabular-nums; }
.pos { color: #6ee7b7; }
.neg { color: #fca5a5; }

.cat-cell,
.opp-cell { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }

.cat-select {
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 6px;
  color: #e5e7eb;
  font-size: 12px;
  padding: 3px 6px;
  max-width: 160px;
  outline: none;
}

.cat-select:focus { border-color: rgba(96, 165, 250, 0.5); }

.ai-dot { font-size: 12px; flex-shrink: 0; }

.new-acc-label {
  font-size: 12px;
  color: #c4b5fd;
  background: rgba(139, 92, 246, 0.12);
  border: 1px solid rgba(139, 92, 246, 0.3);
  border-radius: 6px;
  padding: 2px 6px;
  white-space: nowrap;
}

.btn-ai {
  background: linear-gradient(90deg, #7c3aed, #4f46e5);
  border-color: transparent;
  color: #fff;
}

.btn-ai:not(:disabled):hover {
  background: linear-gradient(90deg, #6d28d9, #4338ca);
}

/* Badges */
.badge {
  display: inline-block;
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(148, 163, 184, 0.1);
  color: #e5e7eb;
}

.badge.ok {
  border-color: rgba(16, 185, 129, 0.35);
  background: rgba(16, 185, 129, 0.1);
  color: #6ee7b7;
}

.badge.warn {
  border-color: rgba(245, 158, 11, 0.35);
  background: rgba(245, 158, 11, 0.1);
  color: #fde68a;
}

/* Errors */
.errors-box {
  margin-top: 16px;
  border: 1px solid rgba(239, 68, 68, 0.3);
  background: rgba(239, 68, 68, 0.06);
  border-radius: 10px;
  padding: 12px 14px;
}

.errors-title { margin: 0 0 8px; font-size: 13px; color: #fca5a5; font-weight: 600; }
.error-line { font-size: 12px; color: #fca5a5; padding: 2px 0; }

/* Actions */
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

.btn-primary {
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
  border-color: transparent;
  color: #fff;
}

.btn-primary:not(:disabled):hover { background: linear-gradient(90deg, #1d4ed8, #4338ca); }
.btn-sm { padding: 6px 12px; font-size: 12px; }

/* Result */
.result-card { text-align: center; padding: 48px 24px; }
.result-icon { font-size: 48px; margin-bottom: 12px; }

.result-text {
  color: #9ca3af;
  font-size: 15px;
  margin: 8px 0 0;
  line-height: 1.7;
}

.result-text strong { color: #6ee7b7; font-size: 18px; }
.result-actions { justify-content: center; margin-top: 28px; }
</style>