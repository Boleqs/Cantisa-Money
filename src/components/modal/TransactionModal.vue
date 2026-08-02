<template>
  <div v-if="modelValue" class="modal-backdrop" @click.self="shake">
    <div class="modal" :class="{ 'modal-shake': shaking }">
      <header class="modal-header">
        <div>
          <h2>{{ isEdit ? 'Modifier la transaction' : 'Nouvelle transaction' }}</h2>
          <p class="subtitle">{{ advancedMode ? 'Mode avancé — saisissez les splits manuellement.' : 'Mode simple — saisissez le montant et les comptes.' }}</p>
        </div>
        <div class="header-actions">
          <button
            v-if="!forcedAdvanced"
            type="button"
            class="mode-toggle"
            @click="toggleMode"
          >
            {{ advancedMode ? '← Mode simple' : 'Mode avancé →' }}
          </button>
          <button class="icon-btn" type="button" @click="close">✕</button>
        </div>
      </header>

      <form class="modal-body" @submit.prevent="onSubmit">
        <!-- Champs principaux -->
        <div class="form-grid">
          <div class="field field-full quickfill-field">
            <label>Description</label>
            <input
              v-model="form.description"
              placeholder="Libellé de la transaction…"
              autocomplete="off"
              @focus="onDescriptionFocus"
              @blur="onDescriptionBlur"
            />
            <ul v-if="showQuickfill && quickfillSuggestions.length" class="quickfill-list">
              <li
                v-for="(s, i) in quickfillSuggestions"
                :key="i"
                class="quickfill-item"
                @mousedown.prevent="applyQuickfill(s)"
              >
                <span class="quickfill-desc">{{ s.description }}</span>
                <span v-if="s.amount != null" class="quickfill-amount">{{ s.amount.toLocaleString('fr-FR') }}</span>
              </li>
            </ul>
          </div>

          <div class="field">
            <label>Date comptable *</label>
            <input v-model="form.post_date" type="date" required />
          </div>

          <div class="field">
            <label>Date effective</label>
            <input v-model="form.effective_date" type="date" />
          </div>

          <div class="field">
            <label>Devise</label>
            <input :value="txCurrencyCode || '—'" disabled title="Déterminée automatiquement par le compte source" />
          </div>

          <div class="field">
            <label>Catégorie</label>
            <div v-if="!showNewCategory" class="category-row">
              <select v-model="form.category_id">
                <option value="">— Aucune —</option>
                <option v-for="c in categories" :key="c.id" :value="c.id">
                  {{ c.name }}
                </option>
              </select>
              <button type="button" class="icon-btn-sm" title="Nouvelle catégorie" @click="openNewCategory">+</button>
            </div>
            <div v-else class="category-row">
              <input
                v-model="newCategoryName"
                placeholder="Nom de la catégorie…"
                autocomplete="off"
                @keydown.enter.prevent="createCategory"
                @keydown.esc.prevent="cancelNewCategory"
              />
              <button type="button" class="icon-btn-sm" :disabled="!newCategoryName.trim() || creatingCategory" title="Créer" @click="createCategory">✓</button>
              <button type="button" class="icon-btn-sm" title="Annuler" @click="cancelNewCategory">✕</button>
            </div>
            <span v-if="newCategoryError" class="field-error">{{ newCategoryError }}</span>
          </div>

          <div class="field toggles">
            <label>
              <input type="checkbox" v-model="form.is_cleared" />
              Pointé / Rapproché
            </label>
          </div>

          <div class="field field-full">
            <label>Tags</label>
            <template v-if="taggableSplits.length">
              <div v-if="taggableSplits.length > 1" class="split-picker">
                <span class="split-picker-hint">Sur le split :</span>
                <button
                  v-for="s in taggableSplits"
                  :key="s.id"
                  type="button"
                  class="split-chip"
                  :class="{ on: selectedTagSplitId === s.id }"
                  @click="selectedTagSplitId = s.id"
                >{{ splitLabel(s) }}</button>
              </div>
              <div class="tag-picker">
                <span v-if="!allTags.length" class="hint">Aucun tag créé — gérez-les depuis la page Tags.</span>
                <button
                  v-for="t in allTags"
                  :key="t.id"
                  type="button"
                  class="tag-chip"
                  :class="{ on: currentSplitTagIds.has(t.id) }"
                  :style="{ '--tag-color': colorHex(t.color) }"
                  :disabled="togglingTag === t.id"
                  @click="toggleTag(t.id)"
                >{{ t.name }}</button>
              </div>
            </template>
            <span v-else class="hint">Enregistrez la transaction pour pouvoir lui attribuer des tags.</span>
          </div>
        </div>

        <!-- Documents joints -->
        <div v-if="form.id" class="documents-section">
          <div class="splits-header">
            <span class="splits-title">Justificatifs</span>
            <div class="doc-header-actions">
              <button type="button" class="btn btn-sm" @click="showOcrPanel = !showOcrPanel">
                {{ showOcrPanel ? '← Retour' : '🔍 Scanner (OCR)' }}
              </button>
              <label v-if="!showOcrPanel" class="btn btn-sm doc-upload-btn">
                <span v-if="uploadingDoc">Envoi…</span>
                <span v-else>+ Joindre un fichier</span>
                <input type="file" accept="image/jpeg,image/png,image/webp,application/pdf" hidden :disabled="uploadingDoc" @change="onDocFileChange" />
              </label>
            </div>
          </div>

          <ReceiptOcrReview
            v-if="showOcrPanel"
            :existing-tx-id="form.id"
            :existing-splits-count="form.splits.length"
            :existing-splits="form.splits"
            :existing-category-id="form.category_id"
            :accounts="accounts"
            :categories="categories"
            :tags="allTags"
            @confirmed="onOcrConfirmed"
          />
          <template v-else>
            <p v-if="docError" class="doc-error">{{ docError }}</p>
            <ul v-if="attachedDocs.length" class="doc-list">
              <li v-for="doc in attachedDocs" :key="doc.id" class="doc-item">
                <button type="button" class="doc-link" @click="viewDocument(doc)">📎 {{ doc.original_filename }}</button>
                <button type="button" class="remove-btn" @click="removeDocument(doc)">✕</button>
              </li>
            </ul>
            <span v-else class="hint">Aucun justificatif joint.</span>
          </template>
        </div>
        <p v-else class="hint">Enregistrez la transaction pour pouvoir y joindre un justificatif.</p>

        <!-- MODE SIMPLE -->
        <div v-if="!advancedMode" class="simple-section">
          <div class="simple-grid">
            <div class="field">
              <label>Montant *</label>
              <input
                v-model.number="simple.amount"
                type="number"
                step="0.01"
                min="0"
                placeholder="0.00"
                required
              />
            </div>

            <div class="field">
              <label>Compte source (débité) *</label>
              <select v-model="simple.from_account_id" required>
                <option value="" disabled>Compte…</option>
                <option v-for="a in accounts" :key="a.id" :value="a.id">
                  {{ accountDisplayLabel(a, accounts) }}
                </option>
              </select>
            </div>

            <div class="field">
              <label>Compte destination (crédité) *</label>
              <select v-model="simple.to_account_id" required>
                <option value="" disabled>Compte…</option>
                <option v-for="a in accounts" :key="a.id" :value="a.id">
                  {{ accountDisplayLabel(a, accounts) }}
                </option>
              </select>
            </div>
          </div>
          <p v-if="simpleMixedCurrencies" class="fx-hint">
            <template v-if="isRatePending(simple.to_account_id)">Récupération du taux {{ txCurrencyCode }} → {{ simpleDestCode }}…</template>
            <template v-else>{{ simple.amount || 0 }} {{ txCurrencyCode }} ≈ {{ simpleDestAmount }} {{ simpleDestCode }} (taux du jour, recalculé côté serveur à l'enregistrement)</template>
          </p>
        </div>

        <!-- MODE AVANCÉ -->
        <div v-else class="splits-section">
          <div class="splits-header">
            <span class="splits-title">Splits</span>
            <span :class="['balance-badge', balanceOk ? 'ok' : 'warn']">
              Balance ({{ txCurrencyCode || '…' }}) : {{ fmtBalance }}
            </span>
          </div>
          <p v-if="hasMixedCurrencies" class="fx-hint">
            Conversion automatique appliquée entre comptes de devises différentes (taux du jour de la transaction, calculé côté serveur à l'enregistrement).
          </p>

          <div class="split-row" v-for="(split, i) in form.splits" :key="i">
            <select v-model="split.account_id" required>
              <option value="" disabled>Compte…</option>
              <option v-for="a in accounts" :key="a.id" :value="a.id">
                {{ accountDisplayLabel(a, accounts) }}
              </option>
            </select>
            <input
              v-model.number="split.quantity"
              type="number"
              step="0.01"
              placeholder="Montant (+/-)"
              required
            />
            <input
              v-model="split.description"
              type="text"
              placeholder="Mémo (optionnel)"
              class="split-memo"
            />
            <span class="fx-badge">{{ splitFxLabel(split) }}</span>
            <button
              type="button"
              class="remove-btn"
              :disabled="form.splits.length <= 2"
              @click="removeSplit(i)"
            >✕</button>
          </div>

          <button type="button" class="btn add-split-btn" @click="addSplit">
            + Ajouter un split
          </button>
        </div>

        <footer class="modal-footer">
          <button type="button" class="btn" @click="close">Annuler</button>
          <button type="submit" class="btn btn-primary" :disabled="!canSubmit">
            {{ isEdit ? 'Enregistrer' : 'Créer la transaction' }}
          </button>
        </footer>
      </form>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, watch, ref, nextTick } from 'vue'
import axios from 'axios'
import ReceiptOcrReview from '@/components/ReceiptOcrReview.vue'
import { useModalShake, useEscapeClose } from '@/utils/modalUX'
import { accountDisplayLabel } from '@/utils/accountDisplay.js'
import { ensureInstitutionsLoaded } from '@/utils/institutions.js'

const props = defineProps({
  modelValue: { type: Boolean, required: true },
  mode: { type: String, default: 'create' },
  transaction: { type: Object, default: null },
})

const commodities = ref([])
const accounts = ref([])
const categories = ref([])
const allTags = ref([])

async function loadReferenceData() {
  try {
    const [comRes, accRes, catRes, tagRes] = await Promise.all([
      axios.get('/api/commodities'),
      axios.get('/api/accounts'),
      axios.get('/api/categories'),
      axios.get('/api/tags'),
      ensureInstitutionsLoaded(),
    ])
    commodities.value = Array.isArray(comRes.data?.response_data) ? comRes.data.response_data : []
    accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
    categories.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
    allTags.value = Array.isArray(tagRes.data?.response_data) ? tagRes.data.response_data : []
  } catch (e) {
    console.error('Erreur chargement données du modal', e)
  }
}

watch(() => props.modelValue, (open) => {
  if (open) loadReferenceData()
}, { immediate: true })

// ── Création de catégorie à la volée ────────────────────────────────────
// Aucun compte/catégorie n'existe par défaut dans l'appli — sans ça, créer une transaction dans
// une nouvelle catégorie obligerait à fermer ce modal, aller sur /categories, puis recommencer.
const showNewCategory = ref(false)
const newCategoryName = ref('')
const newCategoryError = ref('')
const creatingCategory = ref(false)

function openNewCategory() {
  newCategoryName.value = ''
  newCategoryError.value = ''
  showNewCategory.value = true
}

function cancelNewCategory() {
  showNewCategory.value = false
  newCategoryError.value = ''
}

async function createCategory() {
  const name = newCategoryName.value.trim()
  if (!name || creatingCategory.value) return
  creatingCategory.value = true
  newCategoryError.value = ''
  try {
    const { data } = await axios.post('/api/categories', { name, description: null, tax_treatment: null })
    const created = data?.response_data
    if (created?.id) {
      categories.value.push(created)
      form.category_id = created.id
    }
    showNewCategory.value = false
  } catch (e) {
    newCategoryError.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la création'
  } finally {
    creatingCategory.value = false
  }
}

const emit = defineEmits(['update:modelValue', 'save', 'cancel', 'ocr-applied'])

const isEdit = computed(() => props.mode === 'edit')

// Forcé en mode avancé si la transaction a plus de 2 splits
const forcedAdvanced = computed(() =>
  isEdit.value && props.transaction?.splits?.length > 2
)

const advancedMode = ref(false)

function toggleMode() {
  if (!advancedMode.value) {
    // Simple → Avancé : convertir les valeurs simple en splits (montant converti, pas la valeur brute)
    if (simple.amount && simple.from_account_id && simple.to_account_id) {
      const rate = splitRate(simple.to_account_id)
      const destAmount = Math.round((Math.abs(simple.amount) / rate) * 100) / 100
      form.splits = [
        { account_id: simple.from_account_id, quantity: -Math.abs(simple.amount), description: '' },
        { account_id: simple.to_account_id, quantity: destAmount, description: '' },
      ]
    }
  } else {
    // Avancé → Simple : extraire si exactement 2 splits
    if (form.splits.length === 2) {
      const neg = form.splits.find(s => s.quantity < 0)
      const pos = form.splits.find(s => s.quantity > 0)
      if (neg && pos) {
        simple.amount = Math.abs(neg.quantity)
        simple.from_account_id = neg.account_id
        simple.to_account_id = pos.account_id
      }
    }
  }
  advancedMode.value = !advancedMode.value
}

const emptyForm = () => ({
  id: null,
  description: '',
  post_date: new Date().toISOString().slice(0, 10),
  effective_date: '',
  category_id: '',
  is_cleared: false,
  splits: [
    { account_id: '', quantity: 0, description: '' },
    { account_id: '', quantity: 0, description: '' },
  ],
})

const form = reactive(emptyForm())

const simple = reactive({
  amount: null,
  from_account_id: '',
  to_account_id: '',
})

// ── Quick Fill : suggère une transaction passée à partir du début de la description tapée,
// pour pré-remplir catégorie/compte/montant sans ressaisir une dépense récurrente (loyer,
// abonnement non modélisé en tant que tel, etc.). Uniquement en création — éditer une transaction
// existante ne doit pas proposer de "remplacer" ses valeurs par celles d'une autre. ──
const quickfillSuggestions = ref([])
const showQuickfill = ref(false)
let quickfillTimer = null

async function fetchQuickfill(q) {
  try {
    const { data } = await axios.get('/api/transactions/quickfill', { params: { q } })
    quickfillSuggestions.value = Array.isArray(data?.response_data) ? data.response_data : []
  } catch (e) {
    quickfillSuggestions.value = []
  }
}

watch(() => form.description, (val) => {
  clearTimeout(quickfillTimer)
  if (isEdit.value || !val || val.trim().length < 2) {
    quickfillSuggestions.value = []
    return
  }
  quickfillTimer = setTimeout(() => fetchQuickfill(val.trim()), 250)
})

function onDescriptionFocus() {
  if (!isEdit.value) showQuickfill.value = true
}

function onDescriptionBlur() {
  showQuickfill.value = false
}

function applyQuickfill(s) {
  form.description = s.description
  form.category_id = s.category_id || ''
  if (!advancedMode.value && s.amount != null && s.from_account_id && s.to_account_id) {
    simple.amount = s.amount
    simple.from_account_id = s.from_account_id
    simple.to_account_id = s.to_account_id
  }
  showQuickfill.value = false
}

// ── Conversion inter-devises (aperçu du taux appliqué côté serveur) ────────
// La transaction n'a plus de devise choisie manuellement : elle est dérivée du compte source
// (1er split en mode avancé, compte débité en mode simple), comme le fait déjà le backend.
const ratesCache = reactive({}) // "FROM_TO_DATE" -> taux (float) | 'pending' | 'error'

function commodityCode(commodityId) {
  return commodities.value.find(c => c.id === commodityId)?.short_name?.toUpperCase() || null
}

function splitAccountCode(accountId) {
  const acc = accounts.value.find(a => a.id === accountId)
  return acc ? commodityCode(acc.currency_id) : null
}

const primaryAccountId = computed(() =>
  advancedMode.value ? form.splits[0]?.account_id : simple.from_account_id
)
const txCurrencyCode = computed(() => splitAccountCode(primaryAccountId.value))

// ── Documents joints ─────────────────────────────────────────────────────
const attachedDocs = ref([])
const uploadingDoc = ref(false)
const docError = ref('')
const showOcrPanel = ref(false)

function onOcrConfirmed() {
  showOcrPanel.value = false
  emit('ocr-applied')
  emit('update:modelValue', false)
}

async function loadDocuments(txId) {
  attachedDocs.value = []
  if (!txId) return
  try {
    const { data } = await axios.get('/api/documents', { params: { tx_id: txId } })
    attachedDocs.value = Array.isArray(data?.response_data) ? data.response_data : []
  } catch (e) {
    console.error('Erreur chargement des documents joints', e)
  }
}

async function onDocFileChange(e) {
  const file = e.target.files[0]
  if (!file || !form.id) return
  uploadingDoc.value = true
  docError.value = ''
  try {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('tx_id', form.id)
    const { data } = await axios.post('/api/documents/attach', fd)
    if (data?.response_data) attachedDocs.value.unshift(data.response_data)
  } catch (err) {
    docError.value = err?.response?.data?.response_data || err?.message || "Erreur lors de l'envoi"
  } finally {
    uploadingDoc.value = false
    e.target.value = ''
  }
}

async function viewDocument(doc) {
  try {
    const { data } = await axios.get(`/api/documents/${doc.id}`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([data], { type: doc.mime_type }))
    window.open(url, '_blank')
  } catch (e) {
    docError.value = "Erreur lors de l'ouverture du document"
  }
}

async function removeDocument(doc) {
  try {
    await axios.delete(`/api/documents/${doc.id}`)
    attachedDocs.value = attachedDocs.value.filter(d => d.id !== doc.id)
  } catch (e) {
    docError.value = 'Erreur lors de la suppression'
  }
}

// ── Tags ─────────────────────────────────────────────────────────────────
// Un split n'existe (et n'a un id réel) qu'une fois la transaction enregistrée : les tags ne
// peuvent donc être attribués qu'en modification. Un tag qualifie un split précis (compte +
// montant), pas la transaction entière — l'utilisateur choisit sur quel split il s'applique via
// le sélecteur au-dessus des chips de tags.
const splitTagIds = ref(new Map()) // split_id -> Set(tag_id)
const selectedTagSplitId = ref(null)
const togglingTag = ref(null)

const taggableSplits = computed(() => form.splits.filter(s => s.id))
const currentSplitTagIds = computed(() => splitTagIds.value.get(selectedTagSplitId.value) || new Set())

function splitLabel(s) {
  const acc = accounts.value.find(a => a.id === s.account_id)
  const qty = Number(s.quantity) || 0
  const label = acc ? accountDisplayLabel(acc, accounts.value) : '—'
  return `${label} (${qty >= 0 ? '+' : ''}${qty.toFixed(2)})`
}

const TAG_COLOR_HEX = {
  green: '#22c55e', red: '#ef4444', blue: '#3b82f6',
  white: '#f1f5f9', black: '#1e293b', yellow: '#eab308', purple: '#a855f7',
}
function colorHex(color) {
  return TAG_COLOR_HEX[color] || TAG_COLOR_HEX.green
}

async function toggleTag(tagId) {
  const splitId = selectedTagSplitId.value
  if (!splitId || togglingTag.value) return
  togglingTag.value = tagId
  try {
    const current = new Set(splitTagIds.value.get(splitId) || [])
    if (current.has(tagId)) {
      await axios.delete('/api/tags/on-split', { params: { split_id: splitId, tag_id: tagId } })
      current.delete(tagId)
    } else {
      await axios.post('/api/tags/on-split', { split_id: splitId, tag_id: tagId })
      current.add(tagId)
    }
    splitTagIds.value.set(splitId, current)
    splitTagIds.value = new Map(splitTagIds.value)
  } catch (e) {
    console.error('Erreur mise à jour du tag', e)
  } finally {
    togglingTag.value = null
  }
}

// Comptes dont on a besoin du taux vs. txCurrencyCode, selon le mode actif — en mode simple,
// form.splits n'est pas édité en direct donc il faut suivre simple.from/to_account_id séparément.
const relevantAccountIds = computed(() =>
  advancedMode.value
    ? form.splits.map(s => s.account_id)
    : [simple.from_account_id, simple.to_account_id]
)

function rateKey(fromCode, toCode) {
  return `${fromCode}_${toCode}_${form.post_date || 'today'}`
}

async function ensureRate(fromCode, toCode) {
  if (!fromCode || !toCode || fromCode === toCode) return
  const key = rateKey(fromCode, toCode)
  if (ratesCache[key] !== undefined) return
  ratesCache[key] = 'pending'
  try {
    const res = await axios.get('/api/commodities/rate', {
      params: { from_code: fromCode, to_code: toCode, on_date: form.post_date || undefined },
    })
    ratesCache[key] = res.data?.response_data?.rate ?? 'error'
  } catch {
    ratesCache[key] = 'error'
  }
}

function refreshRates() {
  const txCode = txCurrencyCode.value
  if (!txCode) return
  for (const accId of relevantAccountIds.value) {
    const accCode = splitAccountCode(accId)
    if (accCode) ensureRate(accCode, txCode)
  }
}

watch(
  () => [primaryAccountId.value, form.post_date, ...relevantAccountIds.value],
  refreshRates,
  { immediate: true }
)

/** Taux (compte -> devise de la transaction), à la date comptable saisie. 1 tant que le taux réel
 * n'est pas encore chargé — le serveur recalcule et fait foi à l'enregistrement. */
function splitRate(accountId) {
  const txCode = txCurrencyCode.value
  const accCode = splitAccountCode(accountId)
  if (!txCode || !accCode || accCode === txCode) return 1
  const r = ratesCache[rateKey(accCode, txCode)]
  return typeof r === 'number' ? r : 1
}

function isRatePending(accountId) {
  const txCode = txCurrencyCode.value
  const accCode = splitAccountCode(accountId)
  if (!txCode || !accCode || accCode === txCode) return false
  return ratesCache[rateKey(accCode, txCode)] === 'pending'
}

function splitFxLabel(s) {
  const txCode = txCurrencyCode.value
  const accCode = splitAccountCode(s.account_id)
  if (!txCode || !accCode || accCode === txCode) return ''
  if (isRatePending(s.account_id)) return `${accCode} × …`
  return `${accCode} × ${splitRate(s.account_id).toFixed(4)}`
}

// Mode avancé, cas courant à 2 splits : le 2e split (compte de contrepartie) suit automatiquement
// le 1er pour que la transaction démarre déjà équilibrée, converti dans sa propre devise si besoin.
// Désactivé pendant le chargement d'une transaction existante (cf. suppressAutoBalance) pour ne
// pas écraser des montants réels par un recalcul approximatif.
const suppressAutoBalance = ref(false)

function autoBalanceSecondSplit() {
  if (suppressAutoBalance.value || form.splits.length !== 2) return
  const primary = form.splits[0]
  const other = form.splits[1]
  if (!primary?.account_id || !other?.account_id) return
  const primaryQty = Number(primary.quantity) || 0
  if (!primaryQty) return
  const rate = splitRate(other.account_id)
  const balanced = Math.round((-primaryQty / rate) * 100) / 100
  if (other.quantity !== balanced) other.quantity = balanced
}

watch(
  () => [
    form.splits.length,
    form.splits[0]?.account_id,
    form.splits[0]?.quantity,
    form.splits[1]?.account_id,
    splitRate(form.splits[1]?.account_id),
  ],
  autoBalanceSecondSplit
)

// Déclenché par l'ouverture du modal (modelValue), pas par l'identité de `transaction` : en mode
// création, `transaction` reste `null` d'une ouverture à l'autre donc un watch sur `transaction`
// seul ne se redéclenche pas et laisse la saisie précédente dans le formulaire.
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    const tx = props.transaction
    suppressAutoBalance.value = true
    const base = emptyForm()
    if (tx) {
      base.id = tx.id
      base.description = tx.description || ''
      base.post_date = tx.post_date ? tx.post_date.slice(0, 10) : base.post_date
      base.effective_date = tx.effective_date ? tx.effective_date.slice(0, 10) : ''
      base.category_id = tx.category_id || ''
      base.is_cleared = tx.is_cleared || false
      base.splits = (tx.splits && tx.splits.length)
        ? tx.splits.map(s => ({ id: s.id, account_id: s.account_id, quantity: s.quantity, description: s.description || '' }))
        : [{ account_id: '', quantity: 0, description: '' }, { account_id: '', quantity: 0, description: '' }]
    }
    Object.assign(form, base)
    quickfillSuggestions.value = []
    showQuickfill.value = false
    splitTagIds.value = new Map((tx?.splits || []).filter(s => s.id).map(s => [s.id, new Set(s.tag_ids || [])]))
    selectedTagSplitId.value = base.splits.find(s => s.id)?.id || null
    loadDocuments(tx?.id)
    showOcrPanel.value = false

    // Détermine le mode initial
    if (forcedAdvanced.value) {
      advancedMode.value = true
    } else if (tx?.splits?.length === 2) {
      const neg = base.splits.find(s => s.quantity < 0)
      const pos = base.splits.find(s => s.quantity > 0)
      if (neg && pos) {
        simple.amount = Math.abs(neg.quantity)
        simple.from_account_id = neg.account_id
        simple.to_account_id = pos.account_id
        advancedMode.value = false
      } else {
        advancedMode.value = true
      }
    } else {
      simple.amount = null
      simple.from_account_id = ''
      simple.to_account_id = ''
      advancedMode.value = false
    }
    nextTick(() => { suppressAutoBalance.value = false })
  },
  { immediate: true }
)

// Validité selon le mode
const simpleOk = computed(() =>
  simple.amount > 0 && simple.from_account_id && simple.to_account_id && !isRatePending(simple.to_account_id)
)
const balance = computed(() =>
  form.splits.reduce((sum, s) => sum + (Number(s.quantity) || 0) * splitRate(s.account_id), 0)
)
const hasMixedCurrencies = computed(() => {
  const txCode = txCurrencyCode.value
  return form.splits.some(s => {
    const accCode = splitAccountCode(s.account_id)
    return accCode && txCode && accCode !== txCode
  })
})

const simpleDestCode = computed(() => splitAccountCode(simple.to_account_id))
const simpleMixedCurrencies = computed(() =>
  txCurrencyCode.value && simpleDestCode.value && txCurrencyCode.value !== simpleDestCode.value
)
const simpleDestAmount = computed(() => {
  if (!simple.amount) return 0
  const rate = splitRate(simple.to_account_id)
  return Math.round((Math.abs(simple.amount) / rate) * 100) / 100
})
const balanceOk = computed(() => Math.abs(balance.value) < 0.01)
const canSubmit = computed(() => advancedMode.value ? balanceOk.value : simpleOk.value)

const fmtBalance = computed(() => {
  const n = balance.value
  return new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2, signDisplay: 'always' }).format(n)
})

function addSplit() {
  form.splits.push({ account_id: '', quantity: 0, description: '' })
}

function removeSplit(i) {
  if (form.splits.length > 2) form.splits.splice(i, 1)
}

const close = () => {
  emit('update:modelValue', false)
  emit('cancel')
}

const { shaking, shake } = useModalShake()
useEscapeClose(() => { if (props.modelValue) close() }, shake, () => props.modelValue)

const onSubmit = () => {
  if (!canSubmit.value) return

  let splits
  if (advancedMode.value) {
    splits = form.splits.map(s => ({ account_id: s.account_id, quantity: Number(s.quantity), description: s.description || null }))
  } else {
    // Le montant saisi est débité du compte source dans SA devise ; le compte destination reçoit
    // l'équivalent converti (montant / taux compte_dest→devise_source) si sa devise diffère.
    const rate = splitRate(simple.to_account_id)
    const destAmount = Math.round((Math.abs(simple.amount) / rate) * 100) / 100
    splits = [
      { account_id: simple.from_account_id, quantity: -Math.abs(simple.amount) },
      { account_id: simple.to_account_id, quantity: destAmount },
    ]
  }

  emit('save', {
    id: form.id,
    description: form.description,
    post_date: form.post_date,
    effective_date: form.effective_date || null,
    category_id: form.category_id || null,
    is_cleared: form.is_cleared,
    splits,
  })
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
  width: 600px;
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.mode-toggle {
  background: transparent;
  border: 1px solid #374151;
  border-radius: 999px;
  color: #6b7280;
  font-size: 11px;
  padding: 3px 10px;
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.15s, border-color 0.15s;
}

.mode-toggle:hover {
  color: #cbd5e1;
  border-color: #6b7280;
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

.category-row { display: flex; gap: 6px; align-items: center; }
.category-row select, .category-row input { flex: 1; min-width: 0; }
.icon-btn-sm {
  flex-shrink: 0;
  background: transparent;
  border: 1px solid #374151;
  color: #9ca3af;
  border-radius: 6px;
  width: 26px;
  height: 26px;
  line-height: 1;
  cursor: pointer;
  font-size: 13px;
}
.icon-btn-sm:hover:not(:disabled) { color: #e5e7eb; border-color: #6b7280; }
.icon-btn-sm:disabled { opacity: 0.4; cursor: not-allowed; }
.field-error { font-size: 11px; color: #fca5a5; }

.quickfill-field { position: relative; }

.quickfill-list {
  position: absolute;
  top: calc(100% + 2px);
  left: 0;
  right: 0;
  z-index: 20;
  margin: 0;
  padding: 4px;
  list-style: none;
  background: #0b1220;
  border: 1px solid #1f2937;
  border-radius: 10px;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.5);
  max-height: 220px;
  overflow-y: auto;
}

.quickfill-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 7px 9px;
  border-radius: 7px;
  font-size: 13px;
  color: #e5e7eb;
  cursor: pointer;
}

.quickfill-item:hover { background: rgba(96, 165, 250, 0.1); }

.quickfill-desc { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.quickfill-amount {
  flex-shrink: 0;
  font-size: 12px;
  color: #9ca3af;
  font-variant-numeric: tabular-nums;
}

.field input:disabled {
  color: #6b7280;
  cursor: default;
}

.hint {
  font-size: 12px;
  color: #6b7280;
}

.split-picker {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.split-picker-hint {
  font-size: 11px;
  color: #6b7280;
}

.split-chip {
  background: transparent;
  border: 1px solid #374151;
  color: #9ca3af;
  border-radius: 999px;
  padding: 3px 10px;
  font-size: 11px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.split-chip:hover {
  border-color: #6b7280;
  color: #cbd5e1;
}
.split-chip.on {
  background: #2563eb;
  border-color: transparent;
  color: #fff;
}

.tag-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-chip {
  --tag-color: #22c55e;
  background: transparent;
  border: 1px solid var(--tag-color);
  color: var(--tag-color);
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.tag-chip:hover:not(:disabled) {
  background: color-mix(in srgb, var(--tag-color) 15%, transparent);
}
.tag-chip.on {
  background: var(--tag-color);
  color: #020617;
  font-weight: 600;
}
.tag-chip:disabled {
  opacity: 0.5;
  cursor: wait;
}

.toggles {
  flex-direction: row;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #cbd5e1;
}

/* Mode simple */
.simple-section {
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 12px;
}

.simple-grid {
  display: grid;
  grid-template-columns: 120px 1fr 1fr;
  gap: 10px 12px;
}

/* Splits */
.splits-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 12px;
}

.splits-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.doc-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.splits-title {
  font-size: 13px;
  font-weight: 600;
  color: #cbd5e1;
}

.balance-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
}

.balance-badge.ok {
  background: rgba(34, 197, 94, 0.12);
  border: 1px solid rgba(34, 197, 94, 0.3);
  color: #86efac;
}

.balance-badge.warn {
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: #fca5a5;
}

.split-row {
  display: grid;
  grid-template-columns: 1fr 110px 1fr 90px 30px;
  gap: 8px;
  align-items: center;
}

.split-memo {
  min-width: 0;
}

.fx-hint {
  margin: 0;
  font-size: 11px;
  color: #93c5fd;
}

.fx-badge {
  font-size: 11px;
  color: #93c5fd;
  white-space: nowrap;
  text-align: right;
}

.split-row select,
.split-row input {
  background: #020617;
  border-radius: 8px;
  border: 1px solid #1f2937;
  padding: 6px 8px;
  color: #e5e7eb;
  font-size: 13px;
}

.split-row select:focus,
.split-row input:focus {
  outline: none;
  border-color: #2563eb;
}

.remove-btn {
  background: transparent;
  border: none;
  color: #6b7280;
  cursor: pointer;
  font-size: 14px;
  padding: 0;
}

.remove-btn:hover:not(:disabled) {
  color: #fca5a5;
}

.remove-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.add-split-btn {
  align-self: flex-start;
  font-size: 12px;
  padding: 4px 10px;
}

/* Documents joints */
.documents-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid #1f2937;
  border-radius: 12px;
  padding: 12px;
}

.doc-upload-btn {
  display: inline-flex;
  align-items: center;
}

.doc-error {
  margin: 0;
  font-size: 12px;
  color: #fca5a5;
}

.doc-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.doc-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.doc-link {
  background: transparent;
  border: none;
  color: #93c5fd;
  cursor: pointer;
  font-size: 13px;
  padding: 0;
  text-align: left;
  text-decoration: underline;
}

.doc-link:hover {
  color: #bfdbfe;
}

/* Footer */
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

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
  border-color: transparent;
}

.btn:hover:not(:disabled) {
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
