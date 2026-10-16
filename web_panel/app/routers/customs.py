"""SmartCustoms Management Router."""

from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_all_declarations, get_all_orders
from app.services.customs_bridge import trigger_customs_sync, create_manual_declaration_draft

router = APIRouter(prefix="/customs")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("", response_class=HTMLResponse)
async def customs_dashboard(request: Request):
    """SmartCustoms management view with declarations list, status, duty amounts, and manual declaration modal."""
    declarations = get_all_declarations()
    # Find orders without declarations for the manual declaration modal dropdown
    all_orders = get_all_orders(limit=100)
    declared_order_ids = {d["order_id"] for d in declarations if d.get("order_id")}
    undeclared_orders = [o for o in all_orders if o["id"] not in declared_order_ids]

    total_duty = sum(float(d.get("duty_estimate_azn") or 0.0) for d in declarations)

    return templates.TemplateResponse(request=request, name="customs.html", context={
        "page_title": "SmartCustoms Management",
        "active_tab": "customs",
        "declarations": declarations,
        "undeclared_orders": undeclared_orders,
        "total_declarations": len(declarations),
        "total_duty_azn": round(total_duty, 2),
    })


@router.post("/sync")
async def sync_customs(request: Request):
    """Triggers live synchronization with SmartCustoms portal."""
    result = await trigger_customs_sync()
    if request.headers.get("accept", "").find("application/json") != -1 or request.headers.get("hx-request"):
        return JSONResponse(result)
    return RedirectResponse(url="/customs?synced=true", status_code=303)


@router.post("/draft/{order_id}")
async def create_declaration_draft(order_id: str):
    """Generates an auto-categorized declaration draft ready for submission."""
    result = create_manual_declaration_draft(order_id)
    return JSONResponse(result)


@router.post("/submit/{order_id}")
async def submit_declaration_endpoint(order_id: str):
    """Submits declaration officially to SmartCustoms, attaching commercial invoice PDF."""
    from app.services.customs_bridge import submit_official_declaration
    result = await submit_official_declaration(order_id)
    return JSONResponse(result)

