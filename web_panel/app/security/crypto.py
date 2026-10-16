"""Cryptographic primitives and password hashing standards for KargoPilot v4.5.

Enforces:
- Argon2id as primary password hasher (RFC 9106: m=65536 KiB, t=3, p=4)
- bcrypt backward-compatibility & automatic migration on successful login
- Cryptographically secure token and OTP generation via secrets module
- Constant-time string comparison against timing attacks
- Never invent auth primitives.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Tuple

try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, InvalidHashError
    HAS_ARGON2 = True
except ImportError:
    HAS_ARGON2 = False

import bcrypt

logger = logging.getLogger("kargopilot.security.crypto")

# RFC 9106 / OWASP Recommended Argon2id parameters
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST = 65536  # 64 MiB
ARGON2_PARALLELISM = 4
ARGON2_HASH_LEN = 32
ARGON2_SALT_LEN = 16

# bcrypt fallback parameters
BCRYPT_ROUNDS = 12


class PasswordManager:
    """Manages password hashing, verification, and migration between bcrypt and Argon2id."""

    def __init__(self) -> None:
        if HAS_ARGON2:
            self._hasher = PasswordHasher(
                time_cost=ARGON2_TIME_COST,
                memory_cost=ARGON2_MEMORY_COST,
                parallelism=ARGON2_PARALLELISM,
                hash_len=ARGON2_HASH_LEN,
                salt_len=ARGON2_SALT_LEN,
            )
        else:
            self._hasher = None
            logger.warning("argon2-cffi not detected; falling back to bcrypt-only mode.")

    def hash_password(self, password: str) -> str:
        """Hash a plaintext password using Argon2id (or bcrypt if Argon2 is unavailable)."""
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters long.")
        if len(password.encode("utf-8")) > 1024:
            raise ValueError("Password exceeds maximum length limit.")

        if self._hasher is not None:
            return self._hasher.hash(password)
        
        # Fallback to bcrypt
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> Tuple[bool, bool]:
        """Verifies a plaintext password against a stored hash.
        
        Returns:
            Tuple[bool, bool]: (is_valid, needs_rehash)
            - is_valid: True if password matches hash.
            - needs_rehash: True if the hash is legacy (bcrypt) or uses outdated Argon2 parameters.
        """
        if not plain_password or not hashed_password:
            return False, False

        # 1. Check if hash is Argon2id
        if hashed_password.startswith("$argon2"):
            if not self._hasher:
                logger.error("Argon2 hash encountered but argon2-cffi is not installed.")
                return False, False
            try:
                self._hasher.verify(hashed_password, plain_password)
                needs_rehash = self._hasher.check_needs_rehash(hashed_password)
                return True, needs_rehash
            except (VerifyMismatchError, InvalidHashError):
                return False, False
            except Exception as e:
                logger.error("Unexpected error during Argon2 verification: %s", e)
                return False, False

        # 2. Check if hash is bcrypt ($2b$, $2a$, $2y$)
        if hashed_password.startswith(("$2a$", "$2b$", "$2y$")):
            try:
                is_valid = bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
                # If Argon2 is available, any bcrypt hash needs upgrade to Argon2id
                needs_rehash = is_valid and (self._hasher is not None)
                return is_valid, needs_rehash
            except Exception as e:
                logger.error("Unexpected error during bcrypt verification: %s", e)
                return False, False

        logger.warning("Unrecognized password hash format.")
        return False, False


# Global singleton instance
password_manager = PasswordManager()


def hash_token(raw_token: str) -> str:
    """Computes SHA-256 hexadecimal digest of raw token for safe DB storage.
    
    Tokens such as refresh tokens, session identifiers, and OTP codes should
    never be stored in plaintext.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def generate_secure_token(nbytes: int = 32) -> str:
    """Generates a high-entropy cryptographically secure URL-safe token.
    
    Default 32 bytes yields 256 bits of entropy.
    """
    return secrets.token_urlsafe(nbytes)


def generate_numeric_otp(length: int = 6) -> str:
    """Generates a cryptographically secure random numeric OTP string."""
    digits = "0123456789"
    return "".join(secrets.choice(digits) for _ in range(length))


def constant_time_compare(val1: str, val2: str) -> bool:
    """Constant-time string comparison to prevent side-channel timing attacks."""
    if not isinstance(val1, str) or not isinstance(val2, str):
        return False
    return secrets.compare_digest(val1.encode("utf-8"), val2.encode("utf-8"))
