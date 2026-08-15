<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Institutions bancaires</h1>
        <p class="subtitle">Les banques auxquelles rattacher vos comptes.</p>
      </div>
      <div class="header-actions">
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn btn-primary" @click="openCreate">+ Nouvelle institution</button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !institutions.length" class="empty">Chargement…</div>
    <div v-else-if="!loading && !institutions.length" class="empty">Aucune institution.</div>

    <table v-else class="table">
      <thead>
        <tr>
          <th></th>
          <th>Nom</th>
          <th>BIC</th>
          <th>Site web</th>
          <th>Notes</th>
          <th>Synchro bancaire</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="i in institutions" :key="i.id">
          <td><span class="color-dot" :style="{ background: colorHex(i.color) }"></span></td>
          <td>{{ i.name }}</td>
          <td class="muted">{{ i.bic || '—' }}</td>
          <td class="muted">{{ i.website || '—' }}</td>
          <td class="muted">{{ i.notes || '—' }}</td>
          <td>
            <button class="btn-sync" @click="openBankModal(i)">
              {{ syncSummaryLabel(i) }}
            </button>
          </td>
          <td class="actions">
            <button class="btn-action" @click="openEdit(i)">✎</button>
            <button class="btn-action btn-danger" @click="deleteInstitution(i)">✕</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Connexions bancaires orphelines (sans institution — résidus d'anciens tests) -->
    <section v-if="orphanConnections.length" class="card">
      <h2>Connexions bancaires sans institution</h2>
      <table class="table">
        <thead>
          <tr>
            <th>Banque</th>
            <th>Compte banque</th>
            <th>Compte Cantisa</th>
            <th>Statut</th>
            <th>Dernière synchro</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="c in orphanConnections" :key="c.id">
            <td>{{ c.aspsp_name }} <span class="muted">({{ c.aspsp_country }})</span></td>
            <td>{{ c.external_account_name || '—' }}</td>
            <td>{{ accountLabelById(c.account_id, accounts) || '—' }}</td>
            <td><span class="badge" :class="'status-' + c.status">{{ statusLabel(c.status) }}</span></td>
            <td class="muted">{{ c.last_synced_at ? new Date(c.last_synced_at).toLocaleString('fr-FR') : 'jamais' }}</td>
            <td class="actions">
              <button
                v-if="c.status === 'connected'"
                class="btn btn-sm btn-primary"
                :disabled="syncing === c.id"
                @click="sync(c)"
              >
                {{ syncing === c.id ? 'Synchro…' : '⟳ Synchroniser' }}
              </button>
              <button class="btn btn-sm btn-danger" :disabled="deleting === c.id" @click="removeConnection(c)">
                {{ deleting === c.id ? '…' : 'Supprimer' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Modal inline : création/édition institution -->
    <div v-if="showModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>{{ editTarget ? 'Modifier' : 'Nouvelle institution' }}</h2>
        <label>Nom *
          <input v-model="form.name" placeholder="Banque Populaire…" />
        </label>
        <label>Couleur
          <select v-model="form.color">
            <option v-for="c in COLORS" :key="c" :value="c">{{ c }}</option>
          </select>
        </label>
        <div class="color-preview" :style="{ background: colorHex(form.color) }"></div>
        <label>BIC
          <input v-model="form.bic" placeholder="Optionnel" />
        </label>
        <label>Site web
          <input v-model="form.website" placeholder="Optionnel" />
        </label>
        <label>Notes
          <input v-model="form.notes" placeholder="Optionnel" />
        </label>
        <div class="modal-actions">
          <button class="btn" @click="showModal = false">Annuler</button>
          <button class="btn btn-primary" :disabled="!form.name.trim()" @click="save">Enregistrer</button>
        </div>
      </div>
    </div>

    <!-- Modal inline : synchro bancaire d'une institution -->
    <div v-if="showBankModal" class="modal-backdrop" @click.self="closeBankModal">
      <div class="modal modal-wide">
        <h2>Synchro bancaire — {{ bankModalInstitution?.name }}</h2>

        <div v-if="bankError" class="alert"><strong>Erreur :</strong> {{ bankError }}</div>

        <div v-if="!bankModalConnections.length" class="empty">Aucune connexion pour cette institution.</div>
        <table v-else class="table">
          <thead>
            <tr>
              <th>Compte banque</th>
              <th>Compte Cantisa</th>
              <th>Statut</th>
              <th>Dernière synchro</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in bankModalConnections" :key="c.id">
              <td>{{ c.external_account_name || '—' }} <span v-if="c.external_account_currency" class="muted">({{ c.external_account_currency }})</span></td>
              <td>
                <select v-if="c.status === 'needs_linking'" v-model="linkSelections[c.id]" class="form-select form-select-sm">
                  <option value="">— Choisir un compte —</option>
                  <option v-for="acc in availableAccountsFor()" :key="acc.id" :value="acc.id">
                    {{ accountDisplayLabel(acc, accounts) }} ({{ acc.account_type }})
                  </option>
                </select>
                <template v-else>{{ accountLabelById(c.account_id, accounts) || '—' }}</template>
              </td>
              <td><span class="badge" :class="'status-' + c.status">{{ statusLabel(c.status) }}</span></td>
              <td class="muted">{{ c.last_synced_at ? new Date(c.last_synced_at).toLocaleString('fr-FR') : 'jamais' }}</td>
              <td class="actions">
                <button
                  v-if="c.status === 'needs_linking'"
                  class="btn btn-sm btn-primary"
                  :disabled="linking === c.id || !linkSelections[c.id]"
                  @click="linkConnection(c)"
                >
                  {{ linking === c.id ? 'Liaison…' : 'Lier' }}
                </button>
                <button
                  v-if="c.status === 'connected'"
                  class="btn btn-sm btn-primary"
                  :disabled="syncing === c.id"
                  @click="sync(c)"
                >
                  {{ syncing === c.id ? 'Synchro…' : '⟳ Synchroniser' }}
                </button>
                <button class="btn btn-sm btn-danger" :disabled="deleting === c.id" @click="removeConnection(c)">
                  {{ deleting === c.id ? '…' : 'Supprimer' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- Revue des transactions récupérées -->
        <template v-if="review">
          <h3>Transactions récupérées — {{ accountLabelById(review.account_id, accounts) }}</h3>
          <div v-if="!review.transactions.length" class="empty">Aucune nouvelle transaction depuis la dernière synchro.</div>
          <template v-else>
            <div class="form-row">
              <div class="form-group">
                <label class="form-label">Compte de contrepartie — Dépenses</label>
                <select v-model="reviewConfig.expense_opposing_account_id" class="form-select">
                  <option value="">— Sélectionner —</option>
                  <option v-for="acc in accounts" :key="acc.id" :value="acc.id">{{ accountDisplayLabel(acc, accounts) }}</option>
                </select>
              </div>
              <div class="form-group">
                <label class="form-label">Compte de contrepartie — Recettes</label>
                <select v-model="reviewConfig.income_opposing_account_id" class="form-select">
                  <option value="">— Sélectionner —</option>
                  <option v-for="acc in accounts" :key="acc.id" :value="acc.id">{{ accountDisplayLabel(acc, accounts) }}</option>
                </select>
              </div>
            </div>

            <div class="toolbar">
              <button class="btn btn-sm" @click="review.transactions.forEach(t => t.selected = true)">Tout sélectionner</button>
              <button class="btn btn-sm" @click="review.transactions.forEach(t => t.selected = false)">Tout désélectionner</button>
            </div>

            <div class="table-scroll">
              <table class="table">
                <thead>
                  <tr>
                    <th></th>
                    <th>Date</th>
                    <th>Description</th>
                    <th>Montant</th>
                    <th>Catégorie</th>
                    <th>Contrepartie</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="tx in review.transactions" :key="tx.row">
                    <td><input type="checkbox" v-model="tx.selected" /></td>
                    <td class="muted">{{ tx.date }}</td>
                    <td>{{ tx.description }}</td>
                    <td :class="tx.amount < 0 ? 'amount-neg' : 'amount-pos'">{{ tx.amount.toFixed(2) }}</td>
                    <td>
                      <select v-model="tx.category_id" class="form-select form-select-sm">
                        <option :value="null">—</option>
                        <option v-for="cat in categories" :key="cat.id" :value="cat.id">{{ cat.name }}</option>
                      </select>
                      <div v-if="tx.suggested_category_id && tx.suggested_category_id !== tx.category_id" class="rule-chip">
                        🔁 Règle : {{ categoryNameById(tx.suggested_category_id) }}
                        <button class="btn btn-sm" @click="applyRowSuggestion(tx, 'category')">Appliquer</button>
                      </div>
                    </td>
                    <td>
                      <select v-model="tx.opposing_account_id" class="form-select form-select-sm">
                        <option :value="null">— (défaut)</option>
                        <option v-for="acc in accounts" :key="acc.id" :value="acc.id">{{ accountDisplayLabel(acc, accounts) }}</option>
                      </select>
                      <div v-if="tx.suggested_opposing_account_id && tx.suggested_opposing_account_id !== tx.opposing_account_id" class="rule-chip">
                        🔁 Règle : {{ accountLabelById(tx.suggested_opposing_account_id, accounts) }}
                        <button class="btn btn-sm" @click="applyRowSuggestion(tx, 'opposing')">Appliquer</button>
                      </div>
                    </td>
                    <td><span v-if="tx.is_duplicate" class="badge warn">Doublon</span></td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="step-actions">
              <button class="btn" @click="review = null">Annuler</button>
              <button
                class="btn btn-primary"
                :disabled="confirming || !reviewConfig.expense_opposing_account_id || !reviewConfig.income_opposing_account_id"
                @click="confirmReview"
              >
                {{ confirming ? 'Import…' : 'Confirmer l\'import' }}
              </button>
            </div>
          </template>
        </template>

        <!-- Connecter un nouveau compte pour cette institution -->
        <template v-else>
          <h3>Connecter un compte</h3>
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">Pays de la banque</label>
              <select v-model="bankForm.country" class="form-select" @change="loadAspsps">
                <option value="">— Sélectionner —</option>
                <option v-for="c in COUNTRIES" :key="c.code" :value="c.code">{{ c.label }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="form-label">Banque</label>
              <select v-model="bankForm.aspsp_name" class="form-select" :disabled="!aspsps.length">
                <option value="">{{ loadingAspsps ? 'Chargement…' : '— Sélectionner —' }}</option>
                <option v-for="a in aspsps" :key="a.name" :value="a.name">{{ a.name }}</option>
              </select>
            </div>
          </div>
          <div class="step-actions">
            <button class="btn" @click="closeBankModal">Fermer</button>
            <button
              class="btn btn-primary"
              :disabled="connecting || !bankForm.country || !bankForm.aspsp_name"
              @click="connect"
            >
              {{ connecting ? 'Redirection…' : 'Connecter' }}
            </button>
          </div>
          <p class="hint">
            Redirige vers le site de la banque pour autoriser l'accès (lecture seule) à un ou
            plusieurs comptes, puis revient automatiquement ici où tu choisis à quel compte Cantisa
            lier chacun. Aucun identifiant bancaire ne transite par Cantisa Money.
          </p>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useModalShake, useEscapeClose } from '@/utils/modalUX'
import { confirmDialog } from '@/utils/confirmDialog'
import { useToast } from '@/utils/toast'
import { accountDisplayLabel, accountLabelById } from '@/utils/accountDisplay.js'

const toast = useToast()

// Palette tenue synchronisée avec Tags.vue / rt_tags.py (même 7 valeurs, pas de color-picker
// libre dans l'app).
const COLORS = ['green', 'red', 'blue', 'white', 'black', 'yellow', 'purple']
const COLOR_MAP = {
  green: '#22c55e', red: '#ef4444', blue: '#3b82f6',
  white: '#f1f5f9', black: '#1e293b', yellow: '#eab308', purple: '#a855f7',
}
function colorHex(c) { return COLOR_MAP[c] || '#6b7280' }

// Sous-ensemble volontairement limité : suffisant pour la phase 1 (Europe), pas une liste ISO
// complète — Enable Banking couvre surtout l'Europe de toute façon.
const COUNTRIES = [
  { code: 'FR', label: 'France' },
  { code: 'DE', label: 'Allemagne' },
  { code: 'ES', label: 'Espagne' },
  { code: 'IT', label: 'Italie' },
  { code: 'BE', label: 'Belgique' },
  { code: 'NL', label: 'Pays-Bas' },
  { code: 'PT', label: 'Portugal' },
  { code: 'FI', label: 'Finlande' },
]

const institutions = ref([])
const accounts = ref([])
const categories = ref([])
const connections = ref([])
const loading = ref(false)
const error = ref('')
const showModal = ref(false)
const editTarget = ref(null)
const form = ref({ name: '', bic: '', website: '', notes: '', color: 'blue' })

const { shaking, shake } = useModalShake()
useEscapeClose(() => { if (showModal.value) showModal.value = false }, shake, () => showModal.value)

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [instRes, accRes, catRes, connRes] = await Promise.all([
      axios.get('/api/institutions'),
      axios.get('/api/accounts'),
      axios.get('/api/categories'),
      axios.get('/api/bank-sync/connections'),
    ])
    institutions.value = Array.isArray(instRes.data?.response_data) ? instRes.data.response_data : []
    accounts.value = Array.isArray(accRes.data?.response_data) ? accRes.data.response_data : []
    categories.value = Array.isArray(catRes.data?.response_data) ? catRes.data.response_data : []
    connections.value = Array.isArray(connRes.data?.response_data) ? connRes.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editTarget.value = null
  form.value = { name: '', bic: '', website: '', notes: '', color: 'blue' }
  showModal.value = true
}

function openEdit(i) {
  editTarget.value = i
  form.value = { name: i.name, bic: i.bic || '', website: i.website || '', notes: i.notes || '', color: i.color || 'blue' }
  showModal.value = true
}

async function save() {
  try {
    if (editTarget.value) {
      await axios.patch('/api/institutions', {
        institution_id: editTarget.value.id,
        name: form.value.name,
        bic: form.value.bic || null,
        website: form.value.website || null,
        notes: form.value.notes || null,
        color: form.value.color,
      })
    } else {
      await axios.post('/api/institutions', {
        name: form.value.name,
        bic: form.value.bic || null,
        website: form.value.website || null,
        notes: form.value.notes || null,
        color: form.value.color,
      })
    }
    showModal.value = false
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function deleteInstitution(i) {
  const ok = await confirmDialog({
    title: 'Supprimer l’institution',
    message: `Supprimer « ${i.name} » ? Les comptes rattachés seront simplement détachés.`,
    confirmLabel: 'Supprimer',
    danger: true,
  })
  if (!ok) return
  try {
    await axios.delete('/api/institutions', { params: { institution_id: i.id } })
    await reload()
    toast.success(`Institution « ${i.name} » supprimée.`)
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

// ── Synchro bancaire ─────────────────────────────────────────────────────
const showBankModal = ref(false)
const bankModalInstitution = ref(null)
const bankModalConnections = ref([])
const bankError = ref('')
const syncing = ref(null)
const linking = ref(null)
const deleting = ref(null)
const connecting = ref(false)
const confirming = ref(false)
const linkSelections = ref({})
const review = ref(null)
const reviewConfig = ref({ expense_opposing_account_id: '', income_opposing_account_id: '' })

const bankForm = ref({ country: '', aspsp_name: '' })
const aspsps = ref([])
const loadingAspsps = ref(false)

const orphanConnections = ref([])

function refreshDerivedConnections() {
  bankModalConnections.value = bankModalInstitution.value
    ? connections.value.filter(c => c.institution_id === bankModalInstitution.value.id)
    : []
  orphanConnections.value = connections.value.filter(c => !c.institution_id)
}

function syncSummaryLabel(i) {
  const forInst = connections.value.filter(c => c.institution_id === i.id)
  const connected = forInst.filter(c => c.status === 'connected').length
  const pending = forInst.filter(c => c.status === 'needs_linking' || c.status === 'pending').length
  if (!forInst.length) return '+ Connecter'
  if (pending) return `${connected} connecté(s), ${pending} à lier`
  return `${connected} connecté(s)`
}

function statusLabel(s) {
  return { pending: 'En attente', needs_linking: 'À lier', connected: 'Connecté', error: 'Erreur', expired: 'Expiré' }[s] || s
}

// Un compte déjà lié (status 'connected') à une connexion bancaire ne se re-propose pas dans le
// select de liaison d'une autre ligne — sinon deux connexions pourraient pointer vers le même
// compte Cantisa.
function availableAccountsFor() {
  const linked = new Set(connections.value.filter(c => c.status === 'connected').map(c => c.account_id))
  return accounts.value.filter(a => !linked.has(a.id) && !a.is_closed)
}

function openBankModal(i) {
  bankModalInstitution.value = i
  bankForm.value = { country: '', aspsp_name: '' }
  aspsps.value = []
  review.value = null
  bankError.value = ''
  refreshDerivedConnections()
  showBankModal.value = true
}

function closeBankModal() {
  showBankModal.value = false
  bankModalInstitution.value = null
  review.value = null
}

async function loadAspsps() {
  aspsps.value = []
  bankForm.value.aspsp_name = ''
  if (!bankForm.value.country) return
  loadingAspsps.value = true
  try {
    const { data } = await axios.get('/api/bank-sync/aspsps', { params: { country: bankForm.value.country } })
    aspsps.value = Array.isArray(data?.response_data) ? data.response_data : []
  } catch (e) {
    bankError.value = e?.response?.data?.response_data || e?.message || 'Erreur lors du chargement des banques'
  } finally {
    loadingAspsps.value = false
  }
}

async function connect() {
  connecting.value = true
  bankError.value = ''
  try {
    const { data } = await axios.post('/api/bank-sync/authorize', {
      aspsp_name: bankForm.value.aspsp_name,
      aspsp_country: bankForm.value.country,
      institution_id: bankModalInstitution.value?.id || null,
    })
    const url = data?.response_data?.url
    if (!url) throw new Error('Pas d\'URL de redirection renvoyée')
    // Sort intentionnellement de l'app : la banque authentifie l'utilisateur sur son propre site,
    // puis Enable Banking redirige vers /bank-sync/callback (voir router), qui renvoie ensuite ici.
    window.location.href = url
  } catch (e) {
    bankError.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la connexion'
    connecting.value = false
  }
}

async function linkConnection(c) {
  const account_id = linkSelections.value[c.id]
  if (!account_id) return
  linking.value = c.id
  bankError.value = ''
  try {
    await axios.patch(`/api/bank-sync/connections/${c.id}/link`, { account_id })
    toast.success('Compte lié avec succès.')
    await reload()
    refreshDerivedConnections()
  } catch (e) {
    bankError.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la liaison'
  } finally {
    linking.value = null
  }
}

async function removeConnection(c) {
  deleting.value = c.id
  bankError.value = ''
  try {
    await axios.delete(`/api/bank-sync/connections/${c.id}`)
    if (review.value?.account_id === c.account_id) review.value = null
    await reload()
    refreshDerivedConnections()
  } catch (e) {
    bankError.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la suppression'
  } finally {
    deleting.value = null
  }
}

async function sync(c) {
  syncing.value = c.id
  bankError.value = ''
  try {
    const { data } = await axios.post(`/api/bank-sync/connections/${c.id}/sync`)
    const payload = data?.response_data
    review.value = payload
    const profile = loadProfileForAccount(payload.account_id)
    reviewConfig.value = {
      expense_opposing_account_id: profile?.expense_opposing_account_id || '',
      income_opposing_account_id: profile?.income_opposing_account_id || '',
    }
    await reload()
    refreshDerivedConnections()
  } catch (e) {
    bankError.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la synchronisation'
  } finally {
    syncing.value = null
  }
}

function categoryNameById(id) {
  return categories.value.find(c => String(c.id) === String(id))?.name || ''
}

// Copie une suggestion de règle apprise (rt_bank_sync.py::sync) dans le champ réel — n'a lieu que
// sur clic explicite de l'utilisateur, jamais automatiquement (même logique qu'Import.vue).
function applyRowSuggestion(tx, field) {
  if (field === 'category') {
    tx.category_id = tx.suggested_category_id
  } else {
    tx.opposing_account_id = tx.suggested_opposing_account_id
  }
}

// Réutilise le profil d'import mémorisé par Import.vue pour ce compte (mêmes clés localStorage) —
// évite de redemander les contreparties dépenses/recettes si l'utilisateur a déjà importé
// manuellement ce compte auparavant.
function loadProfileForAccount(accountId) {
  try {
    const raw = localStorage.getItem('cantisa_import_profile_' + accountId)
    return raw ? JSON.parse(raw) : null
  } catch (e) {
    return null
  }
}

async function confirmReview() {
  confirming.value = true
  bankError.value = ''
  try {
    const { data } = await axios.post('/api/import/confirm', {
      account_id: review.value.account_id,
      expense_opposing_account_id: reviewConfig.value.expense_opposing_account_id,
      income_opposing_account_id: reviewConfig.value.income_opposing_account_id,
      currency_id: review.value.currency_id,
      transactions: review.value.transactions,
    })
    const { created, skipped } = data.response_data
    toast.success(`${created} transaction(s) importée(s)${skipped ? `, ${skipped} ignorée(s)` : ''}.`)
    review.value = null
  } catch (e) {
    bankError.value = e?.response?.data?.response_data || e?.message || "Erreur lors de l'import"
  } finally {
    confirming.value = false
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
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; }
.header-actions { display: flex; gap: 10px; align-items: center; }

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-sm { padding: 6px 10px; font-size: 13px; }
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
}

.card {
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 14px;
  padding: 20px;
  margin-top: 20px;
}
.card h2 { margin: 0 0 14px; font-size: 17px; }

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.table th {
  text-align: left;
  padding: 10px 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
  color: #9ca3af;
  font-weight: 500;
}
.table td {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.08);
}
.muted { color: #9ca3af; }
.actions { text-align: right; white-space: nowrap; }
.actions .btn + .btn { margin-left: 6px; }
.table-scroll { overflow-x: auto; max-height: 400px; overflow-y: auto; }

.color-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  display: inline-block;
}

.btn-action {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
  margin-left: 4px;
}
.btn-action:hover { background: rgba(148, 163, 184, 0.1); }
.btn-danger { border-color: rgba(239,68,68,0.4); color: #fca5a5; }
.btn-danger:hover { background: rgba(239,68,68,0.1); }

.btn-sync {
  background: transparent;
  border: 1px solid rgba(96, 165, 250, 0.35);
  color: #93c5fd;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.btn-sync:hover { background: rgba(96, 165, 250, 0.1); }

.badge { display: inline-block; padding: 3px 8px; border-radius: 999px; font-size: 12px; border: 1px solid rgba(148,163,184,0.25); }
.badge.warn { color: #fbbf24; border-color: rgba(251,191,36,0.4); background: rgba(251,191,36,0.1); }
.status-pending, .status-needs_linking { color: #fbbf24; border-color: rgba(251,191,36,0.4); }
.status-connected { color: #4ade80; border-color: rgba(74,222,128,0.4); }
.status-error, .status-expired { color: #f87171; border-color: rgba(248,113,113,0.4); }

.form-row { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 14px; }
.form-group { display: flex; flex-direction: column; gap: 6px; min-width: 220px; flex: 1; }
.form-label { font-size: 13px; color: #9ca3af; }
.form-select, .form-select-sm {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px;
  padding: 8px 10px;
  color: #e5e7eb;
  font-size: 14px;
}
.form-select-sm { padding: 4px 6px; font-size: 12px; }

.rule-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 11px;
  color: #c4b5fd;
  border: 1px solid rgba(139, 92, 246, 0.3);
  background: rgba(139, 92, 246, 0.08);
  border-radius: 6px;
  padding: 3px 6px;
  margin-top: 4px;
}

.toolbar { display: flex; gap: 8px; margin-bottom: 10px; }
.step-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 14px; }

.amount-neg { color: #f87171; }
.amount-pos { color: #4ade80; }

.hint { font-size: 13px; color: #9ca3af; margin: 10px 0 0; }

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: #1e293b;
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 16px;
  padding: 24px;
  width: 400px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.modal-wide { width: 720px; max-width: 92vw; max-height: 86vh; overflow-y: auto; }
.modal h2 { margin: 0; font-size: 18px; }
.modal h3 { margin: 8px 0 4px; font-size: 15px; }
.modal label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #9ca3af;
}
.modal input, .modal select {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px;
  padding: 8px 10px;
  color: #e5e7eb;
  font-size: 14px;
}
.color-preview {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 2px solid rgba(255,255,255,0.15);
}
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 4px; }
</style>
