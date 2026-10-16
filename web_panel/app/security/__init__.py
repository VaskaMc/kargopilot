"""KargoPilot v4.5 Security, Identity & Access Package.

Exports:
- UserRole, AuthenticatedUser, ROLE_PERMISSIONS
- PasswordManager, password_manager, hash_token, generate_secure_token
- TokenService, set_auth_cookies, clear_auth_cookies, jti_blacklist
- get_current_user, require_role, require_permissions, verify_tenant_ownership, apply_tenant_filter_sql
- WhatsAppIdentityBridge, AdminCommandGate, normalize_phone_e164
- audit_logger, AuditLogger, AuditEventType, AuthChannel
- rate_limiter, AccountLockoutManager
- router as auth_router
"""

from app.security.models import (
    AuditEventType,
    AuthChannel,
    UserRole,
    WhatsAppUserState,
)
from app.security.crypto import (
    PasswordManager,
    password_manager,
    hash_token,
    generate_secure_token,
    generate_numeric_otp,
    constant_time_compare,
)
from app.security.tokens import (
    TokenService,
    TokenSecurityException,
    TokenExpiredException,
    TokenInvalidException,
    TokenReuseDetectedException,
    set_auth_cookies,
    clear_auth_cookies,
    jti_blacklist,
)
from app.security.rbac import (
    AuthenticatedUser,
    ROLE_PERMISSIONS,
    get_current_user,
    require_role,
    require_permissions,
    verify_tenant_ownership,
    apply_tenant_filter_sql,
)
from app.security.audit import (
    AuditLogger,
    audit_logger,
)
from app.security.rate_limiter import (
    rate_limiter,
    AccountLockoutManager,
)
from app.security.whatsapp_bridge import (
    WhatsAppIdentityBridge,
    AdminCommandGate,
    normalize_phone_e164,
    extract_jid,
)
from app.security.api_routes import router as auth_router

__all__ = [
    "UserRole",
    "WhatsAppUserState",
    "AuthChannel",
    "AuditEventType",
    "PasswordManager",
    "password_manager",
    "hash_token",
    "generate_secure_token",
    "generate_numeric_otp",
    "constant_time_compare",
    "TokenService",
    "TokenSecurityException",
    "TokenExpiredException",
    "TokenInvalidException",
    "TokenReuseDetectedException",
    "set_auth_cookies",
    "clear_auth_cookies",
    "jti_blacklist",
    "AuthenticatedUser",
    "ROLE_PERMISSIONS",
    "get_current_user",
    "require_role",
    "require_permissions",
    "verify_tenant_ownership",
    "apply_tenant_filter_sql",
    "AuditLogger",
    "audit_logger",
    "rate_limiter",
    "AccountLockoutManager",
    "WhatsAppIdentityBridge",
    "AdminCommandGate",
    "normalize_phone_e164",
    "extract_jid",
    "auth_router",
]
