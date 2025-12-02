<template>
  <div class="page">
    <!-- Header -->
    <header class="page-header">
      <div>
        <h1>Bank accounts</h1>
        <p class="subtitle">
          Gérez vos comptes courants, livrets et cartes comme dans Microsoft Money.
        </p>
      </div>

      <div class="header-actions">
        <div class="search-wrapper">
          <span class="search-icon">🔍</span>
          <input
            v-model="search"
            type="text"
            placeholder="Rechercher un compte…"
          />
        </div>

        <label class="checkbox">
          <input type="checkbox" v-model="showArchived" />
          Afficher les comptes archivés
        </label>

        <button class="btn btn-primary" type="button" @click="openCreate">
          <span class="btn-icon">＋</span>
          Nouveau compte
        </button>
      </div>
    </header>

    <!-- Résumé -->
    <section class="summary-grid">
      <div class="summary-card">
        <span class="summary-label">Nombre de comptes</span>
        <span class="summary-value">{{ filteredAccounts.length }}</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">Solde bancaire total</span>
        <span class="summary-value">{{ formatMoney(totalBankBalance) }}</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">Solde ajusté total</span>
        <span class="summary-value">{{ formatMoney(totalAdjBalance) }}</span>
      </div>
      <div class="summary-card">
        <span class="summary-label">Transactions à traiter</span>
        <span class="summary-value">
          {{ totalToReview }} opé
        </span>
      </div>
    </section>

    <div class="layout">
      <!-- Liste des comptes bancaires -->
      <section class="accounts-card">
        <div
          v-for="group in groupedAccounts"
          :key="group.key"
          class="group"
        >
          <!-- En-tête de groupe (pliable) -->
          <button
            class="group-header"
            type="button"
            @click="toggleGroup(group.key)"
          >
            <div class="group-header-left">
              <span class="group-toggle">
                {{ isCollapsed(group.key) ? '▶' : '▼' }}
              </span>
              <span class="group-title">{{ group.label }}</span>
            </div>
            <div class="group-header-right">
              <span class="group-subtitle">
                {{ group.accounts.length }} compte{{ group.accounts.length > 1 ? 's' : '' }}
                · Subtotal {{ formatMoney(group.subtotalAdj) }}
              </span>
            </div>
          </button>

          <!-- Tableau du groupe -->
          <div v-if="!isCollapsed(group.key)" class="group-table-wrapper">
            <table class="table">
              <thead>
                <tr>
                  <th>Compte</th>
                  <th>Dernière maj</th>
                  <th>À traiter</th>
                  <th>Bank balance</th>
                  <th>Adj. balance</th>
                  <th class="col-actions"></th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="acc in group.accounts"
                  :key="acc.id"
                  class="account-row"
                >
                  <td @click="openLedger(acc)">
                    <div class="cell-main">
                      <span class="cell-title">{{ acc.name }}</span>
                      <span class="cell-sub">
                        {{ acc.institution || '—' }}
                        <template v-if="acc.code">
                          · {{ acc.code }}
                        </template>
                      </span>
                    </div>
                  </td>
                  <td>{{ formatDate(acc.last_updated) }}</td>
                  <td>
                    <span
                      :class="[
                        'badge',
                        acc.to_review > 0 ? 'badge-warning' : 'badge-muted'
                      ]"
                    >
                      {{ acc.to_review > 0
                        ? acc.to_review + ' opé à traiter'
                        : 'OK'
                      }}
                    </span>
                  </td>
                  <td class="money">
                    {{ formatMoney(acc.bank_balance) }}
                  </td>
                  <td class="money">
                    {{ formatMoney(acc.adjusted_balance) }}
                  </td>
                  <td class="col-actions">
                    <button
                      class="icon-btn"
                      title="Modifier"
                      @click.stop="openEdit(acc)"
                    >
                      ✏️
                    </button>
                    <button
                      class="icon-btn"
                      :title="acc.is_archived ? 'Réactiver' : 'Archiver'"
                      @click.stop="toggleArchived(acc)"
                    >
                      {{ acc.is_archived ? '🔁' : '🗃️' }}
                    </button>
                  </td>
                </tr>

                <!-- Sous-total -->
                <tr class="subtotal-row">
                  <td colspan="3" class="subtotal-label">
                    Subtotal {{ group.label }}
                  </td>
                  <td class="money">
                    {{ formatMoney(group.subtotalBank) }}
                  </td>
                  <td class="money">
                    {{ formatMoney(group.subtotalAdj) }}
                  </td>
                  <td></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- Total global -->
        <footer class="total-footer">
          <span>Total Account Balance</span>
          <span class="money">{{ formatMoney(totalAdjBalance) }}</span>
        </footer>

        <p v-if="!groupedAccounts.length" class="empty">
          Aucun compte ne correspond à vos filtres.
        </p>
      </section>
    </div>

    <!-- Modal création / édition (celui qu'on a déjà fait) -->
    <AccountModal
      v-model="showModal"
      :mode="modalMode"
      :account="editingAccount"
      @save="handleSave"
    />
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import AccountModal from "@/components/modal/AccountModal.vue";

// --- Données de démo (banques only, comme Money) ---
const accounts = ref([
  {
    id: '1',
    name: 'Compte courant',
    category: 'checking',
    categoryLabel: 'Checking accounts',
    institution: 'Boursorama',
    currency: 'EUR',
    bank_balance: 1234.56,
    adjusted_balance: 1180.12,
    last_updated: '2025-11-29',
    to_review: 3,
    code: 'CCP-BRS',
    is_archived: false
  },
  {
    id: '2',
    name: 'Livret A',
    category: 'savings',
    categoryLabel: 'Savings accounts',
    institution: 'Crédit Agricole',
    currency: 'EUR',
    bank_balance: 8000,
    adjusted_balance: 8000,
    last_updated: '2025-11-15',
    to_review: 0,
    code: 'LIV-A',
    is_archived: false
  },
  {
    id: '3',
    name: 'Compte joint',
    category: 'checking',
    categoryLabel: 'Checking accounts',
    institution: 'Hello Bank',
    currency: 'EUR',
    bank_balance: 420.5,
    adjusted_balance: 395.2,
    last_updated: '2025-11-28',
    to_review: 1,
    code: 'CCP-JNT',
    is_archived: false
  },
  {
    id: '4',
    name: 'Carte de crédit',
    category: 'card',
    categoryLabel: 'Credit cards',
    institution: 'Fortuneo',
    currency: 'EUR',
    bank_balance: -350.0,
    adjusted_balance: -320.0,
    last_updated: '2025-11-20',
    to_review: 2,
    code: 'CB-CRD',
    is_archived: false
  },
  {
    id: '5',
    name: 'Ancien compte',
    category: 'checking',
    categoryLabel: 'Checking accounts',
    institution: 'Banque Populaire',
    currency: 'EUR',
    bank_balance: 0,
    adjusted_balance: 0,
    last_updated: '2023-01-01',
    to_review: 0,
    code: 'OLD-CC',
    is_archived: true
  }
])

// filtres
const search = ref('')
const showArchived = ref(false)

// groupes repliés
const collapsed = ref(new Set())
const isCollapsed = key => collapsed.value.has(key)
const toggleGroup = key => {
  const set = new Set(collapsed.value)
  if (set.has(key)) set.delete(key)
  else set.add(key)
  collapsed.value = set
}

// formatage
const formatMoney = v =>
  v == null
    ? '—'
    : v.toLocaleString('fr-FR', {
        style: 'currency',
        currency: 'EUR',
        maximumFractionDigits: 0
      })

const formatDate = iso => {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('fr-FR')
}

// comptes filtrés
const filteredAccounts = computed(() => {
  const q = search.value.trim().toLowerCase()
  return accounts.value.filter(acc => {
    if (!showArchived.value && acc.is_archived) return false
    const matchSearch =
      !q ||
      acc.name.toLowerCase().includes(q) ||
      (acc.institution && acc.institution.toLowerCase().includes(q)) ||
      (acc.code && acc.code.toLowerCase().includes(q))
    return matchSearch
  })
})

// groupement par catégorie façon Money
const groupedAccounts = computed(() => {
  const map = new Map()
  for (const acc of filteredAccounts.value) {
    const key = acc.category || 'other'
    const label =
      acc.categoryLabel ||
      (key === 'checking'
        ? 'Checking accounts'
        : key === 'savings'
        ? 'Savings accounts'
        : key === 'card'
        ? 'Credit cards'
        : 'Other accounts')

    if (!map.has(key)) {
      map.set(key, { key, label, accounts: [] })
    }
    map.get(key).accounts.push(acc)
  }

  const result = []
  for (const [key, group] of map.entries()) {
    const subtotalBank = group.accounts.reduce(
      (sum, a) => sum + (a.bank_balance || 0),
      0
    )
    const subtotalAdj = group.accounts.reduce(
      (sum, a) => sum + (a.adjusted_balance || 0),
      0
    )
    result.push({ ...group, subtotalBank, subtotalAdj })
  }

  // ordre : checking, savings, card, puis autres
  const order = ['checking', 'savings', 'card']
  return result.sort(
    (a, b) => (order.indexOf(a.key) + 10) - (order.indexOf(b.key) + 10)
  )
})

// totaux
const totalBankBalance = computed(() =>
  filteredAccounts.value.reduce((s, a) => s + (a.bank_balance || 0), 0)
)
const totalAdjBalance = computed(() =>
  filteredAccounts.value.reduce((s, a) => s + (a.adjusted_balance || 0), 0)
)
const totalToReview = computed(() =>
  filteredAccounts.value.reduce((s, a) => s + (a.to_review || 0), 0)
)

// actions simples
const toggleArchived = acc => {
  acc.is_archived = !acc.is_archived
}

const openLedger = acc => {
  // plus tard : router.push({ name: 'ledger', params: { id: acc.id } })
  console.log('open ledger for account', acc.id)
}

// --- Modal création / édition (réutilisation de AccountModal.vue) ---
const showModal = ref(false)
const modalMode = ref('create') // 'create' | 'edit'
const editingAccount = ref(null)

const openCreate = () => {
  modalMode.value = 'create'
  editingAccount.value = null
  showModal.value = true
}

const openEdit = acc => {
  modalMode.value = 'edit'
  // on passe une copie pour ne pas muter directement la ligne si on annule
  editingAccount.value = { ...acc }
  showModal.value = true
}

const handleSave = payload => {
  if (modalMode.value === 'create') {
    const newAcc = {
      id: String(Date.now()),
      category: 'checking',
      categoryLabel: 'Checking accounts',
      to_review: 0,
      ...payload
    }
    accounts.value = [...accounts.value, newAcc]
  } else {
    accounts.value = accounts.value.map(a =>
      a.id === payload.id ? { ...a, ...payload } : a
    )
  }
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* Header */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.page-header h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}
.subtitle {
  margin: 2px 0 0;
  font-size: 13px;
  color: #9ca3af;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.search-wrapper {
  position: relative;
}
.search-wrapper input {
  padding: 6px 10px 6px 24px;
  border-radius: 999px;
  border: 1px solid #1f2937;
  background: #020617;
  color: #e5e7eb;
  font-size: 13px;
}
.search-wrapper input:focus {
  outline: none;
  border-color: #2563eb;
}
.search-icon {
  position: absolute;
  left: 8px;
  top: 50%;
  transform: translateY(-50%);
  font-size: 11px;
}
.checkbox {
  font-size: 12px;
  color: #e5e7eb;
  display: flex;
  align-items: center;
  gap: 4px;
}

/* Résumé */
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 600px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
}
.summary-card {
  padding: 10px 12px;
  border-radius: 10px;
  background: radial-gradient(circle at top left, #111827, #020617);
  border: 1px solid #1f2937;
}
.summary-label {
  font-size: 11px;
  color: #9ca3af;
}
.summary-value {
  font-size: 16px;
  font-weight: 600;
  color: #e5e7eb;
}

/* Layout */
.layout {
  display: grid;
  gap: 14px;
}
@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
}

/* Carte comptes */
.accounts-card {
  border-radius: 14px;
  border: 1px solid #1f2937;
  background: #020617;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  padding: 6px 0 0;
  min-width: 0;
}
.group + .group {
  border-top: 1px solid #111827;
}
.group-header {
  width: 100%;
  padding: 6px 14px;
  background: linear-gradient(to right, #0b1120, #020617);
  border: none;
  border-bottom: 1px solid #111827;
  color: #e5e7eb;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.group-header-left {
  display: flex;
  align-items: center;
  gap: 6px;
}
.group-toggle {
  font-size: 11px;
}
.group-title {
  font-size: 13px;
  font-weight: 600;
}
.group-subtitle {
  font-size: 11px;
  color: #9ca3af;
}
.group-table-wrapper {
  overflow-x: auto;
}

/* Table */
.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.table thead {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: #9ca3af;
}
.table th,
.table td {
  padding: 8px 14px;
  white-space: nowrap;
}
.account-row {
  cursor: pointer;
}
.account-row:hover {
  background: rgba(15, 23, 42, 0.8);
}
.cell-main {
  display: flex;
  flex-direction: column;
}
.cell-title {
  font-weight: 500;
}
.cell-sub {
  font-size: 11px;
  color: #9ca3af;
}
.money {
  font-variant-numeric: tabular-nums;
  text-align: right;
}

/* Sous-total + total */
.subtotal-row {
  background: #020617;
  border-top: 1px solid #111827;
}
.subtotal-label {
  font-size: 12px;
  font-weight: 500;
  color: #e5e7eb;
}
.total-footer {
  margin-top: 4px;
  padding: 6px 14px;
  border-top: 1px solid #111827;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #e5e7eb;
}

/* Panneau tâches */
.tasks-panel {
  border-radius: 14px;
  border: 1px solid #1f2937;
  background: #020617;
  padding: 10px 12px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
  font-size: 12px;
}
.tasks-panel h2 {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 600;
}
.tasks-panel ul {
  margin: 0 0 10px;
  padding-left: 0;
  list-style: none;
}
.tasks-panel li + li {
  margin-top: 4px;
}
.tasks-panel button {
  background: none;
  border: none;
  padding: 0;
  color: #60a5fa;
  cursor: pointer;
  font-size: 12px;
}
.tasks-panel button:hover {
  text-decoration: underline;
}

/* Badges / boutons */
.badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
}
.badge-warning {
  background: rgba(234, 179, 8, 0.15);
  color: #facc15;
}
.badge-muted {
  background: rgba(55, 65, 81, 0.6);
  color: #e5e7eb;
}

.btn {
  border-radius: 999px;
  border: 1px solid #374151;
  background: #111827;
  color: #e5e7eb;
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.btn-primary {
  background: linear-gradient(90deg, #2563eb, #4f46e5);
  border-color: transparent;
}
.btn:hover {
  opacity: 0.92;
}
.btn-icon {
  font-size: 16px;
  line-height: 1;
}
.icon-btn {
  border: none;
  background: transparent;
  color: #9ca3af;
  cursor: pointer;
  font-size: 15px;
}
.icon-btn:hover {
  color: #e5e7eb;
}
</style>
