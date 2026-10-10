"""AES-256-GCM token encryption with key ids (rotation without re-encrypting everything).

TOKEN_ENC_KEYS="k2:<base64 32 bytes>,k1:<base64 32 bytes>": the FIRST key encrypts, any listed
key decrypts. Stored form: nonce(12) || ciphertext+tag, with the key id in its own column
(`oauth_tokens.key_id`). Plaintext tokens never appear in exceptions, reprs or logs.
"""

import base64
import os
from dataclasses import dataclass, field

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

NONCE_BYTES = 12


class CryptoError(Exception):
    """Decryption/configuration failure. Messages never contain secret material."""


@dataclass(frozen=True)
class Encrypted:
    blob: bytes
    key_id: str
    _hidden: bool = field(default=True, repr=False)


def generate_key() -> str:
    """A new random 32-byte key, base64-encoded (for ops: print(generate_key()))."""
    return base64.b64encode(os.urandom(32)).decode()


def _parse_keys(spec: str) -> dict[str, bytes]:
    keys: dict[str, bytes] = {}
    for item in filter(None, (p.strip() for p in spec.split(","))):
        key_id, sep, b64 = item.partition(":")
        if not sep or not key_id:
            raise CryptoError("TOKEN_ENC_KEYS entries must look like 'id:base64key'")
        try:
            raw = base64.b64decode(b64, validate=True)
        except ValueError as e:
            raise CryptoError(f"key {key_id!r} is not valid base64") from e
        if len(raw) != 32:
            raise CryptoError(f"key {key_id!r} must be 32 bytes (AES-256)")
        keys[key_id] = raw
    if not keys:
        raise CryptoError("TOKEN_ENC_KEYS is empty")
    return keys


def _keys(spec: str | None) -> dict[str, bytes]:
    return _parse_keys(spec if spec is not None else get_settings().token_enc_keys)


def encrypt(
    plaintext: str | bytes, *, aad: bytes | None = None, keys: str | None = None
) -> Encrypted:
    """Encrypt with the active (first) key. `aad` binds the ciphertext to a context
    (e.g. the integration id) so a blob cannot be swapped between rows."""
    ring = _keys(keys)
    key_id = next(iter(ring))
    nonce = os.urandom(NONCE_BYTES)
    data = plaintext.encode() if isinstance(plaintext, str) else plaintext
    return Encrypted(nonce + AESGCM(ring[key_id]).encrypt(nonce, data, aad), key_id)


def decrypt(blob: bytes, key_id: str, *, aad: bytes | None = None, keys: str | None = None) -> str:
    ring = _keys(keys)
    if key_id not in ring:
        raise CryptoError(f"unknown key id {key_id!r}; was it removed from TOKEN_ENC_KEYS?")
    if len(blob) <= NONCE_BYTES:
        raise CryptoError("ciphertext too short")
    try:
        plain = AESGCM(ring[key_id]).decrypt(blob[:NONCE_BYTES], blob[NONCE_BYTES:], aad)
        return str(plain.decode())
    except InvalidTag:
        raise CryptoError("decryption failed (wrong key, tampered data or wrong context)") from None
