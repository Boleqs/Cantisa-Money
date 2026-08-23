<template>
  <div class="rte-backdrop" @click.self="emit('cancel')">
    <div class="rte-modal">
      <h2>{{ isEdit ? 'Modifier le gabarit' : 'Créer un gabarit' }}</h2>
      <p class="rte-subtitle">
        Choisis une étiquette puis clique-glisse sur le ticket pour délimiter la zone correspondante — ces zones
        guideront l'OCR sur les prochains tickets du même marchand.
      </p>

      <div class="rte-body">
        <div class="rte-canvas-col">
          <div class="rte-palette">
            <button
              v-for="l in LABELS" :key="l.key" type="button"
              class="rte-chip" :class="[l.key, { active: activeLabel === l.key }]"
              @click="activeLabel = l.key"
            ><span class="dot"></span>{{ l.name }}</button>
          </div>

          <div class="rte-stage">
            <img
              ref="imgEl"
              :src="imageUrl"
              class="rte-img"
              draggable="false"
              @mousedown="onMouseDown"
            />
            <div v-for="(z, i) in zones" :key="i" class="rte-box" :class="z.label" :style="boxStyle(z)">
              <span class="rte-tag">{{ labelName(z.label) }}</span>
            </div>
            <div v-if="drawingBox" class="rte-box drawing" :class="drawingBox.label" :style="boxStyle(drawingBox)"></div>
          </div>
        </div>

        <div class="rte-side">
          <label class="rte-field">Marchand *
            <input v-model="merchantNameLocal" placeholder="ex: Carrefour" />
          </label>

          <div class="rte-field">
            <span class="rte-field-label">Zones ({{ zones.length }})</span>
            <div class="rte-zone-list">
              <div v-if="!zones.length" class="rte-empty">Aucune zone définie pour l'instant.</div>
              <div v-for="(z, i) in zones" :key="i" class="rte-zone-row">
                <span class="swatch" :class="z.label"></span>
                <span class="zname">{{ labelName(z.label) }}</span>
                <button type="button" class="zremove" title="Supprimer" @click="zones.splice(i, 1)">✕</button>
              </div>
            </div>
          </div>

          <p v-if="error" class="rte-error">{{ error }}</p>
          <p class="rte-note">Les zones sont mémorisées en pourcentage de l'image, pas en pixels — elles s'appliqueront même si une prochaine photo du même ticket est cadrée un peu différemment.</p>
        </div>
      </div>

      <div class="rte-actions">
        <button type="button" class="btn" @click="emit('cancel')">Annuler</button>
        <button type="button" class="btn btn-primary" :disabled="!canSave || saving" @click="save">
          {{ saving ? 'Enregistrement…' : (isEdit ? 'Mettre à jour le gabarit' : 'Enregistrer le gabarit') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import axios from 'axios'

const props = defineProps({
  imageUrl: { type: String, required: true },
  merchantName: { type: String, default: '' },
  // { id, merchant_name, zones } — fourni en mode édition (met à jour via PATCH au lieu de POST).
  existingTemplate: { type: Object, default: null },
})
const emit = defineEmits(['saved', 'cancel'])

const LABELS = [
  { key: 'marchand', name: 'Marchand' },
  { key: 'date', name: 'Date' },
  { key: 'total', name: 'Total' },
  { key: 'articles', name: 'Zone articles' },
]
function labelName(key) {
  return LABELS.find(l => l.key === key)?.name || key
}

const isEdit = computed(() => !!props.existingTemplate)
const merchantNameLocal = ref(props.existingTemplate?.merchant_name || props.merchantName || '')
const zones = ref(props.existingTemplate ? props.existingTemplate.zones.map(z => ({ ...z })) : [])
const activeLabel = ref('marchand')
const error = ref('')
const saving = ref(false)

const imgEl = ref(null)
const drawingBox = ref(null)
let dragStart = null

function boxStyle(z) {
  return { top: z.top + '%', left: z.left + '%', width: z.width + '%', height: z.height + '%' }
}

function relativePos(e) {
  const rect = imgEl.value.getBoundingClientRect()
  const x = Math.min(Math.max(e.clientX - rect.left, 0), rect.width)
  const y = Math.min(Math.max(e.clientY - rect.top, 0), rect.height)
  return { xPct: rect.width ? (x / rect.width) * 100 : 0, yPct: rect.height ? (y / rect.height) * 100 : 0 }
}

function onMouseDown(e) {
  e.preventDefault()
  const p = relativePos(e)
  dragStart = p
  drawingBox.value = { label: activeLabel.value, top: p.yPct, left: p.xPct, width: 0, height: 0 }
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

function onMouseMove(e) {
  if (!drawingBox.value || !dragStart) return
  const p = relativePos(e)
  const left = Math.min(p.xPct, dragStart.xPct)
  const top = Math.min(p.yPct, dragStart.yPct)
  const width = Math.abs(p.xPct - dragStart.xPct)
  const height = Math.abs(p.yPct - dragStart.yPct)
  drawingBox.value = { ...drawingBox.value, left, top, width, height }
}

function onMouseUp() {
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  if (drawingBox.value && drawingBox.value.width > 1.5 && drawingBox.value.height > 1) {
    zones.value.push({ ...drawingBox.value })
  }
  drawingBox.value = null
  dragStart = null
}

const canSave = computed(() => merchantNameLocal.value.trim().length > 0 && zones.value.length > 0)

async function save() {
  if (!canSave.value) return
  saving.value = true
  error.value = ''
  try {
    const payload = {
      merchant_name: merchantNameLocal.value.trim(),
      zones: zones.value.map(z => ({
        label: z.label,
        top: Math.round(z.top * 100) / 100,
        left: Math.round(z.left * 100) / 100,
        width: Math.round(z.width * 100) / 100,
        height: Math.round(z.height * 100) / 100,
      })),
    }
    const res = isEdit.value
      ? await axios.patch('/api/receipt-templates', { template_id: props.existingTemplate.id, ...payload })
      : await axios.post('/api/receipt-templates', payload)
    emit('saved', res.data?.response_data)
  } catch (e) {
    error.value = e?.response?.data?.response_data || e?.message || "Erreur lors de l'enregistrement du gabarit"
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.rte-backdrop {
  position: fixed; inset: 0; z-index: 200;
  background: rgba(2,6,23,0.72);
  display: flex; align-items: center; justify-content: center;
  padding: 20px;
}
.rte-modal {
  background: #0f172a;
  border: 1px solid rgba(148,163,184,0.2);
  border-radius: 16px;
  padding: 24px;
  width: min(880px, 100%);
  max-height: 90vh;
  overflow-y: auto;
  display: flex; flex-direction: column; gap: 6px;
}
.rte-modal h2 { margin: 0; font-size: 18px; color: #e5e7eb; }
.rte-subtitle { margin: 0 0 12px; font-size: 12.5px; color: #9ca3af; line-height: 1.6; }

.rte-body { display: grid; grid-template-columns: minmax(0, 1fr) 240px; gap: 18px; align-items: start; }
@media (max-width: 720px) { .rte-body { grid-template-columns: 1fr; } }

.rte-palette { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.rte-chip {
  display: inline-flex; align-items: center; gap: 6px;
  border: 1px solid rgba(148,163,184,0.28); border-radius: 999px;
  padding: 6px 12px; font-size: 12px; font-weight: 600; cursor: pointer;
  background: rgba(2,6,23,0.4); color: #9ca3af;
}
.rte-chip .dot { width: 8px; height: 8px; border-radius: 50%; }
.rte-chip.marchand .dot { background: #a78bfa; }
.rte-chip.date .dot { background: #fbbf24; }
.rte-chip.total .dot { background: #34d399; }
.rte-chip.articles .dot { background: #60a5fa; }
.rte-chip.active.marchand { background: #a78bfa; color: #fff; border-color: transparent; }
.rte-chip.active.date { background: #fbbf24; color: #241a02; border-color: transparent; }
.rte-chip.active.total { background: #34d399; color: #04241a; border-color: transparent; }
.rte-chip.active.articles { background: #60a5fa; color: #fff; border-color: transparent; }

.rte-stage {
  position: relative;
  display: inline-block;
  max-width: 100%;
  border-radius: 8px;
  overflow: hidden;
  background: rgba(2,6,23,0.4);
}
.rte-img { display: block; max-width: 100%; max-height: 58vh; cursor: crosshair; user-select: none; }

.rte-box { position: absolute; border: 2px solid; border-radius: 3px; pointer-events: none; }
.rte-box .rte-tag {
  position: absolute; top: -19px; left: -2px;
  font-size: 10px; font-weight: 700; letter-spacing: 0.02em;
  padding: 2px 6px; border-radius: 4px 4px 4px 0; color: #fff; white-space: nowrap;
}
.rte-box.drawing { border-style: dashed; }
.rte-box.marchand { border-color: #a78bfa; background: rgba(167,139,250,0.16); }
.rte-box.marchand .rte-tag { background: #a78bfa; }
.rte-box.date { border-color: #fbbf24; background: rgba(251,191,36,0.16); }
.rte-box.date .rte-tag { background: #fbbf24; color: #241a02; }
.rte-box.total { border-color: #34d399; background: rgba(52,211,153,0.16); }
.rte-box.total .rte-tag { background: #34d399; color: #04241a; }
.rte-box.articles { border-color: #60a5fa; background: rgba(96,165,250,0.16); }
.rte-box.articles .rte-tag { background: #60a5fa; }

.rte-side { display: flex; flex-direction: column; gap: 14px; }
.rte-field { display: flex; flex-direction: column; gap: 6px; font-size: 12.5px; color: #9ca3af; }
.rte-field input {
  background: rgba(15,23,42,0.7); border: 1px solid rgba(148,163,184,0.25);
  border-radius: 8px; padding: 8px 10px; color: #e5e7eb; font-size: 13px;
}
.rte-field-label { font-size: 12.5px; color: #9ca3af; }

.rte-zone-list { display: flex; flex-direction: column; gap: 6px; margin-top: 4px; }
.rte-zone-row {
  display: flex; align-items: center; gap: 8px;
  border: 1px solid rgba(148,163,184,0.15); border-radius: 8px;
  padding: 7px 9px; background: rgba(2,6,23,0.35); font-size: 12px;
}
.rte-zone-row .swatch { width: 9px; height: 9px; border-radius: 3px; flex-shrink: 0; }
.rte-zone-row .swatch.marchand { background: #a78bfa; }
.rte-zone-row .swatch.date { background: #fbbf24; }
.rte-zone-row .swatch.total { background: #34d399; }
.rte-zone-row .swatch.articles { background: #60a5fa; }
.rte-zone-row .zname { flex: 1; font-weight: 600; color: #e5e7eb; }
.rte-zone-row .zremove { background: none; border: none; color: #64748b; cursor: pointer; font-size: 12px; padding: 2px 4px; border-radius: 6px; }
.rte-zone-row .zremove:hover { color: #f87171; background: rgba(248,113,113,0.1); }
.rte-empty { font-size: 12px; color: #64748b; }

.rte-error { font-size: 12px; color: #fca5a5; margin: 0; }
.rte-note { font-size: 11px; color: #64748b; line-height: 1.55; margin: 0; }

.rte-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.btn {
  border: 1px solid rgba(148,163,184,0.25); background: rgba(15,23,42,0.7); color: #e5e7eb;
  padding: 9px 16px; border-radius: 10px; cursor: pointer; font-size: 13px;
}
.btn:hover { background: rgba(148,163,184,0.1); }
.btn-primary { background: linear-gradient(90deg, var(--color-accent), var(--color-accent-2)); border-color: transparent; color: #fff; }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
