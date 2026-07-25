<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Administration — Rôles &amp; Permissions</h1>
        <p class="subtitle">Gérez les rôles et leurs permissions associées.</p>
      </div>
      <div class="header-actions">
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>
    <div v-if="success" class="success">{{ success }}</div>

    <!-- ── Section Rôles ─────────────────────────────────────────────── -->
    <section class="section">
      <div class="section-header">
        <h2>Rôles</h2>
        <button class="btn btn-primary" @click="openCreateRole">+ Nouveau rôle</button>
      </div>

      <div v-if="loading && !roles.length" class="empty">Chargement…</div>
      <div v-else-if="!loading && !roles.length" class="empty">Aucun rôle.</div>

      <table v-else class="table">
        <thead>
          <tr>
            <th>Nom</th>
            <th>Description</th>
            <th>Permissions</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in roles" :key="r.id">
            <td class="bold">{{ r.name }}</td>
            <td class="muted">{{ r.description || '—' }}</td>
            <td>
              <span v-for="p in r.permissions" :key="p.id" class="perm-badge">{{ p.name }}</span>
              <span v-if="!r.permissions.length" class="muted">Aucune</span>
            </td>
            <td class="actions">
              <button class="btn-action" @click="openEditRole(r)" title="Modifier">✎ Modifier</button>
              <button class="btn-action" @click="openManagePerms(r)" title="Gérer les permissions">⚙ Permissions</button>
              <button class="btn-action btn-danger" @click="deleteRole(r)" title="Supprimer">✕</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- ── Section Permissions ───────────────────────────────────────── -->
    <section class="section">
      <div class="section-header">
        <h2>Permissions</h2>
        <button class="btn btn-primary" @click="openCreatePerm">+ Nouvelle permission</button>
      </div>

      <div v-if="loading && !permissions.length" class="empty">Chargement…</div>
      <div v-else-if="!loading && !permissions.length" class="empty">Aucune permission.</div>

      <table v-else class="table">
        <thead>
          <tr>
            <th>Nom</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="p in permissions" :key="p.id">
            <td class="bold">{{ p.name }}</td>
            <td class="muted">{{ p.description || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- Modal : Créer un rôle -->
    <div v-if="showCreateRoleModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>Nouveau rôle</h2>
        <label>Nom *
          <input v-model="roleForm.name" placeholder="ex: Comptable" autocomplete="off" />
        </label>
        <label>Description
          <input v-model="roleForm.description" placeholder="Description optionnelle" autocomplete="off" />
        </label>
        <div v-if="modalError" class="modal-error">{{ modalError }}</div>
        <div class="modal-actions">
          <button class="btn" @click="showCreateRoleModal = false">Annuler</button>
          <button class="btn btn-primary" :disabled="!roleForm.name.trim()" @click="createRole">Créer</button>
        </div>
      </div>
    </div>

    <!-- Modal : Modifier un rôle -->
    <div v-if="showEditRoleModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>Modifier — <em>{{ editTarget?.name }}</em></h2>
        <label>Nom *
          <input v-model="roleForm.name" autocomplete="off" />
        </label>
        <label>Description
          <input v-model="roleForm.description" autocomplete="off" />
        </label>
        <div v-if="modalError" class="modal-error">{{ modalError }}</div>
        <div class="modal-actions">
          <button class="btn" @click="showEditRoleModal = false">Annuler</button>
          <button class="btn btn-primary" :disabled="!roleForm.name.trim()" @click="editRole">Enregistrer</button>
        </div>
      </div>
    </div>

    <!-- Modal : Gérer les permissions d'un rôle -->
    <div v-if="showPermsModal" class="modal-backdrop" @click.self="shake">
      <div class="modal modal-wide" :class="{ 'modal-shake': shaking }">
        <h2>Permissions — <em>{{ permsTarget?.name }}</em></h2>
        <p class="modal-hint">Cochez les permissions à attribuer à ce rôle.</p>
        <div class="perm-list">
          <label v-for="p in permissions" :key="p.id" class="perm-row">
            <input
              type="checkbox"
              :checked="isAssigned(p.id)"
              :disabled="savingPerm === p.id"
              @change="togglePerm(p, $event.target.checked)"
            />
            <span>
              <strong>{{ p.name }}</strong>
              <span v-if="p.description" class="muted"> — {{ p.description }}</span>
            </span>
          </label>
          <p v-if="!permissions.length" class="muted">Aucune permission disponible.</p>
        </div>
        <div v-if="modalError" class="modal-error">{{ modalError }}</div>
        <div class="modal-actions">
          <button class="btn" @click="showPermsModal = false">Fermer</button>
        </div>
      </div>
    </div>

    <!-- Modal : Créer une permission -->
    <div v-if="showCreatePermModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>Nouvelle permission</h2>
        <label>Nom *
          <input v-model="permForm.name" placeholder="ex: Manage budgets" autocomplete="off" />
        </label>
        <label>Description
          <input v-model="permForm.description" placeholder="Description optionnelle" autocomplete="off" />
        </label>
        <div v-if="modalError" class="modal-error">{{ modalError }}</div>
        <div class="modal-actions">
          <button class="btn" @click="showCreatePermModal = false">Annuler</button>
          <button class="btn btn-primary" :disabled="!permForm.name.trim()" @click="createPerm">Créer</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useModalShake, useEscapeClose } from '@/utils/modalUX'

const roles = ref([])
const permissions = ref([])
const loading = ref(false)
const error = ref('')
const success = ref('')
const modalError = ref('')

const showCreateRoleModal = ref(false)
const showEditRoleModal = ref(false)
const showPermsModal = ref(false)
const showCreatePermModal = ref(false)

const editTarget = ref(null)
const permsTarget = ref(null)
const assignedPermIds = ref(new Set())
const savingPerm = ref(null)

const roleForm = ref({ name: '', description: '' })
const permForm = ref({ name: '', description: '' })

const { shaking, shake } = useModalShake()
useEscapeClose(() => {
  if (showCreateRoleModal.value) showCreateRoleModal.value = false
  else if (showEditRoleModal.value) showEditRoleModal.value = false
  else if (showPermsModal.value) showPermsModal.value = false
  else if (showCreatePermModal.value) showCreatePermModal.value = false
})

function flash(msg) {
  success.value = msg
  setTimeout(() => { success.value = '' }, 3000)
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [rolesRes, permsRes] = await Promise.all([
      axios.get('/api/roles'),
      axios.get('/api/permissions'),
    ])
    roles.value = Array.isArray(rolesRes.data?.response_data) ? rolesRes.data.response_data : []
    permissions.value = Array.isArray(permsRes.data?.response_data) ? permsRes.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

// ── Rôles ────────────────────────────────────────────────────────────────

function openCreateRole() {
  roleForm.value = { name: '', description: '' }
  modalError.value = ''
  showCreateRoleModal.value = true
}

function openEditRole(r) {
  editTarget.value = r
  roleForm.value = { name: r.name, description: r.description || '' }
  modalError.value = ''
  showEditRoleModal.value = true
}

async function createRole() {
  modalError.value = ''
  try {
    await axios.post('/api/roles', roleForm.value)
    showCreateRoleModal.value = false
    flash('Rôle créé.')
    await reload()
  } catch (e) {
    modalError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function editRole() {
  modalError.value = ''
  try {
    await axios.patch(`/api/roles/${editTarget.value.id}`, roleForm.value)
    showEditRoleModal.value = false
    flash('Rôle mis à jour.')
    await reload()
  } catch (e) {
    modalError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function deleteRole(r) {
  if (!confirm(`Supprimer le rôle « ${r.name} » ? Les utilisateurs qui l'ont seront sans rôle.`)) return
  error.value = ''
  try {
    await axios.delete(`/api/roles/${r.id}`)
    flash('Rôle supprimé.')
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

// ── Gestion des permissions d'un rôle ────────────────────────────────────

function openManagePerms(r) {
  permsTarget.value = r
  assignedPermIds.value = new Set(r.permissions.map(p => p.id))
  modalError.value = ''
  showPermsModal.value = true
}

function isAssigned(permId) {
  return assignedPermIds.value.has(permId)
}

async function togglePerm(perm, checked) {
  savingPerm.value = perm.id
  modalError.value = ''
  try {
    if (checked) {
      await axios.post(`/api/roles/${permsTarget.value.id}/permissions/${perm.id}`)
      assignedPermIds.value.add(perm.id)
    } else {
      await axios.delete(`/api/roles/${permsTarget.value.id}/permissions/${perm.id}`)
      assignedPermIds.value.delete(perm.id)
    }
    // Sync local roles list
    const role = roles.value.find(r => r.id === permsTarget.value.id)
    if (role) {
      if (checked) {
        role.permissions.push({ id: perm.id, name: perm.name, description: perm.description })
      } else {
        role.permissions = role.permissions.filter(p => p.id !== perm.id)
      }
    }
  } catch (e) {
    modalError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    savingPerm.value = null
  }
}

// ── Permissions ───────────────────────────────────────────────────────────

function openCreatePerm() {
  permForm.value = { name: '', description: '' }
  modalError.value = ''
  showCreatePermModal.value = true
}

async function createPerm() {
  modalError.value = ''
  try {
    await axios.post('/api/permissions', permForm.value)
    showCreatePermModal.value = false
    flash('Permission créée.')
    await reload()
  } catch (e) {
    modalError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
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
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; }
.header-actions { display: flex; gap: 10px; }

.section {
  margin-bottom: 36px;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.section-header h2 { margin: 0; font-size: 18px; color: #cbd5e1; }

.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.btn:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-primary { background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2)); border-color: transparent; color: #fff; }

.alert {
  border: 1px solid rgba(239, 68, 68, 0.5);
  background: rgba(239, 68, 68, 0.08);
  padding: 12px 14px;
  border-radius: 12px;
  margin-bottom: 16px;
  color: #fecaca;
}
.success {
  border: 1px solid rgba(52, 211, 153, 0.4);
  background: rgba(52, 211, 153, 0.08);
  padding: 12px 14px;
  border-radius: 12px;
  margin-bottom: 16px;
  color: #6ee7b7;
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
.bold { font-weight: 600; }
.muted { color: #9ca3af; }
.actions { text-align: right; white-space: nowrap; }

.perm-badge {
  display: inline-block;
  padding: 2px 9px;
  border-radius: 20px;
  font-size: 12px;
  background: rgba(99,102,241,0.15);
  color: #a5b4fc;
  border: 1px solid rgba(99,102,241,0.3);
  margin-right: 4px;
  margin-bottom: 2px;
}

.btn-action {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
  padding: 5px 10px;
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
  width: 420px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.modal-wide { width: 520px; }
.modal h2 { margin: 0; font-size: 18px; }
.modal em { color: #93c5fd; font-style: normal; }
.modal-hint { margin: 0; color: #9ca3af; font-size: 13px; }
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

.perm-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 300px;
  overflow-y: auto;
  padding-right: 4px;
}
.perm-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #e5e7eb;
  cursor: pointer;
}
.perm-row input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: #6366f1;
  cursor: pointer;
  flex-shrink: 0;
}
.perm-row input:disabled { opacity: 0.5; cursor: wait; }
</style>
