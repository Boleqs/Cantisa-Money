<template>
  <div class="page">
    <!-- Header -->
    <header class="page-header">
      <div class="title-block">
        <h1>Comptes de revenus et dépenses</h1>
        <p class="subtitle">
          Comptes de catégorisation des transactions (contreparties du double-entry) — ne
          représentent pas de l'argent réel, groupés {{ groupByLabel }}.
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
            </div>

            <div class="acc-figure">
              <div class="figure-label">{{ acc._figure.label }}</div>
              <div class="figure-value" :class="acc._figure.colorClass">
                {{ fmtAmount(acc._figure.value) }} {{ acc._figure.currency }}
              </div>
            </div>

            <div class="row-actions">
              <button class="btn-action" @click="openEdit(acc)" title="Modifier">✎</button>
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
    :parent-accounts="incomeExpenseAccounts"
    :type-options="TYPE_OPTIONS"
    default-account-type="Expense"
    @save="handleSave"
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
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import { useRouter } from "vue-router";
import axios from "axios";
import AccountModal from "@/components/modal/AccountModal.vue";
import { confirmDialog } from "@/utils/confirmDialog";
import { useToast } from "@/utils/toast";
import { normalizeSearch } from "@/utils/search.js";
import { accountDisplayLabel } from "@/utils/accountDisplay.js";
import { ensureInstitutionsLoaded } from "@/utils/institutions.js";

const toast = useToast();
const router = useRouter();

// On récupère tous les comptes de l'utilisateur (même endpoint que la page Comptes) puis on ne
// garde que les types Income/Expense — voir Accounts.vue qui fait l'inverse.
const accounts = ref([]);
const commodities = ref([]);

const showModal = ref(false);
const modalMode = ref("create");
const selectedAccount = ref(null);

const loading = ref(false);
const error = ref("");

const search = ref("");
const showHidden = ref(false);
const showVirtual = ref(true);
const groupBy = ref("type");

const collapsed = ref(new Set());
const collapsedParents = ref(new Set());

const TYPE_ORDER = ["Income", "Expense"];
const TYPE_LABELS = { Income: "Revenus", Expense: "Dépenses" };
const TYPE_OPTIONS = [
  { value: "Income", label: "Income (Revenus)" },
  { value: "Expense", label: "Expense (Dépenses)" },
];
const GROUP_ROLLUP_LABEL = { Income: "Total perçu", Expense: "Total dépensé" };

const normalizeText = normalizeSearch;

function fmtAmount(v) {
  if (v === null || v === undefined || v === "") return "0";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(n);
}

function commodityById(id) {
  return commodities.value.find((c) => String(c.id) === String(id));
}

function currencyShort(currencyId) {
  const c = commodityById(currencyId);
  return c?.short_name?.toUpperCase?.() || "—";
}

const GROUP_BY_LABELS = { parent: "par compte parent", type: "par type" };
const groupByLabel = computed(() => GROUP_BY_LABELS[groupBy.value] || "par type");

// Comptes Income/Expense uniquement — sert de base à la fois à l'affichage (via filteredAccounts)
// et au choix du compte parent dans le modal (un sous-compte de catégorie doit avoir un parent de
// la même famille).
const incomeExpenseAccounts = computed(() =>
  accounts.value.filter((a) => a.account_type === "Income" || a.account_type === "Expense")
);

const parentIds = computed(
  () => new Set(incomeExpenseAccounts.value.filter((a) => a.parent_id).map((a) => String(a.parent_id)))
);

function hasChildren(accountId) {
  return parentIds.value.has(String(accountId));
}

function childCount(accountId) {
  return incomeExpenseAccounts.value.filter((a) => String(a.parent_id) === String(accountId)).length;
}

// Un compte Income est toujours crédité en négatif par construction du trigger SQL (le cumul réel
// est dans total_spent) et un compte Expense toujours débité en positif (cumul réel dans
// total_earned) — soustraire les deux donnerait un nombre au signe trompeur (ex. "Solde -9 600" sur
// un compte de salaires). On affiche donc le cumul réel, en neutre, jamais coloré pos/neg puisque
// ce n'est pas un gain ou une perte. Même logique que l'ancienne accountFigure() d'Accounts.vue.
function accountFigure(acc) {
  const hc = hasChildren(acc.id);
  const earned = Number(hc ? acc.consolidated_earned : acc.total_earned) || 0;
  const spent = Number(hc ? acc.consolidated_spent : acc.total_spent) || 0;
  const currency = currencyShort(acc.currency_id);

  if (acc.account_type === "Income") {
    return {
      label: hc ? "Total perçu (consolidé)" : "Total perçu",
      value: spent,
      currency,
      colorClass: "neutral",
      earned,
      spent,
    };
  }

  return {
    label: hc ? "Total dépensé (consolidé)" : "Total dépensé",
    value: earned,
    currency,
    colorClass: "neutral",
    earned,
    spent,
  };
}

function groupRollup(labelKey, items) {
  const roots = items.filter((a) => a._depth === 0);
  if (!roots.length) return null;
  const currencies = new Set(roots.map((a) => a._figure.currency));
  if (currencies.size > 1) return null;
  const value = roots.reduce((s, a) => s + a._figure.value, 0);
  return { label: GROUP_ROLLUP_LABEL[labelKey] || "Cumul", value, currency: roots[0]._figure.currency, colorClass: "neutral" };
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
  const { data } = await axios.get("/api/commodities");
  commodities.value = Array.isArray(data?.response_data) ? data.response_data : [];
}

async function fetchAccounts() {
  const { data } = await axios.get("/api/accounts");
  accounts.value = Array.isArray(data?.response_data) ? data.response_data : [];
}

async function reload() {
  loading.value = true;
  error.value = "";
  try {
    await fetchCommodities();
    await fetchAccounts();
    await ensureInstitutionsLoaded();
  } catch (e) {
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
        account_type: form.account_type || "Expense",
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
        institution_id: form.institution_id || null,
        account_type: form.account_type || "Expense",
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
    error.value = e?.response?.data?.response_data || e?.message || "Erreur inconnue";
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
    error.value = e?.response?.data?.response_data || e?.message || "Erreur inconnue";
  }
}

const closingAccount = ref(null);
const closingTargetId = ref("");
const closingBusy = ref(false);
const closingError = ref("");

// Contrepartie de clôture : n'importe quel compte de l'utilisateur (pas seulement Income/Expense),
// même logique qu'Accounts.vue.
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
    closingError.value = e?.response?.data?.response_data || e?.message || "Erreur lors de la clôture";
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

onMounted(() => {
  reload();
});

const filteredAccounts = computed(() => {
  const q = normalizeText(search.value);

  return incomeExpenseAccounts.value
    .filter((a) => (showHidden.value ? true : !a.is_hidden))
    .filter((a) => (showVirtual.value ? true : !a.is_virtual))
    .filter((a) => {
      if (!q) return true;
      const blob = [a.name, a.description, a.code, a.account_type, a.account_subtype]
        .map(normalizeText)
        .join(" ");
      return blob.includes(q);
    });
});

function buildTreeFlat(items) {
  const itemIds = new Set(items.map((a) => String(a.id)));
  const byParent = new Map();
  byParent.set(null, []);

  for (const item of items) {
    const pid =
      item.parent_id && itemIds.has(String(item.parent_id)) ? String(item.parent_id) : null;
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
      if (!collapsedParents.value.has(String(child.id))) {
        traverse(String(child.id), depth + 1);
      }
    }
  }
  traverse(null, 0);
  return result;
}

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

  const map = new Map();
  for (const acc of filteredAccounts.value) {
    const t = acc.account_type || "Other";
    if (!map.has(t)) map.set(t, []);
    map.get(t).push(acc);
  }

  const keys = Array.from(map.keys());
  keys.sort((a, b) => TYPE_ORDER.indexOf(a) - TYPE_ORDER.indexOf(b));

  return keys.map((key) => {
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

@media (max-width: 640px) {
  .page { padding: 14px; }
  .search-input { width: 100%; max-width: none; }
  .search-wrapper { flex: 1 1 100%; }
  .acc-row { flex-wrap: wrap; row-gap: 8px; }
  .acc-figure { min-width: 0; flex: 1 1 auto; text-align: left; }
  .row-actions { flex: 1 1 auto; justify-content: flex-end; }
}
</style>
