/**
 * Formatage de date respectant le réglage utilisateur (Paramétrage > Format de date), au lieu du
 * 'fr-FR' codé en dur qui traînait dans chaque vue — celles-ci important toutes leur propre
 * fmtDate() locale plutôt que d'utiliser ce module ne respectaient jamais ce réglage.
 */
import { dateFormat } from './settings.js'

/**
 * @param {string|Date|null|undefined} v - date ISO, timestamp ou objet Date
 * @param {{withTime?: boolean}} [opts]
 */
export function formatDate(v, opts = {}) {
  if (!v) return '—'
  const d = v instanceof Date ? v : new Date(v)
  if (Number.isNaN(d.getTime())) return '—'

  if (dateFormat.value === 'iso') {
    const datePart = d.toISOString().slice(0, 10)
    if (!opts.withTime) return datePart
    return `${datePart} ${d.toTimeString().slice(0, 5)}`
  }

  const locale = dateFormat.value || 'fr-FR'
  const dateOpts = { day: '2-digit', month: '2-digit', year: 'numeric' }
  if (opts.withTime) {
    return d.toLocaleDateString(locale, dateOpts) + ' ' + d.toLocaleTimeString(locale, { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString(locale, dateOpts)
}

/** Variante courte (jour/mois uniquement) pour les axes de graphiques — même ordre jour/mois que
 * le réglage utilisateur, sans l'année. */
export function formatDateShort(v) {
  if (!v) return '—'
  const d = v instanceof Date ? v : new Date(v)
  if (Number.isNaN(d.getTime())) return '—'
  if (dateFormat.value === 'iso') return d.toISOString().slice(5, 10)
  const locale = dateFormat.value || 'fr-FR'
  return d.toLocaleDateString(locale, { day: '2-digit', month: '2-digit' })
}
