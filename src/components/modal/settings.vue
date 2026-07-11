<template>
  <div class="overlay" @click.self="$emit('close')">
    <div class="modal">
      <!-- Header -->
      <div class="modal-header">
        <h2 class="modal-title">Paramètres</h2>
        <button class="close-btn" @click="$emit('close')">✕</button>
      </div>

      <!-- Sidebar -->
      <section class="section">
        <h3 class="section-title">Sidebar</h3>

        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-name">Replier au démarrage</span>
            <span class="setting-desc">La sidebar sera réduite à l'ouverture de l'application.</span>
          </div>
          <button
            :class="['toggle', { on: collapseOnStart }]"
            @click="collapseOnStart = !collapseOnStart"
          >
            <span class="toggle-thumb" />
          </button>
        </div>

        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-name">État actuel</span>
            <span class="setting-desc">{{ collapsed ? 'Sidebar repliée' : 'Sidebar dépliée' }}</span>
          </div>
          <button class="btn btn-secondary" @click="toggleSidebar">
            {{ collapsed ? '↔ Déplier' : '↩ Replier' }}
          </button>
        </div>
      </section>

      <hr class="divider" />

      <!-- Affichage -->
      <section class="section">
        <h3 class="section-title">Affichage</h3>

        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-name">Devise par défaut</span>
            <span class="setting-desc">Symbole affiché dans les montants.</span>
          </div>
          <select v-model="currency" class="select">
            <option value="EUR">€ Euro</option>
            <option value="USD">$ Dollar</option>
            <option value="GBP">£ Livre</option>
            <option value="CHF">CHF Franc suisse</option>
          </select>
        </div>

        <div class="setting-row">
          <div class="setting-label">
            <span class="setting-name">Format de date</span>
            <span class="setting-desc">Exemple : {{ dateExample }}</span>
          </div>
          <select v-model="dateFormat" class="select">
            <option value="fr-FR">JJ/MM/AAAA</option>
            <option value="en-GB">DD/MM/YYYY</option>
            <option value="en-US">MM/DD/YYYY</option>
            <option value="iso">AAAA-MM-JJ</option>
          </select>
        </div>
      </section>

      <hr class="divider" />

      <!-- Actions -->
      <div class="footer">
        <button class="btn btn-ghost" @click="resetAll">Réinitialiser les préférences</button>
        <button class="btn btn-primary" @click="save">Enregistrer</button>
      </div>

      <p v-if="saved" class="msg success">Préférences enregistrées.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { collapsed, toggleSidebar } from '@/components/sidebar/state.js'
import { currency as settingsCurrency, dateFormat as settingsDateFormat, saveSettings } from '@/utils/settings.js'

defineEmits(['close'])

// ── Keys ─────────────────────────────────────────────────────────────────────
const KEY_COLLAPSE  = 'cmm_sidebar_collapsed_on_start'

// ── Local state ───────────────────────────────────────────────────────────────
const collapseOnStart = ref(false)
const currency        = ref('EUR')
const dateFormat      = ref('fr-FR')
const saved           = ref(false)

// ── Computed preview ──────────────────────────────────────────────────────────
const dateExample = computed(() => {
  const d = new Date()
  if (dateFormat.value === 'iso') return d.toISOString().slice(0, 10)
  return d.toLocaleDateString(dateFormat.value)
})

// ── Persist ───────────────────────────────────────────────────────────────────
function load() {
  try {
    collapseOnStart.value = localStorage.getItem(KEY_COLLAPSE) === 'true'
  } catch {}
  currency.value   = settingsCurrency.value
  dateFormat.value = settingsDateFormat.value
}

async function save() {
  try {
    localStorage.setItem(KEY_COLLAPSE, String(collapseOnStart.value))
  } catch {}
  await saveSettings({ currency: currency.value, dateFormat: dateFormat.value })
  saved.value = true
  setTimeout(() => { saved.value = false }, 2500)
}

function resetAll() {
  collapseOnStart.value = false
  currency.value        = 'EUR'
  dateFormat.value      = 'fr-FR'
  save()
}

onMounted(load)
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
  width: 460px;
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

/* Section */
.section { display: flex; flex-direction: column; gap: 14px; }
.section-title {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: #6b7280;
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

/* Row */
.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.setting-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}
.setting-name { font-size: 14px; color: #e5e7eb; }
.setting-desc { font-size: 12px; color: #6b7280; }

/* Toggle switch */
.toggle {
  position: relative;
  width: 42px;
  height: 24px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.2);
  border: none;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.2s;
  padding: 0;
}
.toggle.on { background: #2563eb; }
.toggle-thumb {
  position: absolute;
  top: 3px;
  left: 3px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #fff;
  transition: transform 0.2s;
  display: block;
}
.toggle.on .toggle-thumb { transform: translateX(18px); }

/* Select */
.select {
  background: rgba(15, 23, 42, 0.7);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  color: #e5e7eb;
  padding: 7px 10px;
  font-size: 13px;
  cursor: pointer;
  outline: none;
  flex-shrink: 0;
}
.select:focus { border-color: #2563eb; }

/* Divider */
.divider {
  border: none;
  border-top: 1px solid rgba(148, 163, 184, 0.12);
  margin: 0;
}

/* Footer */
.footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

/* Buttons */
.btn {
  padding: 9px 16px;
  border-radius: 9px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: opacity 0.15s, background 0.15s;
}
.btn-primary {
  background: linear-gradient(90deg, #2563eb, #4f46e5);
  color: #fff;
}
.btn-primary:hover { opacity: 0.88; }
.btn-secondary {
  background: rgba(148, 163, 184, 0.1);
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #e5e7eb;
}
.btn-secondary:hover { background: rgba(148, 163, 184, 0.18); }
.btn-ghost {
  background: transparent;
  color: #6b7280;
  font-size: 12px;
  padding: 9px 0;
}
.btn-ghost:hover { color: #fca5a5; }

/* Message */
.msg { margin: 0; font-size: 13px; text-align: center; }
.msg.success { color: #86efac; }
</style>
