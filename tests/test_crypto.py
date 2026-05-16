from __future__ import annotations

import os

import pytest

from src.infra.security.crypto import (
    MAGIC,
    NONCE_LEN,
    SALT_LEN,
    InvalidPasswordError,
    decrypt_bytes,
    encrypt_bytes,
)

_PASSPHRASE = "supersecret123"
_HEADER_LEN = len(MAGIC) + SALT_LEN + NONCE_LEN


def test_encrypt_decrypt_roundtrip() -> None:
    pt = os.urandom(1024)
    blob = encrypt_bytes(plaintext=pt, passphrase=_PASSPHRASE)
    out = decrypt_bytes(blob=blob, passphrase=_PASSPHRASE)
    assert out == pt


def test_encrypt_decrypt_empty_plaintext() -> None:
    blob = encrypt_bytes(plaintext=b"", passphrase=_PASSPHRASE)
    out = decrypt_bytes(blob=blob, passphrase=_PASSPHRASE)
    assert out == b""


def test_decrypt_rejects_wrong_password() -> None:
    pt = b"hello"
    blob = encrypt_bytes(plaintext=pt, passphrase=_PASSPHRASE)
    with pytest.raises(InvalidPasswordError):
        decrypt_bytes(blob=blob, passphrase="wrongpassword123")


def test_decrypt_rejects_corrupted_ciphertext() -> None:
    blob = encrypt_bytes(plaintext=b"sensitive data", passphrase=_PASSPHRASE)
    corrupted = bytearray(blob)
    corrupted[_HEADER_LEN] ^= 0xFF  # flip first byte of ciphertext
    with pytest.raises(InvalidPasswordError):
        decrypt_bytes(blob=bytes(corrupted), passphrase=_PASSPHRASE)


def test_decrypt_rejects_wrong_header() -> None:
    with pytest.raises(ValueError):
        decrypt_bytes(blob=b"NOPE", passphrase="x")


def test_passphrase_too_short() -> None:
    with pytest.raises(ValueError, match="at least"):
        encrypt_bytes(plaintext=b"data", passphrase="short")

