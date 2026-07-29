/**
 * Normalisation de texte pour une recherche insensible à la casse ET aux accents (ex: "medecin"
 * doit retrouver "Médecin" et vice versa) — utilisée par tous les filtres de recherche côté client
 * de l'appli (Accounts.vue, Budgets.vue, Portfolio.vue, Subscriptions.vue, AccountDetail.vue,
 * Tags.vue, Categories.vue...). Équivalent côté serveur : backend/utils/text_search.py.
 */
export function normalizeSearch(v) {
  return (v ?? '')
    .toString()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim()
}
