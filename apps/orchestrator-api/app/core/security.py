from base64 import urlsafe_b64encode
from hashlib import sha256

from cryptography.fernet import Fernet


class SecretCipher:
    def __init__(self, secret: str) -> None:
        key = urlsafe_b64encode(sha256(secret.encode("utf-8")).digest())
        self._fernet = Fernet(key)

    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
