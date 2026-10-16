"""FastAPI Router for KargoPilot v4.5 Authentication, Session Management, and Identity Bridge.

Endpoints:
- POST /api/v1/auth/login: Dual-token login, Argon2id verification, auto-rehash, rate-limited
- POST /api/v1/auth/refresh: Refresh Token Rotation (RTR) with token family reuse detection
- POST /api/v1/auth/logout: Revoke current session, blacklist JTI, clear cookies
- POST /api/v1/auth/logout-all: Invalidate all active sessions for user
- GET  /api/v1/auth/me: Retrieve current identity, role, and permissions
- POST /api/v1/auth/whatsapp/link-code: Generate 6-digit one-time binding code for WhatsApp
- POST /api/v1/auth/whatsapp/webhook: Inbound WhatsApp message hook with multi-user routing
- GET  /api/v1/admin/audit-logs: Query structured audit trail (Admin-only)
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.security.audit import audit_logger
from app.security.crypto import hash_token, password_manager
from app.security.models import AuditEventType, AuthChannel, UserRole
from app.security.rate_limiter import (
    AccountLockoutManager,
    rate_limiter,
)
from app.security.rbac import (
    AuthenticatedUser,
    ROLE_PERMISSIONS,
    get_current_user,
    require_role,
)
from app.security.tokens import (
    ACCESS_COOKIE_NAME,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_COOKIE_NAME,
    REFRESH_TOKEN_EXPIRE_DAYS,
    TokenService,
    clear_auth_cookies,
    jti_blacklist,
    set_auth_cookies,
)
from app.security.whatsapp_bridge import (
    AdminCommandGate,
    WhatsAppIdentityBridge,
    normalize_phone_e164,
)

logger = logging.getLogger("kargopilot.security.routes")

router = APIRouter(prefix="/api/v1", tags=["Authentication & Identity"])

DEFAULT_DB_PATH = Path("/data/pcs/pcs.db")
wa_bridge = WhatsAppIdentityBridge(DEFAULT_DB_PATH)
admin_gate = AdminCommandGate(wa_bridge)


# ==============================================================================
# Pydantic Request/Response Schemas
# ==============================================================================

class LoginRequest(BaseModel):
    email: str = Field(..., example="admin@kargopilot.az")
    password: str = Field(..., min_length=8, example="StrongP@ssw0rd2026")
    device_fingerprint: Optional[str] = Field(None, example="Chrome-Win11-x86_64")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in_seconds: int
    user_id: str
    email: str
    full_name: str
    role: str
    csrf_token: str


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in_seconds: int


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str
    phone: Optional[str]
    role: str
    permissions: List[str]


class WhatsAppWebhookRequest(BaseModel):
    sender: str = Field(..., example="994501234567@s.whatsapp.net")
    message: str = Field(..., example="!kargo")
    timestamp: Optional[int] = None


class WhatsAppWebhookResponse(BaseModel):
    status: str
    sender: str
    user_id: Optional[str]
    reply: str


from contextlib import contextmanager

# ==============================================================================
# Database Helper
# ==============================================================================

@contextmanager
def get_db():
    conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ==============================================================================
# Auth Routes
# ==============================================================================

@router.post("/auth/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
) -> LoginResponse:
    """Authenticates credentials, issues dual tokens, and handles auto-rehash."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    user_agent = request.headers.get("user-agent", "Unknown")

    # 1. IP-level rate limit check
    is_limited, retry_after = rate_limiter.is_ip_rate_limited(client_ip)
    if is_limited:
        audit_logger.log(
            event_type=AuditEventType.LOGIN_FAILED,
            status="BLOCKED",
            ip_address=client_ip,
            user_agent=user_agent,
            reason="IP rate limit exceeded.",
            metadata={"retry_after": retry_after},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts from this IP. Retry in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    clean_email = req.email.strip().lower()

    with get_db() as conn:
        user_row = conn.execute("SELECT * FROM users WHERE LOWER(email) = ?", (clean_email,)).fetchone()

        if not user_row:
            rate_limiter.record_ip_failure(client_ip)
            audit_logger.log(
                event_type=AuditEventType.LOGIN_FAILED,
                status="FAILED",
                ip_address=client_ip,
                user_agent=user_agent,
                reason="Invalid credentials (user not found).",
                metadata={"email": clean_email},
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

        # 2. Account lockout check
        AccountLockoutManager.check_and_enforce_lockout(dict(user_row), client_ip)

        # 3. Password Verification
        is_valid, needs_rehash = password_manager.verify_password(req.password, user_row["password_hash"])
        if not is_valid:
            rate_limiter.record_ip_failure(client_ip)
            rem = AccountLockoutManager.register_failed_attempt(conn, dict(user_row), client_ip)
            audit_logger.log(
                event_type=AuditEventType.LOGIN_FAILED,
                status="FAILED",
                user_id=user_row["id"],
                actor_role=user_row["role"],
                ip_address=client_ip,
                user_agent=user_agent,
                reason="Invalid credentials (password mismatch).",
                metadata={"remaining_attempts": rem},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid email or password. Remaining attempts: {rem}" if rem > 0 else "Account has been locked.",
            )

        # 4. Successful credentials verification
        AccountLockoutManager.register_successful_login(conn, user_row["id"])
        rate_limiter.reset_ip(client_ip)

        # 5. Transparent Argon2id auto-upgrade if legacy hash (bcrypt)
        if needs_rehash:
            try:
                new_hash = password_manager.hash_password(req.password)
                conn.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                    (new_hash, datetime.now(timezone.utc).isoformat(), user_row["id"]),
                )
                conn.commit()
                logger.info("Migrated password hash for user %s to current Argon2id standard.", user_row["id"])
            except Exception as e:
                logger.error("Failed to rehash password: %s", e)

        # 6. Issue Session, Token Family, and Dual Tokens
        session_id = str(uuid.uuid4())
        family_id = str(uuid.uuid4())
        raw_refresh, hashed_refresh, refresh_exp = TokenService.create_refresh_token()
        raw_access, jti, access_exp = TokenService.create_access_token(
            user_id=user_row["id"],
            email=user_row["email"],
            role=user_row["role"],
            session_id=session_id,
            family_id=family_id,
        )
        csrf_token = TokenService.create_csrf_token()

        now_str = datetime.now(timezone.utc).isoformat()
        exp_str = refresh_exp.isoformat()

        # Insert user session and refresh record
        conn.execute(
            """INSERT INTO user_sessions 
               (id, user_id, family_id, current_refresh_token_hash, device_fingerprint, ip_address, user_agent, created_at, last_active_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, user_row["id"], family_id, hashed_refresh, req.device_fingerprint, client_ip, user_agent, now_str, now_str, exp_str),
        )
        refresh_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO refresh_token_records 
               (id, session_id, family_id, token_hash, is_revoked, expires_at, created_at)
               VALUES (?, ?, ?, ?, 0, ?, ?)""",
            (refresh_id, session_id, family_id, hashed_refresh, exp_str, now_str),
        )
        conn.commit()

        # Set cookies
        set_auth_cookies(response, raw_access, raw_refresh, csrf_token=csrf_token)

        audit_logger.log(
            event_type=AuditEventType.LOGIN_SUCCESS,
            status="SUCCESS",
            user_id=user_row["id"],
            actor_role=user_row["role"],
            ip_address=client_ip,
            user_agent=user_agent,
            reason="User authenticated successfully.",
            metadata={"session_id": session_id, "family_id": family_id},
        )

        return LoginResponse(
            access_token=raw_access,
            token_type="Bearer",
            expires_in_seconds=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user_id=user_row["id"],
            email=user_row["email"],
            full_name=user_row["full_name"],
            role=user_row["role"],
            csrf_token=csrf_token,
        )


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh_tokens(
    request: Request,
    response: Response,
    body: Optional[RefreshRequest] = None,
) -> TokenResponse:
    """Rotates refresh tokens and issues fresh access token with Token Reuse Detection."""
    client_ip = request.client.host if request.client else "127.0.0.1"

    # Extract raw refresh token from cookie or body
    raw_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_token and body and body.refresh_token:
        raw_token = body.refresh_token

    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token in cookie or request body.",
        )

    target_hash = hash_token(raw_token)
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()

    with get_db() as conn:
        token_rec = conn.execute(
            "SELECT * FROM refresh_token_records WHERE token_hash = ?",
            (target_hash,),
        ).fetchone()

        if not token_rec:
            audit_logger.log(
                event_type=AuditEventType.TOKEN_REFRESH_SUCCESS,
                status="FAILED",
                ip_address=client_ip,
                reason="Unknown refresh token presented.",
            )
            clear_auth_cookies(response)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

        family_id = token_rec["family_id"]
        session_id = token_rec["session_id"]

        # ======================================================================
        # CRITICAL REUSE DETECTION (RTR SECURITY VIOLATION)
        # ======================================================================
        if token_rec["is_revoked"] == 1:
            # Token was already used and rotated! Replay attack or leakage detected!
            # Invalidate ALL tokens in this family immediately!
            conn.execute(
                "UPDATE refresh_token_records SET is_revoked = 1, revoked_at = ? WHERE family_id = ?",
                (now_str, family_id),
            )
            conn.execute(
                "UPDATE user_sessions SET revoked_at = ?, revocation_reason = 'TOKEN_REUSE_DETECTED' WHERE family_id = ?",
                (now_str, family_id),
            )
            conn.commit()

            audit_logger.log(
                event_type=AuditEventType.TOKEN_REUSE_DETECTED,
                status="BLOCKED",
                ip_address=client_ip,
                reason="Previously invalidated refresh token replayed! Entire family terminated.",
                metadata={"family_id": family_id, "session_id": session_id},
            )
            clear_auth_cookies(response)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Security breach detected: Reused authentication token. All sessions revoked.",
            )

        # Check session validity
        session_row = conn.execute(
            "SELECT s.*, u.email, u.role FROM user_sessions s JOIN users u ON s.user_id = u.id WHERE s.id = ?",
            (session_id,),
        ).fetchone()

        if not session_row or session_row["revoked_at"] is not None:
            clear_auth_cookies(response)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session has been revoked.")

        if now > datetime.fromisoformat(token_rec["expires_at"]):
            clear_auth_cookies(response)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token has expired.")

        # ======================================================================
        # Valid Rotation: Invalidate used token, issue new token in same family
        # ======================================================================
        conn.execute(
            "UPDATE refresh_token_records SET is_revoked = 1, revoked_at = ? WHERE id = ?",
            (now_str, token_rec["id"]),
        )

        new_raw_refresh, new_hash_refresh, new_refresh_exp = TokenService.create_refresh_token()
        new_refresh_id = str(uuid.uuid4())
        new_refresh_exp_str = new_refresh_exp.isoformat()

        conn.execute(
            """INSERT INTO refresh_token_records 
               (id, session_id, family_id, token_hash, is_revoked, expires_at, created_at)
               VALUES (?, ?, ?, ?, 0, ?, ?)""",
            (new_refresh_id, session_id, family_id, new_hash_refresh, new_refresh_exp_str, now_str),
        )
        conn.execute(
            "UPDATE user_sessions SET current_refresh_token_hash = ?, last_active_at = ? WHERE id = ?",
            (new_hash_refresh, now_str, session_id),
        )
        conn.commit()

        # Issue fresh Access Token
        raw_access, jti, access_exp = TokenService.create_access_token(
            user_id=session_row["user_id"],
            email=session_row["email"],
            role=session_row["role"],
            session_id=session_id,
            family_id=family_id,
        )

        set_auth_cookies(response, raw_access, new_raw_refresh)

        audit_logger.log(
            event_type=AuditEventType.TOKEN_REFRESH_SUCCESS,
            status="SUCCESS",
            user_id=session_row["user_id"],
            actor_role=session_row["role"],
            ip_address=client_ip,
            reason="Refresh token rotated successfully.",
            metadata={"session_id": session_id, "family_id": family_id},
        )

        return TokenResponse(
            access_token=raw_access,
            token_type="Bearer",
            expires_in_seconds=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )


@router.post("/auth/logout")
async def logout(
    response: Response,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, str]:
    """Terminates active session, blacklists JTI, and clears cookies."""
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()

    # Blacklist current access token JTI for remaining 15-min window
    jti_blacklist.revoke(current_user.jti, now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    with get_db() as conn:
        conn.execute(
            "UPDATE user_sessions SET revoked_at = ?, revocation_reason = 'LOGOUT' WHERE id = ?",
            (now_str, current_user.session_id),
        )
        conn.execute(
            "UPDATE refresh_token_records SET is_revoked = 1, revoked_at = ? WHERE session_id = ?",
            (now_str, current_user.session_id),
        )
        conn.commit()

    clear_auth_cookies(response)

    audit_logger.log(
        event_type=AuditEventType.LOGOUT,
        status="SUCCESS",
        user_id=current_user.id,
        actor_role=current_user.role,
        reason="Explicit logout completed.",
        metadata={"session_id": current_user.session_id},
    )

    return {"status": "success", "message": "Logged out successfully."}


@router.post("/auth/logout-all")
async def logout_all(
    response: Response,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, str]:
    """Revokes all active sessions across all devices for current user."""
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()

    jti_blacklist.revoke(current_user.jti, now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

    with get_db() as conn:
        conn.execute(
            "UPDATE user_sessions SET revoked_at = ?, revocation_reason = 'LOGOUT_ALL' WHERE user_id = ? AND revoked_at IS NULL",
            (now_str, current_user.id),
        )
        conn.execute(
            """UPDATE refresh_token_records SET is_revoked = 1, revoked_at = ?
               WHERE session_id IN (SELECT id FROM user_sessions WHERE user_id = ?)""",
            (now_str, current_user.id),
        )
        conn.commit()

    clear_auth_cookies(response)

    audit_logger.log(
        event_type=AuditEventType.LOGOUT_ALL_SESSIONS,
        status="SUCCESS",
        user_id=current_user.id,
        actor_role=current_user.role,
        reason="User terminated all active sessions.",
    )

    return {"status": "success", "message": "All sessions terminated."}


@router.get("/auth/me", response_model=UserProfileResponse)
async def get_my_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserProfileResponse:
    """Returns the caller's profile and RBAC permissions."""
    with get_db() as conn:
        user_row = conn.execute("SELECT * FROM users WHERE id = ?", (current_user.id,)).fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found.")

        perms = list(ROLE_PERMISSIONS.get(current_user.role, []))
        return UserProfileResponse(
            id=user_row["id"],
            email=user_row["email"],
            full_name=user_row["full_name"],
            phone=user_row["phone"],
            role=user_row["role"],
            permissions=perms,
        )


# ==============================================================================
# WhatsApp Identity Bridge Endpoints
# ==============================================================================

@router.post("/auth/whatsapp/link-code")
async def generate_whatsapp_link_code(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Generates a 6-digit one-time binding code for WhatsApp account linking."""
    code = wa_bridge.generate_web_binding_code(current_user.id)
    return {
        "status": "success",
        "link_code": code,
        "expires_in_minutes": 10,
        "instructions": f"WhatsApp-da bot nömrəmizə `!link {code}` yazaraq hesabınızı təsdiqləyin.",
    }


@router.post("/auth/whatsapp/webhook", response_model=WhatsAppWebhookResponse)
async def whatsapp_webhook(
    req: WhatsAppWebhookRequest,
) -> WhatsAppWebhookResponse:
    """Inbound webhook called by WhatsApp Sidecar / Baileys for message routing."""
    sender = req.sender
    msg = req.message

    # Rate limiting on high-frequency spam per JID
    if rate_limiter.is_whatsapp_rate_limited(sender):
        return WhatsAppWebhookResponse(
            status="throttled",
            sender=sender,
            user_id=None,
            reply="⚠️ Çoxlu sayda ardıcıl mesaj göndərildi. Zəhmət olmasa bir qədər gözləyin.",
        )

    # 1. Check if it's an admin command first
    resolved_user = wa_bridge.resolve_user(sender)
    is_admin_cmd, admin_reply = admin_gate.process_admin_command(sender, msg, resolved_user)
    if is_admin_cmd:
        return WhatsAppWebhookResponse(
            status="handled_by_admin_gate",
            sender=sender,
            user_id=resolved_user.get("id") if resolved_user else None,
            reply=admin_reply,
        )

    # 2. Pass to Onboarding State Machine & User Resolver
    user, reply = wa_bridge.handle_incoming_message(sender, msg)

    if not user:
        # User in onboarding state, send back onboarding reply
        return WhatsAppWebhookResponse(
            status="onboarding",
            sender=sender,
            user_id=None,
            reply=reply,
        )

    # User is authenticated!
    # If there was an onboarding completion message (e.g. initial greeting), return it
    if reply:
        return WhatsAppWebhookResponse(
            status="authenticated_init",
            sender=sender,
            user_id=user["id"],
            reply=reply,
        )

    # User is ready for normal operational commands (!kargo, !unvan, !hesabla)
    return WhatsAppWebhookResponse(
        status="authenticated",
        sender=sender,
        user_id=user["id"],
        reply=f"Hörmətli {user['full_name']}, əmriniz qəbul edildi: `{msg}`",
    )


# ==============================================================================
# Admin Audit Inspection Route
# ==============================================================================

@router.get("/admin/audit-logs")
async def get_audit_logs(
    user_id: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 50,
    current_admin: AuthenticatedUser = Depends(require_role(UserRole.SUPER_ADMIN, UserRole.ADMIN)),
) -> List[Dict[str, Any]]:
    """Admin-only endpoint to inspect structured security audit logs."""
    return audit_logger.query(user_id=user_id, event_type=event_type, limit=limit)
