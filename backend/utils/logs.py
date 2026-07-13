import logging

_logger = logging.getLogger('cantisa')
if not _logger.handlers:
    # stdout : capturé nativement par `docker compose logs` / le terminal, plutôt qu'un chemin de
    # fichier en dur (l'ancienne version écrivait dans C:\Users\Loris\Downloads\debug.txt, inutilisable
    # ailleurs que sur cette machine).
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('%(asctime)s %(name)s | %(message)s', datefmt='%d/%m/%Y %H:%M:%S'))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)


def log(message: str, filename='app', separator=False):
    if separator:
        _logger.info('-' * 60)
    _logger.info(f"{filename} | {message}")
