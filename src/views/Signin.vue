<template>
  <div class="page">
    <div class="card">

      <div class="brand">
        <img class="brand-logo-img" src="../components/icons/cantisa-logo-wordmark.svg" alt="Cantisa Money Manager" />
        <span v-if="appVersion" class="brand-version">{{ appVersion }}</span>
      </div>

      <h1 class="card-title">Connexion</h1>
      <p class="card-subtitle">Bienvenue, connectez-vous à votre espace.</p>

      <form class="form" @submit.prevent="login">
        <div class="field">
          <label for="login">Identifiant</label>
          <input
            id="login"
            v-model="loginValue"
            type="text"
            placeholder="Nom d'utilisateur ou e-mail"
            autocomplete="username"
            :disabled="loading"
            required
          />
        </div>

        <div class="field">
          <label for="password">Mot de passe</label>
          <div class="input-wrapper">
            <input
              id="password"
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="••••••••"
              autocomplete="current-password"
              :disabled="loading"
              minlength="4"
              required
            />
            <button
              type="button"
              class="eye-btn"
              :aria-label="showPassword ? 'Masquer' : 'Afficher'"
              @click="showPassword = !showPassword"
            >
              {{ showPassword ? '🙈' : '👁' }}
            </button>
          </div>
        </div>

        <div v-if="error" class="alert">{{ error }}</div>

        <button type="submit" class="btn-submit" :disabled="loading">
          <span v-if="!loading">Se connecter</span>
          <span v-else class="spinner-row"><span class="spinner"></span> Connexion…</span>
        </button>
      </form>

      <p class="footer-link">
        Pas encore de compte ?
        <router-link to="/init/Signup">Créer un compte</router-link>
      </p>

    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'

const emit = defineEmits(['msg-event'])

const loginValue  = ref('')
const password    = ref('')
const loading     = ref(false)
const error       = ref('')
const showPassword = ref(false)
const appVersion  = ref('')
const router      = useRouter()

onMounted(async () => {
  try {
    const { data } = await axios.get('/api/version')
    appVersion.value = data?.response_data || ''
  } catch (e) {
    // Non bloquant : l'écran de connexion reste utilisable sans le numéro de version affiché.
  }
})

async function login() {
  loading.value = true
  error.value   = ''
  try {
    const { data } = await axios.post('/api/auth/login', {
      login: loginValue.value,
      password: password.value,
    })
    emit('msg-event', { type: 'info', content: data })
    router.push('/')
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur de connexion.'
    emit('msg-event', { type: 'error', content: error.value })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #0b1220;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}

.card {
  width: 380px;
  max-width: calc(100vw - 32px);
  background: rgba(15, 23, 42, 0.85);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 20px;
  padding: 36px 32px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
}

/* Brand */
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.brand-logo-img {
  height: 42px;
  width: auto;
  border-radius: 6px;
}

.brand-version {
  font-size: 11px;
  color: #4b5563;
  font-weight: 500;
}

/* Header */
.card-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #f1f5f9;
}

.card-subtitle {
  margin: 2px 0 16px;
  font-size: 13px;
  color: #6b7280;
}

/* Form */
.form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-size: 12px;
  font-weight: 500;
  color: #9ca3af;
  letter-spacing: 0.02em;
}

.field input {
  background: rgba(2, 6, 23, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 10px;
  padding: 10px 12px;
  color: #e5e7eb;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s;
  width: 100%;
  box-sizing: border-box;
}

.field input:focus {
  border-color: #2563eb;
}

.field input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Password toggle */
.input-wrapper {
  position: relative;
}

.input-wrapper input {
  padding-right: 42px;
}

.eye-btn {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0;
  color: #6b7280;
}

/* Error */
.alert {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.08);
  color: #fca5a5;
  font-size: 13px;
}

/* Submit */
.btn-submit {
  margin-top: 4px;
  width: 100%;
  padding: 11px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2));
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}

.btn-submit:hover:not(:disabled) {
  opacity: 0.9;
}

.btn-submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.spinner-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Footer */
.footer-link {
  margin: 12px 0 0;
  text-align: center;
  font-size: 13px;
  color: #6b7280;
}

.footer-link a {
  color: #60a5fa;
  text-decoration: none;
  font-weight: 500;
}

.footer-link a:hover {
  text-decoration: underline;
}
</style>