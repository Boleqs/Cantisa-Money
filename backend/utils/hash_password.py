import hashlib


def hash_password(clear_password, salt, pepper):
    return hashlib.sha256(bytes(clear_password + salt + pepper, encoding="utf8")).hexdigest()