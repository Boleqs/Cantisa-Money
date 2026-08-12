<template>
  <div class="page">
    <div class="card">

      <div class="brand">
        <span class="brand-logo">CMM</span>
        <span class="brand-version">Configuration initiale</span>
      </div>

      <h1 class="card-title">Bienvenue !</h1>
      <p class="card-subtitle">Avant de commencer, configurons le minimum pour que l'app soit utilisable.</p>

      <div class="steps">
        <div class="step" :class="{ active: step === 1, done: step > 1 }">1. Devise</div>
        <div class="step-sep"></div>
        <div class="step" :class="{ active: step === 2 }">2. Comptes</div>
      </div>

      <div v-if="error" class="alert">{{ error }}</div>

      <!-- ── Étape 1 : devise ─────────────────────────────────────────────── -->
      <form v-if="step === 1" class="form" @submit.prevent="goToStep2">
        <p class="hint">Toutes vos données seront affichées dans cette devise par défaut (modifiable plus tard dans Paramétrage).</p>

        <div class="field">
          <label for="cur-name">Nom de la devise</label>
          <input id="cur-name" v-model="currencyName" type="text" placeholder="Euro" required />
        </div>

        <div class="field-row">
          <div class="field">
            <label for="cur-code">Code (≤ 6 caractères)</label>
            <input id="cur-code" v-model="currencyShortName" type="text" maxlength="6" placeholder="EUR" required
              @input="currencyShortName = currencyShortName.toUpperCase()" />
          </div>
          <div class="field field-small">
            <label for="cur-fraction">Décimales</label>
            <input id="cur-fraction" v-model.number="currencyFraction" type="number" min="0" max="8" />
          </div>
        </div>

        <button type="submit" class="btn-submit" :disabled="!currencyName.trim() || !currencyShortName.trim()">
          Continuer
        </button>
      </form>

      <!-- ── Étape 2 : comptes ────────────────────────────────────────────── -->
      <div v-else class="form">
        <div class="choice-grid">
          <button
            type="button"
            class="choice-card"
            :class="{ selected: mode === 'preset' }"
            @click="mode = 'preset'"
          >
            <div class="choice-title">📋 Modèle standard</div>
            <div class="choice-desc">
              Un plan de comptes complet façon GnuCash : les comptes répondent à « à qui ? »
              (employeur, bailleur, assureur…), les catégories à « pourquoi ? » et les tags à
              « quoi ? ».
            </div>
            <ul class="preview-list">
              <li v-for="a in presetBaseAccounts" :key="a.name">{{ a.name }} <span class="muted">({{ a.account_type }})</span></li>
              <li v-for="g in presetAccountGroups" :key="g.root">
                {{ g.root }} <span class="muted">({{ g.total }} comptes — {{ g.children.join(', ') }})</span>
              </li>
            </ul>
            <div class="preview-cats">+ catégories (pourquoi) : {{ presetCategories.join(', ') }}</div>
            <div class="preview-cats">+ tags (quoi) : {{ presetTags.join(', ') }}</div>
          </button>

          <button
            type="button"
            class="choice-card"
            :class="{ selected: mode === 'manual' }"
            @click="mode = 'manual'"
          >
            <div class="choice-title">✎ Un seul compte</div>
            <div class="choice-desc">Créez juste un compte pour commencer, vous ajouterez le reste vous-même.</div>
          </button>
        </div>

        <template v-if="mode === 'manual'">
          <div class="field">
            <label for="acc-name">Nom du compte</label>
            <input id="acc-name" v-model="manualAccountName" type="text" placeholder="Compte courant" required />
          </div>
          <div class="field">
            <label for="acc-type">Type de compte</label>
            <select id="acc-type" v-model="manualAccountType">
              <option v-for="t in ACCOUNT_TYPES" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
        </template>

        <div class="actions-row">
          <button type="button" class="btn-secondary" :disabled="loading" @click="step = 1">Retour</button>
          <button
            type="button"
            class="btn-submit"
            :disabled="loading || (mode === 'manual' && !manualAccountName.trim())"
            @click="submit"
          >
            <span v-if="!loading">Terminer la configuration</span>
            <span v-else class="spinner-row"><span class="spinner"></span> Configuration…</span>
          </button>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'
import { useRouter } from 'vue-router'
import { refreshSettings } from '@/utils/settings.js'

const ACCOUNT_TYPES = ['Current', 'Assets', 'Income', 'Expense', 'Equity', 'Liability']

const router = useRouter()

const step = ref(1)
const error = ref('')
const loading = ref(false)

const currencyName = ref('Euro')
const currencyShortName = ref('EUR')
const currencyFraction = ref(2)

const mode = ref('preset')
const manualAccountName = ref('')
const manualAccountType = ref('Current')

// Doit rester synchronisé avec PRESET_ACCOUNTS/PRESET_CATEGORIES/PRESET_TAGS dans
// backend/routes/rt_onboarding.py — juste un résumé pour l'aperçu (35 comptes au total serait
// illisible en liste plate ici, donc regroupés par racine Revenus/Dépenses).
const presetBaseAccounts = [
  { name: 'Compte courant', account_type: 'Current' },
  { name: 'Épargne', account_type: 'Assets' },
]
const presetAccountGroups = [
  {
    root: 'Revenus', total: 11,
    children: ['Employeur(s)', 'Clients', 'Établissement bancaire', 'Locataire(s)', 'Organismes sociaux', 'Administration fiscale', 'Particuliers'],
  },
  {
    root: 'Dépenses', total: 22,
    children: ['Bailleur / Agence immobilière', 'Syndic', "Fournisseur d'énergie", 'Opérateur télécom', 'Assureurs', 'Banque (frais)', 'Administrations', 'Supermarchés', 'Restaurants', 'Transporteurs', 'Professionnels de santé', 'Établissements scolaires', 'Commerces', 'Particuliers'],
  },
]
const presetCategories = ['Logement', 'Alimentation', 'Transport', 'Santé', 'Assurances', 'Impôts et taxes', 'Loisirs & sorties', 'Habillement', 'Éducation', 'Famille & enfants', 'Cadeaux & dons', 'Salaire', 'Revenus financiers', 'Remboursements', 'Autres revenus']
const presetTags = ['Alimentaire', 'Vêtements', 'Électronique / High-tech', 'Carburant', 'Facture / Abonnement', 'Loyer', 'Titre de transport', 'Loisir / Divertissement', 'Santé / Médicaments', 'Matériel / Équipement', 'Service / Prestation', 'Cadeau']

function goToStep2() {
  error.value = ''
  step.value = 2
}

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await axios.post('/api/onboarding/setup', {
      currency_name: currencyName.value.trim(),
      currency_short_name: currencyShortName.value.trim().toUpperCase(),
      currency_fraction: currencyFraction.value,
      mode: mode.value,
      accounts: mode.value === 'manual'
        ? [{ name: manualAccountName.value.trim(), account_type: manualAccountType.value }]
        : [],
    })
    await refreshSettings()
    router.push('/Dashboard')
  } catch (e) {
    if (e?.response?.status === 409) {
      // Déjà configuré (double-soumission) — pas la peine d'effrayer l'utilisateur.
      await refreshSettings()
      router.push('/Dashboard')
      return
    }
    error.value = e?.response?.data?.response_data || e?.message || 'Erreur lors de la configuration.'
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
  padding: 24px;
}

.card {
  width: 560px;
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

.brand {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 16px;
}
.brand-logo {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -1px;
  background: linear-gradient(90deg, #60a5fa, #818cf8);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.brand-version { font-size: 11px; color: #4b5563; font-weight: 500; }

.card-title { margin: 0; font-size: 22px; font-weight: 700; color: #f1f5f9; }
.card-subtitle { margin: 2px 0 16px; font-size: 13px; color: #6b7280; }

.steps {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}
.step {
  font-size: 12px;
  font-weight: 600;
  color: #4b5563;
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.2);
}
.step.active { color: #60a5fa; border-color: rgba(96, 165, 250, 0.4); background: rgba(96, 165, 250, 0.08); }
.step.done { color: #34d399; border-color: rgba(52, 211, 153, 0.3); }
.step-sep { flex: 1; height: 1px; background: rgba(148, 163, 184, 0.15); }

.hint { font-size: 12px; color: #6b7280; margin: 0 0 4px; }

.form { display: flex; flex-direction: column; gap: 14px; }

.field { display: flex; flex-direction: column; gap: 6px; }
.field-row { display: flex; gap: 12px; }
.field-small { max-width: 110px; }

.field label { font-size: 12px; font-weight: 500; color: #9ca3af; letter-spacing: 0.02em; }
.field input, .field select {
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
.field input:focus, .field select:focus { border-color: #2563eb; }

.alert {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(239, 68, 68, 0.4);
  background: rgba(239, 68, 68, 0.08);
  color: #fca5a5;
  font-size: 13px;
}

.choice-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.choice-card {
  text-align: left;
  background: rgba(2, 6, 23, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 14px;
  padding: 14px;
  cursor: pointer;
  color: #e5e7eb;
  transition: border-color 0.15s, background 0.15s;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.choice-card:hover { border-color: rgba(96, 165, 250, 0.35); }
.choice-card.selected { border-color: #2563eb; background: rgba(37, 99, 235, 0.08); }
.choice-title { font-size: 14px; font-weight: 700; }
.choice-desc { font-size: 12px; color: #9ca3af; }
.preview-list { margin: 4px 0 0; padding-left: 16px; font-size: 12px; color: #cbd5e1; max-height: 130px; overflow-y: auto; }
.preview-list li { margin-bottom: 3px; line-height: 1.4; }
.preview-cats { font-size: 11px; color: #6b7280; margin-top: 4px; line-height: 1.5; }
.muted { color: #6b7280; }

.actions-row { display: flex; gap: 10px; margin-top: 4px; }
.actions-row .btn-submit { flex: 1; }

.btn-secondary {
  padding: 11px 16px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: transparent;
  color: #cbd5e1;
  font-size: 14px;
  cursor: pointer;
}
.btn-secondary:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-submit {
  margin-top: 4px;
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
.btn-submit:hover:not(:disabled) { opacity: 0.9; }
.btn-submit:disabled { opacity: 0.55; cursor: not-allowed; }

.spinner-row { display: inline-flex; align-items: center; gap: 8px; }
.spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: inline-block;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
