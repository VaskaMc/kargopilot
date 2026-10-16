"""System Status, Service Health, and Live Logs Router."""

from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.services.system_monitor import get_system_telemetry, tail_recent_logs

router = APIRouter(prefix="/system")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("", response_class=HTMLResponse)
async def system_dashboard(request: Request):
    """System health dashboard, SQLite database size, and live operational logs."""
    telemetry = get_system_telemetry()
    logs = tail_recent_logs(max_lines=100)

    return templates.TemplateResponse(request=request, name="system.html", context={
        "page_title": "System Status & Logs",
        "active_tab": "system",
        "telemetry": telemetry,
        "logs": logs,
    })


@router.get("/logs/raw", response_class=JSONResponse)
async def get_raw_logs():
    """Returns the latest operational logs for dynamic terminal updates."""
    logs = tail_recent_logs(max_lines=150)
    return {"logs": logs}
