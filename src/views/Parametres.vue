<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Paramétrage</h1>
        <p class="subtitle">Préférences et configuration de Cantisa Money.</p>
      </div>
      <button class="btn-save" @click="saveAll" :disabled="!dirty">
        {{ saved ? 'Enregistré ✓' : 'Enregistrer' }}
      </button>
    </header>

    <!-- Navigation sections -->
    <div class="layout">
      <nav class="section-nav">
        <a
          v-for="s in sections"
          :key="s.id"
          class="nav-item"
          :class="{ active: activeSection === s.id }"
          @click="activeSection = s.id"
        >{{ s.label }}</a>
      </nav>

      <div class="content">

        <!-- ═══ INTERFACE ═══ -->
        <section v-if="activeSection === 'interface'">
          <h2 class="section-title">Interface</h2>

          <div class="settings-card">
            <h3 class="card-title">Sidebar</h3>
            <div class="setting-row">
              <div class="setting-label">
                <span class="setting-name">Replier au démarrage</span>
                <span class="setting-desc">La sidebar sera réduite à l'ouverture de l'application.</span>
              </div>
              <button :class="['toggle', { on: collapseOnStart }]" @click="collapseOnStart = !collapseOnStart; dirty = true">
                <span class="toggle-thumb" />
              </button>
            </div>
          </div>

          <div class="settings-card">
            <h3 class="card-title">Affichage</h3>
            <div class="setting-row">
              <div class="setting-label">
                <span class="setting-name">Devise par défaut</span>
                <span class="setting-desc">Symbole affiché dans les montants.</span>
              </div>
              <select v-model="currency" class="select" @change="dirty = true">
                <option v-for="c in currencyOptions" :key="c.id" :value="c.short_name">
                  {{ c.short_name }} — {{ c.name }}
                </option>
              </select>
            </div>
            <div class="setting-row">
              <div class="setting-label">
                <span class="setting-name">Format de date</span>
                <span class="setting-desc">Exemple : {{ dateExample }}</span>
              </div>
              <select v-model="dateFormat" class="select" @change="dirty = true">
                <option value="fr-FR">JJ/MM/AAAA</option>
                <option value="en-GB">DD/MM/YYYY</option>
                <option value="en-US">MM/DD/YYYY</option>
                <option value="iso">AAAA-MM-JJ</option>
              </select>
            </div>
          </div>
        </section>

        <!-- ═══ MARCHÉS ═══ -->
        <section v-if="activeSection === 'marches'">
          <h2 class="section-title">Marchés — Score de notation</h2>
          <p class="section-desc">
            Configurez l'importance de chaque indicateur dans le calcul du score global affiché sur les fiches d'analyse.
            Le total des pondérations doit faire <strong>100 %</strong>.
          </p>

          <div class="settings-card">
            <h3 class="card-title">Pondérations</h3>

            <div class="weights-table">
              <div class="weights-header">
                <span>Indicateur</span>
                <span>Actif</span>
                <span>Pondération</span>
                <span>Poids</span>
              </div>

              <div v-for="metric in DEFAULT_METRICS" :key="metric.key" class="weight-row">
                <div class="metric-info">
                  <span class="metric-name">{{ metric.label }}</span>
                  <span class="metric-dir" :class="metric.direction === 'lower' ? 'dir-low' : 'dir-high'">
                    {{ metric.direction === 'lower' ? '↓ plus bas = mieux' : '↑ plus haut = mieux' }}
                  </span>
                </div>

                <button
                  :class="['toggle', { on: weights[metric.key].enabled }]"
                  @click="toggleMetric(metric.key)"
                >
                  <span class="toggle-thumb" />
                </button>

                <div class="slider-wrap" :class="{ disabled: !weights[metric.key].enabled }">
                  <input
                    type="range"
                    min="0"
                    max="100"
                    :value="weights[metric.key].weight"
                    :disabled="!weights[metric.key].enabled"
                    @input="onWeightInput(metric.key, $event.target.value)"
                    class="slider"
                  />
                </div>

                <div class="weight-value" :class="{ disabled: !weights[metric.key].enabled }">
                  <input
                    type="number"
                    min="0"
                    max="100"
                    :value="weights[metric.key].weight"
                    :disabled="!weights[metric.key].enabled"
                    @change="onWeightInput(metric.key, $event.target.value)"
                    class="weight-input"
                  />
                  <span>%</span>
                </div>
              </div>
            </div>

            <!-- Total -->
            <div class="total-row" :class="totalClass">
              <span>Total</span>
              <span class="total-value">{{ totalWeight }} %</span>
              <span class="total-hint" v-if="totalWeight !== 100">
                {{ totalWeight < 100 ? `— il manque ${100 - totalWeight} %` : `— ${totalWeight - 100} % en trop` }}
              </span>
              <span class="total-hint ok" v-else>— parfait</span>
              <button class="btn-normalize" @click="normalizeWeights" title="Répartir automatiquement à 100%">
                Équilibrer
              </button>
            </div>
          </div>

          <div class="settings-card">
            <h3 class="card-title">Barèmes de notation</h3>
            <p class="card-desc">
              Valeurs de référence pour convertir chaque indicateur en note sur 10.
              La note est interpolée linéairement entre les deux bornes.
            </p>
            <div class="scale-table">
              <div class="scale-header">
                <span>Indicateur</span>
                <span class="col-center">Note 10 — excellent</span>
                <span class="col-center">Note 0 — mauvais</span>
                <span class="col-center">Réinitialiser</span>
              </div>
              <div v-for="m in DEFAULT_METRICS" :key="m.key" class="scale-row">
                <div class="metric-info">
                  <span class="metric-name">{{ m.label }}</span>
                  <span class="metric-dir" :class="m.direction === 'lower' ? 'dir-low' : 'dir-high'">
                    {{ m.direction === 'lower' ? '↓ plus bas = mieux' : '↑ plus haut = mieux' }}
                  </span>
                </div>

                <div class="threshold-cell">
                  <span class="threshold-op good">{{ m.direction === 'lower' ? '≤' : '≥' }}</span>
                  <input
                    type="number"
                    class="threshold-input good-input"
                    :value="thresholds[m.key].great"
                    @change="onThreshold(m.key, 'great', $event.target.value)"
                  />
                  <span class="threshold-unit">{{ isPct(m.key) ? '%' : '' }}</span>
                </div>

                <div class="threshold-cell">
                  <span class="threshold-op bad">{{ m.direction === 'lower' ? '≥' : '≤' }}</span>
                  <input
                    type="number"
                    class="threshold-input bad-input"
                    :value="thresholds[m.key].bad"
                    @change="onThreshold(m.key, 'bad', $event.target.value)"
                  />
                  <span class="threshold-unit">{{ isPct(m.key) ? '%' : '' }}</span>
                </div>

                <div class="col-center">
                  <button class="btn-reset-row" @click="resetThreshold(m)" title="Remettre les valeurs par défaut">↺</button>
                </div>
              </div>
            </div>
            <div class="scale-footer">
              <button class="btn-normalize" @click="resetAllThresholds">Réinitialiser tous les barèmes</button>
            </div>
          </div>
        </section>

        <!-- ═══ DEVISES ═══ -->
        <section v-if="activeSection === 'devises'">
          <h2 class="section-title">Devises</h2>
          <p class="section-desc">
            Les devises et cryptomonnaies utilisées comme monnaie de vos comptes, transactions et actifs.
          </p>

          <div v-if="commoditiesError" class="alert"><strong>Erreur :</strong> {{ commoditiesError }}</div>

          <div class="settings-card">
            <div class="card-header-row">
              <h3 class="card-title">Liste des devises</h3>
              <button class="btn-normalize" @click="openCreateCommodity">+ Nouvelle devise</button>
            </div>

            <div v-if="commoditiesLoading && !commodities.length" class="empty">Chargement…</div>
            <div v-else-if="!commoditiesLoading && !commodities.length" class="empty">Aucune devise.</div>

            <table v-else class="table">
              <thead>
                <tr>
                  <th>Code</th>
                  <th>Nom</th>
                  <th>Type</th>
                  <th>Décimales</th>
                  <th>Description</th>
                  <th>Suivi auto</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="c in commodities" :key="c.id">
                  <td class="bold">{{ c.short_name }}</td>
                  <td>{{ c.name }}</td>
                  <td class="muted">{{ c.type === 'Crypto' ? 'Cryptomonnaie' : 'Devise' }}</td>
                  <td class="muted">{{ c.fraction }}</td>
                  <td class="muted">{{ c.description || '—' }}</td>
                  <td class="muted">
                    <span v-if="c.track_live_rate" class="track-badge" :title="c.last_rate_updated_at ? ('Dernière mise à jour : ' + fmtDateTime(c.last_rate_updated_at)) : 'Pas encore rafraîchi'">
                      ● Suivi{{ c.short_name !== currency ? (' vs ' + currency) : '' }}
                    </span>
                    <span v-else>—</span>
                  </td>
                  <td class="actions">
                    <button
                      v-if="c.track_live_rate"
                      class="btn-action"
                      :disabled="refreshingRateIds.has(c.id)"
                      title="Rafraîchir le taux maintenant"
                      @click="refreshCommodityRate(c)"
                    >⟳</button>
                    <button class="btn-action" @click="openEditCommodity(c)" title="Modifier">✎</button>
                    <button class="btn-action btn-danger" @click="deleteCommodity(c)" title="Supprimer">✕</button>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <!-- ═══ SAUVEGARDE ═══ -->
        <section v-if="activeSection === 'sauvegarde'">
          <h2 class="section-title">Sauvegarde</h2>
          <p class="section-desc">
            Exportez l'intégralité de vos données (comptes, transactions, budgets, actifs…) dans un fichier JSON,
            à conserver ou à réimporter — dans cette instance ou une autre. Les éléments déjà présents (même nom,
            mêmes montants et dates) sont automatiquement reconnus et ne sont jamais dupliqués.
          </p>

          <div class="settings-card">
            <h3 class="card-title">Exporter</h3>
            <div class="setting-row">
              <div class="setting-label">
                <span class="setting-name">Télécharger une sauvegarde complète</span>
                <span class="setting-desc">Fichier JSON contenant toutes vos données actuelles.</span>
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
              <input ref="importInput" type="file" accept="application/json,.json" style="display: none" @change="onImportFileChosen" />
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
        </section>

      </div>
    </div>

    <!-- Modal : Créer / modifier une devise -->
    <div v-if="showCommodityModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>{{ commodityEditTarget ? 'Modifier la devise' : 'Nouvelle devise' }}</h2>
        <label>Nom *
          <input v-model="commodityForm.name" placeholder="ex: Livre Sterling" autocomplete="off" />
        </label>
        <label>Code *
          <input v-model="commodityForm.short_name" placeholder="ex: GBP" maxlength="6" autocomplete="off" style="text-transform: uppercase" />
        </label>
        <label>Type
          <select v-model="commodityForm.type" class="select">
            <option value="Currency">Devise</option>
            <option value="Crypto">Cryptomonnaie</option>
          </select>
        </label>
        <label>Décimales
          <input v-model.number="commodityForm.fraction" type="number" min="0" max="8" />
        </label>
        <label>Description
          <input v-model="commodityForm.description" placeholder="Optionnel" autocomplete="off" />
        </label>
        <label class="toggle-row">
          <span>
            Suivre le cours automatiquement
            <span class="muted">— rafraîchi périodiquement contre la devise par défaut ({{ currency }})</span>
          </span>
          <button type="button" :class="['toggle', { on: commodityForm.track_live_rate }]" @click="commodityForm.track_live_rate = !commodityForm.track_live_rate">
            <span class="toggle-thumb" />
          </button>
        </label>
        <div v-if="commodityModalError" class="modal-error">{{ commodityModalError }}</div>
        <div class="modal-actions">
          <button class="btn" @click="showCommodityModal = false">Annuler</button>
          <button class="btn btn-primary" :disabled="!commodityForm.name.trim() || !commodityForm.short_name.trim()" @click="saveCommodity">Enregistrer</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted } from 'vue'
import axios from 'axios'
import { DEFAULT_METRICS, loadWeights, loadThresholds } from '@/utils/marketScore.js'
import { currency as settingsCurrency, dateFormat as settingsDateFormat, saveSettings } from '@/utils/settings.js'
import { useModalShake, useEscapeClose } from '@/utils/modalUX'

// ── Sections ─────────────────────────────────────────────────────────────────
const sections = [
  { id: 'interface', label: 'Interface' },
  { id: 'marches',   label: 'Marchés' },
  { id: 'devises',   label: 'Devises' },
  { id: 'sauvegarde', label: 'Sauvegarde' },
]
const activeSection = ref('interface')

// ── État ─────────────────────────────────────────────────────────────────────
const dirty  = ref(false)
const saved  = ref(false)

// Interface
const KEY_COLLAPSE = 'cmm_sidebar_collapsed_on_start'
const collapseOnStart = ref(false)
const currency        = ref('EUR')
const dateFormat      = ref('fr-FR')

// Marchés
const weights    = reactive({})
const thresholds = reactive({})

// Sauvegarde
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

// Devises
const commodities        = ref([])
const commoditiesLoading = ref(false)
const commoditiesError   = ref('')
const showCommodityModal = ref(false)
const commodityEditTarget = ref(null)
const commodityModalError = ref('')
const commodityForm = ref({ name: '', short_name: '', type: 'Currency', fraction: 2, description: '', track_live_rate: false })
const refreshingRateIds = ref(new Set())

const { shaking, shake } = useModalShake()
useEscapeClose(() => { if (showCommodityModal.value) showCommodityModal.value = false })

// Options de devise dérivées des devises que l'utilisateur a lui-même créées (onglet "Devises"),
// pas une liste figée — sinon une devise ajoutée ici (ex: JPY) ne serait jamais sélectionnable
// comme devise affichée, et inversement des devises jamais utilisées y apparaîtraient.
const currencyOptions = computed(() => {
  const currencies = commodities.value.filter(c => c.type === 'Currency')
  if (currencies.length) return currencies
  // Repli le temps du chargement (ou si l'utilisateur n'a encore aucune devise) : au moins la
  // valeur actuellement enregistrée, pour ne pas afficher un select vide.
  return [{ id: currency.value, short_name: currency.value, name: currency.value }]
})

const dateExample = computed(() => {
  const d = new Date()
  if (dateFormat.value === 'iso') return d.toISOString().slice(0, 10)
  return d.toLocaleDateString(dateFormat.value)
})

const totalWeight = computed(() =>
  DEFAULT_METRICS.reduce((s, m) => s + (weights[m.key]?.enabled ? (weights[m.key]?.weight || 0) : 0), 0)
)

const totalClass = computed(() => {
  if (totalWeight.value === 100) return 'total-ok'
  return 'total-error'
})

// ── Chargement ────────────────────────────────────────────────────────────────
onMounted(() => {
  collapseOnStart.value = localStorage.getItem(KEY_COLLAPSE) === 'true'
  currency.value        = settingsCurrency.value
  dateFormat.value      = settingsDateFormat.value

  const stored = loadWeights()
  DEFAULT_METRICS.forEach(m => { weights[m.key] = { ...stored[m.key] } })

  const storedT = loadThresholds()
  DEFAULT_METRICS.forEach(m => { thresholds[m.key] = { ...storedT[m.key] } })

  reloadCommodities()
})

// ── Devises ───────────────────────────────────────────────────────────────────
async function reloadCommodities() {
  commoditiesLoading.value = true
  commoditiesError.value = ''
  try {
    const res = await axios.get('/api/commodities')
    commodities.value = Array.isArray(res.data?.response_data) ? res.data.response_data : []
  } catch (e) {
    commoditiesError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    commoditiesLoading.value = false
  }
}

function openCreateCommodity() {
  commodityEditTarget.value = null
  commodityForm.value = { name: '', short_name: '', type: 'Currency', fraction: 2, description: '', track_live_rate: false }
  commodityModalError.value = ''
  showCommodityModal.value = true
}

function openEditCommodity(c) {
  commodityEditTarget.value = c
  commodityForm.value = { name: c.name, short_name: c.short_name, type: c.type, fraction: c.fraction, description: c.description || '', track_live_rate: !!c.track_live_rate }
  commodityModalError.value = ''
  showCommodityModal.value = true
}

function fmtDateTime(v) {
  if (!v) return '—'
  return new Date(v).toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })
}

async function saveCommodity() {
  commodityModalError.value = ''
  const payload = {
    name: commodityForm.value.name.trim(),
    short_name: commodityForm.value.short_name.trim(),
    type: commodityForm.value.type,
    fraction: commodityForm.value.fraction,
    description: commodityForm.value.description?.trim() || null,
    track_live_rate: commodityForm.value.track_live_rate,
  }
  try {
    if (commodityEditTarget.value) {
      await axios.patch('/api/commodities', { commodity_id: commodityEditTarget.value.id, ...payload })
    } else {
      await axios.post('/api/commodities', payload)
    }
    showCommodityModal.value = false
    await reloadCommodities()
  } catch (e) {
    commodityModalError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function refreshCommodityRate(c) {
  refreshingRateIds.value.add(c.id)
  commoditiesError.value = ''
  try {
    await axios.post('/api/commodities/refresh-rate', { commodity_id: c.id })
    await reloadCommodities()
  } catch (e) {
    commoditiesError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    refreshingRateIds.value.delete(c.id)
  }
}

async function deleteCommodity(c) {
  if (!confirm(`Supprimer la devise « ${c.short_name} » ?`)) return
  commoditiesError.value = ''
  try {
    await axios.delete('/api/commodities', { params: { commodity_id: c.id } })
    await reloadCommodities()
  } catch (e) {
    commoditiesError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

// ── Sauvegarde ────────────────────────────────────────────────────────────────
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
    a.download = `cantisa-backup-${stamp}.json`
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

// ── Actions ───────────────────────────────────────────────────────────────────
function toggleMetric(key) {
  weights[key].enabled = !weights[key].enabled
  dirty.value = true
}

function onWeightInput(key, val) {
  weights[key].weight = Math.min(100, Math.max(0, parseInt(val) || 0))
  dirty.value = true
}

function normalizeWeights() {
  const active = DEFAULT_METRICS.filter(m => weights[m.key].enabled)
  if (!active.length) return
  const base = Math.floor(100 / active.length)
  const remainder = 100 - base * active.length
  active.forEach((m, i) => {
    weights[m.key].weight = i === 0 ? base + remainder : base
  })
  dirty.value = true
}

function onThreshold(key, bound, val) {
  thresholds[key][bound] = parseFloat(val) || 0
  dirty.value = true
}

function resetThreshold(m) {
  thresholds[m.key] = { great: m.great, bad: m.bad }
  dirty.value = true
}

function resetAllThresholds() {
  DEFAULT_METRICS.forEach(m => { thresholds[m.key] = { great: m.great, bad: m.bad } })
  dirty.value = true
}

function isPct(key) {
  return ['roe', 'roa', 'net_margin', 'gross_margin', 'operating_margin', 'dividend_yield'].includes(key)
}

async function saveAll() {
  try {
    localStorage.setItem(KEY_COLLAPSE, String(collapseOnStart.value))
  } catch {}
  await saveSettings({
    currency: currency.value,
    dateFormat: dateFormat.value,
    weights: { ...weights },
    thresholds: { ...thresholds },
  })
  dirty.value = false
  saved.value = true
  setTimeout(() => { saved.value = false }, 2500)
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
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; }

.btn-save {
  background: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 8px;
  padding: 10px 22px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s, opacity 0.2s;
  white-space: nowrap;
  margin-top: 4px;
}
.btn-save:hover:not(:disabled) { background: #2563eb; }
.btn-save:disabled { opacity: 0.45; cursor: default; }

/* Layout */
.layout {
  display: flex;
  gap: 24px;
  align-items: flex-start;
}

.section-nav {
  width: 180px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: #1e293b;
  border: 1px solid rgba(148,163,184,0.1);
  border-radius: 12px;
  padding: 8px;
  position: sticky;
  top: 24px;
}
.nav-item {
  padding: 9px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: #94a3b8;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.nav-item:hover { background: rgba(148,163,184,0.08); color: #cbd5e1; }
.nav-item.active { background: rgba(59,130,246,0.15); color: #60a5fa; font-weight: 600; }

.content { flex: 1; display: flex; flex-direction: column; gap: 20px; }

/* Section */
.section-title { margin: 0 0 4px; font-size: 20px; font-weight: 700; color: #f1f5f9; }
.section-desc  { margin: 0 0 16px; font-size: 13px; color: #64748b; line-height: 1.6; }

/* Cards */
.settings-card {
  background: #1e293b;
  border: 1px solid rgba(148,163,184,0.1);
  border-radius: 14px;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.card-title { margin: 0; font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.07em; }
.card-desc { margin: -8px 0 0; font-size: 12px; color: #475569; }

/* Setting rows */
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

/* Toggle */
.toggle {
  position: relative;
  width: 42px;
  height: 24px;
  border-radius: 999px;
  background: rgba(148,163,184,0.2);
  border: none;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.2s;
  padding: 0;
}
.toggle.on { background: #2563eb; }
.toggle-thumb {
  position: absolute;
  top: 3px; left: 3px;
  width: 18px; height: 18px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.2s;
  display: block;
}
.toggle.on .toggle-thumb { transform: translateX(18px); }

/* Select */
.select {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 8px;
  color: #e5e7eb;
  padding: 7px 10px;
  font-size: 13px;
  cursor: pointer;
  outline: none;
  flex-shrink: 0;
}
.select:focus { border-color: #2563eb; }

/* Weights table */
.weights-table { display: flex; flex-direction: column; gap: 0; }
.weights-header {
  display: grid;
  grid-template-columns: 1fr 60px 1fr 90px;
  gap: 12px;
  padding: 6px 0 10px;
  font-size: 11px;
  font-weight: 700;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  border-bottom: 1px solid rgba(148,163,184,0.1);
}
.weight-row {
  display: grid;
  grid-template-columns: 1fr 60px 1fr 90px;
  gap: 12px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid rgba(148,163,184,0.06);
}
.weight-row:last-child { border-bottom: none; }
.metric-info { display: flex; flex-direction: column; gap: 2px; }
.metric-name { font-size: 13px; color: #cbd5e1; font-weight: 500; }
.metric-dir { font-size: 11px; }
.dir-low  { color: #60a5fa; }
.dir-high { color: #4ade80; }

.slider-wrap { display: flex; align-items: center; }
.slider-wrap.disabled { opacity: 0.35; }
.slider {
  width: 100%;
  accent-color: #3b82f6;
  cursor: pointer;
}
.slider:disabled { cursor: not-allowed; }

.weight-value {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  font-weight: 700;
  color: #e5e7eb;
}
.weight-value.disabled { opacity: 0.35; }
.weight-input {
  width: 52px;
  background: rgba(15,23,42,0.6);
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 6px;
  color: #e5e7eb;
  padding: 5px 8px;
  font-size: 13px;
  font-weight: 700;
  text-align: right;
  outline: none;
}
.weight-input:focus { border-color: #3b82f6; }
.weight-input:disabled { opacity: 0.4; cursor: not-allowed; }

/* Total row */
.total-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0 0;
  border-top: 1px solid rgba(148,163,184,0.12);
  font-size: 13px;
  font-weight: 700;
  margin-top: 4px;
}
.total-value { font-size: 18px; }
.total-hint { font-size: 12px; font-weight: 400; }
.total-hint.ok { color: #4ade80; }
.total-ok .total-value { color: #4ade80; }
.total-error .total-value { color: #f87171; }
.total-error .total-hint { color: #f87171; }

.btn-normalize {
  margin-left: auto;
  background: rgba(59,130,246,0.1);
  border: 1px solid rgba(59,130,246,0.3);
  border-radius: 6px;
  color: #60a5fa;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-normalize:hover { background: rgba(59,130,246,0.2); }

/* Scale table */
.scale-table { display: flex; flex-direction: column; }
.scale-header {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr 60px;
  gap: 12px;
  padding: 6px 0 10px;
  font-size: 11px;
  font-weight: 700;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  border-bottom: 1px solid rgba(148,163,184,0.1);
}
.scale-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr 60px;
  gap: 12px;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid rgba(148,163,184,0.06);
}
.scale-row:last-child { border-bottom: none; }
.col-center { display: flex; align-items: center; justify-content: center; }

.threshold-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.threshold-op { font-size: 14px; font-weight: 700; flex-shrink: 0; }
.threshold-op.good { color: #4ade80; }
.threshold-op.bad  { color: #f87171; }
.threshold-input {
  width: 64px;
  background: rgba(15,23,42,0.6);
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 6px;
  color: #e5e7eb;
  padding: 5px 8px;
  font-size: 13px;
  font-weight: 600;
  text-align: right;
  outline: none;
}
.threshold-input:focus { border-color: #3b82f6; }
.threshold-input.good-input:focus { border-color: #4ade80; }
.threshold-input.bad-input:focus  { border-color: #f87171; }
.threshold-unit { font-size: 12px; color: #64748b; flex-shrink: 0; }

.btn-reset-row {
  background: none;
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 6px;
  color: #64748b;
  font-size: 14px;
  cursor: pointer;
  padding: 3px 8px;
  transition: all 0.15s;
}
.btn-reset-row:hover { color: #94a3b8; background: rgba(148,163,184,0.1); }

.scale-footer {
  display: flex;
  justify-content: flex-end;
  padding-top: 12px;
  border-top: 1px solid rgba(148,163,184,0.08);
  margin-top: 4px;
}

/* Devises */
.card-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
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
.table { width: 100%; border-collapse: collapse; font-size: 14px; }
.table th {
  text-align: left; padding: 10px 12px;
  border-bottom: 1px solid rgba(148,163,184,0.15);
  color: #9ca3af; font-weight: 500;
}
.table td { padding: 10px 12px; border-bottom: 1px solid rgba(148,163,184,0.08); vertical-align: middle; }
.table tr:last-child td { border-bottom: none; }
.bold { font-weight: 600; }
.muted { color: #9ca3af; }
.actions { text-align: right; white-space: nowrap; }

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: linear-gradient(90deg, #2563eb, #4f46e5); border-color: transparent; color: #fff; }

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
.modal h2 { margin: 0; font-size: 18px; }
.modal label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #9ca3af;
}
.modal input {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px;
  padding: 8px 10px;
  color: #e5e7eb;
  font-size: 14px;
}
.modal-error {
  font-size: 13px;
  color: #fca5a5;
  background: rgba(239,68,68,0.08);
  border: 1px solid rgba(239,68,68,0.3);
  border-radius: 8px;
  padding: 8px 10px;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 4px; }

.toggle-row {
  flex-direction: row !important;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.track-badge {
  color: #4ade80;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

/* Sauvegarde */
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
.import-errors {
  margin: 8px 0 0;
  font-size: 12px;
  color: #fca5a5;
  line-height: 1.6;
}
</style>
