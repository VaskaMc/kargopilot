"""Role-Based Access Control (RBAC), Permission Matrix, and Data-Layer Tenant Scoping.

Enforces:
- Authoritative role hierarchy: SUPER_ADMIN > ADMIN > CUSTOMER
- Granular permissions mapping across platform resources
- FastAPI dependencies: get_current_user, require_role, require_permissions
- Mandatory Data-Layer Tenant Isolation (the client is NEVER the authority)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.security.models import UserRole
from app.security.tokens import (
    ACCESS_COOKIE_NAME,
    TokenExpiredException,
    TokenInvalidException,
    TokenService,
)

logger = logging.getLogger("kargopilot.security.rbac")

bearer_scheme = HTTPBearer(auto_error=False)


# ==============================================================================
# RBAC Permissions Matrix
# ==============================================================================

ROLE_PERMISSIONS: Dict[str, Set[str]] = {
    UserRole.SUPER_ADMIN.value: {
        # Wildcard / Root permissions
        "*",
        # Users
        "users:read:all", "users:read:own", "users:create", "users:update:all", "users:update:own", "users:delete", "users:change_role", "users:unlock",
        # Orders
        "orders:read:all", "orders:read:own", "orders:create:any", "orders:create:own", "orders:update:all", "orders:update:own", "orders:delete",
        # Customs
        "customs:read:all", "customs:read:own", "customs:declare:any", "customs:declare:own", "customs:approve", "customs:override",
        # Carriers
        "carriers:read:all", "carriers:read:own", "carriers:sync:all", "carriers:sync:own", "carriers:manage_credentials",
        # Invoices
        "invoices:read:all", "invoices:read:own", "invoices:upload:any", "invoices:upload:own", "invoices:delete",
        # System Logs & Settings
        "logs:read", "logs:export", "settings:read", "settings:manage", "settings:backup",
    },
    UserRole.ADMIN.value: {
        # Logistics Operations / Support
        "users:read:all", "users:unlock",
        "orders:read:all", "orders:create:any", "orders:update:all",
        "customs:read:all", "customs:declare:any", "customs:approve",
        "carriers:read:all", "carriers:sync:all",
        "invoices:read:all", "invoices:upload:any",
        "logs:read",
        "settings:read",
    },
    UserRole.CUSTOMER.value: {
        # Strictly Tenant-Scoped (Own resources only)
        "users:read:own", "users:update:own",
        "orders:read:own", "orders:create:own", "orders:update:own",
        "customs:read:own", "customs:declare:own",
        "carriers:read:own", "carriers:sync:own",
        "invoices:read:own", "invoices:upload:own",
    },
}


@dataclass
class AuthenticatedUser:
    """Represents the validated identity extracted from the verified access token."""
    id: str
    email: str
    role: str
    session_id: str
    family_id: str
    jti: str

    def has_permission(self, permission: str) -> bool:
        """Checks if the user's role possesses the requested permission."""
        perms = ROLE_PERMISSIONS.get(self.role, set())
        if "*" in perms:
            return True
        return permission in perms

    @property
    def is_super_admin(self) -> bool:
        return self.role == UserRole.SUPER_ADMIN.value

    @property
    def is_admin(self) -> bool:
        return self.role in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value)

    @property
    def is_customer(self) -> bool:
        return self.role == UserRole.CUSTOMER.value


# ==============================================================================
# FastAPI Dependencies
# ==============================================================================

async def get_current_user(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> AuthenticatedUser:
    """Extracts and verifies JWT token from Authorization Bearer header or HTTP-only cookie."""
    token: Optional[str] = None

    # 1. Bearer header has priority
    if bearer and bearer.credentials:
        token = bearer.credentials
    # 2. Fall back to secure HTTP-only cookie
    elif ACCESS_COOKIE_NAME in request.cookies:
        token = request.cookies[ACCESS_COOKIE_NAME]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Missing token in header or cookie.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = TokenService.verify_access_token(token)
    except TokenExpiredException as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token has expired. Please refresh your session.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\", error_description=\"token_expired\""},
        ) from exc
    except TokenInvalidException as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token signature or payload.",
            headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
        ) from exc

    user = AuthenticatedUser(
        id=payload["sub"],
        email=payload.get("email", ""),
        role=payload.get("role", UserRole.CUSTOMER.value),
        session_id=payload.get("session_id", ""),
        family_id=payload.get("family_id", ""),
        jti=payload.get("jti", ""),
    )

    # Attach identity to request state for downstream middleware and audit logging
    request.state.user = user
    return user


def require_role(*allowed_roles: UserRole | str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """FastAPI dependency factory enforcing that caller possesses one of the allowed roles."""
    role_values = {r.value if isinstance(r, UserRole) else r for r in allowed_roles}

    def role_checker(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if current_user.role not in role_values and not current_user.is_super_admin:
            logger.warning(
                "Access denied: User %s with role %s attempted to access resource requiring %s",
                current_user.id,
                current_user.role,
                role_values,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient privileges. Required role: {list(role_values)}",
            )
        return current_user

    return role_checker


def require_permissions(*required_permissions: str) -> Callable[[AuthenticatedUser], AuthenticatedUser]:
    """FastAPI dependency factory enforcing that caller possesses all specified permissions."""

    def permission_checker(current_user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        for perm in required_permissions:
            if not current_user.has_permission(perm):
                logger.warning(
                    "Permission denied: User %s (role: %s) lacks permission '%s'",
                    current_user.id,
                    current_user.role,
                    perm,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: Missing required permission '{perm}'.",
                )
        return current_user

    return permission_checker


# ==============================================================================
# Data-Layer Tenant Isolation (Client is NEVER the authority)
# ==============================================================================

def verify_tenant_ownership(current_user: AuthenticatedUser, resource_user_id: str) -> None:
    """Enforces strict tenant isolation for customer roles.
    
    Admins and Super Admins may access resources across tenants. Customers may
    strictly access only records matching their authenticated user ID.
    """
    if current_user.is_admin:
        return

    if current_user.id != resource_user_id:
        logger.security_warning = (  # type: ignore
            f"BOLA / IDOR Violation detected! User {current_user.id} tried to access "
            f"resource owned by {resource_user_id}."
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You do not have permission to access or modify this resource.",
        )


def apply_tenant_filter_sql(base_query: str, current_user: AuthenticatedUser, user_col: str = "user_id") -> Tuple[str, Dict[str, Any]]:
    """Appends data-layer tenant isolation filter to raw SQL queries.
    
    If CUSTOMER: injects `AND {user_col} = :tenant_user_id`
    If ADMIN / SUPER_ADMIN: leaves query unscoped to allow global logistics view.
    """
    params: Dict[str, Any] = {}
    if current_user.is_customer:
        connector = "WHERE" if "WHERE" not in base_query.upper() else "AND"
        filtered_query = f"{base_query} {connector} {user_col} = :tenant_user_id"
        params["tenant_user_id"] = current_user.id
        return filtered_query, params
    return base_query, params
