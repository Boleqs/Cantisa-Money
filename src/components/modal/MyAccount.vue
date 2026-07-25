<template>
  <div class="overlay" @click.self="shake">
    <div class="modal" :class="{ 'modal-shake': shaking }">
      <!-- Header -->
      <div class="modal-header">
        <h2 class="modal-title">Mon compte</h2>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>

      <!-- Profil -->
      <div class="profile-block">
        <div class="avatar">{{ initials }}</div>
        <div class="profile-info">
          <span class="profile-name">{{ user?.username ?? '…' }}</span>
          <span class="profile-email">{{ user?.email ?? '' }}</span>
        </div>
      </div>

      <hr class="divider" />

      <!-- Changer le mot de passe -->
      <section class="section">
        <h3 class="section-title">Changer le mot de passe</h3>

        <div class="field">
          <label class="label">Nouveau mot de passe</label>
          <input
            v-model="newPassword"
            type="password"
            class="input"
            placeholder="••••••••"
            autocomplete="new-password"
          />
        </div>
        <div class="field">
          <label class="label">Confirmer le mot de passe</label>
          <input
            v-model="confirmPassword"
            type="password"
            class="input"
            placeholder="••••••••"
            autocomplete="new-password"
          />
        </div>

        <p v-if="pwError" class="msg error">{{ pwError }}</p>
        <p v-if="pwSuccess" class="msg success">{{ pwSuccess }}</p>

        <button class="btn btn-primary" :disabled="saving" @click="changePassword">
          {{ saving ? 'Enregistrement…' : 'Mettre à jour' }}
        </button>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import { useModalShake, useEscapeClose } from '@/utils/modalUX'

const emit = defineEmits(['close'])
const { shaking, shake } = useModalShake()
useEscapeClose(() => emit('close'))

const user = ref(null)
const newPassword = ref('')
const confirmPassword = ref('')
const saving = ref(false)
const pwError = ref('')
const pwSuccess = ref('')

const initials = computed(() => {
  const name = user.value?.username ?? ''
  return name.slice(0, 2).toUpperCase() || '?'
})

async function loadUser() {
  try {
    const res = await axios.get('/api/auth/me')
    user.value = res.data?.response_data ?? null
  } catch { /* silencieux */ }
}

async function changePassword() {
  pwError.value = ''
  pwSuccess.value = ''

  if (!newPassword.value) {
    pwError.value = 'Le mot de passe ne peut pas être vide.'
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    pwError.value = 'Les mots de passe ne correspondent pas.'
    return
  }

  saving.value = true
  try {
    await axios.post('/api/user/reset_password', {
      user_id: user.value.id,
      password: newPassword.value,
    })
    pwSuccess.value = 'Mot de passe mis à jour.'
    newPassword.value = ''
    confirmPassword.value = ''
  } catch (e) {
    pwError.value = e?.response?.data?.response_data || 'Erreur lors de la mise à jour.'
  } finally {
    saving.value = false
  }
}

onMounted(loadUser)
</script>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  z-index: 500;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal {
  width: 420px;
  background: #111827;
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  color: #e5e7eb;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}

/* Header */
.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.modal-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #f1f5f9;
}
.close-btn {
  background: transparent;
  border: none;
  color: #6b7280;
  font-size: 16px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.12s;
}
.close-btn:hover { background: rgba(255,255,255,0.07); color: #e5e7eb; }

/* Profile */
.profile-block {
  display: flex;
  align-items: center;
  gap: 16px;
}
.avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
  letter-spacing: 0.03em;
}
.profile-info { display: flex; flex-direction: column; gap: 3px; }
.profile-name  { font-size: 16px; font-weight: 700; color: #f1f5f9; }
.profile-email { font-size: 13px; color: #6b7280; }

/* Divider */
.divider {
  border: none;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  margin: 0;
}

/* Section */
.section { display: flex; flex-direction: column; gap: 12px; }
.section-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

/* Fields */
.field { display: flex; flex-direction: column; gap: 5px; }
.label { font-size: 12px; color: #9ca3af; }
.input {
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  color: #e5e7eb;
  padding: 9px 12px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
}
.input:focus { border-color: #2563eb; }

/* Messages */
.msg { margin: 0; font-size: 13px; }
.msg.error   { color: #fca5a5; }
.msg.success { color: #86efac; }

/* Button */
.btn {
  padding: 10px 16px;
  border-radius: 9px;
  border: none;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
  align-self: flex-start;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary {
  background: linear-gradient(90deg, #2563eb, #4f46e5);
  color: #fff;
}
.btn-primary:not(:disabled):hover { opacity: 0.88; }
</style>
