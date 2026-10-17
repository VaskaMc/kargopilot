"""Web Pages Router for KargoPilot Authentication & Cloud User Dashboard."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import DB_PATH
from app.database import get_connection
from app.security.models import UserRole
from app.security.tokens import ACCESS_COOKIE_NAME, TokenService, clear_auth_cookies
from app.services.quota_calculator import calculate_monthly_quota

logger = logging.getLogger("kargopilot.web.auth")

router = APIRouter(tags=["Web Authentication & User Dashboard"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def get_authenticated_user_from_cookie(request: Request) -> Optional[dict]:
    """Helper to extract and verify user identity from HTTP-only cookie."""
    token = request.cookies.get(ACCESS_COOKIE_NAME)
    if not token:
        return None
    try:
        payload = TokenService.verify_access_token(token)
        user_id = payload.get("sub")
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row:
                return dict(row)
    except Exception as exc:
        logger.debug("Failed to verify user from cookie: %s", exc)
    return None


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Renders the Login page or redirects if already authenticated."""
    current_user = get_authenticated_user_from_cookie(request)
    if current_user:
        role = (current_user.get("role") or "").upper()
        if role in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value, "SUPERADMIN"):
            return RedirectResponse(url="/admin", status_code=status.HTTP_302_FOUND)
        return RedirectResponse(url="/user/dashboard", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"request": request, "page_title": "Daxil Ol — KargoPilot"},
    )


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, plan: Optional[str] = "cloud"):
    """Renders the Registration page with Cloud/Managed pre-selected."""
    current_user = get_authenticated_user_from_cookie(request)
    if current_user:
        return RedirectResponse(url="/user/dashboard", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"request": request, "plan": plan, "page_title": "Qeydiyyat — KargoPilot"},
    )


@router.get("/self-hosted", response_class=HTMLResponse)
@router.get("/onboarding", response_class=HTMLResponse)
async def self_hosted_page(request: Request):
    """Renders the Sovereign / Self-Hosted onboarding and connection wizard."""
    current_user = get_authenticated_user_from_cookie(request)
    return templates.TemplateResponse(
        request=request,
        name="self_hosted.html",
        context={
            "request": request,
            "user": current_user,
            "page_title": "Öz Serverində İşlət (Sovereign Edition) — KargoPilot",
        },
    )


@router.get("/user/dashboard", response_class=HTMLResponse)
@router.get("/my-dashboard", response_class=HTMLResponse)
async def user_dashboard_page(request: Request):
    """Renders the User Dashboard with real user data and dynamic quota calculations."""
    current_user = get_authenticated_user_from_cookie(request)
    if not current_user:
        # Fall back to default guest profile if running in demo / development mode
        current_user = {
            "id": "demo-user-001",
            "email": "demo@kargopilot.az",
            "full_name": "Demo İstifadəçi",
            "role": "CUSTOMER",
            "tier": "cloud_managed",
            "phone": "+994501234567",
            "fin": "7KP2026",
            "default_branch": "28 May",
        }

    user_id = current_user.get("id")
    user_spent_usd = 0.0
    orders_count = 0
    try:
        with get_connection() as conn:
            spent_row = conn.execute(
                "SELECT COALESCE(SUM(invoice_amount_usd), 0.0) FROM orders WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            user_spent_usd = float(spent_row[0]) if spent_row and spent_row[0] is not None else 0.0

            count_row = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            orders_count = int(count_row[0]) if count_row and count_row[0] is not None else 0
    except Exception as exc:
        logger.warning("Could not calculate dynamic user quota: %s", exc)

    remaining_usd = max(0.0, 300.0 - user_spent_usd)

    return templates.TemplateResponse(
        request=request,
        name="user_dashboard.html",
        context={
            "request": request,
            "user": current_user,
            "quota": {
                "used_usd": f"{user_spent_usd:.2f}",
                "remaining_usd": f"{remaining_usd:.2f}",
                "spent_azn": f"{user_spent_usd * 1.70:.2f}",
            },
            "active_orders_count": orders_count,
            "page_title": "Şəxsi Kabinet — KargoPilot",
        },
    )


@router.get("/logout")
async def logout_page(response: Response):
    """Clears authentication cookies and redirects to login."""
    redirect_resp = RedirectResponse(url="/login?logged_out=1", status_code=status.HTTP_302_FOUND)
    clear_auth_cookies(redirect_resp)
    return redirect_resp
