"""RESTful JSON API endpoints for PCS Web Panel."""

from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.database import (
    get_all_orders,
    get_all_declarations,
    get_db_metrics,
    get_fin_profiles,
    get_active_fin,
    switch_active_fin,
)
from app.services.quota_calculator import calculate_monthly_quota
from app.services.customs_bridge import submit_official_declaration

router = APIRouter(prefix="/api")


@router.get("/quota")
async def api_quota(fin: Optional[str] = Query(None)):
    """Returns monthly 300 USD customs quota metrics for active or selected FIN."""
    return calculate_monthly_quota(target_fin=fin)


@router.get("/fin-profiles")
async def api_fin_profiles():
    """Returns all registered FIN profiles and active profile info."""
    return {
        "active_fin": get_active_fin(),
        "profiles": get_fin_profiles(),
    }


@router.post("/fin-profiles/switch")
async def api_switch_fin(data: dict):
    """Switches active customs declaration profile."""
    target_fin = data.get("fin")
    if not target_fin:
        return JSONResponse({"ok": False, "error": "FIN is required"}, status_code=400)
    return switch_active_fin(target_fin)


@router.post("/customs/submit-declaration/{order_id}")
async def api_submit_declaration(order_id: str):
    """Submits declaration with commercial invoice PDF to SmartCustoms."""
    return await submit_official_declaration(order_id)


@router.get("/orders")
async def api_orders(
    q: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    """Returns filtered orders."""
    return get_all_orders(search=q, platform=platform, status=status)


@router.get("/declarations")
async def api_declarations():
    """Returns SmartCustoms declarations list."""
    return get_all_declarations()


@router.get("/stats")
async def api_stats():
    """Returns DB and storage telemetry."""
    return get_db_metrics()

