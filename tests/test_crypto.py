from __future__ import annotations

import os

import pytest

from src.infra.security.crypto import InvalidPasswordError, decrypt_bytes, encrypt_bytes


def test_encrypt_decrypt_roundtrip() -> None:
    pt = os.urandom(1024)
    blob = encrypt_bytes(plaintext=pt, passphrase="secret")
    out = decrypt_bytes(blob=blob, passphrase="secret")
    assert out == pt


def test_decrypt_rejects_wrong_password() -> None:
    pt = b"hello"
    blob = encrypt_bytes(plaintext=pt, passphrase="secret")
    with pytest.raises(InvalidPasswordError):
        decrypt_bytes(blob=blob, passphrase="nope")


def test_decrypt_rejects_wrong_header() -> None:
    with pytest.raises(ValueError):
        decrypt_bytes(blob=b"NOPE", passphrase="x")

