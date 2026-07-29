import sqlalchemy as sa

# Accents français courants (Postgres n'a pas d'extension 'unaccent' garantie disponible selon
# l'hébergeur — translate() est portable et suffit largement pour l'usage de cette appli, toute
# en français).
_ACCENTED = 'àáâãäåèéêëìíîïòóôõöùúûüýÿñçÀÁÂÃÄÅÈÉÊËÌÍÎÏÒÓÔÕÖÙÚÛÜÝŸÑÇ'
_PLAIN    = 'aaaaaaeeeeiiiiooooouuuuyyncAAAAAAEEEEIIIIOOOOOUUUUYYNC'


def _folded(column_expr):
    """minuscule + accents retirés, pour une comparaison insensible à la casse ET aux accents."""
    return sa.func.translate(sa.func.lower(column_expr), _ACCENTED, _PLAIN)


def unaccent_contains(column, term):
    """Filtre SQLAlchemy 'contient', insensible à la casse et aux accents français courants —
    ex: une recherche "medecin" retrouve "Médecin" et vice versa."""
    return _folded(column).like(sa.func.concat('%', _folded(sa.literal(term)), '%'))


def unaccent_startswith(column, term):
    """Comme unaccent_contains mais en préfixe (LIKE 'term%') — pour l'autocomplétion."""
    return _folded(column).like(sa.func.concat(_folded(sa.literal(term)), '%'))
