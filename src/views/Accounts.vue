<template>
  <div class="page">
    <!-- Header -->
    <header class="page-header">
      <div class="title-block">
        <h1>Accounts</h1>
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
          <button class="icon-btn" type="button" :aria-label="isCollapsed(group.key) ? 'Déplier' : 'Replier'">
            {{ isCollapsed(group.key) ? '▸' : '▾' }}
          </button>
        </div>

        <div v-if="!isCollapsed(group.key)" class="cards">
          <div
            v-for="acc in group.items"
            :key="acc.id"
            class="card"
            :class="{ 'card--child': acc._depth > 0 }"
            :style="acc._depth > 0 ? { marginLeft: (acc._depth * 28) + 'px' } : {}"
          >
            <div class="card-top">
              <div class="name-wrap">
                <div class="name-row">
                  <span v-if="acc._depth > 0" class="tree-prefix">└</span>
                  <h3 class="name account-link" @click="router.push(`/accounts/${acc.id}`)">{{ acc.name }}</h3>
                  <span v-if="acc.code" class="code">#{{ acc.code }}</span>
                </div>
                <p v-if="acc.description" class="desc">
                  {{ acc.description }}
                </p>
              </div>

              <div class="badges">
                <span class="badge">{{ acc.account_type }}</span>
                <span v-if="acc.account_subtype" class="badge soft">
                  {{ acc.account_subtype }}
                </span>
                <span v-if="acc.is_hidden" class="badge danger">Hidden</span>
                <span v-if="acc.is_virtual" class="badge warn">Virtual</span>
              </div>
            </div>

            <div class="card-grid">
              <div class="kv">
                <div class="k">Devise</div>
                <div class="v">
                  {{ currencyLabel(acc.currency_id) }}
                </div>
              </div>

              <div class="kv">
                <div class="k">Total earned</div>
                <div class="v mono">
                  {{ fmtAmount(acc.total_earned) }} {{ currencyShort(acc.currency_id) }}
                </div>
              </div>

              <div class="kv">
                <div class="k">Total spent</div>
                <div class="v mono">
                  {{ fmtAmount(acc.total_spent) }} {{ currencyShort(acc.currency_id) }}
                </div>
              </div>

              <template v-if="hasChildren(acc.id)">
                <div class="kv">
                  <div class="k">Solde consolidé — earned</div>
                  <div class="v mono">
                    {{ fmtAmount(acc.consolidated_earned) }} {{ currencyShort(acc.currency_id) }}
                  </div>
                </div>

                <div class="kv">
                  <div class="k">Solde consolidé — spent</div>
                  <div class="v mono">
                    {{ fmtAmount(acc.consolidated_spent) }} {{ currencyShort(acc.currency_id) }}
                  </div>
                </div>
              </template>

              <div class="kv" v-if="acc.parent_id">
                <div class="k">Parent</div>
                <div class="v">{{ parentName(acc.parent_id) }}</div>
              </div>

              <div class="kv">
                <div class="k">Created</div>
                <div class="v">{{ fmtDate(acc.created_at) }}</div>
              </div>

              <div class="kv">
                <div class="k">Updated</div>
                <div class="v">{{ fmtDate(acc.updated_at) }}</div>
              </div>
            </div>

            <div class="card-actions">
              <button class="btn-action" @click="openEdit(acc)">✎ Modifier</button>
              <button class="btn-action btn-danger" @click="deleteAccount(acc)">✕ Supprimer</button>
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

const router = useRouter();

const accounts = ref([]);
const commodities = ref([]);

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
  Current: "Current accounts",
  Assets: "Assets",
  Equity: "Equity",
  Liability: "Crédits / Dettes",
  Income: "Income",
  Expense: "Expense",
};

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

function currencyShort(currencyId) {
  const c = commodityById(currencyId);
  return c?.short_name?.toUpperCase?.() || "—";
}

function currencyLabel(currencyId) {
  const c = commodityById(currencyId);
  if (!c) return String(currencyId ?? "—");
  const short = c.short_name ? c.short_name.toUpperCase() : "";
  return short ? `${c.name} (${short})` : c.name;
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

async function reload() {
  loading.value = true;
  error.value = "";
  try {
    // commodities avant accounts pour afficher les devises correctement
    await fetchCommodities();
    await fetchAccounts();
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

function parentName(parentId) {
  const p = accounts.value.find((a) => String(a.id) === String(parentId));
  return p ? p.name : String(parentId);
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
      result.push({ ...child, _depth: depth });
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

  return keys.map((key) => ({
    key,
    label: TYPE_LABELS[key] || key,
    // Chaque groupe est ordonné en arborescence parent → enfants
    items: buildTreeFlat(map.get(key)),
  }));
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

.cards {
  padding: 14px;
  display: grid;
  gap: 12px;
}

.card {
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(2, 6, 23, 0.45);
  border-radius: 14px;
  padding: 14px;
}

.card--child {
  border-left: 2px solid rgba(96, 165, 250, 0.35);
}

.tree-prefix {
  color: rgba(148, 163, 184, 0.35);
  font-size: 14px;
  flex-shrink: 0;
  margin-right: 2px;
}

.card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.name-wrap {
  min-width: 0;
  flex: 1;
}

.name-row {
  display: flex;
  gap: 10px;
  align-items: baseline;
  flex-wrap: wrap;
}
.name {
  margin: 0;
  font-size: 16px;
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
  margin: 6px 0 0;
  color: #9ca3af;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.badge {
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(148, 163, 184, 0.10);
  color: #e5e7eb;
}
.badge.soft {
  background: rgba(148, 163, 184, 0.06);
}
.badge.danger {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.10);
  color: #fecaca;
}
.badge.warn {
  border-color: rgba(245, 158, 11, 0.35);
  background: rgba(245, 158, 11, 0.10);
  color: #fde68a;
}

.card-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px 14px;
  margin-top: 12px;
}
@media (max-width: 900px) {
  .card-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 560px) {
  .card-grid {
    grid-template-columns: 1fr;
  }
}

.kv .k {
  color: #9ca3af;
  font-size: 12px;
}
.kv .v {
  margin-top: 4px;
  font-size: 13px;
  color: #e5e7eb;
}
.mono {
  font-variant-numeric: tabular-nums;
}

.card-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  justify-content: flex-end;
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
  background: linear-gradient(90deg, #2563eb, #4f46e5);
  border-color: transparent;
  color: #fff;
}
</style>
