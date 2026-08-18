<script setup>
import { ref, computed } from 'vue'
import { feature } from 'topojson-client'
import worldTopology from 'world-atlas/countries-50m.json'

const props = defineProps({
  countries: { type: Array, default: () => [] }, // [{country, value, percent}]
  unmappedPercent: { type: Number, default: 0 },
})

// Yahoo Finance (yfinance) renvoie des noms de pays qui ne correspondent pas toujours
// exactement à ceux de Natural Earth (source des tracés) — table de correspondance pour les
// écarts rencontrés en pratique sur des tickers réels. Un pays absent de cette table est
// utilisé tel quel (la plupart des noms coïncident déjà).
const COUNTRY_NAME_ALIASES = {
  'United States': 'United States of America',
  'USA': 'United States of America',
  'UK': 'United Kingdom',
  'UAE': 'United Arab Emirates',
  'Czech Republic': 'Czechia',
  'Ivory Coast': "Côte d'Ivoire",
  "Cote d'Ivoire": "Côte d'Ivoire",
  'Macau': 'Macao',
  'Vatican City': 'Vatican',
  'Democratic Republic of the Congo': 'Dem. Rep. Congo',
  'Republic of the Congo': 'Congo',
  'North Macedonia': 'Macedonia',
  'Cape Verde': 'Cabo Verde',
  'Swaziland': 'eSwatini',
  'Myanmar (Burma)': 'Myanmar',
  'British Virgin Islands': 'British Virgin Is.',
  'Cayman Islands': 'Cayman Is.',
  'U.S. Virgin Islands': 'U.S. Virgin Is.',
  'Faroe Islands': 'Faeroe Is.',
  'Trinidad & Tobago': 'Trinidad and Tobago',
  'Bosnia and Herzegovina': 'Bosnia and Herz.',
  'East Timor': 'Timor-Leste',
}

// Rampe séquentielle à une teinte (skill dataviz) — un seul indicateur continu (pondération %),
// pas de palette catégorielle nécessaire ici. Cet écran (comme Portfolio.vue/WealthForecast.vue,
// même groupe de nav) est sur fond sombre (#0b1220) : l'ancre séquentielle est donc inversée
// ("flips anchor in dark" — sur fond sombre, une valeur haute doit être claire/lumineuse pour
// se détacher, pas foncée) ; on reprend l'échelle bleue Tailwind déjà utilisée par --color-accent
// (#2563eb, base.css) plutôt qu'une rampe générique.
const SEQUENTIAL_BLUE = [
  '#172554', '#1e3a8a', '#1e40af', '#1d4ed8', '#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe',
]
const NO_DATA_FILL = '#1e293b' // même gris-ardoise que le reste du dashboard (Portfolio.vue) — "aucune position ici"

const WIDTH = 960
const HEIGHT = 500

function project([lon, lat]) {
  const x = (lon + 180) * (WIDTH / 360)
  const y = (90 - lat) * (HEIGHT / 180)
  return [x, y]
}

function ringToPath(ring) {
  // Projection équirectangulaire naïve (pas de découpe à l'antiméridien) : un anneau qui traverse
  // 180°/-180° (ex: la Russie côté Tchoukotka) verrait sinon son dernier et son premier point de
  // ce côté-là reliés par une ligne droite traversant toute la carte. On détecte le saut de
  // longitude (>180° d'un point au suivant) et on ouvre un nouveau sous-tracé à la place.
  let d = ''
  let prevX = null
  ring.forEach((pt, i) => {
    const [x, y] = project(pt)
    const jumped = prevX !== null && Math.abs(x - prevX) > WIDTH / 2
    d += `${i === 0 || jumped ? 'M' : 'L'}${x},${y}`
    prevX = x
  })
  return d + 'Z'
}

function geometryToPath(geometry) {
  if (!geometry) return ''
  if (geometry.type === 'Polygon') {
    return geometry.coordinates.map(ringToPath).join(' ')
  }
  if (geometry.type === 'MultiPolygon') {
    return geometry.coordinates.map(poly => poly.map(ringToPath).join(' ')).join(' ')
  }
  return ''
}

const geoFeatures = feature(worldTopology, worldTopology.objects.countries).features
  .filter(f => f.properties.name !== 'Antarctica')

const dataByName = computed(() => {
  const map = new Map()
  for (const c of props.countries) {
    const mapped = COUNTRY_NAME_ALIASES[c.country] || c.country
    map.set(mapped, c)
  }
  return map
})

const maxPercent = computed(() => props.countries.reduce((m, c) => Math.max(m, c.percent), 0))

function colorFor(percent) {
  if (!percent || !maxPercent.value) return NO_DATA_FILL
  const t = Math.min(1, percent / maxPercent.value)
  const idx = Math.round(t * (SEQUENTIAL_BLUE.length - 1))
  return SEQUENTIAL_BLUE[idx]
}

const countryPaths = computed(() => geoFeatures.map(f => {
  const entry = dataByName.value.get(f.properties.name)
  return {
    key: f.id || f.properties.name,
    name: entry ? entry.country : f.properties.name, // libellé d'origine (yfinance), pas le nom Natural Earth utilisé en interne pour l'appariement
    d: geometryToPath(f.geometry),
    percent: entry ? entry.percent : 0,
    fill: entry ? colorFor(entry.percent) : NO_DATA_FILL,
    hasData: !!entry,
  }
}))

const sortedCountries = computed(() => [...props.countries].sort((a, b) => b.percent - a.percent))

const svgEl = ref(null)
const hovered = ref(null) // { name, percent, x, y }

function showTooltip(entry, evt) {
  if (!entry.hasData) { hovered.value = null; return }
  const rect = svgEl.value.getBoundingClientRect()
  const clientX = evt.clientX ?? (rect.left + rect.width / 2)
  const clientY = evt.clientY ?? (rect.top + rect.height / 2)
  hovered.value = {
    name: entry.name,
    percent: entry.percent,
    x: clientX - rect.left,
    y: clientY - rect.top,
  }
}

function showTooltipOnFocus(entry, evt) {
  showTooltip(entry, { clientX: undefined, clientY: undefined, currentTarget: evt.currentTarget })
  if (!entry.hasData) return
  const rect = svgEl.value.getBoundingClientRect()
  const bbox = evt.target.getBoundingClientRect()
  hovered.value = {
    name: entry.name,
    percent: entry.percent,
    x: bbox.left + bbox.width / 2 - rect.left,
    y: bbox.top + bbox.height / 2 - rect.top,
  }
}

function hideTooltip() {
  hovered.value = null
}

function fmtPct(p) {
  return `${p.toFixed(p < 10 ? 2 : 1)} %`
}
</script>

<template>
  <div class="world-map-root">
    <div class="map-wrap" ref="svgEl">
      <svg :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" preserveAspectRatio="xMidYMid meet" class="map-svg">
        <path
          v-for="c in countryPaths"
          :key="c.key"
          :d="c.d"
          :fill="c.fill"
          class="country"
          :class="{ 'has-data': c.hasData }"
          :tabindex="c.hasData ? 0 : -1"
          :aria-label="c.hasData ? `${c.name} : ${fmtPct(c.percent)}` : null"
          @pointermove="showTooltip(c, $event)"
          @pointerleave="hideTooltip"
          @focus="showTooltipOnFocus(c, $event)"
          @blur="hideTooltip"
        />
      </svg>

      <div
        v-if="hovered"
        class="map-tooltip"
        :style="{ left: hovered.x + 'px', top: hovered.y + 'px' }"
      >
        <div class="tooltip-value">{{ fmtPct(hovered.percent) }}</div>
        <div class="tooltip-label">{{ hovered.name }}</div>
      </div>
    </div>

    <div class="map-legend">
      <span class="legend-label">0&nbsp;%</span>
      <div class="legend-gradient"></div>
      <span class="legend-label">{{ maxPercent ? fmtPct(maxPercent) : '—' }}</span>
      <span class="legend-nodata"><i class="legend-swatch"></i>Aucune position</span>
    </div>

    <div v-if="sortedCountries.length" class="country-list">
      <div v-for="c in sortedCountries" :key="c.country" class="country-row">
        <span class="country-row-name">{{ c.country }}</span>
        <div class="country-row-bar-track">
          <div class="country-row-bar" :style="{ width: (c.percent / (maxPercent || 1) * 100) + '%', background: colorFor(c.percent) }"></div>
        </div>
        <span class="country-row-pct">{{ fmtPct(c.percent) }}</span>
      </div>
    </div>

    <p v-if="unmappedPercent > 0" class="unmapped-note">
      {{ fmtPct(unmappedPercent) }} du portefeuille actions/ETF n'a pas pu être rattaché à un pays
      (donnée indisponible sur Yahoo Finance) et n'est pas comptabilisé ci-dessus.
    </p>
  </div>
</template>

<style scoped>
.world-map-root {
  display: flex;
  flex-direction: column;
  gap: 1em;
}

.map-wrap {
  position: relative;
  width: 100%;
}

.map-svg {
  width: 100%;
  height: auto;
  display: block;
}

.country {
  stroke: #0b1220;
  stroke-width: 0.5;
  transition: filter 0.15s ease;
  outline: none;
}

.country.has-data {
  cursor: pointer;
}

.country.has-data:hover,
.country.has-data:focus-visible {
  filter: brightness(1.12);
}

.country:focus-visible {
  stroke: #60a5fa;
  stroke-width: 1.5;
}

.map-tooltip {
  position: absolute;
  transform: translate(-50%, -100%);
  margin-top: -10px;
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #e5e7eb;
  border-radius: 8px;
  padding: 0.4em 0.7em;
  font-size: 0.85em;
  pointer-events: none;
  white-space: nowrap;
  z-index: 5;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

.tooltip-value {
  font-weight: 600;
  color: #e5e7eb;
}

.tooltip-label {
  color: #9ca3af;
}

.map-legend {
  display: flex;
  align-items: center;
  gap: 0.6em;
  font-size: 0.85em;
  color: #9ca3af;
}

.legend-gradient {
  width: 140px;
  height: 10px;
  border-radius: 4px;
  background: linear-gradient(to right, #172554, #bfdbfe);
}

.legend-nodata {
  display: flex;
  align-items: center;
  gap: 0.4em;
  margin-left: 1em;
}

.legend-swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  background: #1e293b;
  display: inline-block;
}

.country-list {
  display: flex;
  flex-direction: column;
  gap: 0.4em;
  max-width: 480px;
}

.country-row {
  display: grid;
  grid-template-columns: 9em 1fr 4em;
  align-items: center;
  gap: 0.6em;
  font-size: 0.9em;
}

.country-row-name {
  color: #e5e7eb;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.country-row-bar-track {
  height: 8px;
  border-radius: 4px;
  background: rgba(148, 163, 184, 0.15);
  overflow: hidden;
}

.country-row-bar {
  height: 100%;
  border-radius: 4px;
}

.country-row-pct {
  text-align: right;
  color: #9ca3af;
  font-variant-numeric: tabular-nums;
}

.unmapped-note {
  font-size: 0.85em;
  color: #6b7280;
  margin: 0;
}
</style>
