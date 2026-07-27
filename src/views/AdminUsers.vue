<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Administration — Utilisateurs</h1>
        <p class="subtitle">Gérez les comptes utilisateurs de l'application.</p>
      </div>
      <div class="header-actions">
        <button class="btn" :disabled="loading" @click="reload">
          <span v-if="!loading">↻ Rafraîchir</span>
          <span v-else>Chargement…</span>
        </button>
        <button class="btn btn-primary" @click="openCreate">+ Nouvel utilisateur</button>
      </div>
    </header>

    <div v-if="error" class="alert"><strong>Erreur :</strong> {{ error }}</div>

    <div v-if="loading && !users.length" class="empty">Chargement…</div>
    <div v-else-if="!loading && !users.length" class="empty">Aucun utilisateur.</div>

    <table v-else class="table">
      <thead>
        <tr>
          <th>Utilisateur</th>
          <th>Email</th>
          <th>Rôle</th>
          <th>Créé le</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td class="username">{{ u.username }}</td>
          <td class="muted">{{ u.email }}</td>
          <td>
            <span v-for="r in u.roles" :key="r.id" class="role-badge">{{ r.name }}</span>
            <span v-if="!u.roles.length" class="muted">—</span>
          </td>
          <td class="muted">{{ fmtDate(u.created_at) }}</td>
          <td class="actions">
            <button class="btn-action" @click="openChangeRole(u)" title="Changer de rôle">⬡ Rôle</button>
            <button class="btn-action" @click="openResetPassword(u)" title="Réinitialiser le mot de passe">🔑 MDP</button>
            <button class="btn-action btn-danger" @click="deleteUser(u)" title="Supprimer">✕</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Modal : Créer un utilisateur -->
    <div v-if="showCreateModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>Nouvel utilisateur</h2>
        <label>Nom d'utilisateur *
          <input v-model="createForm.username" placeholder="john_doe" autocomplete="off" />
        </label>
        <label>Email *
          <input v-model="createForm.email" type="email" placeholder="john@exemple.com" autocomplete="off" />
        </label>
        <label>Mot de passe *
          <input v-model="createForm.password" type="password" placeholder="••••••••" autocomplete="new-password" />
        </label>
        <label>Rôle *
          <select v-model="createForm.role_id">
            <option disabled value="">— Sélectionner —</option>
            <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
          </select>
        </label>
        <div v-if="modalError" class="modal-error">{{ modalError }}</div>
        <div class="modal-actions">
          <button class="btn" @click="showCreateModal = false">Annuler</button>
          <button class="btn btn-primary"
            :disabled="!createForm.username || !createForm.email || !createForm.password || !createForm.role_id"
            @click="createUser">
            Créer
          </button>
        </div>
      </div>
    </div>

    <!-- Modal : Changer de rôle -->
    <div v-if="showRoleModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>Changer de rôle — <em>{{ roleTarget?.username }}</em></h2>
        <label>Nouveau rôle *
          <select v-model="roleForm.role_id">
            <option disabled value="">— Sélectionner —</option>
            <option v-for="r in roles" :key="r.id" :value="r.id">{{ r.name }}</option>
          </select>
        </label>
        <div v-if="modalError" class="modal-error">{{ modalError }}</div>
        <div class="modal-actions">
          <button class="btn" @click="showRoleModal = false">Annuler</button>
          <button class="btn btn-primary" :disabled="!roleForm.role_id" @click="changeRole">Enregistrer</button>
        </div>
      </div>
    </div>

    <!-- Modal : Réinitialiser le mot de passe -->
    <div v-if="showPasswordModal" class="modal-backdrop" @click.self="shake">
      <div class="modal" :class="{ 'modal-shake': shaking }">
        <h2>Réinitialiser le MDP — <em>{{ passwordTarget?.username }}</em></h2>
        <label>Nouveau mot de passe *
          <input v-model="passwordForm.password" type="password" placeholder="••••••••" autocomplete="new-password" />
        </label>
        <div v-if="modalError" class="modal-error">{{ modalError }}</div>
        <div class="modal-actions">
          <button class="btn" @click="showPasswordModal = false">Annuler</button>
          <button class="btn btn-primary" :disabled="passwordForm.password.length < 4" @click="resetPassword">Réinitialiser</button>
        </div>
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

const toast = useToast()

const users = ref([])
const roles = ref([])
const loading = ref(false)
const error = ref('')

const showCreateModal = ref(false)
const showRoleModal = ref(false)
const showPasswordModal = ref(false)
const roleTarget = ref(null)
const passwordTarget = ref(null)
const modalError = ref('')

const createForm = ref({ username: '', email: '', password: '', role_id: '' })
const roleForm = ref({ role_id: '' })
const passwordForm = ref({ password: '' })

const { shaking, shake } = useModalShake()
useEscapeClose(
  () => {
    if (showCreateModal.value) showCreateModal.value = false
    else if (showRoleModal.value) showRoleModal.value = false
    else if (showPasswordModal.value) showPasswordModal.value = false
  },
  shake,
  () => showCreateModal.value || showRoleModal.value || showPasswordModal.value
)

function fmtDate(v) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' })
}

async function reload() {
  loading.value = true
  error.value = ''
  try {
    const [usersRes, rolesRes] = await Promise.all([
      axios.get('/api/user'),
      axios.get('/api/user/roles'),
    ])
    users.value = Array.isArray(usersRes.data?.response_data) ? usersRes.data.response_data : []
    roles.value = Array.isArray(rolesRes.data?.response_data) ? rolesRes.data.response_data : []
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  createForm.value = { username: '', email: '', password: '', role_id: roles.value[0]?.id || '' }
  modalError.value = ''
  showCreateModal.value = true
}

function openChangeRole(u) {
  roleTarget.value = u
  roleForm.value = { role_id: u.roles[0]?.id || '' }
  modalError.value = ''
  showRoleModal.value = true
}

function openResetPassword(u) {
  passwordTarget.value = u
  passwordForm.value = { password: '' }
  modalError.value = ''
  showPasswordModal.value = true
}

async function createUser() {
  modalError.value = ''
  try {
    await axios.post('/api/user', {
      username: createForm.value.username,
      email: createForm.value.email,
      password: createForm.value.password,
      role_id: createForm.value.role_id,
    })
    showCreateModal.value = false
    toast.success('Utilisateur créé avec succès.')
    await reload()
  } catch (e) {
    modalError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function changeRole() {
  modalError.value = ''
  try {
    await axios.patch('/api/user/role', {
      user_id: roleTarget.value.id,
      role_id: roleForm.value.role_id,
    })
    showRoleModal.value = false
    toast.success('Rôle mis à jour.')
    await reload()
  } catch (e) {
    modalError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function resetPassword() {
  modalError.value = ''
  try {
    await axios.post('/api/user/reset_password', {
      user_id: passwordTarget.value.id,
      password: passwordForm.value.password,
    })
    showPasswordModal.value = false
    toast.success('Mot de passe réinitialisé.')
  } catch (e) {
    modalError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  }
}

async function deleteUser(u) {
  const ok = await confirmDialog({
    title: "Supprimer l'utilisateur",
    message: `Supprimer l'utilisateur « ${u.username} » ? Cette action est irréversible.`,
    confirmLabel: 'Supprimer',
    danger: true,
  })
  if (!ok) return
  error.value = ''
  try {
    await axios.delete('/api/user', { params: { user_id: u.id } })
    toast.success('Utilisateur supprimé.')
    await reload()
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
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
.header-actions { display: flex; gap: 10px; }

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
.username { font-weight: 600; }
.muted { color: #9ca3af; }
.actions { text-align: right; white-space: nowrap; }

.role-badge {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 20px;
  font-size: 12px;
  background: rgba(99,102,241,0.2);
  color: #a5b4fc;
  border: 1px solid rgba(99,102,241,0.3);
  margin-right: 4px;
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
  width: 400px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.modal h2 { margin: 0; font-size: 18px; }
.modal em { color: #93c5fd; font-style: normal; }
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
.modal-error {
  font-size: 13px;
  color: #fca5a5;
  background: rgba(239,68,68,0.08);
  border: 1px solid rgba(239,68,68,0.3);
  border-radius: 8px;
  padding: 8px 10px;
}
.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 4px; }
</style>
