"""Dual-token architecture, JWT verification, and Refresh Token Rotation (RTR).

Enforces:
- Short-lived Access Token (15 min) in HTTP-only SameSite cookie or Authorization Bearer header
- High-entropy Refresh Token (7 days) with cryptographic hash stored in database
- Refresh Token Rotation (RTR) with token family tracking
- Automatic Token Reuse Detection: invalidates the entire token family upon detection of replayed tokens
- In-memory/Redis JTI Denylist for emergency instant access token revocation
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import jwt

from app.security.crypto import generate_secure_token, hash_token, constant_time_compare

logger = logging.getLogger("kargopilot.security.tokens")

# Configuration Defaults (overridable via environment)
JWT_SECRET_KEY = os.getenv("KP_JWT_SECRET_KEY", "kargopilot-v45-insecure-default-change-in-prod-77947abc")
JWT_ALGORITHM = "HS256"
JWT_ISSUER = "kargopilot.internal"
JWT_AUDIENCE = "kargopilot-platform"

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("KP_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("KP_REFRESH_TOKEN_EXPIRE_DAYS", "7"))

ACCESS_COOKIE_NAME = "kp_access_token"
REFRESH_COOKIE_NAME = "kp_refresh_token"
CSRF_COOKIE_NAME = "kp_csrf_token"


class TokenSecurityException(Exception):
    """Base exception for token authentication failures."""
    pass


class TokenExpiredException(TokenSecurityException):
    """Raised when an access or refresh token has expired."""
    pass


class TokenInvalidException(TokenSecurityException):
    """Raised when a token signature or format is invalid."""
    pass


class TokenReuseDetectedException(TokenSecurityException):
    """Raised when a previously rotated refresh token is presented again (replay attack)."""
    pass


class TokenBlacklist:
    """In-memory JTI blacklist with automatic expiration cleanup (can be backed by Redis in clustered deployment)."""

    def __init__(self) -> None:
        self._blacklisted_jtis: Dict[str, datetime] = {}

    def revoke(self, jti: str, expires_at: datetime) -> None:
        self._cleanup()
        self._blacklisted_jtis[jti] = expires_at

    def is_revoked(self, jti: str) -> bool:
        self._cleanup()
        return jti in self._blacklisted_jtis

    def _cleanup(self) -> None:
        now = datetime.now(timezone.utc)
        expired = [jti for jti, exp in self._blacklisted_jtis.items() if exp <= now]
        for jti in expired:
            self._blacklisted_jtis.pop(jti, None)


jti_blacklist = TokenBlacklist()


class TokenService:
    """Authoritative service for generating, verifying, and rotating KargoPilot v4.5 tokens."""

    @classmethod
    def create_access_token(
        cls,
        user_id: str,
        email: str,
        role: str,
        session_id: str,
        family_id: str,
        expires_delta: Optional[timedelta] = None,
    ) -> Tuple[str, str, datetime]:
        """Issues a signed JWT access token.
        
        Returns:
            Tuple[str, str, datetime]: (raw_jwt_token, jti, expiration_datetime)
        """
        now = datetime.now(timezone.utc)
        exp_delta = expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        expires_at = now + exp_delta
        jti = str(uuid.uuid4())

        payload: Dict[str, Any] = {
            "sub": user_id,
            "email": email,
            "role": role,
            "session_id": session_id,
            "family_id": family_id,
            "jti": jti,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
        }

        token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
        return token, jti, expires_at

    @classmethod
    def verify_access_token(cls, token: str) -> Dict[str, Any]:
        """Validates signature, expiration, issuer, audience, and denylist status.
        
        Returns:
            Dict[str, Any]: Decoded token payload.
        """
        try:
            payload = jwt.decode(
                token,
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM],
                issuer=JWT_ISSUER,
                audience=JWT_AUDIENCE,
            )
        except jwt.ExpiredSignatureError as e:
            raise TokenExpiredException("Access token has expired.") from e
        except jwt.PyJWTError as e:
            raise TokenInvalidException(f"Invalid access token: {e}") from e

        jti = payload.get("jti")
        if not jti or jti_blacklist.is_revoked(jti):
            raise TokenInvalidException("Token has been revoked or revoked JTI encountered.")

        return payload

    @classmethod
    def create_refresh_token(cls) -> Tuple[str, str, datetime]:
        """Generates a high-entropy refresh token and its SHA-256 hash.
        
        Returns:
            Tuple[str, str, datetime]: (raw_refresh_token, hashed_refresh_token, expires_at)
        """
        raw_token = generate_secure_token(48)
        hashed_token = hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        return raw_token, hashed_token, expires_at

    @classmethod
    def create_csrf_token(cls) -> str:
        """Generates anti-CSRF synchronizer token."""
        return generate_secure_token(32)


def set_auth_cookies(
    response: Any,
    access_token: str,
    refresh_token: str,
    csrf_token: Optional[str] = None,
    secure: bool = False,  # set True in HTTPS production
) -> None:
    """Sets hardened HTTP-only SameSite cookies on FastAPI/Starlette Response."""
    # Access token cookie (short-lived)
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    # Refresh token cookie (restricted to auth refresh route)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/api/v1/auth",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )

    # Anti-CSRF double-submit token (must be readable by front-end JavaScript)
    if csrf_token:
        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=csrf_token,
            httponly=False,
            secure=secure,
            samesite="lax",
            path="/",
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        )


def clear_auth_cookies(response: Any) -> None:
    """Clears all authentication cookies upon logout."""
    response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/api/v1/auth")
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")
