import hashlib


def hash_password(clear_password, salt, pepper):
    #hashlib.scrypt(password=clear_password, salt=salt, n=16384, r=8, p=1, dklen=32)
    return hashlib.scrypt(password=bytes(clear_password+pepper, encoding="utf8"), salt=salt, n=16384, r=8, p=1, dklen=32)
