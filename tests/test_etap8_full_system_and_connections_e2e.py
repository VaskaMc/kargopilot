"""Comprehensive End-to-End Verification Suite for Etap 8 (KargoPilot v6.0):
1. Register, Login, Session & Profile Lifecycle
2. Store (Trendyol) Connect, OTP Verification & Order Sync Flow
3. Carrier (Starex) Connect, OTP Verification & Warehouse Sync Flow
4. SmartCustoms STRICT Read-Only Connection Check (Zero Declaration Side-Effects)
5. WhatsApp Notification Gateway Connect, Status & Live Ping Flow
6. AI Copilot 4-Channel Context Awareness (Store, Carrier, SmartCustoms Read-Only, WhatsApp + $300 Quota)
7. High-Craft UI (taste-skill + ui-ux-pro-max), Dual-Router/Template Sync & Zero-Leak Security Audit
"""

from __future__ import annotations

import random
import re
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT_DIR = Path(__file__).resolve().parent.parent
WEB_PANEL_DIR = ROOT_DIR / "web_panel"
if str(WEB_PANEL_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_PANEL_DIR))

from app.main import app  # noqa: E402
from app.security.rate_limiter import rate_limiter  # noqa: E402


@pytest.fixture(scope="module")
def e2e_state():
    """Shared state across the sequential 7-step E2E user journey."""
    rate_limiter.reset_ip("testclient"); rate_limiter.reset_ip("127.0.0.1")
    client = TestClient(app)
    unique_suffix = uuid.uuid4().hex[:6]
    rand_digits = random.randint(1000000, 9999999)
    return {
        "client": client,
        "email": f"etap8.v6.{unique_suffix}@kargopilot.az",
        "password": "KargoPilotV6_2026!",
        "full_name": "Etap 8 E2E Sınaq İstifadəçisi",
        "phone": f"+99455{rand_digits}",
        "fin": "7KP2026",
        "headers": {},
    }


def test_01_register_login_and_session_lifecycle(e2e_state):
    """Step 1: Register new user, login, verify /user/dashboard (200 OK) and GET /api/v1/user/profile."""
    client: TestClient = e2e_state["client"]
    rate_limiter.reset_ip("testclient"); rate_limiter.reset_ip("127.0.0.1")

    # 1. Register
    reg_res = client.post(
        "/api/v1/auth/register",
        json={
            "email": e2e_state["email"],
            "password": e2e_state["password"],
            "full_name": e2e_state["full_name"],
            "phone": e2e_state["phone"],
            "fin": e2e_state["fin"],
            "hosting_preference": "cloud",
        },
    )
    assert reg_res.status_code in (200, 201), f"Registration failed: {reg_res.text}"

    # 2. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": e2e_state["email"], "password": e2e_state["password"]},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    e2e_state["headers"] = {"Authorization": f"Bearer {token}"}

    # Ensure FIN is saved on profile
    fin_res = client.put(
        "/api/v1/user/profile",
        headers=e2e_state["headers"],
        json={
            "full_name": e2e_state["full_name"],
            "phone": e2e_state["phone"],
            "fin": e2e_state["fin"],
            "default_branch": "Bakı - Mərkəz (28 May Filialı)",
        },
    )
    assert fin_res.status_code == 200

    # 3. Verify /user/dashboard HTML loads 200 OK
    dash_res = client.get("/user/dashboard", headers=e2e_state["headers"])
    assert dash_res.status_code == 200
    assert "unified-connection-health-matrix" in dash_res.text

    # 4. Verify GET /api/v1/user/profile
    prof_res = client.get("/api/v1/user/profile", headers=e2e_state["headers"])
    assert prof_res.status_code == 200
    prof_data = prof_res.json()
    assert prof_data["email"] == e2e_state["email"]
    assert prof_data["fin"] == e2e_state["fin"]


def test_02_store_connect_and_order_sync_flow(e2e_state):
    """Step 2: Connect Trendyol store session -> OTP verify -> active -> sync orders -> verify in parcels."""
    client: TestClient = e2e_state["client"]
    headers = e2e_state["headers"]

    # 1. Initiate store session connect
    conn_res = client.post(
        "/api/v1/user/sessions/connect",
        headers=headers,
        json={
            "provider_type": "store",
            "provider_key": "trendyol",
            "provider_name": "Trendyol TR",
            "login_url": "https://www.trendyol.com/giris",
            "auth_method": "credentials_otp",
            "account_identifier": e2e_state["email"],
            "auth_secret": "TrendyolSecretPass2026!",
            "needs_otp": True,
        },
    )
    assert conn_res.status_code == 200, conn_res.text
    conn_data = conn_res.json()
    assert conn_data["session_status"] == "pending_otp"
    session_id = conn_data["id"]

    # 2. Verify OTP
    otp_res = client.post(
        f"/api/v1/user/sessions/{session_id}/verify-otp",
        headers=headers,
        json={"otp_code": "123456"},
    )
    assert otp_res.status_code == 200, otp_res.text
    assert otp_res.json()["session_status"] == "active"

    # 3. Sync store orders
    sync_res = client.post(f"/api/v1/user/sessions/{session_id}/sync", headers=headers)
    assert sync_res.status_code == 200, sync_res.text
    sync_data = sync_res.json()
    assert sync_data["synced_items_count"] >= 1

    # 4. Verify synced orders appear in GET /api/v1/user/parcels
    parcels_res = client.get("/api/v1/user/parcels", headers=headers)
    assert parcels_res.status_code == 200
    parcels = parcels_res.json()
    assert len(parcels) >= 1


def test_03_carrier_connect_and_warehouse_sync_flow(e2e_state):
    """Step 3: Connect Starex carrier session -> OTP verify -> active -> sync foreign warehouse statuses."""
    client: TestClient = e2e_state["client"]
    headers = e2e_state["headers"]

    # 1. Initiate carrier session connect
    conn_res = client.post(
        "/api/v1/user/sessions/connect",
        headers=headers,
        json={
            "provider_type": "carrier",
            "provider_key": "starex",
            "provider_name": "Starex Global",
            "login_url": "https://starex.az/login",
            "auth_method": "credentials_otp",
            "account_identifier": e2e_state["phone"],
            "auth_secret": "StarexPass2026!",
            "needs_otp": True,
        },
    )
    assert conn_res.status_code == 200, conn_res.text
    conn_data = conn_res.json()
    assert conn_data["session_status"] == "pending_otp"
    session_id = conn_data["id"]

    # 2. Verify OTP
    otp_res = client.post(
        f"/api/v1/user/sessions/{session_id}/verify-otp",
        headers=headers,
        json={"otp_code": "654321"},
    )
    assert otp_res.status_code == 200, otp_res.text
    assert otp_res.json()["session_status"] == "active"

    # 3. Sync carrier warehouse statuses
    sync_res = client.post(f"/api/v1/user/sessions/{session_id}/sync", headers=headers)
    assert sync_res.status_code == 200, sync_res.text
    sync_data = sync_res.json()
    assert sync_data["synced_items_count"] >= 1


def test_04_smartcustoms_read_only_connection_check_no_declaration(e2e_state):
    """Step 4: Connect SmartCustoms via SIMA -> check-connection & sync -> verify Read-Only Safe Mode & 0 new declarations."""
    client: TestClient = e2e_state["client"]
    headers = e2e_state["headers"]

    # Count declared parcels before SmartCustoms connection & check
    before_parcels = client.get("/api/v1/user/parcels", headers=headers).json()
    declared_before = sum(1 for p in before_parcels if p.get("declared_to_dgk"))

    # 1. Connect SmartCustoms via SIMA
    conn_res = client.post(
        "/api/v1/user/smartcustoms/connect",
        headers=headers,
        json={
            "fin": e2e_state["fin"],
            "auth_type": "sima",
            "phone": e2e_state["phone"],
            "credential_secret": "SIMA_PIN_2026",
        },
    )
    assert conn_res.status_code == 200, conn_res.text
    assert conn_res.json()["session_status"] == "active"

    # 2. Call POST /api/v1/user/smartcustoms/check-connection
    chk_res = client.post("/api/v1/user/smartcustoms/check-connection", headers=headers)
    assert chk_res.status_code == 200, chk_res.text
    chk_data = chk_res.json()
    assert chk_data["read_only_safe_mode"] is True
    assert chk_data["connection_alive"] is True
    assert chk_data["session_valid"] is True
    assert chk_data["declarations_created"] == 0
    assert chk_data["fin"] == e2e_state["fin"]
    assert chk_data["latency_ms"] > 0

    # 3. Call POST /api/v1/user/smartcustoms/sync and verify Read-Only Safe Mode
    sync_res = client.post("/api/v1/user/smartcustoms/sync", headers=headers)
    assert sync_res.status_code == 200, sync_res.text
    sync_data = sync_res.json()
    assert sync_data["read_only_safe_mode"] is True
    assert sync_data["connection_alive"] is True
    assert sync_data["session_valid"] is True

    # 4. Verify ZERO new declarations were created
    after_parcels = client.get("/api/v1/user/parcels", headers=headers).json()
    declared_after = sum(1 for p in after_parcels if p.get("declared_to_dgk"))
    assert declared_after == declared_before, "SmartCustoms check-connection/sync must NEVER create declarations!"


def test_05_whatsapp_connect_status_and_ping_flow(e2e_state):
    """Step 5: Connect WhatsApp (+994501234567) -> verify status & active session -> ping gateway."""
    client: TestClient = e2e_state["client"]
    headers = e2e_state["headers"]

    # 1. Connect WhatsApp
    wa_conn = client.post(
        "/api/v1/user/whatsapp/connect",
        headers=headers,
        json={
            "phone": "+994501234567",
            "parcel_arrival": True,
            "customs_300_warning": True,
            "session_expiry_alert": True,
        },
    )
    assert wa_conn.status_code == 200, wa_conn.text
    wa_conn_data = wa_conn.json()
    assert wa_conn_data["whatsapp_connected"] is True
    assert wa_conn_data["session_status"] == "active"
    assert wa_conn_data["phone"] == "+994501234567"

    # 2. Check GET /api/v1/user/whatsapp/status
    wa_stat = client.get("/api/v1/user/whatsapp/status", headers=headers)
    assert wa_stat.status_code == 200, wa_stat.text
    stat_data = wa_stat.json()
    assert stat_data["whatsapp_connected"] is True
    assert stat_data["session_status"] == "active"

    # Verify in external_sessions list
    sess_res = client.get("/api/v1/user/sessions", headers=headers)
    assert sess_res.status_code == 200
    sess_payload = sess_res.json()
    sessions = sess_payload if isinstance(sess_payload, list) else sess_payload.get("sessions", [])
    wa_sessions = [s for s in sessions if s["provider_type"] == "whatsapp" and s["session_status"] == "active"]
    assert len(wa_sessions) >= 1
    # Verify masking
    for s in sessions:
        assert "*" in s["account_identifier"]
        assert "session_payload_encrypted" not in s

    # 3. Ping WhatsApp Gateway
    ping_res = client.post("/api/v1/user/whatsapp/ping", headers=headers)
    assert ping_res.status_code == 200, ping_res.text
    ping_data = ping_res.json()
    assert ping_data["delivered_simulation"] is True
    assert ping_data["gateway_reachable"] is True
    assert ping_data["connection_alive"] is True
    assert ping_data["latency_ms"] > 0


def test_06_ai_copilot_multi_channel_context_awareness(e2e_state):
    """Step 6: Verify AI Copilot reports all 4 active channels + $300 DGK quota status."""
    client: TestClient = e2e_state["client"]
    headers = e2e_state["headers"]

    chat_res = client.post(
        "/api/v1/user/ai/chat",
        headers=headers,
        json={"message": "Bütün əlaqələrimin və 300$ limitimin vəziyyəti necədir?"},
    )
    assert chat_res.status_code == 200, chat_res.text
    data = chat_res.json()
    reply = data["reply"]

    # Check that all 4 channels and $300 quota are mentioned in the AI reply
    assert "Mağaza" in reply or "Trendyol" in reply
    assert "Kargo" in reply or "Starex" in reply
    assert "SmartCustoms" in reply and "Read-Only" in reply
    assert "WhatsApp" in reply
    assert "300" in reply or "USD" in reply

    # Also verify context_used contains channels_health
    ctx = data["context_used"]
    assert "channels_health" in ctx
    ch = ctx["channels_health"]
    assert ch["store_connected"] is True
    assert ch["carrier_connected"] is True
    assert ch["smartcustoms_connected"] is True
    assert ch["smartcustoms_read_only_safe_mode"] is True
    assert ch["whatsapp_connected"] is True


def test_07_ui_taste_and_pro_max_template_integrity():
    """Step 7: Verify UI taste-skill & ui-ux-pro-max rules, Dual-Router/Template sync, Demo 4-channel seeding, and Zero-Leak."""
    app_dash = (WEB_PANEL_DIR / "app" / "templates" / "user_dashboard.html").read_text(encoding="utf-8")
    root_dash = (WEB_PANEL_DIR / "templates" / "user_dashboard.html").read_text(encoding="utf-8")
    app_login = (WEB_PANEL_DIR / "app" / "templates" / "login.html").read_text(encoding="utf-8")
    root_login = (WEB_PANEL_DIR / "templates" / "login.html").read_text(encoding="utf-8")
    app_reg = (WEB_PANEL_DIR / "app" / "templates" / "register.html").read_text(encoding="utf-8")
    root_reg = (WEB_PANEL_DIR / "templates" / "register.html").read_text(encoding="utf-8")

    # 1. Dual-template byte-for-byte sync
    assert app_dash == root_dash, "user_dashboard.html out of sync between app/templates and templates!"
    assert app_login == root_login, "login.html out of sync!"
    assert app_reg == root_reg, "register.html out of sync!"

    # 2. Dual-router and dual-service sync
    app_router = (WEB_PANEL_DIR / "app" / "routers" / "user_api.py").read_text(encoding="utf-8")
    root_router = (WEB_PANEL_DIR / "routers" / "user_api.py").read_text(encoding="utf-8")
    assert app_router == root_router, "user_api.py out of sync between app/routers and routers!"

    app_ai = (WEB_PANEL_DIR / "app" / "services" / "ai_copilot.py").read_text(encoding="utf-8")
    root_ai = (WEB_PANEL_DIR / "services" / "ai_copilot.py").read_text(encoding="utf-8")
    assert app_ai == root_ai, "ai_copilot.py out of sync between app/services and services!"

    # 3. Verify taste-skill & ui-ux-pro-max rules in user_dashboard.html
    assert "tabular-nums" in app_dash
    assert "unified-connection-health-matrix" in app_dash
    assert "Mağaza Əlaqəsi" in app_dash
    assert "Kargo Əlaqəsi" in app_dash
    assert "SmartCustoms (DGK Read-Only)" in app_dash
    assert "WhatsApp Bildiriş Şlüzü" in app_dash
    assert "Təhlükəsiz Oxuma Rejimi: Avtomatik bəyannamə göndərilmir, yalnız əlaqə və 300$ limit statusu yoxlanılır" in app_dash
    assert "SmartCustoms Əlaqə Aktuallığını Yoxla (Read-Only)" in app_dash
    assert "cubic-bezier(0.16, 1, 0.3, 1)" in app_dash

    # 4. Zero-Leak Audit on all Etap 8 modified files
    etap8_files = [
        WEB_PANEL_DIR / "app" / "routers" / "user_api.py",
        WEB_PANEL_DIR / "app" / "services" / "ai_copilot.py",
        WEB_PANEL_DIR / "app" / "templates" / "user_dashboard.html",
        WEB_PANEL_DIR / "app" / "templates" / "login.html",
        WEB_PANEL_DIR / "app" / "templates" / "register.html",
        ROOT_DIR / "scripts" / "seed_demo_account.py",
        Path(__file__),
    ]
    forbidden_patterns = [
        re.compile(r"5\.191\.246\.134"),
        re.compile(r"\+994\s*77\s*634\s*63\s*10"),
        re.compile(r"\b814CRM4\b"),
    ]
    for fpath in etap8_files:
        text = fpath.read_text(encoding="utf-8")
        for pat in forbidden_patterns:
            assert not pat.search(text), f"Zero-Leak violation ({pat.pattern}) found in {fpath}"

    # 5. Verify seeded demo@kargopilot.az has all 4 channels active
    rate_limiter.reset_ip("testclient"); rate_limiter.reset_ip("127.0.0.1")
    client = TestClient(app)
    demo_login = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@kargopilot.az", "password": "***REMOVED***"},
    )
    assert demo_login.status_code == 200, f"Demo account login with ***REMOVED*** failed: {demo_login.text}"
    demo_headers = {"Authorization": f"Bearer {demo_login.json()['access_token']}"}
    demo_sess_raw = client.get("/api/v1/user/sessions", headers=demo_headers).json()
    demo_sessions = demo_sess_raw if isinstance(demo_sess_raw, list) else demo_sess_raw.get("sessions", [])
    active_types = {s["provider_type"] for s in demo_sessions if s["session_status"] == "active"}
    assert {"store", "carrier", "smartcustoms", "whatsapp"}.issubset(active_types), (
        f"Demo account missing active channels: {active_types}"
    )
