import hashlib

from app.core.security import generate_token, hash_password, hash_token, verify_password


def test_password_hash_uses_argon2id_and_verifies_only_the_original_password() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash.startswith("$argon2id$")
    assert verify_password("correct horse battery staple", password_hash) is True
    assert verify_password("wrong password", password_hash) is False


def test_token_hash_is_sha256_and_raw_tokens_are_cryptographically_random() -> None:
    first = generate_token()
    second = generate_token()

    assert first != second
    assert hash_token(first) == hashlib.sha256(first.encode("utf-8")).hexdigest()
    assert first not in hash_token(first)

