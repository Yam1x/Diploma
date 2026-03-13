from app.core.security import SecretCipher


def test_secret_cipher_is_passthrough_in_dev_mode() -> None:
    cipher = SecretCipher()

    assert cipher.encrypt("top-secret") == "top-secret"
    assert cipher.decrypt("top-secret") == "top-secret"
