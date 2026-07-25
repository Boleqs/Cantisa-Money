<template>
  <div class="page">
    <!-- Header -->
    <header class="page-header">
      <div class="title-block">
        <h1>Comptes</h1>
        <p class="subtitle">
          Tous les comptes de l’utilisateur connecté, groupés par type.
        </p>
      </div>

      <div class="header-actions">
        <div class="search-wrapper">
          <span class="search-icon">🔍</span>
          <input
            v-model="search"
            class="search-input"
            type="text"
            placeholder="Rechercher un compte (nom, description, code)…"
          />
        </div>

        <label class="toggle">
          <input type="checkbox" v-model="showHidden" />
          <span>Afficher cachés</span>
        </label>

        <label class="toggle">
          <input type="checkbox" v-model="showVirtual" />
          <span>Afficher virtuels</span>
        </label>

        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>

        <button class="btn btn-primary" @click="openCreate">+ Nouveau compte</button>
      </div>
    </header>

    <!-- Errors -->
    <div v-if="error" class="alert">
      <strong>Erreur :</strong> {{ error }}
    </div>

    <!-- Skeleton / Empty -->
    <div v-if="loading && !accounts.length" class="skeleton">
      Chargement des comptes…
    </div>

    <div v-else-if="!loading && !filteredAccounts.length" class="empty">
      Aucun compte à afficher.
    </div>

    <!-- Groups -->
    <section v-else class="groups">
      <article
        v-for="group in groupedAccounts"
        :key="group.key"
        class="group"
      >
        <div class="group-header" @click="toggleGroup(group.key)">
          <div class="group-title">
            <h2>{{ group.label }}</h2>
            <span class="pill">{{ group.items.length }}</span>
          </div>
          <div class="group-header-right">
            <div v-if="group.rollup" class="group-rollup">
              <div class="rollup-label">{{ group.rollup.label }}</div>
              <div class="rollup-value" :class="group.rollup.colorClass">
                {{ fmtAmount(group.rollup.value) }} {{ group.rollup.currency }}
              </div>
            </div>
            <div v-else-if="group.items.length > 1" class="group-rollup">
              <div class="rollup-label muted-note">Devises multiples</div>
            </div>
            <button class="icon-btn" type="button" :aria-label="isCollapsed(group.key) ? 'Déplier' : 'Replier'">
              {{ isCollapsed(group.key) ? '▸' : '▾' }}
            </button>
          </div>
        </div>

        <div v-if="!isCollapsed(group.key)" class="acc-list">
          <div
            v-for="acc in group.items"
            :key="acc.id"
            class="acc-row"
            :class="{ 'is-child': acc._depth > 0 }"
          >
            <div class="acc-id">
              <div class="acc-name-row">
                <h3 class="name account-link" @click="router.push(`/accounts/${acc.id}`)">{{ acc.name }}</h3>
                <span v-if="acc.code" class="code">#{{ acc.code }}</span>
                <span class="acc-badge currency">{{ currencyShort(acc.currency_id) }}</span>
                <span v-if="acc.account_subtype" class="acc-badge">{{ acc.account_subtype }}</span>
                <span v-if="hasChildren(acc.id)" class="acc-badge soft">{{ childCount(acc.id) }} sous-compte{{ childCount(acc.id) > 1 ? 's' : '' }}</span>
                <span v-if="acc.is_hidden" class="acc-badge danger">Caché</span>
                <span v-if="acc.is_virtual" class="acc-badge warn">Virtuel</span>
              </div>
              <p v-if="acc.description" class="desc">{{ acc.description }}</p>
              <div class="acc-sub" v-if="acc._figure.kind !== 'flow'">
                <template v-if="acc._figure.positions != null">
                  <span>{{ acc._figure.positions }} position{{ acc._figure.positions > 1 ? 's' : '' }}</span>
                </template>
                <template v-else>
                  <span class="flow-pos">↑ {{ fmtAmount(acc._figure.earned) }}</span>
                  <span class="flow-neg">↓ {{ fmtAmount(acc._figure.spent) }}</span>
                </template>
              </div>
            </div>

            <div class="acc-figure">
              <div class="figure-label">{{ acc._figure.label }}</div>
              <div class="figure-value" :class="acc._figure.colorClass">
                {{ fmtAmount(acc._figure.value) }} {{ acc._figure.currency }}
              </div>
            </div>

            <div class="row-actions">
              <button class="btn-action" @click="openEdit(acc)" title="Modifier">✎</button>
              <button class="btn-action btn-danger" @click="deleteAccount(acc)" title="Supprimer">✕</button>
            </div>
          </div>
        </div>
      </article>
    </section>
  </div>

  <AccountModal
    v-model="showModal"
    :mode="modalMode"
    :account="selectedAccount"
    :commodities="commodities"
    :parent-accounts="accounts"
    @save="handleSave"
  />
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import axios from "axios";
import AccountModal from "@/components/modal/AccountModal.vue";
import { hasPermission } from "@/utils/permissions.js";

const router = useRouter();

const accounts = ref([]);
const commodities = ref([]);
const assets = ref([]);

// Modal state
const showModal = ref(false);
const modalMode = ref("create");
const selectedAccount = ref(null);

const loading = ref(false);
const error = ref("");

const search = ref("");
const showHidden = ref(false);
const showVirtual = ref(false);

// Group collapse state
const collapsed = ref(new Set());

// Order & labels for account_type
const TYPE_ORDER = ["Current", "Assets", "Equity", "Liability", "Income", "Expense"];
const TYPE_LABELS = {
  Current: "Comptes courants",
  Assets: "Actifs",
  Equity: "Equity",
  Liability: "Crédits / Dettes",
  Income: "Revenus",
  Expense: "Dépenses",
};

// Libellé du rollup de groupe : les comptes de type Assets/Equity peuvent mélanger de vrais
// soldes (ex. Livret A) et des comptes-titres valorisés par leurs positions (ex. Compte Titres,
// voir accountFigure) — "Valeur cumulée" reste correct dans les deux cas contrairement à "Solde".
const GROUP_ROLLUP_LABEL = {
  Liability: "Capital restant dû",
  Assets: "Valeur cumulée",
  Equity: "Valeur cumulée",
  Income: "Total perçu",
  Expense: "Total dépensé",
};
// Groupes dont la figure n'est pas un solde signé (gain/perte) mais un simple cumul — jamais
// coloré pos/neg, cf. accountFigure().
const NEUTRAL_ROLLUP_GROUPS = new Set(["Income", "Expense", "Assets", "Equity"]);

function normalizeText(v) {
  return (v ?? "").toString().toLowerCase().trim();
}

function fmtDate(v) {
  if (!v) return "—";
  // backend renvoie souvent un ISO ou une string parseable
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return String(v);
  return d.toLocaleString("fr-FR");
}

function fmtAmount(v) {
  if (v === null || v === undefined || v === "") return "0";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(n);
}

function commodityById(id) {
  return commodities.value.find((c) => String(c.id) === String(id));
}

const parentIds = computed(
  () => new Set(accounts.value.filter((a) => a.parent_id).map((a) => String(a.parent_id)))
);

function hasChildren(accountId) {
  return parentIds.value.has(String(accountId));
}

function childCount(accountId) {
  return accounts.value.filter((a) => String(a.parent_id) === String(accountId)).length;
}

// Un compte Assets/Equity qui détient des positions (AssetPossession) est valorisé par ces
// positions plutôt que par son solde de flux (crédité/débité n'y représente que les mouvements
// d'achat/vente, pas la valeur réelle) — même logique que AccountDetail.vue (point 8 du backlog).
const assetValueByAccount = computed(() => {
  const map = new Map();
  for (const a of assets.value) {
    for (const p of a.possessions || []) {
      const key = String(p.account_id);
      const qty = p.remaining_quantity != null ? p.remaining_quantity : p.quantity;
      const entry = map.get(key) || { value: 0, currency: a.display_currency, positionsCount: 0 };
      entry.value += qty * (a.converted_value_per_unit || 0);
      entry.positionsCount += 1;
      map.set(key, entry);
    }
  }
  return map;
});

// Calcule la figure clé à afficher pour un compte : valeur des actifs détenus si applicable,
// sinon solde (consolidé si le compte a des sous-comptes), avec un traitement dédié pour les
// comptes de type Liability (capital restant dû, toujours affiché en positif/rouge).
function accountFigure(acc) {
  const assetInfo = assetValueByAccount.value.get(String(acc.id));
  if (assetInfo && assetInfo.positionsCount > 0) {
    return {
      kind: "assets",
      label: "Valeur des actifs",
      value: assetInfo.value,
      currency: assetInfo.currency,
      colorClass: "neutral",
      positions: assetInfo.positionsCount,
    };
  }

  const hc = hasChildren(acc.id);
  const earned = Number(hc ? acc.consolidated_earned : acc.total_earned) || 0;
  const spent = Number(hc ? acc.consolidated_spent : acc.total_spent) || 0;
  const solde = earned - spent;
  const currency = currencyShort(acc.currency_id);

  if (acc.account_type === "Liability") {
    return {
      kind: "liability",
      label: "Capital restant dû",
      value: Math.abs(solde),
      currency,
      colorClass: "neg",
      earned,
      spent,
    };
  }

  // Income/Expense ne portent pas un "solde" au sens classique : par construction du trigger SQL
  // (total_earned = somme des splits positifs, total_spent = somme des splits négatifs), un compte
  // Income est toujours crédité en négatif (le cumul réel est dans total_spent) et un compte Expense
  // toujours débité en positif (cumul réel dans total_earned) — soustraire les deux donnerait un
  // nombre au signe trompeur (ex. "Solde -9 600" sur un compte de salaires). On affiche donc le
  // cumul réel, en neutre, jamais coloré pos/neg puisque ce n'est pas un gain ou une perte.
  if (acc.account_type === "Income") {
    return {
      kind: "flow",
      label: hc ? "Total perçu (consolidé)" : "Total perçu",
      value: spent,
      currency,
      colorClass: "neutral",
      earned,
      spent,
    };
  }

  if (acc.account_type === "Expense") {
    return {
      kind: "flow",
      label: hc ? "Total dépensé (consolidé)" : "Total dépensé",
      value: earned,
      currency,
      colorClass: "neutral",
      earned,
      spent,
    };
  }

  return {
    kind: "solde",
    label: hc ? "Solde consolidé" : "Solde",
    value: solde,
    currency,
    colorClass: solde >= 0 ? "pos" : "neg",
    earned,
    spent,
  };
}

// Somme des figures des comptes racines d'un groupe (jamais leurs enfants, déjà inclus dans le
// solde consolidé du parent — sinon double-comptage). Retourne null si les comptes racines du
// groupe ne sont pas tous dans la même devise : mieux vaut ne rien afficher qu'additionner à tort
// des montants dans des devises différentes.
function groupRollup(key, items) {
  const roots = items.filter((a) => a._depth === 0);
  if (!roots.length) return null;
  const currencies = new Set(roots.map((a) => a._figure.currency));
  if (currencies.size > 1) return null;
  const value = roots.reduce((s, a) => s + a._figure.value, 0);
  const label = GROUP_ROLLUP_LABEL[key] || "Solde cumulé";
  const colorClass = key === "Liability" ? "neg" : NEUTRAL_ROLLUP_GROUPS.has(key) ? "neutral" : value >= 0 ? "pos" : "neg";
  return { label, value, currency: roots[0]._figure.currency, colorClass };
}

function currencyShort(currencyId) {
  const c = commodityById(currencyId);
  return c?.short_name?.toUpperCase?.() || "—";
}

function isCollapsed(key) {
  return collapsed.value.has(key);
}

function toggleGroup(key) {
  const next = new Set(collapsed.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  collapsed.value = next;
}

async function fetchCommodities() {
  // GET /api/commodities -> { response_data: [...] }
  const { data } = await axios.get("/api/commodities");
  commodities.value = Array.isArray(data?.response_data) ? data.response_data : [];
}

async function fetchAccounts() {
  // GET /api/accounts -> { response_data: [...] }
  const { data } = await axios.get("/api/accounts");
  accounts.value = Array.isArray(data?.response_data) ? data.response_data : [];
}

async function fetchAssets() {
  // Valeur des positions par compte (voir accountFigure) — seulement si la permission est
  // accordée, pour ne pas déclencher un 403 inutile pour les utilisateurs sans accès Patrimoine.
  if (!hasPermission("Patrimoine")) {
    assets.value = [];
    return;
  }
  const { data } = await axios.get("/api/assets");
  assets.value = Array.isArray(data?.response_data) ? data.response_data : [];
}

async function reload() {
  loading.value = true;
  error.value = "";
  try {
    // commodities avant accounts pour afficher les devises correctement
    await fetchCommodities();
    await Promise.all([fetchAccounts(), fetchAssets()]);
  } catch (e) {
    // erreurs typiques : 401 si auth invalide, ou backend down
    const msg =
      e?.response?.data?.response_data ||
      e?.response?.statusText ||
      e?.message ||
      "Erreur inconnue";
    error.value = msg;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  selectedAccount.value = null;
  modalMode.value = "create";
  showModal.value = true;
}

function openEdit(acc) {
  selectedAccount.value = { ...acc };
  modalMode.value = "edit";
  showModal.value = true;
}

async function handleSave(form) {
  try {
    if (modalMode.value === "create") {
      await axios.post("/api/accounts", {
        name: form.name,
        description: form.description,
        currency_id: form.currency_id,
        parent_id: form.parent_id || undefined,
        account_type: form.account_type || 'Current',
        account_subtype: form.account_subtype || undefined,
        is_virtual: form.is_virtual,
        is_hidden: form.is_hidden,
        code: form.code || undefined,
        tax_treatment: form.tax_treatment || null,
      });
    } else {
      await axios.patch("/api/accounts", {
        account_id: form.id,
        name: form.name,
        description: form.description,
        currency_id: form.currency_id,
        parent_id: form.parent_id || undefined,
        account_type: form.account_type || 'Current',
        account_subtype: form.account_subtype || undefined,
        is_virtual: form.is_virtual,
        is_hidden: form.is_hidden,
        code: form.code || undefined,
        tax_treatment: form.tax_treatment || null,
      });
    }
    await reload();
  } catch (e) {
    error.value =
      e?.response?.data?.response_data || e?.message || "Erreur inconnue";
  }
}

async function deleteAccount(acc) {
  if (!confirm(`Supprimer le compte « ${acc.name} » ?`)) return;
  try {
    await axios.delete("/api/accounts", { params: { account_id: acc.id } });
    await reload();
  } catch (e) {
    error.value =
      e?.response?.data?.response_data || e?.message || "Erreur inconnue";
  }
}

onMounted(() => {
  reload();
});

// Filtering (search + flags)
const filteredAccounts = computed(() => {
  const q = normalizeText(search.value);

  return accounts.value
    .filter((a) => (showHidden.value ? true : !a.is_hidden))
    .filter((a) => (showVirtual.value ? true : !a.is_virtual))
    .filter((a) => {
      if (!q) return true;
      const blob = [
        a.name,
        a.description,
        a.code,
        a.account_type,
        a.account_subtype,
      ]
        .map(normalizeText)
        .join(" ");
      return blob.includes(q);
    });
});

// Construit un tableau ordonné en profondeur (DFS) avec la propriété _depth
function buildTreeFlat(items) {
  const itemIds = new Set(items.map((a) => String(a.id)));
  const byParent = new Map();
  byParent.set(null, []);

  for (const item of items) {
    // Si le parent existe dans le groupe, on l'utilise ; sinon on traite comme racine
    const pid =
      item.parent_id && itemIds.has(String(item.parent_id))
        ? String(item.parent_id)
        : null;
    if (!byParent.has(pid)) byParent.set(pid, []);
    byParent.get(pid).push(item);
  }

  const result = [];
  function traverse(parentId, depth) {
    const children = [...(byParent.get(parentId) || [])].sort((a, b) =>
      normalizeText(a.name).localeCompare(normalizeText(b.name), "fr")
    );
    for (const child of children) {
      result.push({ ...child, _depth: depth, _figure: accountFigure(child) });
      traverse(String(child.id), depth + 1);
    }
  }
  traverse(null, 0);
  return result;
}

// Grouping by account_type + ordering
const groupedAccounts = computed(() => {
  // Regrouper par type
  const map = new Map();
  for (const acc of filteredAccounts.value) {
    const t = acc.account_type || "Other";
    if (!map.has(t)) map.set(t, []);
    map.get(t).push(acc);
  }

  const keys = Array.from(map.keys());

  // Ordonner les groupes selon TYPE_ORDER, puis alphanumérique
  keys.sort((a, b) => {
    const ia = TYPE_ORDER.indexOf(a);
    const ib = TYPE_ORDER.indexOf(b);
    if (ia !== -1 || ib !== -1) {
      if (ia === -1) return 1;
      if (ib === -1) return -1;
      return ia - ib;
    }
    return a.localeCompare(b, "fr");
  });

  return keys.map((key) => {
    // Chaque groupe est ordonné en arborescence parent → enfants
    const items = buildTreeFlat(map.get(key));
    return {
      key,
      label: TYPE_LABELS[key] || key,
      items,
      rollup: groupRollup(key, items),
    };
  });
});
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
}

.title-block h1 {
  margin: 0;
  font-size: 28px;
  letter-spacing: 0.2px;
}

.subtitle {
  margin: 6px 0 0;
  color: #9ca3af;
  font-size: 14px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.search-wrapper {
  position: relative;
}

.search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0.7;
}

.search-input {
  padding: 10px 10px 10px 32px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  outline: none;
  width: 320px;
  max-width: 70vw;
}

.toggle {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  font-size: 13px;
  color: #cbd5e1;
  user-select: none;
}
.toggle input {
  accent-color: #60a5fa;
}

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.alert {
  border: 1px solid rgba(239, 68, 68, 0.5);
  background: rgba(239, 68, 68, 0.08);
  padding: 12px 14px;
  border-radius: 12px;
  margin-bottom: 16px;
  color: #fecaca;
}

.skeleton,
.empty {
  padding: 18px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 14px;
  color: #cbd5e1;
}

.groups {
  display: grid;
  gap: 14px;
}

.group {
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 16px;
  overflow: hidden;
}

.group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  cursor: pointer;
  border-bottom: 1px solid rgba(148, 163, 184, 0.12);
}

.group-title {
  display: flex;
  align-items: center;
  gap: 10px;
}
.group-title h2 {
  margin: 0;
  font-size: 16px;
}

.group-header-right {
  display: flex;
  align-items: center;
  gap: 18px;
}

.group-rollup {
  text-align: right;
}
.rollup-label {
  font-size: 10.5px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.rollup-label.muted-note {
  text-transform: none;
  letter-spacing: normal;
  font-size: 12px;
}
.rollup-value {
  font-size: 15px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  margin-top: 2px;
}
.rollup-value.pos { color: #4ade80; }
.rollup-value.neg { color: #f87171; }
.rollup-value.neutral { color: #e5e7eb; }

.pill {
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 999px;
  background: rgba(96, 165, 250, 0.15);
  border: 1px solid rgba(96, 165, 250, 0.25);
  color: #bfdbfe;
}

.icon-btn {
  border: none;
  background: transparent;
  color: #e5e7eb;
  cursor: pointer;
  font-size: 16px;
  opacity: 0.85;
}

.acc-list {
  display: flex;
  flex-direction: column;
}

.acc-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 13px 16px;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  transition: background 0.12s;
}
.acc-row:hover {
  background: rgba(148, 163, 184, 0.04);
}
.acc-row.is-child {
  padding-left: 40px;
  position: relative;
}
.acc-row.is-child::before {
  content: "└";
  position: absolute;
  left: 18px;
  color: rgba(148, 163, 184, 0.35);
  font-size: 13px;
}

.acc-id {
  flex: 1;
  min-width: 0;
}

.acc-name-row {
  display: flex;
  gap: 8px;
  align-items: baseline;
  flex-wrap: wrap;
}
.name {
  margin: 0;
  font-size: 15px;
}

.account-link {
  cursor: pointer;
  transition: color 0.15s;
}
.account-link:hover {
  color: #93c5fd;
  text-decoration: underline;
}
.code {
  color: #93c5fd;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(96, 165, 250, 0.25);
  background: rgba(96, 165, 250, 0.10);
}

.desc {
  margin: 4px 0 0;
  color: #9ca3af;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60ch;
}

.acc-badge {
  font-size: 10.5px;
  padding: 2px 7px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(148, 163, 184, 0.08);
  color: #cbd5e1;
  font-weight: 600;
}
.acc-badge.currency {
  color: #93c5fd;
  border-color: rgba(96, 165, 250, 0.25);
  background: rgba(96, 165, 250, 0.08);
}
.acc-badge.soft {
  background: transparent;
  color: #9ca3af;
}
.acc-badge.danger {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.10);
  color: #fecaca;
}
.acc-badge.warn {
  border-color: rgba(245, 158, 11, 0.35);
  background: rgba(245, 158, 11, 0.10);
  color: #fde68a;
}

.acc-sub {
  margin-top: 4px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #64748b;
}
.acc-sub .flow-pos { color: rgba(74, 222, 128, 0.75); }
.acc-sub .flow-neg { color: rgba(248, 113, 113, 0.75); }

.acc-figure {
  text-align: right;
  flex-shrink: 0;
  min-width: 150px;
}
.figure-label {
  font-size: 10.5px;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.figure-value {
  font-size: 16px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  margin-top: 2px;
}
.figure-value.pos { color: #4ade80; }
.figure-value.neg { color: #f87171; }
.figure-value.neutral { color: #e5e7eb; }

.row-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.btn-action {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
  padding: 5px 10px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
}

.btn-action:hover {
  background: rgba(148, 163, 184, 0.1);
}

.btn-danger {
  border-color: rgba(239, 68, 68, 0.4);
  color: #fca5a5;
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.1);
}

.btn-primary {
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
  border-color: transparent;
  color: #fff;
}
</style>
