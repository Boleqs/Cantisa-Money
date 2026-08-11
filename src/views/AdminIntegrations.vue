<template>
  <div class="page">
    <header class="page-header">
      <div class="title-block">
        <h1>Administration — Intégrations</h1>
        <p class="subtitle">
          Configuration des services externes utilisés par l'application. Ces réglages sont globaux
          à l'instance (pas propres à un utilisateur) et persistent entre les redémarrages, y compris
          en Docker.
        </p>
      </div>
    </header>

    <div class="settings-card">
      <div class="card-header">
        <h3 class="card-title">Enable Banking — synchro bancaire</h3>
        <span class="status-badge" :class="{ ok: config.key_configured }">
          {{ config.key_configured ? 'Configuré ✓' : 'Non configuré' }}
        </span>
      </div>

      <label>UUID de l'application
        <input v-model="form.app_id" type="text" placeholder="ex: 3fa85f64-5717-4562-b3fc-2c963f66afa6" autocomplete="off" />
      </label>

      <label>Clé privée (.pem)
        <div class="file-row">
          <button type="button" class="btn" @click="keyInput?.click()">Choisir un fichier…</button>
          <span class="file-name">{{ keyFileName || (config.key_configured ? 'Clé déjà enregistrée (non affichée)' : 'Aucun fichier choisi') }}</span>
          <input ref="keyInput" type="file" accept=".pem,application/x-pem-file,text/plain" style="display: none" @change="onKeyFileChosen" />
        </div>
        <span class="field-hint">Téléchargée au Control Panel Enable Banking à l'enregistrement de l'application. Jamais réaffichée une fois enregistrée.</span>
      </label>

      <label>URL de callback (redirect_url)
        <input v-model="form.redirect_url" type="text" placeholder="https://localhost:5173/bank-sync/callback" autocomplete="off" />
        <span class="field-hint">Doit être whitelistée à l'identique au Control Panel Enable Banking.</span>
      </label>

      <div v-if="saveError" class="modal-error">{{ saveError }}</div>

      <div class="actions-row">
        <button class="btn btn-primary" :disabled="saving" @click="save">
          {{ saving ? 'Enregistrement…' : 'Enregistrer' }}
        </button>
        <button class="btn" :disabled="!config.key_configured || testing" @click="test">
          {{ testing ? 'Test…' : 'Tester la connexion' }}
        </button>
        <span v-if="testResult" class="test-result" :class="{ error: testError }">{{ testResult }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'

const config = reactive({ app_id: '', redirect_url: '', key_configured: false })
const form = reactive({ app_id: '', redirect_url: '' })
const keyInput = ref(null)
const keyFile = ref(null)
const keyFileName = ref('')
const saving = ref(false)
const saveError = ref('')
const testing = ref(false)
const testResult = ref('')
const testError = ref(false)

async function loadConfig() {
  const { data } = await axios.get('/api/admin/bank-sync/config')
  Object.assign(config, data.response_data)
  form.app_id = config.app_id
  form.redirect_url = config.redirect_url || `${window.location.origin}/bank-sync/callback`
}

function onKeyFileChosen(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  keyFile.value = file
  keyFileName.value = file.name
}

async function save() {
  saving.value = true
  saveError.value = ''
  testResult.value = ''
  try {
    const formData = new FormData()
    formData.append('app_id', form.app_id || '')
    formData.append('redirect_url', form.redirect_url || '')
    if (keyFile.value) formData.append('private_key', keyFile.value)
    const { data } = await axios.put('/api/admin/bank-sync/config', formData)
    Object.assign(config, data.response_data)
    keyFile.value = null
    keyFileName.value = ''
  } catch (e) {
    saveError.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    saving.value = false
  }
}

async function test() {
  testing.value = true
  testResult.value = ''
  testError.value = false
  try {
    const { data } = await axios.get('/api/bank-sync/aspsps', { params: { country: 'FR' } })
    const count = data.response_data?.length || 0
    testResult.value = `OK — ${count} banque${count > 1 ? 's' : ''} trouvée${count > 1 ? 's' : ''} (FR)`
  } catch (e) {
    testError.value = true
    testResult.value = e?.response?.data?.response_data || e?.message || 'Erreur inconnue'
  } finally {
    testing.value = false
  }
}

onMounted(loadConfig)
</script>

<style scoped>
.page {
  padding: 28px;
  color: #e5e7eb;
  background: #0b1220;
  min-height: 100vh;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial;
}
.page-header { margin-bottom: 28px; }
.title-block h1 { margin: 0; font-size: 28px; }
.subtitle { margin: 6px 0 0; color: #9ca3af; font-size: 14px; max-width: 720px; line-height: 1.6; }

.settings-card {
  background: #1e293b;
  border: 1px solid rgba(148,163,184,0.1);
  border-radius: 14px;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
  max-width: 560px;
}
.card-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.card-title { margin: 0; font-size: 13px; font-weight: 700; color: #64748b; text-transform: uppercase; letter-spacing: 0.07em; }

.status-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
  color: #94a3b8;
  background: rgba(148,163,184,0.12);
}
.status-badge.ok { color: #4ade80; background: rgba(74,222,128,0.12); }

label { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #9ca3af; }
input {
  background: rgba(15,23,42,0.7);
  border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px;
  padding: 8px 10px;
  color: #e5e7eb;
  font-size: 14px;
}
.field-hint { font-size: 12px; color: #6b7280; }

.file-row { display: flex; align-items: center; gap: 12px; }
.file-name { font-size: 13px; color: #cbd5e1; }

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

.actions-row { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.test-result { font-size: 13px; color: #4ade80; }
.test-result.error { color: #fca5a5; }

.modal-error {
  font-size: 13px;
  color: #fca5a5;
  background: rgba(239,68,68,0.08);
  border: 1px solid rgba(239,68,68,0.3);
  border-radius: 8px;
  padding: 8px 10px;
}
</style>
