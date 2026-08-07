<template>
  <div class="page">
    <!-- Header -->
    <header class="page-header">
      <div class="title-block">
        <h1>Comptes</h1>
        <p class="subtitle">
          Tous les comptes de l’utilisateur connecté, groupés {{ groupByLabel }}.
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

        <label class="toggle group-by-toggle">
          <span>Organiser par</span>
          <select v-model="groupBy" class="group-by-select">
            <option value="type">Type</option>
            <option value="parent">Compte parent</option>
            <option value="institution">Institution</option>
          </select>
        </label>

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
            <span v-if="group.typeLabel" class="acc-badge soft">{{ group.typeLabel }}</span>
            <span class="pill">{{ group.items.length }}</span>
          </div>
          <div class="group-header-right">
            <div v-if="group.rollup" class="group-rollup">
              <div class="rollup-label">{{ group.rollup.label }}</div>
              <div class="rollup-value" :class="group.rollup.colorClass">
                {{ fmtAmount(group.rollup.value) }} {{ group.rollup.currency }}
              </div>
            </div>
            <div v-else-if="groupBy !== 'institution' && group.items.length > 1" class="group-rollup">
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
                <button
                  v-if="hasChildren(acc.id)"
                  class="icon-btn tree-toggle"
                  type="button"
                  :aria-label="isParentCollapsed(acc.id) ? 'Déplier les sous-comptes' : 'Replier les sous-comptes'"
                  @click="toggleParent(acc.id)"
                >{{ isParentCollapsed(acc.id) ? '▸' : '▾' }}</button>
                <h3 class="name account-link" @click="router.push(`/accounts/${acc.id}`)">{{ accountDisplayLabel(acc, accounts) }}</h3>
                <span v-if="acc.code" class="code">#{{ acc.code }}</span>
                <span class="acc-badge currency">{{ currencyShort(acc.currency_id) }}</span>
                <span v-if="acc.account_subtype" class="acc-badge">{{ acc.account_subtype }}</span>
                <span v-if="hasChildren(acc.id)" class="acc-badge soft">{{ childCount(acc.id) }} sous-compte{{ childCount(acc.id) > 1 ? 's' : '' }}</span>
                <span v-if="acc.is_hidden" class="acc-badge danger">Caché</span>
                <span v-if="acc.is_closed" class="acc-badge danger">Clôturé</span>
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
              <button class="btn-action" @click="startOpeningBalance(acc)" title="Solde initial">⚖</button>
              <button v-if="acc.is_closed" class="btn-action" @click="reopenAccount(acc)" title="Réouvrir">🔓</button>
              <button v-else class="btn-action" @click="startClosing(acc)" title="Clôturer">🔒</button>
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
    :institutions="institutions"
    :type-options="TYPE_OPTIONS"
    @save="handleSave"
    @institution-created="institutions.push($event)"
  />

  <!-- Clôture d'un compte non soldé : demande un compte de contrepartie pour la transaction
       d'équilibrage finale (le backend renvoie needs_balancing + le solde si aucun n'est fourni). -->
  <div v-if="closingAccount" class="modal-backdrop" @click.self="cancelClosing">
    <div class="close-modal">
      <h3>Clôturer « {{ closingAccount.name }} »</h3>
      <p class="hint">
        Ce compte n'est pas soldé (solde : {{ fmtAmount(closingAccount.balance) }} {{ currencyShort(closingAccount.currencyId) }}).
        Choisissez un compte de contrepartie pour la transaction d'équilibrage finale qui le ramènera à zéro.
      </p>
      <select v-model="closingTargetId" class="group-by-select close-select">
        <option value="">Compte de contrepartie…</option>
        <option v-for="a in balancingCandidates" :key="a.id" :value="a.id">{{ accountDisplayLabel(a, accounts) }}</option>
      </select>
      <p v-if="closingError" class="alert">{{ closingError }}</p>
      <div class="close-modal-actions">
        <button class="btn btn-sm" :disabled="closingBusy" @click="cancelClosing">Annuler</button>
        <button class="btn btn-primary" :disabled="!closingTargetId || closingBusy" @click="confirmBalancingClose">
          {{ closingBusy ? "…" : "Créer la transaction et clôturer" }}
        </button>
      </div>
    </div>
  </div>

  <!-- Solde initial : pour un compte dont l'historique de transactions a été perdu lors de son
       intégration à l'app — crée/met à jour une transaction d'équilibrage contre un compte
       Equity "Solde d'ouverture" partagé par devise (voir backend/routes/rt_accounts.py). -->
  <div v-if="openingBalanceAccount" class="modal-backdrop" @click.self="cancelOpeningBalance">
    <div class="close-modal">
      <h3>Solde initial — « {{ openingBalanceAccount.name }} »</h3>
      <p class="hint">
        À renseigner si l'historique des transactions de ce compte a été perdu lors de son
        intégration à l'app : un montant et une date de reprise suffisent, une transaction
        d'équilibrage est créée automatiquement contre un compte de contrepartie dédié.
      </p>
      <input
        v-model="openingBalanceAmount"
        type="number"
        step="0.01"
        class="group-by-select close-select"
        placeholder="Montant (positif ou négatif)"
      />
      <input
        v-model="openingBalanceDate"
        type="date"
        class="group-by-select close-select"
      />
      <p v-if="openingBalanceError" class="alert">{{ openingBalanceError }}</p>
      <div class="close-modal-actions">
        <button
          v-if="openingBalanceAccount.opening_balance_transaction_id"
          class="btn btn-sm btn-danger"
          :disabled="openingBalanceBusy"
          @click="removeOpeningBalance"
        >Supprimer</button>
        <button class="btn btn-sm" :disabled="openingBalanceBusy" @click="cancelOpeningBalance">Annuler</button>
        <button
          class="btn btn-primary"
          :disabled="!openingBalanceAmount || openingBalanceBusy"
          @click="confirmOpeningBalance"
        >{{ openingBalanceBusy ? "…" : "Enregistrer" }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import axios from "axios";
import AccountModal from "@/components/modal/AccountModal.vue";
import { hasPermission } from "@/utils/permissions.js";
import { currency as defaultCurrency } from "@/utils/settings.js";
import { confirmDialog } from "@/utils/confirmDialog";
import { useToast } from "@/utils/toast";
import { normalizeSearch } from "@/utils/search.js";
import { formatDate } from "@/utils/dateFormat.js";
import { accountDisplayLabel } from "@/utils/accountDisplay.js";
import { institutions, ensureInstitutionsLoaded } from "@/utils/institutions.js";

const toast = useToast();

const router = useRouter();

// Income/Expense ont leur propre page dédiée (voir IncomeExpenseAccounts.vue) — pas de sens de
// pouvoir les créer/modifier depuis la liste des comptes réels.
const TYPE_OPTIONS = [
  { value: "Current", label: "Current" },
  { value: "Assets", label: "Assets" },
  { value: "Equity", label: "Equity" },
];

const accounts = ref([]);
const commodities = ref([]);
const assets = ref([]);
// Valeur autoritaire (positions + cash libre) des comptes-conteneurs de portefeuille, calculée
// côté backend — voir fetchAccountValues() et assetValueByAccount plus bas.
const accountValues = ref(new Map());

// Modal state
const showModal = ref(false);
const modalMode = ref("create");
const selectedAccount = ref(null);

const loading = ref(false);
const error = ref("");

const search = ref("");
const showHidden = ref(false);
// Les comptes virtuels (ex. enveloppes budgétaires) sont utiles au quotidien, contrairement aux
// comptes cachés (archivés) — affichés par défaut, à la différence de showHidden.
const showVirtual = ref(true);
const groupBy = ref("type");

// Group collapse state (au niveau du groupe : type ou compte racine selon groupBy)
const collapsed = ref(new Set());
// Repli/dépli d'un compte parent précis, indépendant du groupe qui le contient
const collapsedParents = ref(new Set());

// Order & labels for account_type (Income/Expense/Liability exclus : voir
// IncomeExpenseAccounts.vue et Credits.vue)
const TYPE_ORDER = ["Current", "Assets", "Equity"];
const TYPE_LABELS = {
  Current: "Comptes courants",
  Assets: "Actifs",
  Equity: "Equity",
};

// Libellé du rollup de groupe : les comptes de type Assets/Equity peuvent mélanger de vrais
// soldes (ex. Livret A) et des comptes-titres valorisés par leurs positions (ex. Compte Titres,
// voir accountFigure) — "Valeur cumulée" reste correct dans les deux cas contrairement à "Solde".
const GROUP_ROLLUP_LABEL = {
  Assets: "Valeur cumulée",
  Equity: "Valeur cumulée",
};
// Groupes dont la figure n'est pas un solde signé (gain/perte) mais un simple cumul — jamais
// coloré pos/neg, cf. accountFigure().
const NEUTRAL_ROLLUP_GROUPS = new Set(["Assets", "Equity"]);

const normalizeText = normalizeSearch;

function fmtDate(v) {
  return formatDate(v, { withTime: true });
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

function institutionById(id) {
  if (!id) return null;
  return institutions.value.find((i) => String(i.id) === String(id)) || null;
}

const GROUP_BY_LABELS = { parent: "par compte parent", institution: "par institution", type: "par type" };
const groupByLabel = computed(() => GROUP_BY_LABELS[groupBy.value] || "par type");

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
// d'achat/vente, pas la valeur réelle) — même logique que AccountDetail.vue. La valeur position-
// seule calculée ci-dessous ne sert plus que de repli tant que fetchAccountValues() n'a pas
// répondu : la valeur autoritaire (positions + cash libre éventuellement laissé sur le compte)
// vient du backend (GET /api/wealth/account-values, voir accountValues).
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
  for (const [key, entry] of map) {
    const backendValue = accountValues.value.get(key);
    if (backendValue != null) entry.value = backendValue;
  }
  return map;
});

// Calcule la figure clé à afficher pour un compte : valeur des actifs détenus si applicable,
// sinon solde (consolidé si le compte a des sous-comptes).
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
// `labelKey` sert à choisir le libellé/la couleur (le type de compte : "Liability", "Income"...) ;
// en mode "par compte parent" ce n'est pas le même que l'identifiant unique du groupe (l'id du
// compte racine), d'où la séparation des deux paramètres.
function groupRollup(labelKey, items) {
  const roots = items.filter((a) => a._depth === 0);
  if (!roots.length) return null;
  const currencies = new Set(roots.map((a) => a._figure.currency));
  if (currencies.size > 1) return null;
  const value = roots.reduce((s, a) => s + a._figure.value, 0);
  const label = GROUP_ROLLUP_LABEL[labelKey] || "Solde cumulé";
  const colorClass = NEUTRAL_ROLLUP_GROUPS.has(labelKey) ? "neutral" : value >= 0 ? "pos" : "neg";
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

function isParentCollapsed(accountId) {
  return collapsedParents.value.has(String(accountId));
}

function toggleParent(accountId) {
  const next = new Set(collapsedParents.value);
  const key = String(accountId);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  collapsedParents.value = next;
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

async function fetchInstitutions() {
  await ensureInstitutionsLoaded();
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

async function fetchAccountValues() {
  // Valeur position + cash libre par compte-conteneur (voir assetValueByAccount) — même garde de
  // permission que fetchAssets(), l'endpoint est sous la même permission Patrimoine.
  if (!hasPermission("Patrimoine")) {
    accountValues.value = new Map();
    return;
  }
  const { data } = await axios.get("/api/wealth/account-values", {
    params: { currency: defaultCurrency.value },
  });
  const values = data?.response_data?.values || {};
  accountValues.value = new Map(Object.entries(values));
}

async function reload() {
  loading.value = true;
  error.value = "";
  try {
    // commodities avant accounts pour afficher les devises correctement
    await fetchCommodities();
    await Promise.all([fetchAccounts(), fetchAssets(), fetchInstitutions(), fetchAccountValues()]);
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
        institution_id: form.institution_id || null,
        account_type: form.account_type || 'Current',
        account_subtype: form.account_subtype || undefined,
        is_virtual: form.is_virtual,
        is_hidden: form.is_hidden,
        code: form.code || undefined,
        tax_treatment: form.tax_treatment || null,
        opening_balance: form.opening_balance ? Number(form.opening_balance) : undefined,
        opening_balance_date: form.opening_balance_date || undefined,
      });
    } else {
      await axios.patch("/api/accounts", {
        account_id: form.id,
        name: form.name,
        description: form.description,
        currency_id: form.currency_id,
        parent_id: form.parent_id || undefined,
        institution_id: form.institution_id || null,
        account_type: form.account_type || 'Current',
        account_subtype: form.account_subtype || undefined,
        is_virtual: form.is_virtual,
        is_hidden: form.is_hidden,
        code: form.code || undefined,
        tax_treatment: form.tax_treatment || null,
      });
    }
    await reload();
    toast.success(modalMode.value === "create" ? `Compte « ${form.name} » créé.` : `Compte « ${form.name} » mis à jour.`);
  } catch (e) {
    error.value =
      e?.response?.data?.response_data || e?.message || "Erreur inconnue";
  }
}

async function deleteAccount(acc) {
  const ok = await confirmDialog({
    title: "Supprimer le compte",
    message: `Supprimer le compte « ${acc.name} » ?`,
    confirmLabel: "Supprimer",
    danger: true,
  });
  if (!ok) return;
  try {
    await axios.delete("/api/accounts", { params: { account_id: acc.id } });
    await reload();
    toast.success(`Compte « ${acc.name} » supprimé.`);
  } catch (e) {
    error.value =
      e?.response?.data?.response_data || e?.message || "Erreur inconnue";
  }
}

// ── clôture de compte ─────────────────────────────────────────────────────────
// closingAccount porte soit le compte brut (avant tentative), soit { ...acc, balance,
// currencyId } une fois que le backend a répondu needs_balancing avec le solde à résorber.
const closingAccount = ref(null);
const closingTargetId = ref("");
const closingBusy = ref(false);
const closingError = ref("");

const balancingCandidates = computed(() =>
  accounts.value.filter((a) => a.id !== closingAccount.value?.id && !a.is_closed)
);

async function startClosing(acc) {
  closingError.value = "";
  closingTargetId.value = "";
  closingBusy.value = true;
  try {
    await axios.post("/api/accounts/close", { account_id: acc.id });
    closingBusy.value = false;
    await reload();
    toast.success(`Compte « ${acc.name} » clôturé.`);
  } catch (e) {
    closingBusy.value = false;
    const rd = e?.response?.data?.response_data;
    if (e?.response?.status === 409 && rd?.needs_balancing) {
      closingAccount.value = { ...acc, balance: rd.balance, currencyId: rd.currency_id };
    } else {
      error.value = rd || e?.message || "Erreur lors de la clôture";
    }
  }
}

function cancelClosing() {
  closingAccount.value = null;
  closingTargetId.value = "";
  closingError.value = "";
}

async function confirmBalancingClose() {
  if (!closingTargetId.value || !closingAccount.value) return;
  closingBusy.value = true;
  closingError.value = "";
  try {
    await axios.post("/api/accounts/close", {
      account_id: closingAccount.value.id,
      balancing_account_id: closingTargetId.value,
    });
    const closedName = closingAccount.value.name;
    closingAccount.value = null;
    closingTargetId.value = "";
    await reload();
    toast.success(`Compte « ${closedName} » clôturé après équilibrage.`);
  } catch (e) {
    closingError.value =
      e?.response?.data?.response_data || e?.message || "Erreur lors de la clôture";
  } finally {
    closingBusy.value = false;
  }
}

async function reopenAccount(acc) {
  const ok = await confirmDialog({
    title: "Réouvrir le compte",
    message: `Réouvrir le compte « ${acc.name} » ?`,
    confirmLabel: "Réouvrir",
  });
  if (!ok) return;
  try {
    await axios.patch("/api/accounts", {
      account_id: acc.id,
      name: acc.name,
      description: acc.description,
      currency_id: acc.currency_id,
      parent_id: acc.parent_id || undefined,
      institution_id: acc.institution_id || null,
      account_type: acc.account_type,
      account_subtype: acc.account_subtype || undefined,
      is_virtual: acc.is_virtual,
      is_hidden: false,
      is_closed: false,
      code: acc.code || undefined,
      tax_treatment: acc.tax_treatment || null,
    });
    await reload();
    toast.success(`Compte « ${acc.name} » réouvert.`);
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || "Erreur inconnue";
  }
}

// ── solde initial ─────────────────────────────────────────────────────────────
// Cas d'un compte dont l'historique de transactions a été perdu lors de son intégration à
// l'app : un montant + une date de reprise génèrent une transaction d'équilibrage contre un
// compte Equity "Solde d'ouverture" partagé par devise (voir rt_accounts.py).
const openingBalanceAccount = ref(null);
const openingBalanceAmount = ref("");
const openingBalanceDate = ref("");
const openingBalanceBusy = ref(false);
const openingBalanceError = ref("");

async function startOpeningBalance(acc) {
  openingBalanceError.value = "";
  openingBalanceAmount.value = "";
  openingBalanceDate.value = "";
  openingBalanceAccount.value = acc;
  if (acc.opening_balance_transaction_id) {
    try {
      const { data } = await axios.get("/api/transactions", {
        params: { transaction_id: acc.opening_balance_transaction_id },
      });
      const tx = data?.response_data;
      const split = tx?.splits?.find((s) => String(s.account_id) === String(acc.id));
      if (split) openingBalanceAmount.value = String(split.quantity);
      if (tx?.post_date) openingBalanceDate.value = String(tx.post_date).slice(0, 10);
    } catch (e) {
      // Pré-remplissage best-effort : en cas d'échec, les champs restent vides et l'utilisateur
      // ressaisit le montant/la date (l'enregistrement écrasera la transaction existante).
    }
  }
}

function cancelOpeningBalance() {
  openingBalanceAccount.value = null;
  openingBalanceError.value = "";
}

async function confirmOpeningBalance() {
  if (!openingBalanceAmount.value || !openingBalanceAccount.value) return;
  openingBalanceBusy.value = true;
  openingBalanceError.value = "";
  try {
    await axios.post("/api/accounts/opening-balance", {
      account_id: openingBalanceAccount.value.id,
      amount: Number(openingBalanceAmount.value),
      as_of_date: openingBalanceDate.value || undefined,
    });
    const name = openingBalanceAccount.value.name;
    openingBalanceAccount.value = null;
    await reload();
    toast.success(`Solde initial enregistré pour « ${name} ».`);
  } catch (e) {
    openingBalanceError.value =
      e?.response?.data?.response_data || e?.message || "Erreur lors de l'enregistrement";
  } finally {
    openingBalanceBusy.value = false;
  }
}

async function removeOpeningBalance() {
  if (!openingBalanceAccount.value) return;
  openingBalanceBusy.value = true;
  openingBalanceError.value = "";
  try {
    await axios.delete("/api/accounts/opening-balance", {
      params: { account_id: openingBalanceAccount.value.id },
    });
    const name = openingBalanceAccount.value.name;
    openingBalanceAccount.value = null;
    await reload();
    toast.success(`Solde initial supprimé pour « ${name} ».`);
  } catch (e) {
    openingBalanceError.value =
      e?.response?.data?.response_data || e?.message || "Erreur lors de la suppression";
  } finally {
    openingBalanceBusy.value = false;
  }
}

onMounted(() => {
  reload();
});

// Filtering (search + flags)
const filteredAccounts = computed(() => {
  const q = normalizeText(search.value);

  return accounts.value
    // Les comptes Income/Expense ne représentent pas de l'argent réel de l'utilisateur (ce sont
    // les contreparties de catégorisation du double-entry) — affichés sur leur propre page, voir
    // IncomeExpenseAccounts.vue. Les comptes Liability, ainsi que les comptes Equity de
    // contrepartie d'ouverture de crédit (subtype 'loan') ou de solde initial de reprise (subtype
    // 'opening_balance'), sont auto-générés/gérés exclusivement par leur flux dédié (Crédits, ou
    // le bouton "Solde initial" ci-dessous) — les manipuler ici court-circuiterait ce flux.
    .filter((a) => a.account_type !== "Income" && a.account_type !== "Expense" && a.account_type !== "Liability")
    .filter((a) => !(a.account_type === "Equity" && ["loan", "opening_balance"].includes(a.account_subtype)))
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
      // Un parent replié (collapsedParents) reste affiché lui-même, seuls ses
      // descendants sont masqués — on n'explore donc pas ses enfants dans ce cas.
      if (!collapsedParents.value.has(String(child.id))) {
        traverse(String(child.id), depth + 1);
      }
    }
  }
  traverse(null, 0);
  return result;
}

// Regroupe un ensemble déjà mis en arborescence (buildTreeFlat) en un groupe par compte racine
// (parent_id vide, ou parent hors de l'ensemble filtré) : chaque racine et tous ses descendants
// visibles forment un groupe, quel que soit leur account_type.
function splitByRootAccount(items) {
  const flat = buildTreeFlat(items);
  const groups = [];
  let current = null;
  for (const acc of flat) {
    if (acc._depth === 0) {
      current = { key: String(acc.id), label: acc.name, labelKey: acc.account_type, items: [] };
      groups.push(current);
    }
    current.items.push(acc);
  }
  return groups;
}

// Grouping selon groupBy : par type de compte (défaut), par compte parent racine ou par
// institution bancaire (bucket "Sans institution" pour les comptes non rattachés).
const groupedAccounts = computed(() => {
  if (groupBy.value === "parent") {
    return splitByRootAccount(filteredAccounts.value)
      .sort((a, b) => normalizeText(a.label).localeCompare(normalizeText(b.label), "fr"))
      .map((g) => ({
        key: g.key,
        label: g.label,
        typeLabel: TYPE_LABELS[g.labelKey] || g.labelKey,
        items: g.items,
        rollup: groupRollup(g.labelKey, g.items),
      }));
  }

  if (groupBy.value === "institution") {
    const map = new Map();
    for (const acc of filteredAccounts.value) {
      const key = acc.institution_id ? String(acc.institution_id) : "__none__";
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(acc);
    }
    const keys = Array.from(map.keys()).sort((a, b) => {
      if (a === "__none__") return 1;
      if (b === "__none__") return -1;
      const la = institutionById(a)?.name || "";
      const lb = institutionById(b)?.name || "";
      return normalizeText(la).localeCompare(normalizeText(lb), "fr");
    });
    return keys.map((key) => {
      const items = buildTreeFlat(map.get(key));
      return {
        key,
        label: key === "__none__" ? "Sans institution" : institutionById(key)?.name || "—",
        items,
        rollup: null,
      };
    });
  }

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
  flex-wrap: wrap;
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

.group-by-toggle {
  gap: 8px;
}

.group-by-select {
  padding: 6px 8px;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  font-size: 13px;
  outline: none;
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

.close-modal {
  width: 440px;
  max-width: 92vw;
  background: #020617;
  border-radius: 16px;
  border: 1px solid #1f2937;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
  padding: 20px;
}

.close-modal h3 {
  margin: 0 0 10px;
}

.close-modal .hint {
  color: #94a3b8;
  font-size: 13px;
  margin-bottom: 14px;
}

.close-select {
  width: 100%;
  margin-bottom: 10px;
}

.close-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
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
.rollup-value.pos { color: var(--color-success-text); }
.rollup-value.neg { color: var(--color-danger-text); }
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

.tree-toggle {
  font-size: 12px;
  padding: 0 2px;
  align-self: center;
  flex-shrink: 0;
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
.acc-badge.institution {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.acc-badge-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
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
.figure-value.pos { color: var(--color-success-text); }
.figure-value.neg { color: var(--color-danger-text); }
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
  border-color: var(--color-danger-border);
  color: var(--color-danger-text);
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.1);
}

.btn-primary {
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
  border-color: transparent;
  color: #fff;
}

/* Écran étroit (tablette/mobile) : audit UX du 2026-07-27 — aucun breakpoint jusqu'ici. .acc-row
   (nom + solde + actions sur une seule ligne, solde et actions non rétrécissables) était le point
   de débordement le plus concret : sur un viewport étroit, le nom du compte n'avait presque plus
   de place. */
@media (max-width: 640px) {
  .page { padding: 14px; }
  .search-input { width: 100%; max-width: none; }
  .search-wrapper { flex: 1 1 100%; }
  .acc-row { flex-wrap: wrap; row-gap: 8px; }
  .acc-figure { min-width: 0; flex: 1 1 auto; text-align: left; }
  .row-actions { flex: 1 1 auto; justify-content: flex-end; }
}
</style>
