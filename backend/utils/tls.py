import ipaddress
import os
from datetime import datetime, timedelta, timezone

# Emplacement par défaut (utilisé quand TLS_CERT_PATH/TLS_KEY_PATH ne sont pas fournis) : à
# l'intérieur de backend/, monté en volume Docker (voir docker-compose.yml) pour persister le
# certificat auto-généré entre deux redémarrages du conteneur.
_CERTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'certs')
DEFAULT_CERT_PATH = os.path.join(_CERTS_DIR, 'selfsigned.crt')
DEFAULT_KEY_PATH = os.path.join(_CERTS_DIR, 'selfsigned.key')


def resolve_tls_paths():
    """Retourne (cert_path, key_path) prêts à passer à Flask/gunicorn pour servir l'API en HTTPS.

    Si TLS_CERT_PATH/TLS_KEY_PATH (voir .env.example) ne sont pas renseignés, génère — au premier
    appel seulement, le fichier est ensuite réutilisé tel quel — un certificat auto-signé. Pratique
    pour un usage LAN/perso ; le navigateur affichera malgré tout un avertissement "connexion non
    sécurisée" à accepter manuellement, une autorité auto-signée n'étant reconnue par personne.
    Pour un vrai déploiement public sans cet avertissement, fournir un certificat existant (ex:
    Let's Encrypt) via ces deux variables.
    """
    cert_path = os.environ.get('TLS_CERT_PATH') or DEFAULT_CERT_PATH
    key_path = os.environ.get('TLS_KEY_PATH') or DEFAULT_KEY_PATH

    if not (os.path.exists(cert_path) and os.path.exists(key_path)):
        _generate_self_signed_cert(cert_path, key_path)

    return cert_path, key_path


def _generate_self_signed_cert(cert_path, key_path):
    # Import différé : la dépendance 'cryptography' n'est nécessaire que si HTTPS est activé.
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, 'Cantisa Money (certificat auto-signé)'),
    ])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(_subject_alt_names()), critical=False)
        .sign(key, hashes.SHA256())
    )

    for path in (cert_path, key_path):
        os.makedirs(os.path.dirname(path), exist_ok=True)

    with open(key_path, 'wb') as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    with open(cert_path, 'wb') as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))


def _subject_alt_names():
    from cryptography import x509

    names = [x509.DNSName('localhost'), x509.IPAddress(ipaddress.ip_address('127.0.0.1'))]
    # API_HOST (voir .env.example) est l'hôte réellement utilisé par les navigateurs des
    # utilisateurs (IP LAN, nom de domaine...) : l'inclure évite l'avertissement supplémentaire
    # "nom de certificat invalide" en plus de celui, inévitable, sur l'autorité auto-signée.
    extra_host = os.environ.get('API_HOST', 'localhost')
    if extra_host and extra_host != 'localhost':
        try:
            names.append(x509.IPAddress(ipaddress.ip_address(extra_host)))
        except ValueError:
            names.append(x509.DNSName(extra_host))
    return names


if __name__ == '__main__':
    # Appelé par backend/docker-entrypoint.sh : imprime le chemin du certificat puis celui de la
    # clé (une ligne chacun) après génération/résolution, pour que le shell les récupère.
    printed_cert_path, printed_key_path = resolve_tls_paths()
    print(printed_cert_path)
    print(printed_key_path)
