/**
 * Couleur d'accent personnalisable (point 10 du backlog UI/UX) — portée volontairement limitée à
 * la sidebar et aux boutons/liens primaires (.btn-primary), pas à toute l'app (badges d'état,
 * couleurs sémantiques vert/rouge de gain-perte, etc. restent fixes).
 *
 * Stockage en localStorage uniquement, comme "Replier la sidebar au démarrage" dans Parametres.vue
 * — préférence d'affichage locale, pas une donnée utilisateur à synchroniser en base.
 */
const KEY_ACCENT = 'cmm_accent_color'
export const DEFAULT_ACCENT = '#2563eb'

function hexToHsl(hex) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex)
  if (!m) return null
  const r = parseInt(m[1].slice(0, 2), 16) / 255
  const g = parseInt(m[1].slice(2, 4), 16) / 255
  const b = parseInt(m[1].slice(4, 6), 16) / 255
  const max = Math.max(r, g, b), min = Math.min(r, g, b)
  let h, s
  const l = (max + min) / 2
  if (max === min) {
    h = s = 0
  } else {
    const d = max - min
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min)
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break
      case g: h = (b - r) / d + 2; break
      default: h = (r - g) / d + 4
    }
    h /= 6
  }
  return { h: h * 360, s: s * 100, l: l * 100 }
}

function hslToHex(h, s, l) {
  h = ((h % 360) + 360) % 360
  s = Math.min(100, Math.max(0, s)) / 100
  l = Math.min(100, Math.max(0, l)) / 100
  const k = n => (n + h / 30) % 12
  const a = s * Math.min(l, 1 - l)
  const f = n => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)))
  const toHex = v => Math.round(v * 255).toString(16).padStart(2, '0')
  return `#${toHex(f(0))}${toHex(f(8))}${toHex(f(4))}`
}

/** Applique une couleur d'accent : normalise sa teinte pour rester lisible (texte blanc dessus)
 * puis dérive les variantes sidebar (fond sombre, survol, actif) par décalage de luminosité —
 * même logique que la palette bleue par défaut (#2563eb bouton / #1a4396 fond sidebar). */
export function applyAccentColor(hex) {
  const hsl = hexToHsl(hex)
  if (!hsl) return
  const { h, s } = hsl

  const accent = hslToHex(h, Math.max(s, 55), 52)
  const accent2 = hslToHex(h + 26, Math.max(s, 55), 52)
  const sidebarBg = hslToHex(h, Math.max(s, 45), 28)
  const sidebarHover = hslToHex(h, Math.max(s, 45), 48)
  const sidebarActive = hslToHex(h, Math.max(s - 15, 20), 62)

  const root = document.documentElement.style
  root.setProperty('--color-accent', accent)
  root.setProperty('--color-accent-2', accent2)
  root.setProperty('--sidebar-bg-color', sidebarBg)
  root.setProperty('--sidebar-item-hover', sidebarHover)
  root.setProperty('--sidebar-item-active', sidebarActive)
}

export function loadAccentColor() {
  let stored
  try {
    stored = localStorage.getItem(KEY_ACCENT)
  } catch {
    stored = null
  }
  applyAccentColor(stored || DEFAULT_ACCENT)
  return stored || DEFAULT_ACCENT
}

export function saveAccentColor(hex) {
  applyAccentColor(hex)
  try {
    localStorage.setItem(KEY_ACCENT, hex)
  } catch {}
}

export function resetAccentColor() {
  try {
    localStorage.removeItem(KEY_ACCENT)
  } catch {}
  applyAccentColor(DEFAULT_ACCENT)
}
