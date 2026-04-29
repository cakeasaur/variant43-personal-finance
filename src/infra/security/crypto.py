from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    _CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover - platform-dependent (e.g. Android build without cryptography)
    AESGCM = None  # type: ignore[assignment]
    Scrypt = None  # type: ignore[assignment]
    _CRYPTO_AVAILABLE = False

MAGIC = b"PFM1"  # Personal Finance Manager v1
SALT_LEN = 16
NONCE_LEN = 12  # AESGCM nonce length
KEY_LEN = 32  # 256-bit


class InvalidPasswordError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class EncryptedBlob:
    salt: bytes
    nonce: bytes
    ciphertext: bytes


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography is not available on this platform")
    if not isinstance(passphrase, str) or not passphrase:
        raise ValueError("passphrase must be a non-empty string")
    if len(salt) != SALT_LEN:
        raise ValueError("invalid salt length")
    kdf = Scrypt(salt=salt, length=KEY_LEN, n=2**14, r=8, p=1)  # type: ignore[misc]
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_bytes(*, plaintext: bytes, passphrase: str) -> bytes:
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography is not available on this platform")
    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = _derive_key(passphrase, salt)
    aes = AESGCM(key)  # type: ignore[misc]
    ciphertext = aes.encrypt(nonce, plaintext, None)
    return MAGIC + salt + nonce + ciphertext


def decrypt_bytes(*, blob: bytes, passphrase: str) -> bytes:
    if not _CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography is not available on this platform")
    if len(blob) < len(MAGIC) + SALT_LEN + NONCE_LEN + 1:
        raise ValueError("encrypted blob is too small")
    if blob[: len(MAGIC)] != MAGIC:
        raise ValueError("invalid blob header")
    salt = blob[len(MAGIC) : len(MAGIC) + SALT_LEN]
    nonce = blob[len(MAGIC) + SALT_LEN : len(MAGIC) + SALT_LEN + NONCE_LEN]
    ciphertext = blob[len(MAGIC) + SALT_LEN + NONCE_LEN :]
    key = _derive_key(passphrase, salt)
    aes = AESGCM(key)  # type: ignore[misc]
    try:
        return aes.decrypt(nonce, ciphertext, None)
    except Exception as exc:  # cryptography raises InvalidTag
        raise InvalidPasswordError("invalid password or corrupted data") from exc


def decrypt_file_to_path(*, encrypted_path: Path, passphrase: str, out_path: Path) -> None:
    data = encrypted_path.read_bytes()
    plaintext = decrypt_bytes(blob=data, passphrase=passphrase)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(plaintext)


def encrypt_file_to_path(*, plaintext_path: Path, passphrase: str, out_path: Path) -> None:
    plaintext = plaintext_path.read_bytes()
    blob = encrypt_bytes(plaintext=plaintext, passphrase=passphrase)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(blob)

