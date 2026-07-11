/** Référentiel des indicateurs du score de notation d'actions — sans dépendance, pour éviter
 * un import circulaire entre marketScore.js (calcul) et settings.js (persistance). */
export const DEFAULT_METRICS = [
  { key: 'pe_trailing',      label: 'P/E (trailing)',   direction: 'lower', great: 10,  bad: 35  },
  { key: 'pe_forward',       label: 'P/E (forward)',    direction: 'lower', great: 10,  bad: 35  },
  { key: 'pb_ratio',         label: 'P/B',              direction: 'lower', great: 1,   bad: 5   },
  { key: 'dividend_yield',   label: 'Dividende',        direction: 'higher', great: 5,  bad: 0   },
  { key: 'roe',              label: 'ROE',              direction: 'higher', great: 20, bad: 0   },
  { key: 'roa',              label: 'ROA',              direction: 'higher', great: 15, bad: 0   },
  { key: 'net_margin',       label: 'Marge nette',      direction: 'higher', great: 25, bad: 0   },
  { key: 'gross_margin',     label: 'Marge brute',      direction: 'higher', great: 60, bad: 10  },
  { key: 'operating_margin', label: 'Marge opérat.',    direction: 'higher', great: 25, bad: 0   },
]
