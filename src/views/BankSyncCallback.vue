<template>
  <div class="page">
    <div class="card">
      <template v-if="status === 'pending'">
        <p>Finalisation de la connexion bancaire…</p>
      </template>
      <template v-else-if="status === 'success'">
        <p class="ok">✓ Autorisation réussie — {{ accountCount }} compte(s) trouvé(s) côté banque.</p>
        <p class="hint">Reste à choisir à quel compte Cantisa lier chacun.</p>
        <button class="btn btn-primary" @click="goBack">Retour aux institutions</button>
      </template>
      <template v-else>
        <p class="error">{{ errorMessage }}</p>
        <button class="btn" @click="goBack">Retour aux institutions</button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import axios from 'axios'

const route = useRoute()
const router = useRouter()

const status = ref('pending')
const errorMessage = ref('')
const accountCount = ref(0)

function goBack() {
  router.push('/institutions')
}

onMounted(async () => {
  const { code, state, error: authError } = route.query
  if (authError) {
    status.value = 'error'
    errorMessage.value = `Autorisation refusée par la banque : ${authError}`
    return
  }
  if (!code || !state) {
    status.value = 'error'
    errorMessage.value = 'Paramètres de retour manquants (code/state).'
    return
  }
  try {
    const { data } = await axios.post('/api/bank-sync/callback', { code, state })
    accountCount.value = Array.isArray(data?.response_data) ? data.response_data.length : 1
    status.value = 'success'
  } catch (e) {
    status.value = 'error'
    errorMessage.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la finalisation'
  }
})
</script>

<style scoped>
.page {
  padding: 28px;
  color: #e5e7eb;
  background: #0b1220;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}
.card {
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 14px;
  padding: 32px;
  text-align: center;
  min-width: 320px;
}
.ok { color: #4ade80; font-size: 16px; margin-bottom: 4px; }
.hint { color: #9ca3af; font-size: 13px; margin: 0 0 16px; }
.error { color: #f87171; font-size: 15px; margin-bottom: 16px; }
.btn {
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.7);
  color: #e5e7eb;
  padding: 10px 14px;
  border-radius: 10px;
  cursor: pointer;
}
.btn-primary { background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2)); border-color: transparent; color: #fff; }
</style>
