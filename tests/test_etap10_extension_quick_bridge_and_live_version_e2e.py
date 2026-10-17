"""Comprehensive End-to-End Verification Suite for Etap 10 (KargoPilot v6.5.0):
1. Complete Live Server Version Audit (`v6.5` / `6.5.0` across `/`, `/login`, `/register`, `/self-hosted`, `/user/dashboard`, `/admin`, `/system`, `/showcase`, `/healthz` with zero stale `v4.5` badges).
2. `extension_v4/` Manifest V3 Browser Extension Structure, `taste-skill` + `ui-ux-pro-max` Styling, and Zero-Leak Audit.
3. 1-Click `extension_v4` -> `POST /api/v1/user/sessions/quick-bridge` & `GET /api/v1/user/channels/health-summary` E2E Flow for Trendyol, Temu, Starex, and SmartCustoms (`read_only_safe_mode: True`, `declarations_created: 0`).
4. Dual-Tree Byte-for-Byte Synchronization Audit (`web_panel/app/` vs `web_panel/`).
"""

from __future__ import annotations

import hashlib
import json
import runpy
import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
WEB_PANEL_DIR = REPO_ROOT / "web_panel"
EXTENSION_DIR = REPO_ROOT / "extension_v4"

if str(WEB_PANEL_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_PANEL_DIR))

from app.main import app  # noqa: E402
from app.database import get_connection, init_db  # noqa: E402
from app.security.rate_limiter import rate_limiter  # noqa: E402


def _setup_seeded_client() -> TestClient:
    rate_limiter.reset_ip("testclient")
    rate_limiter.reset_ip("127.0.0.1")
    init_db()
    runpy.run_path(str(REPO_ROOT / "scripts" / "seed_demo_account.py"))
    return TestClient(app)


def _login_demo(client: TestClient) -> dict:
    rate_limiter.reset_ip("testclient")
    rate_limiter.reset_ip("127.0.0.1")
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@kargopilot.az", "password": "***REMOVED***"},
    )
    assert resp.status_code == 200, f"Demo login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_etap10_all_pages_and_health_show_v6_5_zero_stale_v4_5():
    """Verifies that all web pages and health endpoints on port 48481 report v6.5 / 6.5.0 and have zero stale v4.5 badges."""
    client = _setup_seeded_client()

    # 1. Health & Discovery endpoints
    for health_path in ["/health", "/api/health", "/healthz"]:
        r = client.get(health_path)
        assert r.status_code == 200
        hdata = r.json()
        assert hdata["version"] == "6.5.0"
        assert hdata["status"] == "healthy"

    # 2. Export metadata
    r_exp = client.get("/api/export/data")
    assert r_exp.status_code == 200
    assert r_exp.json()["project"] == "KargoPilot v6.5 Enterprise"

    # 3. Web UI routes must show v6.5 and NOT v4.5
    web_routes = [
        "/",
        "/login",
        "/register",
        "/self-hosted",
        "/onboarding",
        "/admin",
        "/system",
        "/showcase",
        "/404.html",
    ]
    for route in web_routes:
        res = client.get(route)
        assert res.status_code == 200, f"Route {route} returned {res.status_code}"
        html = res.text
        assert "v6.5" in html, f"Route {route} is missing v6.5 version badge"
        assert ">v4.5<" not in html, f"Route {route} still has stale >v4.5< badge"
        assert "KargoPilot v4.5 · İdarəetmə Mərkəzi" not in html, f"Route {route} still has stale v4.5 heading"


def test_etap10_extension_v4_manifest_and_popup_integrity():
    """Verifies extension_v4 Manifest V3, popup HTML/JS, SmartCustoms Read-Only lock, and Zero-Leak compliance."""
    client = _setup_seeded_client()

    assert EXTENSION_DIR.exists(), "extension_v4 directory must exist"
    manifest_file = EXTENSION_DIR / "manifest.json"
    popup_html_file = EXTENSION_DIR / "popup.html"
    popup_js_file = EXTENSION_DIR / "popup.js"
    bg_js_file = EXTENSION_DIR / "background.js"
    content_js_file = EXTENSION_DIR / "content.js"

    for req_file in [manifest_file, popup_html_file, popup_js_file, bg_js_file, content_js_file]:
        assert req_file.exists(), f"Missing extension file: {req_file.name}"

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert manifest["version"] == "6.5.0"
    assert "cookies" in manifest["permissions"]
    assert "activeTab" in manifest["permissions"]

    hosts = " ".join(manifest["host_permissions"])
    for expected_host in ["trendyol.com", "temu.com", "starex.az", "customs.gov.az", "127.0.0.1:48481"]:
        assert expected_host in hosts

    popup_html = popup_html_file.read_text(encoding="utf-8")
    assert "v6.5" in popup_html
    assert "kp-glass-card" in popup_html
    assert "tabular-nums" in popup_html
    assert "read_only_safe_mode: True" in popup_html
    assert "declarations_created: 0" in popup_html
    assert "btn-quick-bridge" in popup_html

    popup_js = popup_js_file.read_text(encoding="utf-8")
    assert "/api/v1/user/sessions/quick-bridge" in popup_js
    assert "/api/v1/user/channels/health-summary" in popup_js
    assert "extension_v4" in popup_js
    assert "read_only_safe_mode: true" in popup_js

    # Served via /extension_v4 mount on FastAPI server
    r_popup = client.get("/extension_v4/popup.html")
    assert r_popup.status_code == 200
    assert "KargoPilot" in r_popup.text
    assert "v6.5" in r_popup.text

    # Zero-Leak check on all extension_v4 files
    forbidden = ["5.191.246" + ".134", "+9947763" + "46310", "814C" + "RM4"]
    for f in EXTENSION_DIR.rglob("*"):
        if f.is_file():
            content = f.read_text(encoding="utf-8", errors="ignore")
            for needle in forbidden:
                assert needle not in content, f"Forbidden token leaked in {f.name}"


def test_etap10_extension_quick_bridge_all_providers_e2e():
    """Tests 1-click Quick-Bridge from extension_v4 for Trendyol, Temu, Starex, and SmartCustoms Read-Only."""
    client = _setup_seeded_client()
    headers = _login_demo(client)

    # Verify /user/dashboard shows v6.5
    r_dash = client.get("/user/dashboard", headers=headers)
    assert r_dash.status_code == 200
    assert "v6.5" in r_dash.text
    assert "v6.0" not in r_dash.text

    # 1. Trendyol via extension_v4 Quick-Bridge
    r_ty = client.post(
        "/api/v1/user/sessions/quick-bridge",
        headers=headers,
        json={
            "provider_type": "store",
            "provider_key": "trendyol",
            "provider_name": "Trendyol",
            "session_token": "ext_v65_cookie_trendyol_live_session_token_998877",
            "account_identifier": "demo@kargopilot.az",
            "source": "extension_v4",
        },
    )
    assert r_ty.status_code == 200, r_ty.text
    ty_data = r_ty.json()
    assert ty_data["bridge_status"] == "connected"
    assert ty_data["source"] == "extension_v4"
    assert "*" in ty_data["masked_identifier"]
    assert "ext_v65_cookie_trendyol_live_session_token_998877" not in json.dumps(ty_data)

    # 2. Temu via extension_v4 Quick-Bridge
    r_temu = client.post(
        "/api/v1/user/sessions/quick-bridge",
        headers=headers,
        json={
            "provider_type": "store",
            "provider_key": "temu",
            "provider_name": "Temu",
            "session_token": "ext_v65_cookie_temu_live_session_token_554433",
            "account_identifier": "demo@kargopilot.az",
            "source": "extension_v4",
        },
    )
    assert r_temu.status_code == 200, r_temu.text
    assert r_temu.json()["bridge_status"] == "connected"

    # 3. Starex via extension_v4 Quick-Bridge
    r_stx = client.post(
        "/api/v1/user/sessions/quick-bridge",
        headers=headers,
        json={
            "provider_type": "carrier",
            "provider_key": "starex",
            "provider_name": "Starex",
            "session_token": "ext_v65_cookie_starex_live_session_token_112233",
            "account_identifier": "STX-EXT10",
            "source": "extension_v4",
        },
    )
    assert r_stx.status_code == 200, r_stx.text
    assert r_stx.json()["bridge_status"] == "connected"

    # 4. SmartCustoms via extension_v4 Quick-Bridge (Strict Read-Only Safe Mode!)
    with get_connection() as conn:
        before_decl = conn.execute("SELECT COUNT(*) FROM customs_declarations").fetchone()[0]

    r_sc = client.post(
        "/api/v1/user/sessions/quick-bridge",
        headers=headers,
        json={
            "provider_type": "smartcustoms",
            "provider_key": "smartcustoms",
            "provider_name": "SmartCustoms (DGK Read-Only)",
            "session_token": "ext_v65_cookie_smartcustoms_gov_az_token_776655",
            "account_identifier": "7KP2026",
            "source": "extension_v4",
        },
    )
    assert r_sc.status_code == 200, r_sc.text
    sc_data = r_sc.json()
    assert sc_data["bridge_status"] == "connected"
    assert sc_data["read_only_safe_mode"] is True
    assert sc_data["declarations_created"] == 0

    with get_connection() as conn:
        after_decl = conn.execute("SELECT COUNT(*) FROM customs_declarations").fetchone()[0]
    assert after_decl == before_decl, "SmartCustoms Quick-Bridge MUST NOT create declarations!"

    # 5. Verify 4-Channel Health Summary reflects all bridged sessions
    r_health = client.get("/api/v1/user/channels/health-summary", headers=headers)
    assert r_health.status_code == 200
    hsum = r_health.json()
    assert hsum["store_channel"]["connection_alive"] is True
    assert hsum["store_channel"]["connected_stores_count"] >= 2
    assert hsum["carrier_channel"]["connection_alive"] is True
    assert hsum["smartcustoms_channel"]["connection_alive"] is True
    assert hsum["smartcustoms_channel"]["read_only_safe_mode"] is True
    assert hsum["smartcustoms_channel"]["declarations_created"] == 0
    assert hsum["overall_health_score"] == 100


def test_etap10_dual_tree_byte_for_byte_sync():
    """Ensures 100% SHA-256 parity between web_panel/app/{routers,services,templates} and web_panel/{routers,services,templates}."""
    for sub in ["routers", "services", "templates"]:
        app_sub = WEB_PANEL_DIR / "app" / sub
        root_sub = WEB_PANEL_DIR / sub
        for src in app_sub.rglob("*"):
            if src.is_file() and src.suffix in {".py", ".html", ".js"} and "__pycache__" not in str(src):
                dst = root_sub / src.relative_to(app_sub)
                assert dst.exists(), f"Missing mirrored file: {dst}"
                h1 = hashlib.sha256(src.read_bytes()).hexdigest()
                h2 = hashlib.sha256(dst.read_bytes()).hexdigest()
                assert h1 == h2, f"SHA-256 mismatch on {src.relative_to(WEB_PANEL_DIR)}"


def test_etap10_playwright_browser_extension_and_v6_5_ui():
    """Runs a real headless Chromium browser via Playwright to verify v6.5 UI and 1-Click Quick-Bridge in extension_v4/popup.html."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return

    import socket
    import threading
    import time
    import uvicorn

    client = _setup_seeded_client()
    auth_headers = _login_demo(client)
    jwt_token = auth_headers["Authorization"].split(" ", 1)[1]

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    free_port = sock.getsockname()[1]
    sock.close()

    config = uvicorn.Config(app, host="127.0.0.1", port=free_port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{free_port}"
    for _ in range(30):
        try:
            s = socket.create_connection(("127.0.0.1", free_port), timeout=0.2)
            s.close()
            break
        except OSError:
            time.sleep(0.1)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 1. Verify root / renders KargoPilot v6.5
            page.goto(f"{base_url}/", wait_until="domcontentloaded")
            body_text = page.content()
            assert "v6.5" in body_text
            assert ">v4.5<" not in body_text

            # 2. Open extension_v4/popup.html with simulated site=customs.gov.az & real JWT
            popup_url = (
                f"{base_url}/extension_v4/popup.html"
                f"?site=https://e.customs.gov.az&server={base_url}&token={jwt_token}"
            )
            page.goto(popup_url, wait_until="domcontentloaded")

            # Verify SmartCustoms auto-detected in extension popup
            badge_text = page.locator("#detected-provider-badge").inner_text()
            assert "smartcustoms" in badge_text.lower()

            # Click 1-Click Quick-Bridge button in real Chromium DOM
            page.locator("#btn-quick-bridge").click()
            page.wait_for_function(
                "document.getElementById('ext-status-box').textContent.includes('✅')",
                timeout=8000,
            )
            status_text = page.locator("#ext-status-box").inner_text()
            assert "✅" in status_text
            assert "Read-Only (Bəyannamə: 0)" in status_text

            browser.close()
    finally:
        server.should_exit = True
        thread.join(timeout=3.0)

