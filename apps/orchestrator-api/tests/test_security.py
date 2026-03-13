from app.core.security import SecretCipher


def test_encrypt_decrypt_roundtrip() -> None:
    cipher = SecretCipher("top-secret")

    encrypted = cipher.encrypt("value")

    assert encrypted != "value"
    assert cipher.decrypt(encrypted) == "value"
