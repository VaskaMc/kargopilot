"""In-Panel Interactive Screencast & Re-Auth Router.

Renders interactive browser canvas and provides WebSocket streaming for login and captcha challenges.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.services.screencast_service import (
    get_or_create_screencast,
    close_screencast,
    PLATFORM_URLS,
)

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/screencast", response_class=HTMLResponse)
async def default_screencast_viewer(request: Request, platform: str = "temu"):
    """Renders interactive HTML5 Canvas Screencast interface from the main sidebar."""
    p_lower = platform.lower()
    target_url = PLATFORM_URLS.get(p_lower, "https://www.temu.com")
    platform_name = "SmartCustoms" if p_lower == "e_customs" else p_lower.capitalize()

    return templates.TemplateResponse(request=request, name="screencast.html", context={
        "page_title": f"{platform_name} — Canlı Re-Auth & Captcha",
        "active_tab": "screencast",
        "platform": p_lower,
        "platform_name": platform_name,
        "target_url": target_url,
    })


@router.get("/connectors/{platform}/screencast", response_class=HTMLResponse)
async def screencast_viewer(request: Request, platform: str):
    """Renders interactive HTML5 Canvas Screencast interface for browser interaction."""
    p_lower = platform.lower()
    target_url = PLATFORM_URLS.get(p_lower, "https://www.google.com")
    platform_name = "SmartCustoms" if p_lower == "e_customs" else platform.capitalize()

    return templates.TemplateResponse(request=request, name="screencast.html", context={
        "page_title": f"{platform_name} Re-Auth & Captcha",
        "active_tab": "screencast",
        "platform": p_lower,
        "platform_name": platform_name,
        "target_url": target_url,
    })


@router.websocket("/ws/screencast/{platform}")
async def screencast_websocket(websocket: WebSocket, platform: str):
    """Bidirectional WebSocket for live frame streaming and mouse/keyboard interaction."""
    await websocket.accept()
    session = get_or_create_screencast(platform)

    # Initialize browser if not running
    if not session.is_running:
        await websocket.send_json({"type": "status", "text": "Brauzer işə salınır...", "color": "amber"})
        started = await session.start()
        if not started:
            await websocket.send_json({"type": "status", "text": "Brauzer başladıla bilmədi!", "color": "rose"})
            await websocket.close()
            return
        await websocket.send_json({"type": "status", "text": "Canlı Bağlantı Quruldu", "color": "emerald"})

    # Task to stream frames
    async def frame_streamer():
        try:
            while session.is_running:
                frame_b64 = await session.capture_frame()
                if frame_b64:
                    await websocket.send_json({
                        "type": "frame",
                        "image": f"data:image/jpeg;base64,{frame_b64}",
                        "url": session.page.url if session.page else "",
                    })
                await asyncio.sleep(0.4)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception as e:
            logger.debug("Frame streaming ended: %s", e)

    import asyncio
    streamer_task = asyncio.create_task(frame_streamer())

    try:
        while True:
            data_text = await websocket.receive_text()
            try:
                data = json.loads(data_text)
                action_type = data.get("type")

                if action_type == "save_session":
                    res = await session.save_session_cookies()
                    await websocket.send_json({
                        "type": "notification",
                        "success": res.get("ok", False),
                        "message": res.get("message", res.get("error", "Xəta baş verdi")),
                    })

                elif action_type == "close":
                    break

                else:
                    await session.handle_input(data)
            except json.JSONDecodeError:
                pass
    except (WebSocketDisconnect, RuntimeError):
        logger.info("WebSocket client disconnected for screencast: %s", platform)
    finally:
        streamer_task.cancel()
        try:
            await streamer_task
        except asyncio.CancelledError:
            pass


@router.post("/connectors/{platform}/screencast/save")
async def save_session_route(platform: str):
    """Saves live cookies extracted from active screencast session."""
    session = get_or_create_screencast(platform)
    res = await session.save_session_cookies()
    return JSONResponse(res)


@router.post("/connectors/{platform}/screencast/stop")
async def stop_screencast_route(platform: str):
    """Stops the active screencast session and closes browser."""
    await close_screencast(platform)
    return JSONResponse({"ok": True, "message": f"{platform} sessiyası bağlandı."})
