import { institutions } from './institutions.js'

// Depuis que le nom de compte n'est plus unique globalement (seulement sous un même compte
// parent ou une même institution, voir backend/routes/rt_accounts.py::_name_conflict), deux
// comptes peuvent légitimement porter le même nom — toute liste/select de comptes doit donc
// afficher assez de contexte pour les distinguer : "Institution → Parent → Compte".

function buildAccountsById(accounts) {
  const map = new Map()
  for (const a of accounts || []) map.set(String(a.id), a)
  return map
}

// Chaîne de comptes ancêtres (racine → ... → compte lui-même), et institution résolue en
// remontant la chaîne jusqu'au premier compte qui en a une (le plus souvent le compte racine
// bancaire, ses enfants n'ont généralement pas d'institution propre).
function resolveChainAndInstitution(account, accountsById) {
  const chain = [];
  const institutionsById = new Map(institutions.value.map((i) => [String(i.id), i]));
  let institutionName = null;
  let current = account;
  const seen = new Set();
  while (current && !seen.has(current.id)) {
    seen.add(current.id);
    chain.unshift(current.name);
    if (!institutionName && current.institution_id) {
      const inst = institutionsById.get(String(current.institution_id));
      if (inst) institutionName = inst.name;
    }
    current = current.parent_id ? accountsById.get(String(current.parent_id)) : null;
  }
  return { chain, institutionName };
}

// `accounts` : le tableau complet des comptes de l'utilisateur (pour résoudre parent_id en
// remontant la chaîne) — pas seulement le sous-ensemble filtré affiché dans le select/la liste
// appelante, sinon un parent hors de ce sous-ensemble ne serait pas résolu.
export function accountDisplayLabel(account, accounts) {
  if (!account) return '';
  const { chain, institutionName } = resolveChainAndInstitution(account, buildAccountsById(accounts));
  const parts = institutionName ? [institutionName, ...chain] : chain;
  return parts.join(' → ');
}

export function accountLabelById(accountId, accounts) {
  if (!accountId) return '';
  const account = (accounts || []).find((a) => String(a.id) === String(accountId));
  return account ? accountDisplayLabel(account, accounts) : '';
}
