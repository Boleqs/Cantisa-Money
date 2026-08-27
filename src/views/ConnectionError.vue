<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'

const emit = defineEmits(['fullpage'])
emit('fullpage', { value: true })

const router = useRouter()
const retrying = ref(false)
const retryFailed = ref(false)
// Reflète la config réelle (voir router/index.js) plutôt qu'une adresse en dur. baseURL vide =
// appels relatifs sur l'origine courante (cas nominal derrière le reverse proxy).
const apiBaseUrl = axios.defaults.baseURL || `${window.location.origin}/api`

async function retry() {
  retrying.value = true
  retryFailed.value = false
  try {
    // Endpoint public : on veut seulement savoir si le backend répond, pas si l'utilisateur est
    // authentifié. /auth/check-auth renvoie 404 "Not logged in" pour un visiteur déconnecté —
    // axios le traite comme une erreur, ce qui laissait à tort l'utilisateur bloqué ici alors que
    // le backend était revenu.
    await axios.get('/api/version')
    // Le backend répond : on relance la navigation normale, la garde router redirige vers Signin
    // ou le Dashboard selon l'état de session.
    router.push('/')
  } catch (err) {
    // Pas de réponse, ou 502/503/504 du reverse proxy (backend toujours down) : on reste ici.
    // Toute autre réponse HTTP prouve que le backend est joignable -> on repart.
    if (!err.response || [502, 503, 504].includes(err.response.status)) {
      retryFailed.value = true
    } else {
      router.push('/')
    }
  } finally {
    retrying.value = false
  }
}
</script>

<template>
  <div class="error-page">
    <!-- Fond animé -->
    <div class="bg-grid"></div>
    <div class="glow glow-1"></div>
    <div class="glow glow-2"></div>

    <div class="card">
      <!-- Icône -->
      <div class="icon-wrap">
        <svg viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg" class="error-icon">
          <circle cx="32" cy="32" r="30" stroke="#ef4444" stroke-width="2" stroke-dasharray="6 4" />
          <path d="M20 20 L44 44M44 20 L20 44" stroke="#ef4444" stroke-width="3" stroke-linecap="round"/>
          <circle cx="32" cy="32" r="14" fill="rgba(239,68,68,0.08)" stroke="rgba(239,68,68,0.3)" stroke-width="1"/>
        </svg>
      </div>

      <!-- Texte -->
      <div class="text-block">
        <span class="badge">Erreur de connexion</span>
        <h1>Serveur inaccessible</h1>
        <p class="desc">
          Impossible de contacter l'API backend.<br>
          Vérifiez que le serveur est bien démarré sur
          <code>{{ apiBaseUrl }}</code> et réessayez.
        </p>
      </div>

      <!-- Feedback retry -->
      <div v-if="retryFailed" class="retry-feedback">
        Le serveur ne répond toujours pas.
      </div>

      <!-- Actions -->
      <div class="actions">
        <button class="btn btn-primary" :disabled="retrying" @click="retry">
          <span v-if="retrying" class="spinner"></span>
          <span v-else>↻</span>
          {{ retrying ? 'Connexion…' : 'Réessayer' }}
        </button>
      </div>

      <!-- Infos techniques -->
      <div class="tech-info">
        <span class="dot red"></span>
        API&nbsp;·&nbsp;<span class="mono">{{ apiBaseUrl }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.error-page {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: #040d1a;
  overflow: hidden;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}

/* Grille de fond */
.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
}

/* Halos colorés */
.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(100px);
  pointer-events: none;
}
.glow-1 {
  width: 480px;
  height: 480px;
  top: -120px;
  left: -80px;
  background: rgba(239, 68, 68, 0.08);
}
.glow-2 {
  width: 400px;
  height: 400px;
  bottom: -100px;
  right: -60px;
  background: rgba(37, 99, 235, 0.07);
}

/* Carte centrale */
.card {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  text-align: center;
  background: rgba(2, 6, 23, 0.8);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 24px;
  padding: 48px 56px;
  width: 480px;
  max-width: 92vw;
  box-shadow:
    0 0 0 1px rgba(239, 68, 68, 0.05),
    0 24px 80px rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(12px);
}

/* Icône */
.icon-wrap {
  width: 80px;
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 50%;
}
.error-icon {
  width: 48px;
  height: 48px;
}

/* Texte */
.badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.25);
  border-radius: 999px;
  padding: 3px 10px;
}

.text-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

h1 {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  color: #f1f5f9;
}

.desc {
  margin: 0;
  font-size: 14px;
  color: #94a3b8;
  line-height: 1.6;
}

code {
  font-family: 'JetBrains Mono', 'Fira Code', ui-monospace, monospace;
  font-size: 12px;
  background: rgba(148, 163, 184, 0.1);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 4px;
  padding: 1px 5px;
  color: #93c5fd;
}

/* Feedback */
.retry-feedback {
  font-size: 13px;
  color: #fca5a5;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 8px;
  padding: 8px 14px;
}

/* Actions */
.actions {
  display: flex;
  gap: 10px;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  border-radius: 999px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.8);
  color: #e5e7eb;
  transition: opacity 0.15s;
}
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary {
  background: linear-gradient(135deg, #1d4ed8, #4f46e5);
  border-color: transparent;
  color: #fff;
  box-shadow: 0 4px 20px rgba(37, 99, 235, 0.35);
}
.btn:hover:not(:disabled) { opacity: 0.88; }

/* Spinner */
.spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Infos techniques */
.tech-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #475569;
}
.dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}
.dot.red {
  background: #ef4444;
  box-shadow: 0 0 6px #ef4444;
  animation: pulse 1.8s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
.mono {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  color: #64748b;
}
</style>