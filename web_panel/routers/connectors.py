"""Multi-Platform Connectors Router."""

from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_platform_sessions
from app.services.platform_manager import trigger_reauth, submit_otp_code

router = APIRouter(prefix="/connectors")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("", response_class=HTMLResponse)
async def list_connectors(request: Request):
    """Displays multi-platform connector status, session health, and re-auth triggers."""
    sessions = get_platform_sessions()
    return templates.TemplateResponse(request=request, name="connectors.html", context={
        "page_title": "Multi-Platform Connectors",
        "active_tab": "connectors",
        "sessions": sessions,
    })


@router.post("/{platform}/reauth")
async def reauthenticate_platform(platform: str):
    """Triggers re-authentication flow for a connector."""
    result = trigger_reauth(platform)
    return JSONResponse(result)


@router.post("/{platform}/otp")
async def verify_otp(platform: str, otp_code: str = Form(...)):
    """Verifies SMS OTP code and activates session."""
    result = submit_otp_code(platform, otp_code)
    return JSONResponse(result)


@router.post("/{platform}/cookies")
async def import_cookies_route(platform: str, cookies_raw: str = Form(...)):
    """Imports raw cookie string or JSON and marks the platform ACTIVE."""
    import json
    from datetime import datetime, timezone, timedelta
    from app.database import get_connection

    raw = cookies_raw.strip()
    if not raw:
        return JSONResponse({"success": False, "error": "Kuki mətni boşdur!"})

    parsed_cookies = []
    if raw.startswith("[") or raw.startswith("{"):
        try:
            parsed = json.loads(raw)
            parsed_cookies = parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            pass

    if not parsed_cookies:
        for pair in raw.split(";"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                parsed_cookies.append({"name": k.strip(), "value": v.strip(), "domain": f".{platform.lower()}.com"})

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    platform_title = "SmartCustoms" if platform.lower() == "e_customs" else platform.capitalize()

    try:
        cookie_path = Path(f"/data/pcs/cookies_{platform.lower()}.json")
        cookie_path.parent.mkdir(parents=True, exist_ok=True)
        cookie_path.write_text(json.dumps(parsed_cookies, indent=2), encoding="utf-8")
    except Exception:
        pass

    details = json.dumps({
        "cookies_count": len(parsed_cookies),
        "last_auth_method": "MANUAL_IMPORT",
        "imported_at": now_iso
    })

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO platform_sessions (platform, status, last_authenticated_at, expires_at, details)
        VALUES (?, 'ACTIVE', ?, ?, ?)
        ON CONFLICT(platform) DO UPDATE SET
            status = 'ACTIVE',
            last_authenticated_at = excluded.last_authenticated_at,
            expires_at = excluded.expires_at,
            details = excluded.details
    """, (platform_title, now_iso, expires_at, details))
    conn.commit()
    conn.close()

    return JSONResponse({
        "success": True,
        "message": f"{platform_title} sessiyası uğurla idxal edildi və aktivləşdirildi! ({len(parsed_cookies)} kuki)",
        "platform": platform_title,
        "cookies_count": len(parsed_cookies)
    })
