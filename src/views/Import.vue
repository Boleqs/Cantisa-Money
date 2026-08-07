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
    <div v-if="restoredFileName" class="info-banner">
      Import repris automatiquement après une interruption (fichier : {{ restoredFileName }}).
      <button class="btn btn-sm" style="margin-left:10px" @click="reset">Abandonner et recommencer</button>
    </div>

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
              {{ accountDisplayLabel(acc, accounts) }} ({{ acc.account_type }})
            </option>
          </select>
          <p v-if="profileApplied" class="hint hint-ok">✓ Configuration du dernier import de ce compte réappliquée (modifiable ci-dessous).</p>
        </div>
        <div class="form-group">
          <label class="form-label">Compte de contrepartie — Dépenses</label>
          <select v-model="config.expense_opposing_account_id" class="form-select">
            <option value="">— Sélectionner —</option>
            <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
              {{ accountDisplayLabel(acc, accounts) }} ({{ acc.account_type }})
            </option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">Compte de contrepartie — Recettes</label>
          <select v-model="config.income_opposing_account_id" class="form-select">
            <option value="">— Sélectionner —</option>
            <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
              {{ accountDisplayLabel(acc, accounts) }} ({{ acc.account_type }})
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
        <button
          class="btn btn-sm"
          title="Annuler toutes les modifications manuelles de catégorie/contrepartie"
          :disabled="!hasAnyOverride"
          @click="resetAllOverrides"
        >↺ Réinitialiser catégories/contreparties</button>

        <span class="controls-sep"></span>

        <div class="bulk-cat-group">
          <template v-if="bulkAddingCategory">
            <input
              v-model="bulkNewCategoryName"
              class="cat-select"
              placeholder="Nom de la catégorie…"
              autofocus
              @keyup.enter="createBulkCategory"
              @keyup.esc="bulkAddingCategory = false"
            />
            <button
              class="btn btn-sm"
              :disabled="!bulkNewCategoryName?.trim() || bulkCreatingCategory"
              @click="createBulkCategory"
            >✓</button>
            <button class="btn btn-sm" @click="bulkAddingCategory = false">✕</button>
          </template>
          <template v-else>
            <select v-model="bulkCategoryId" class="cat-select">
              <option :value="null">Catégorie…</option>
              <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
            </select>
            <button class="btn btn-sm" title="Nouvelle catégorie" @click="bulkAddingCategory = true; bulkNewCategoryName = ''">+</button>
            <button
              class="btn btn-sm btn-primary"
              :disabled="!bulkCategoryId || selectedCount === 0"
              @click="applyBulkCategory"
            >Appliquer à {{ selectedCount }} sélectionnée(s)</button>
          </template>
        </div>
      </div>

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
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="tx in transactions"
              :key="tx.row"
              :class="{ 'row-dup': tx.is_duplicate, 'row-deselected': !tx.selected }"
            >
              <td><input type="checkbox" v-model="tx.selected" /></td>
              <td>{{ fmtDate(tx.date) }}</td>
              <td class="desc-cell">{{ tx.description }}</td>
              <td class="amount-col" :class="tx.amount >= 0 ? 'pos' : 'neg'">
                {{ fmtAmount(tx.amount) }}
              </td>
              <td class="cat-cell">
                <span v-if="tx.ruleSuggested && tx.category_id" class="rule-dot" title="Suggéré d'après vos imports précédents">🔁</span>
                <template v-if="tx.addingCategory">
                  <input
                    v-model="tx.newCategoryName"
                    class="cat-select"
                    placeholder="Nom de la catégorie…"
                    autofocus
                    @keyup.enter="createCategoryForTx(tx)"
                    @keyup.esc="tx.addingCategory = false"
                  />
                  <button
                    class="btn btn-sm"
                    style="padding:2px 6px;font-size:11px"
                    :disabled="!tx.newCategoryName?.trim() || tx.creatingCategory"
                    @click="createCategoryForTx(tx)"
                  >✓</button>
                  <button class="btn btn-sm" style="padding:2px 6px;font-size:11px" @click="tx.addingCategory = false">✕</button>
                </template>
                <template v-else>
                  <select v-model="tx.category_id" class="cat-select" @change="tx.ruleSuggested = false">
                    <option :value="null">—</option>
                    <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
                  </select>
                  <button
                    class="btn btn-sm"
                    style="padding:2px 6px;font-size:11px"
                    title="Nouvelle catégorie"
                    @click="tx.addingCategory = true; tx.newCategoryName = ''"
                  >+</button>
                </template>
              </td>
              <td class="opp-cell">
                <span v-if="tx.ruleSuggested && tx.opposing_account_id" class="rule-dot" title="Suggéré d'après vos imports précédents">🔁</span>
                <select v-model="tx.opposing_account_id" class="cat-select" @change="tx.ruleSuggested = false">
                  <option :value="null">— (défaut)</option>
                  <option v-for="acc in accounts" :key="acc.id" :value="acc.id">
                    {{ accountDisplayLabel(acc, accounts) }}
                  </option>
                </select>
              </td>
              <td>
                <span v-if="tx.is_duplicate" class="badge warn">Doublon</span>
                <span v-else class="badge ok">Nouveau</span>
              </td>
              <td>
                <button
                  v-if="tx.category_id !== tx.original_category_id || tx.opposing_account_id !== tx.original_opposing_account_id"
                  class="btn btn-sm"
                  style="padding:2px 6px;font-size:11px"
                  title="Annuler les modifications de cette ligne"
                  @click="resetTxOverrides(tx)"
                >↺</button>
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
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { formatDate } from '@/utils/dateFormat.js'
import { dateFormat } from '@/utils/settings.js'
import { accountDisplayLabel } from '@/utils/accountDisplay.js'
import { ensureInstitutionsLoaded } from '@/utils/institutions.js'

// Format de date par défaut proposé pour le parsing du fichier importé, dérivé du réglage
// utilisateur (Paramétrage > Format de date) plutôt que codé en dur sur le format US — celui-ci
// reste modifiable via le sélecteur si le fichier source (ex: export bancaire US) diffère du
// format habituel de l'utilisateur.
function defaultDateFormat() {
  const map = { 'fr-FR': '%d/%m/%Y', 'en-GB': '%d/%m/%Y', 'en-US': '%m/%d/%Y', 'iso': '%Y-%m-%d' }
  return map[dateFormat.value] || '%d/%m/%Y'
}

const router = useRouter()

const STORAGE_KEY = 'cantisa_import_wizard_v1'
const PROFILE_PREFIX = 'cantisa_import_profile_'

const steps = ['Fichier', 'Configuration', 'Révision', 'Résultat']
const step = ref(0)

const file = ref(null)
const fileInput = ref(null)
const dragging = ref(false)
const error = ref('')
const parsing = ref(false)
const importing = ref(false)
const detectedFormat = ref('csv')
const restoredFileName = ref('')
let restoring = false

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
const profileApplied = ref(false)

const bulkCategoryId = ref(null)
const bulkAddingCategory = ref(false)
const bulkNewCategoryName = ref('')
const bulkCreatingCategory = ref(false)

const config = ref({
  delimiter: ';',
  has_header: true,
  date_col: 0,
  desc_col: 1,
  date_format: defaultDateFormat(),
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

// ── Profils d'import mémorisés par compte ──────────────────────────────────
// Un compte bancaire donné a quasi toujours le même relevé (même banque, même mise en page) :
// mémoriser le mapping qui a fonctionné évite à l'utilisateur de tout resaisir à chaque import.
function profileKey(accountId) {
  return PROFILE_PREFIX + accountId
}

function loadProfileForAccount(accountId) {
  try {
    const raw = localStorage.getItem(profileKey(accountId))
    return raw ? JSON.parse(raw) : null
  } catch (e) {
    return null
  }
}

function saveProfileForAccount(accountId) {
  if (!accountId) return
  try {
    const {
      delimiter, has_header, date_col, desc_col, date_format, decimal_sep,
      amount_mode, amount_col, debit_col, credit_col,
      expense_opposing_account_id, income_opposing_account_id, currency_id,
    } = config.value
    localStorage.setItem(profileKey(accountId), JSON.stringify({
      delimiter, has_header, date_col, desc_col, date_format, decimal_sep,
      amount_mode, amount_col, debit_col, credit_col,
      expense_opposing_account_id, income_opposing_account_id, currency_id,
    }))
  } catch (e) {
    // localStorage indisponible ou quota dépassé : le profil ne sera simplement pas mémorisé.
  }
}

// Dès qu'un compte cible est choisi, réapplique automatiquement le mapping qui a fonctionné la
// dernière fois pour ce même compte (sans l'imposer : tout reste modifiable ensuite).
watch(() => config.value.account_id, (newId, oldId) => {
  if (restoring || !newId || newId === oldId) return
  const profile = loadProfileForAccount(newId)
  if (profile) {
    config.value = { ...config.value, ...profile }
    profileApplied.value = true
  } else {
    profileApplied.value = false
  }
})

// ── Auto-détection du mapping CSV (délimiteur, colonnes, format date, séparateur décimal) ──────
// Ne fait que proposer une valeur par défaut plus pertinente que les index 0/1/2/3 codés en dur :
// l'utilisateur garde la main via les champs de l'étape Configuration.
const DIACRITICS_RE = /[̀-ͯ]/g

function normalizeHeader(s) {
  return (s || '').toString().trim().toLowerCase().normalize('NFD').replace(DIACRITICS_RE, '')
}

const HEADER_KEYWORDS = {
  date: ['date operation', 'date valeur', 'date comptable', 'transaction date', 'posted date', 'date'],
  description: ['libelle', 'description', 'label', 'memo', 'communication', 'objet', 'intitule', 'beneficiaire', 'tiers', 'payee', 'details'],
  amount: ['montant operation', 'montant', 'amount', 'valeur'],
  debit: ['debit', 'withdrawal', 'sortie'],
  credit: ['credit', 'deposit', 'entree'],
}

function matchHeaderIndex(headers, keywords) {
  for (const keyword of keywords) {
    const idx = headers.findIndex(h => normalizeHeader(h) === keyword)
    if (idx >= 0) return idx
  }
  for (const keyword of keywords) {
    const idx = headers.findIndex(h => normalizeHeader(h).includes(keyword))
    if (idx >= 0) return idx
  }
  return -1
}

function autoDetectColumns(headers) {
  if (!headers || !headers.length) return
  const dateIdx = matchHeaderIndex(headers, HEADER_KEYWORDS.date)
  const descIdx = matchHeaderIndex(headers, HEADER_KEYWORDS.description)
  const debitIdx = matchHeaderIndex(headers, HEADER_KEYWORDS.debit)
  const creditIdx = matchHeaderIndex(headers, HEADER_KEYWORDS.credit)
  const amountIdx = matchHeaderIndex(headers, HEADER_KEYWORDS.amount)

  if (dateIdx >= 0) config.value.date_col = dateIdx
  if (descIdx >= 0) config.value.desc_col = descIdx

  if (debitIdx >= 0 && creditIdx >= 0) {
    config.value.amount_mode = 'debit_credit'
    config.value.debit_col = debitIdx
    config.value.credit_col = creditIdx
  } else if (amountIdx >= 0) {
    config.value.amount_mode = 'single'
    config.value.amount_col = amountIdx
  }
}

// Devine le délimiteur CSV le plus probable à partir de la 1re ligne du fichier (le plus fréquent
// parmi ; , et tabulation) — reste modifiable via le sélecteur de l'étape Fichier.
function guessDelimiter(text) {
  const firstLine = (text.split(/\r?\n/).find(l => l.trim()) || '')
  const counts = {
    ';': (firstLine.match(/;/g) || []).length,
    ',': (firstLine.match(/,/g) || []).length,
    '\t': (firstLine.match(/\t/g) || []).length,
  }
  let best = null, bestCount = 0
  for (const [d, c] of Object.entries(counts)) {
    if (c > bestCount) { best = d; bestCount = c }
  }
  if (!best) return null
  return best === '\t' ? '\\t' : best
}

// Devine le format de date à partir d'un échantillon de valeurs (ex: rawPreview) : ne tranche que
// si le format est non ambigu (ex: un jour > 12 révèle l'ordre jour/mois) ; sinon renvoie null et
// laisse le format par défaut (dérivé du réglage utilisateur) en place.
function detectDateFormat(samples) {
  const clean = samples.map(s => (s || '').toString().trim()).filter(Boolean)
  if (!clean.length) return null

  if (clean.every(s => /^\d{4}-\d{2}-\d{2}$/.test(s))) return '%Y-%m-%d'

  const longYear = clean.every(s => /^\d{1,2}[\/-]\d{1,2}[\/-]\d{4}$/.test(s))
  const shortYear = !longYear && clean.every(s => /^\d{1,2}[\/-]\d{1,2}[\/-]\d{2}$/.test(s))
  if (longYear || shortYear) {
    const sep = clean[0].includes('/') ? '/' : '-'
    const parts = clean.map(s => s.split(/[\/-]/).map(Number))
    const dayFirst = parts.some(([a]) => a > 12)
    const monthFirst = parts.some(([, b]) => b > 12)
    if (dayFirst && !monthFirst) return longYear ? `%d${sep}%m${sep}%Y` : `%d${sep}%m${sep}%y`
    if (monthFirst && !dayFirst) return longYear ? `%m${sep}%d${sep}%Y` : `%m${sep}%d${sep}%y`
  }
  return null
}

// Devine le séparateur décimal à partir d'un échantillon de montants : entre virgule et point,
// celui qui apparaît en dernière position dans le nombre est le séparateur décimal (l'autre étant
// alors un séparateur de milliers).
function detectDecimalSep(samples) {
  const clean = samples.map(s => (s || '').toString().trim()).filter(Boolean)
  if (!clean.length) return null
  let commaVotes = 0, dotVotes = 0
  for (const s of clean) {
    const hasComma = s.includes(',')
    const hasDot = s.includes('.')
    if (hasComma && hasDot) {
      if (s.lastIndexOf(',') > s.lastIndexOf('.')) commaVotes++
      else dotVotes++
    } else if (hasComma) {
      commaVotes++
    } else if (hasDot) {
      dotVotes++
    }
  }
  if (commaVotes === 0 && dotVotes === 0) return null
  return commaVotes >= dotVotes ? ',' : '.'
}

function fmtAmount(v) {
  return new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v)
}

// tx.date reste au format ISO (YYYY-MM-DD) tel que renvoyé par le backend — seul l'affichage
// respecte le format de date choisi dans Paramétrage, pas la valeur envoyée à /import/confirm.
function fmtDate(v) {
  return formatDate(v)
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

async function setFile(f) {
  file.value = f
  error.value = ''
  profileApplied.value = false
  detectedFormat.value = detectFormatFromFile(f)
  // QIF default: US decimal separator (convention historique du format, indépendante de la
  // locale de l'utilisateur) — mais le format de date suit le réglage utilisateur dans les deux
  // cas, modifiable ensuite via le sélecteur si le fichier source diffère (ex: export QIF US).
  if (detectedFormat.value === 'qif') {
    config.value.decimal_sep = '.'
  } else {
    config.value.decimal_sep = ','
    try {
      const guessedDelim = guessDelimiter(await f.text())
      if (guessedDelim) config.value.delimiter = guessedDelim
    } catch (e) {
      // Lecture impossible : le délimiteur par défaut reste sélectionné, modifiable à la main.
    }
  }
  config.value.date_format = defaultDateFormat()
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
      autoDetectColumns(previewHeaders.value)
    } else {
      previewHeaders.value = allRows[0]?.map((_, i) => `Colonne ${i}`) || []
      rawPreview.value = allRows.slice(0, 5)
    }

    const dateSamples = rawPreview.value.map(r => r[config.value.date_col])
    const guessedDateFormat = detectDateFormat(dateSamples)
    if (guessedDateFormat) config.value.date_format = guessedDateFormat

    const amountColIdx = config.value.amount_mode === 'single' ? config.value.amount_col : config.value.credit_col
    const amountSamples = rawPreview.value.map(r => r[amountColIdx])
    const guessedDecimalSep = detectDecimalSep(amountSamples)
    if (guessedDecimalSep) config.value.decimal_sep = guessedDecimalSep
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
    transactions.value = res.transactions.map(t => {
      const defaultCategoryId = t.category_id ?? null
      // t.opposing_account_id peut venir d'une règle de catégorisation apprise (voir
      // backend rt_import.py) — sinon on retombe sur la contrepartie par défaut selon le signe.
      const defaultOpposingAccountId = t.opposing_account_id || (Number(t.amount) < 0
        ? config.value.expense_opposing_account_id
        : config.value.income_opposing_account_id) || null
      return {
        ...t,
        category_id: defaultCategoryId,
        opposing_account_id: defaultOpposingAccountId,
        // Suggestion d'origine (règle apprise ou résolution automatique côté serveur pour le QIF) —
        // permet de revenir en arrière si l'utilisateur a modifié à la main sans se souvenir de la
        // valeur de départ.
        original_category_id: defaultCategoryId,
        original_opposing_account_id: defaultOpposingAccountId,
        ruleSuggested: Boolean(t.category_id || t.opposing_account_id),
        addingCategory: false,
        newCategoryName: '',
        creatingCategory: false,
      }
    })
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

    // Le parsing QIF peut créer de nouvelles catégories à la volée côté serveur (voir
    // resolve_category dans rt_import.py) : sans ce refetch, elles n'apparaissent pas
    // dans le select "Catégorie" tant que la page n'est pas rechargée.
    try {
      const catRes = await axios.get('/api/categories')
      categories.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : categories.value
    } catch (e) {
      // Non bloquant : la liste de catégories reste simplement celle chargée au montage.
    }

    saveProfileForAccount(config.value.account_id)
    restoredFileName.value = ''
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
    sessionStorage.removeItem(STORAGE_KEY)
    restoredFileName.value = ''
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

async function createCategoryForTx(tx) {
  const name = (tx.newCategoryName || '').trim()
  if (!name) return
  tx.creatingCategory = true
  try {
    const existing = categories.value.find(c => c.name.toLowerCase() === name.toLowerCase())
    if (existing) {
      tx.category_id = existing.id
    } else {
      const { data } = await axios.post('/api/categories', { name })
      const created = data?.response_data
      if (created) {
        categories.value.push(created)
        tx.category_id = created.id
      }
    }
    tx.addingCategory = false
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la création de la catégorie'
  } finally {
    tx.creatingCategory = false
  }
}

// Annule les modifications manuelles (ou suggestions de règle apprise) d'une ligne — catégorie et
// compte de contrepartie reviennent à la suggestion d'origine calculée à l'analyse du fichier.
function resetTxOverrides(tx) {
  tx.category_id = tx.original_category_id
  tx.opposing_account_id = tx.original_opposing_account_id
  tx.ruleSuggested = false
  tx.addingCategory = false
}

function resetAllOverrides() {
  transactions.value.forEach(resetTxOverrides)
}

const hasAnyOverride = computed(() =>
  transactions.value.some(t =>
    t.category_id !== t.original_category_id || t.opposing_account_id !== t.original_opposing_account_id
  )
)

function applyBulkCategory() {
  if (!bulkCategoryId.value) return
  transactions.value.forEach(t => {
    if (!t.selected) return
    t.category_id = bulkCategoryId.value
    t.ruleSuggested = false
  })
}

async function createBulkCategory() {
  const name = (bulkNewCategoryName.value || '').trim()
  if (!name) return
  bulkCreatingCategory.value = true
  try {
    const existing = categories.value.find(c => c.name.toLowerCase() === name.toLowerCase())
    let catId
    if (existing) {
      catId = existing.id
    } else {
      const { data } = await axios.post('/api/categories', { name })
      const created = data?.response_data
      if (created) {
        categories.value.push(created)
        catId = created.id
      }
    }
    if (catId) {
      bulkCategoryId.value = catId
      applyBulkCategory()
    }
    bulkAddingCategory.value = false
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la création de la catégorie'
  } finally {
    bulkCreatingCategory.value = false
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
  error.value = ''
  result.value = { created: 0, skipped: 0 }
  profileApplied.value = false
  if (fileInput.value) fileInput.value.value = ''
  restoredFileName.value = ''
  sessionStorage.removeItem(STORAGE_KEY)
}

// Persiste l'état de l'assistant (config + transactions révisées) dès l'étape 2 : une transaction
// analysée en QIF/CSV n'a plus besoin du fichier d'origine, donc un refresh accidentel à l'étape
// "Réviser" peut être restauré sans perte, au lieu de repartir de zéro (le fichier brut, lui,
// n'est pas sérialisable et n'est donc jamais restauré).
function persistState() {
  if (restoring) return
  if (step.value < 2) {
    sessionStorage.removeItem(STORAGE_KEY)
    return
  }
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      step: step.value,
      detectedFormat: detectedFormat.value,
      config: config.value,
      transactions: transactions.value,
      parseErrors: parseErrors.value,
      accountsFound: accountsFound.value,
      showAccountsFound: showAccountsFound.value,
      fileName: file.value?.name || restoredFileName.value || '',
    }))
  } catch (e) {
    // sessionStorage indisponible ou quota dépassé : pas de persistance, tant pis.
  }
}

function restoreState() {
  let saved
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return
    saved = JSON.parse(raw)
  } catch (e) {
    return
  }
  if (!saved || saved.step < 2 || !saved.transactions?.length) return

  restoring = true
  detectedFormat.value = saved.detectedFormat || 'csv'
  config.value = { ...config.value, ...saved.config }
  transactions.value = saved.transactions
  parseErrors.value = saved.parseErrors || []
  accountsFound.value = saved.accountsFound || []
  showAccountsFound.value = saved.showAccountsFound ?? true
  restoredFileName.value = saved.fileName || 'fichier précédent'
  step.value = saved.step
  restoring = false
}

watch([step, config, transactions, accountsFound, parseErrors], persistState, { deep: true })

async function loadReferentials() {
  try {
    const [accRes, comRes, catRes] = await Promise.all([
      axios.get('/api/accounts'),
      axios.get('/api/commodities'),
      axios.get('/api/categories'),
      ensureInstitutionsLoaded(),
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
  restoreState()
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
.hint-ok { color: #6ee7b7; margin-top: 6px; }

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
.review-controls { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.controls-sep { width: 1px; align-self: stretch; background: rgba(148, 163, 184, 0.2); margin: 0 2px; }
.bulk-cat-group { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }

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

.rule-dot { font-size: 12px; flex-shrink: 0; }

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