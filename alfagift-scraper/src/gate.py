"""Mint the `fingerprint` header Alfagift's gateway demands.

The whole mechanism is documented in `constants.py` under "THE GATE". In one
line: the header is Base64(AES-256-CBC(plaintext, passphrase, iv)) and the
server checks only that it decrypts, so the plaintext can be anything.

Using a random plaintext per run rather than a fixed one is deliberate. A
constant would make every run of every copy of this actor share one identifier,
which is exactly the shape a rate limiter keys on. A fresh 20-hex-character
value per run matches what FingerprintJS v3 emits and costs nothing.
"""

from __future__ import annotations

import base64
import secrets
import uuid

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .constants import GATE_IV, GATE_PASSPHRASE

_BLOCK = 16


def _pkcs7(data: bytes) -> bytes:
    pad = _BLOCK - (len(data) % _BLOCK)
    return data + bytes([pad]) * pad


def encrypt(plaintext: str) -> str:
    """CryptoJS-compatible AES-256-CBC + PKCS7, Base64 of the ciphertext only.

    CryptoJS's `AES.encrypt(...).ciphertext` is the raw block output with no
    OpenSSL "Salted__" prefix, which is why this returns the ciphertext alone.
    """
    encryptor = Cipher(
        algorithms.AES(GATE_PASSPHRASE), modes.CBC(GATE_IV)
    ).encryptor()
    body = encryptor.update(_pkcs7(plaintext.encode("utf-8"))) + encryptor.finalize()
    return base64.b64encode(body).decode("ascii")


def decrypt(token: str) -> str:
    """Inverse of `encrypt`, used by the local test to prove the round trip."""
    decryptor = Cipher(
        algorithms.AES(GATE_PASSPHRASE), modes.CBC(GATE_IV)
    ).decryptor()
    body = decryptor.update(base64.b64decode(token)) + decryptor.finalize()
    return body[: -body[-1]].decode("utf-8")


def new_fingerprint() -> str:
    """A fresh gate token. 20 hex chars is FingerprintJS v3's visitorId shape."""
    return encrypt(secrets.token_hex(10))


def new_trx_id() -> str:
    """Per-request correlation id. The gateway echoes it and never checks it."""
    return str(uuid.uuid4())
