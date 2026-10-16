"""In-Panel Interactive Screencast & Re-Auth Service via Playwright and WebSocket.

Provides zero-public-port browser interaction directly through the 127.0.0.1:48481 SSH tunnel.
Runs in an ephemeral, isolated profile to prevent SingletonLock conflicts with pcs-worker.
"""

from __future__ import annotations

import asyncio
import math
import random
import base64
import json
import logging
import shutil
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from app.database import get_connection

logger = logging.getLogger(__name__)

PLATFORM_URLS: Dict[str, str] = {
    "temu": "https://www.temu.com/bgt_order_list.html",
    "e_customs": "https://e.customs.gov.az/login",
    "trendyol": "https://www.trendyol.com/giris",
    "taobao": "https://login.taobao.com/",
}


async def simulate_human_drag(page: Any, from_x: int, from_y: int, to_x: int, to_y: int) -> None:
    """Simulates a natural human drag movement to satisfy anti-bot detection algorithms:
    - Ease-in-out cosine velocity (starts slow, speeds up in the middle, slows down near target).
    - Realistic vertical micro-jitter (human hand wobbles +/- 1.0-1.5px).
    - Slight overshoot (3-5px) and smooth micro-adjustment.
    - Realistic human delays at each movement phase.
    """
    total_dx = to_x - from_x
    total_dy = to_y - from_y
    dist = math.hypot(total_dx, total_dy)

    # Move smoothly to start point and pause before pressing down
    await page.mouse.move(from_x, from_y)
    await asyncio.sleep(random.uniform(0.08, 0.16))
    await page.mouse.down()
    await asyncio.sleep(random.uniform(0.06, 0.12))

    # Number of track points based on distance (at least 30 points)
    num_points = max(30, int(dist / 4.5))

    # Calculate slight human overshoot if moving more than 40px
    overshoot_px = random.randint(3, 5) if abs(total_dx) > 40 else 0
    target_dx = total_dx + overshoot_px

    for i in range(1, num_points + 1):
        t = i / num_points
        # Cosine ease-in-out: progress in [0, 1]
        progress = (1.0 - math.cos(t * math.pi)) / 2.0

        cur_x = from_x + (target_dx * progress)
        # Vertical wobble with slight decay towards the end
        wobble_y = random.uniform(-1.2, 1.2) * (1.0 - (t * 0.5))
        cur_y = from_y + (total_dy * progress) + wobble_y

        await page.mouse.move(round(cur_x), round(cur_y))

        # Dynamic human delay: slower at start/finish, faster during sprint
        step_delay = 0.008 + 0.018 * (1.0 - math.sin(t * math.pi))
        await asyncio.sleep(step_delay)

    # If overshot, adjust gently back to exact destination
    if overshoot_px > 0:
        await asyncio.sleep(random.uniform(0.05, 0.09))
        adjust_steps = random.randint(4, 6)
        for step in range(1, adjust_steps + 1):
            st = step / adjust_steps
            adj_x = (from_x + target_dx) - (overshoot_px * st)
            adj_y = to_y + random.uniform(-0.5, 0.5)
            await page.mouse.move(round(adj_x), round(adj_y))
            await asyncio.sleep(0.015)

    await asyncio.sleep(random.uniform(0.12, 0.22))
    await page.mouse.up()


class ScreencastSession:
    """Manages an active interactive browser session for a specific platform."""

    def __init__(self, platform: str):
        self.platform = platform.lower()
        self.target_url = PLATFORM_URLS.get(self.platform, "https://www.google.com")
        self.temp_dir: Optional[str] = None
        self.playwright: Any = None
        self.browser: Any = None
        self.context: Any = None
        self.page: Any = None
        self.is_running: bool = False
        self._lock = asyncio.Lock()

    async def start(self) -> bool:
        """Starts an isolated headless browser and navigates to the target platform."""
        async with self._lock:
            if self.is_running and self.page is not None:
                return True

            try:
                from playwright.async_api import async_playwright

                self.temp_dir = tempfile.mkdtemp(prefix=f"pcs_reauth_{self.platform}_")
                self.playwright = await async_playwright().start()

                self.context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=self.temp_dir,
                    headless=True,
                    viewport={"width": 1280, "height": 800},
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
                    ),
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                        "--disable-software-rasterizer",
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-infobars",
                    ]
                )
                self.browser = None

                # Apply anti-bot stealth evading Alibaba/GeeTest/Cloudflare detection
                try:
                    from playwright_stealth import Stealth
                    await Stealth().apply_stealth_async(self.context)
                    logger.info("[%s] Playwright stealth anti-bot protections applied.", self.platform)
                except Exception as stealth_err:
                    logger.warning("[%s] Stealth apply warning: %s", self.platform, stealth_err)

                await self.context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    window.chrome = window.chrome || { runtime: {} };
                """)

                pages = self.context.pages
                self.page = pages[0] if pages else await self.context.new_page()
                logger.info("[%s] Navigating to %s", self.platform, self.target_url)
                try:
                    await self.page.goto(self.target_url, wait_until="domcontentloaded", timeout=30_000)
                except Exception as goto_err:
                    logger.warning("[%s] Goto initial load warning: %s", self.platform, goto_err)
                self.is_running = True
                return True
            except Exception as exc:
                logger.error("Failed to start screencast session for %s: %s", self.platform, exc)
                await self.stop()
                return False

    async def capture_frame(self) -> Optional[str]:
        """Captures a JPEG screenshot frame encoded as base64 string."""
        if not self.is_running or not self.page:
            return None
        try:
            buf = await self.page.screenshot(type="jpeg", quality=60)
            return base64.b64encode(buf).decode("ascii")
        except Exception as exc:
            logger.debug("Frame capture skipped: %s", exc)
            return None

    async def handle_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Executes interactive mouse and keyboard commands on the browser page."""
        if not self.is_running or not self.page:
            return {"ok": False, "error": "Session not active"}

        action = data.get("type")
        try:
            if action == "click":
                x = int(data.get("x", 0))
                y = int(data.get("y", 0))
                await self.page.mouse.click(x, y)
                return {"ok": True, "action": "click", "x": x, "y": y}

            elif action == "mousedown":
                x = int(data.get("x", 0))
                y = int(data.get("y", 0))
                await self.page.mouse.move(x, y)
                await self.page.mouse.down()
                return {"ok": True, "action": "mousedown", "x": x, "y": y}

            elif action == "mousemove":
                x = int(data.get("x", 0))
                y = int(data.get("y", 0))
                await self.page.mouse.move(x, y, steps=3)
                return {"ok": True, "action": "mousemove", "x": x, "y": y}

            elif action == "mouseup":
                x = int(data.get("x", 0))
                y = int(data.get("y", 0))
                await self.page.mouse.move(x, y)
                await self.page.mouse.up()
                return {"ok": True, "action": "mouseup", "x": x, "y": y}

            elif action == "drag":
                from_x = int(data.get("from_x", 0))
                from_y = int(data.get("from_y", 0))
                to_x = int(data.get("to_x", 0))
                to_y = int(data.get("to_y", 0))
                await simulate_human_drag(self.page, from_x, from_y, to_x, to_y)
                logger.info("[%s] Executed human-like anti-bot drag from (%d, %d) to (%d, %d)", self.platform, from_x, from_y, to_x, to_y)
                return {"ok": True, "action": "drag", "from": [from_x, from_y], "to": [to_x, to_y]}

            elif action == "type":
                text = str(data.get("text", ""))
                if text:
                    await self.page.keyboard.type(text)
                return {"ok": True, "action": "type"}

            elif action == "press":
                key = str(data.get("key", ""))
                if key:
                    await self.page.keyboard.press(key)
                return {"ok": True, "action": "press", "key": key}

            elif action == "scroll":
                delta_y = int(data.get("delta_y", 0))
                await self.page.mouse.wheel(0, delta_y)
                return {"ok": True, "action": "scroll"}

            elif action == "navigate":
                url = str(data.get("url", ""))
                if url:
                    await self.page.goto(url, wait_until="domcontentloaded", timeout=25_000)
                return {"ok": True, "action": "navigate", "url": url}

            return {"ok": False, "error": f"Unknown action: {action}"}
        except Exception as exc:
            logger.warning("Error executing screencast action %s: %s", action, exc)
            return {"ok": False, "error": str(exc)}

    async def save_session_cookies(self) -> Dict[str, Any]:
        """Extracts live cookies from the session and updates platform_sessions in SQLite."""
        if not self.context:
            return {"ok": False, "error": "Context not available"}

        try:
            cookies = await self.context.cookies()
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")

            platform_title = self.platform.capitalize()
            if self.platform == "e_customs":
                platform_title = "SmartCustoms"

            details = json.dumps({
                "cookies_count": len(cookies),
                "last_auth_method": "IN_PANEL_SCREENCAST",
                "current_url": self.page.url if self.page else "",
                "captured_at": now_iso,
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

            logger.info("Session saved for %s with %d cookies.", platform_title, len(cookies))
            return {
                "ok": True,
                "platform": platform_title,
                "cookies_count": len(cookies),
                "status": "ACTIVE",
                "message": f"{platform_title} sessiyası uğurla qeyd edildi və aktivləşdirildi!"
            }
        except Exception as exc:
            logger.error("Failed to save session for %s: %s", self.platform, exc)
            return {"ok": False, "error": str(exc)}

    async def stop(self):
        """Cleanly terminates the browser context and removes ephemeral temp files."""
        self.is_running = False
        try:
            if self.page:
                await self.page.close()
        except Exception:
            pass
        try:
            if self.context:
                await self.context.close()
        except Exception:
            pass
        try:
            if self.browser:
                await self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass

        if self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = None

        self.page = None
        self.context = None
        self.browser = None
        self.playwright = None
        logger.info("[%s] Screencast session stopped and cleaned up.", self.platform)


# Session registry per platform
_ACTIVE_SCREENCASTS: Dict[str, ScreencastSession] = {}


def get_or_create_screencast(platform: str) -> ScreencastSession:
    p = platform.lower()
    if p not in _ACTIVE_SCREENCASTS:
        _ACTIVE_SCREENCASTS[p] = ScreencastSession(p)
    return _ACTIVE_SCREENCASTS[p]


async def close_screencast(platform: str):
    p = platform.lower()
    if p in _ACTIVE_SCREENCASTS:
        session = _ACTIVE_SCREENCASTS.pop(p)
        await session.stop()
