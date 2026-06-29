"""API-key encryption at rest.

Keys are encrypted with Fernet, using a symmetric key deterministically
derived from the app's ``SECRET_KEY``. The derived key is cached so we
do not re-run PBKDF2 on every call (600k iterations).

Security properties:
- The plaintext key is never persisted: only the Fernet token is stored
  in ``Service.api_key_encrypted``.
- The same ``SECRET_KEY`` always derives the same Fernet key, so encrypted
  values remain decryptable across restarts (no separate key store).
- Rotating ``SECRET_KEY`` invalidates all stored keys — by design, key
  rotation is a deliberate admin operation.
"""

from __future__ import annotations

import base64
import hashlib
import threading
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


_CACHE_LOCK = threading.Lock()
_CACHED_KEY: Optional[bytes] = None
_CACHED_SECRET: Optional[str] = None


def _derive_fernet_key() -> bytes:
    """Derive a 32-byte url-safe Fernet key from SECRET_KEY (cached)."""
    global _CACHED_KEY, _CACHED_SECRET
    settings = get_settings()
    secret = settings.SECRET_KEY
    with _CACHE_LOCK:
        if _CACHED_KEY is not None and _CACHED_SECRET == secret:
            return _CACHED_KEY
        # SHA-256 of the secret → 32 bytes → url-safe base64 (Fernet key format)
        digest = hashlib.sha256(secret.encode("utf-8")).digest()
        key = base64.urlsafe_b64encode(digest)
        _CACHED_KEY = key
        _CACHED_SECRET = secret
        return key


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt an API key, returning a Fernet token string."""
    if not plaintext:
        return ""
    f = Fernet(_derive_fernet_key())
    return f.encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_api_key(token: str) -> str:
    """Decrypt a Fernet token back to the plaintext API key.

    Returns an empty string for empty input. Raises ValueError on a
    token that cannot be decrypted (e.g. SECRET_KEY changed).
    """
    if not token:
        return ""
    f = Fernet(_derive_fernet_key())
    try:
        return f.decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:  # pragma: no cover - defensive
        raise ValueError("API key could not be decrypted (SECRET_KEY changed?)") from exc


def mask_key(plaintext: str, visible_prefix: int = 4, visible_suffix: int = 1) -> str:
    """Mask an API key for display: keep a short prefix/suffix, star the rest.

    Empty input → empty string. Very short input → all-but-prefix masked.
    """
    if not plaintext:
        return ""
    if len(plaintext) <= visible_prefix:
        return plaintext[:visible_prefix] + "****"
    suffix = plaintext[-visible_suffix:] if visible_suffix > 0 else ""
    masked_len = max(1, len(plaintext) - visible_prefix - len(suffix))
    return plaintext[:visible_prefix] + ("*" * masked_len) + suffix
