"""Dashboard & Executive Overview Router."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.database import get_all_orders, get_all_declarations, get_platform_sessions, get_connection
from app.services.quota_calculator import calculate_monthly_quota

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def dashboard_overview(request: Request):
    fin_param = request.query_params.get("fin")
    quota_data = calculate_monthly_quota(target_fin=fin_param)
    orders = get_all_orders(limit=8)
    declarations = get_all_declarations()
    sessions = get_platform_sessions()

    # Lifetime Financials
    conn = get_connection()
    cur = conn.cursor()
    total_orders_count = cur.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    total_lifetime_azn = cur.execute(
        "SELECT SUM(COALESCE(invoice_amount_azn, temu_invoice_amount, 0)) FROM orders"
    ).fetchone()[0] or 0.0
    conn.close()

    declared_count = sum(1 for d in declarations if "bəyan" in (d.get("status") or "").lower() or "təsdiq" in (d.get("status") or "").lower())
    pending_count = total_orders_count - declared_count

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "page_title": "Executive Overview",
        "active_tab": "dashboard",
        "quota": quota_data,
        "total_orders": total_orders_count,
        "declared_count": declared_count,
        "pending_count": pending_count,
        "lifetime_azn": round(total_lifetime_azn, 2),
        "recent_orders": orders,
        "declarations_count": len(declarations),
        "sessions": sessions,
    })
