"""Orders Explorer Router."""

from __future__ import annotations

from typing import Optional
from pathlib import Path
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.database import get_all_orders, get_order_by_id

router = APIRouter(prefix="/orders")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("", response_class=HTMLResponse)
async def orders_explorer(
    request: Request,
    q: Optional[str] = Query(None, description="Search keyword"),
    platform: Optional[str] = Query(None, description="Filter by platform"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """Full orders explorer page with items table, carrier, tracking number, and status."""
    orders = get_all_orders(search=q, platform=platform, status=status, limit=100)

    return templates.TemplateResponse(request=request, name="orders.html", context={
        "page_title": "Orders Explorer",
        "active_tab": "orders",
        "orders": orders,
        "total_count": len(orders),
        "search_query": q or "",
        "selected_platform": platform or "ALL",
        "selected_status": status or "ALL",
    })


@router.get("/{order_id}", response_class=JSONResponse)
async def get_order_details(order_id: str):
    """Fetches single order breakdown with itemized list."""
    order = get_order_by_id(order_id)
    if not order:
        return JSONResponse(status_code=404, content={"error": "Sifariş tapılmadı"})
    return order
