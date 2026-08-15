// Un compte "réel" représente de l'argent que possède l'utilisateur (Current/Assets/Equity), à
// l'exclusion des comptes Income/Expense (contreparties de catégorisation, pas de l'argent réel),
// Liability, et des comptes Equity auto-générés par un flux dédié (ouverture de crédit ou solde
// initial de reprise) qu'il ne faut pas manipuler directement — voir Accounts.vue et Import.vue.
export function isRealAccount(a) {
  return a.account_type !== 'Income' && a.account_type !== 'Expense' && a.account_type !== 'Liability'
    && !(a.account_type === 'Equity' && ['loan', 'opening_balance'].includes(a.account_subtype))
}

export function isIncomeExpenseAccount(a) {
  return a.account_type === 'Income' || a.account_type === 'Expense'
}
