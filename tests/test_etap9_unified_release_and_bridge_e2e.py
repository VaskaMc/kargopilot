"""
KargoPilot v6.5 (Etap 9) — Unified Release, First-Screen Dual-Hosting Flow,
1-Click Session Quick-Bridge, 4-Channel Health Diagnostics & Zero-Leak E2E Suite.
"""

import hashlib
from pathlib import Path
import runpy
import sys
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEB_PANEL_DIR = PROJECT_ROOT / "web_panel"
if str(WEB_PANEL_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_PANEL_DIR))

from app.main import app  # noqa: E402
from app.database import get_connection, init_db  # noqa: E402
from app.security.rate_limiter import rate_limiter  # noqa: E402


def _setup_seeded_client() -> TestClient:
    rate_limiter.reset_ip("testclient")
    rate_limiter.reset_ip("127.0.0.1")
    init_db()
    runpy.run_path(str(PROJECT_ROOT / "scripts" / "seed_demo_account.py"))
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


def test_01_repo_documentation_and_config_v6_5_compliance():
    """
    Verifies that README.md, CHANGELOG.md, Dockerfile, docker-compose.yml,
    docker-compose.sovereign.yml, .env.example, .env.sovereign.example,
    install_sovereign.sh, setup_sovereign.ps1, llms.txt, and index.html
    are synchronized to v6.5 / 6.5.0, enforce SmartCustoms Read-Only wording,
    and contain zero hardcoded production IPs or personal PII.
    """
    versioned_files = [
        "README.md",
        "CHANGELOG.md",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.sovereign.yml",
        ".env.example",
        ".env.sovereign.example",
        "install_sovereign.sh",
        "setup_sovereign.ps1",
        "llms.txt",
        "index.html",
    ]

    forbidden_tokens = [
        "5.191.246.134",
        ":1999",
        "+994776346310",
        "814CRM4",
    ]

    for rel_path in versioned_files:
        fpath = PROJECT_ROOT / rel_path
        assert fpath.exists(), f"Missing required repository file: {rel_path}"
        content = fpath.read_text(encoding="utf-8")
        assert ("v6.5" in content or "6.5.0" in content), (
            f"{rel_path} must be updated to KargoPilot v6.5 / 6.5.0"
        )
        for token in forbidden_tokens:
            assert token not in content, f"Zero-Leak violation ({token}) in {rel_path}"

    readme_text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    assert "read_only_safe_mode: True" in readme_text
    assert "/api/v1/user/sessions/quick-bridge" in readme_text
    assert "/api/v1/user/channels/health-summary" in readme_text

    changelog_text = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [6.5.0]" in changelog_text
    assert "quick-bridge" in changelog_text


def test_02_first_screen_dual_hosting_to_dashboard_e2e():
    """
    Tests the complete user journey from the first screen (/, /onboarding, /self-hosted)
    with Dual-Hosting selection cards, taste-skill/ui-ux-pro-max classes, node health check,
    and transition into /user/dashboard.
    """
    client = _setup_seeded_client()

    # 1. Inspect /onboarding and /self-hosted first-screen experience
    for route in ["/onboarding", "/self-hosted"]:
        res = client.get(route)
        assert res.status_code == 200
        html = res.text
        assert "Məlumat Müstəqilliyinizə" in html
        assert "Bizim Serverimizdə — 30 Saniyəyə Hazır Bulud Hesabı" in html
        assert "Öz Serverimdə — Açıq Qaynaq / Müstəqil Server" in html
        assert "Hansı Rejim Mənə Uyğundur?" in html
        assert "docker compose up -d --build" in html
        assert "tabular-nums" in html
        assert "kp-glass-card" in html

    # 2. Verify SSRF-protected node connection test (/api/v1/system/verify-node)
    ssrf_res = client.post(
        "/api/v1/system/verify-node",
        json={"target_url": "http://169.254.169.254/latest/meta-data"},
    )
    assert ssrf_res.status_code in (200, 400)
    if ssrf_res.status_code == 200:
        assert ssrf_res.json().get("healthy") is False

    # 3. Authenticate and verify /user/dashboard renders the 4-Channel Matrix & Quick-Bridge UI
    headers = _login_demo(client)
    dash_res = client.get("/user/dashboard", headers=headers)
    assert dash_res.status_code == 200
    dash_html = dash_res.text
    assert 'id="unified-connection-health-matrix"' in dash_html
    assert "Bütün Əlaqələri Yoxla" in dash_html
    assert "1-Kliklə Sürətli Sessiya Bağla" in dash_html
    assert "Təhlükəsiz Oxuma Rejimi: Avtomatik bəyannamə göndərilmir" in dash_html


def test_03_one_click_quick_bridge_and_4channel_health_summary():
    """
    Verifies POST /api/v1/user/sessions/quick-bridge and
    GET /api/v1/user/channels/health-summary across all 4 channels.
    """
    client = _setup_seeded_client()
    headers = _login_demo(client)

    # 1. Verify SSRF protection on quick-bridge
    bad_bridge = client.post(
        "/api/v1/user/sessions/quick-bridge",
        headers=headers,
        json={
            "provider_type": "store",
            "provider_key": "trendyol",
            "provider_name": "Trendyol",
            "login_url": "http://169.254.169.254/secret",
        },
    )
    assert bad_bridge.status_code in (400, 422)

    # 2. Connect Store, Carrier, and SmartCustoms via 1-Click Quick-Bridge
    for p_type, p_key, p_name, l_url in [
        ("store", "trendyol", "Trendyol", "https://www.trendyol.com/giris"),
        ("carrier", "starex", "Starex", "https://starex.az/login"),
        ("customs", "smartcustoms", "SmartCustoms", "https://e.customs.gov.az"),
    ]:
        qb_res = client.post(
            "/api/v1/user/sessions/quick-bridge",
            headers=headers,
            json={
                "provider_type": p_type,
                "provider_key": p_key,
                "provider_name": p_name,
                "login_url": l_url,
            },
        )
        assert qb_res.status_code == 200, f"Quick-Bridge failed for {p_name}: {qb_res.text}"
        qb_data = qb_res.json()
        assert qb_data["bridge_status"] == "connected"
        assert qb_data["session_status"] == "active"
        assert qb_data["connection_alive"] is True
        assert qb_data["auth_method"] == "quick_bridge"
        assert qb_data["read_only_safe_mode"] is True
        assert qb_data["declarations_created"] == 0
        assert qb_data["encrypted_in_vault"] is True
        assert "*" in qb_data["masked_identifier"]

        # Verify encrypted storage in SQLite external_sessions table
        with get_connection() as conn:
            row = conn.execute(
                "SELECT session_payload_encrypted FROM external_sessions WHERE id = ?",
                (qb_data["session_id"],),
            ).fetchone()
            assert row is not None
            assert str(row[0]).startswith("gAAAAA"), "Session payload must be Fernet-encrypted"

    # 3. Call GET /api/v1/user/channels/health-summary and verify 100% 4-channel readiness
    summary_res = client.get("/api/v1/user/channels/health-summary", headers=headers)
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["overall_health_score"] == 100
    assert summary["healthy_channels_count"] == 4
    assert summary["total_channels"] == 4
    assert summary["store_channel"]["connection_alive"] is True
    assert summary["carrier_channel"]["connection_alive"] is True
    assert summary["smartcustoms_channel"]["connection_alive"] is True
    assert summary["smartcustoms_channel"]["read_only_safe_mode"] is True
    assert summary["smartcustoms_channel"]["declarations_created"] == 0
    assert summary["whatsapp_channel"]["connection_alive"] is True
    assert "***" in summary["whatsapp_channel"]["masked_phone"]


def test_04_smartcustoms_readonly_strict_enforcement_and_ai_copilot():
    """
    Verifies that SmartCustoms endpoints never create declarations
    (read_only_safe_mode: True, declarations_created: 0) and that Loyd AI Copilot
    reports live 4-channel health and $300 DGK quota status.
    """
    client = _setup_seeded_client()
    headers = _login_demo(client)

    with get_connection() as conn:
        before_count = conn.execute("SELECT COUNT(*) FROM customs_declarations").fetchone()[0]

    chk_res = client.post("/api/v1/user/smartcustoms/check-connection", headers=headers)
    assert chk_res.status_code == 200
    chk_data = chk_res.json()
    assert chk_data["read_only_safe_mode"] is True
    assert chk_data["declarations_created"] == 0
    assert chk_data["connection_alive"] is True

    sync_res = client.post("/api/v1/user/smartcustoms/sync", headers=headers)
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data["read_only_safe_mode"] is True
    assert sync_data["declarations_created"] == 0

    with get_connection() as conn:
        after_count = conn.execute("SELECT COUNT(*) FROM customs_declarations").fetchone()[0]
    assert after_count == before_count, "SmartCustoms Read-Only mode must never insert declarations!"

    # Verify AI Copilot 4-channel awareness
    ai_res = client.post(
        "/api/v1/user/ai/chat",
        headers=headers,
        json={"message": "4 kanal əlaqə statusum və 300$ gömrük limitim nə yerdədir?"},
    )
    assert ai_res.status_code == 200
    reply = ai_res.json()["reply"]
    assert "SmartCustoms" in reply
    assert "WhatsApp" in reply
    assert "300" in reply or "Read-Only" in reply


def test_05_dual_router_template_sync_and_zero_leak_audit():
    """
    Verifies 100% byte-for-byte SHA-256 parity between web_panel/app/* and web_panel/*
    for routers, services, and templates, plus zero IP/PII leakage across the repo.
    """
    pairs = [
        ("web_panel/app/routers/user_api.py", "web_panel/routers/user_api.py"),
        ("web_panel/app/routers/auth_web.py", "web_panel/routers/auth_web.py"),
        ("web_panel/app/services/ai_copilot.py", "web_panel/services/ai_copilot.py"),
        ("web_panel/app/templates/self_hosted.html", "web_panel/templates/self_hosted.html"),
        ("web_panel/app/templates/user_dashboard.html", "web_panel/templates/user_dashboard.html"),
        ("web_panel/app/templates/login.html", "web_panel/templates/login.html"),
        ("web_panel/app/templates/register.html", "web_panel/templates/register.html"),
        ("web_panel/app/templates/showcase.html", "web_panel/templates/showcase.html"),
    ]

    for left_rel, right_rel in pairs:
        left_bytes = (PROJECT_ROOT / left_rel).read_bytes()
        right_bytes = (PROJECT_ROOT / right_rel).read_bytes()
        left_hash = hashlib.sha256(left_bytes).hexdigest()
        right_hash = hashlib.sha256(right_bytes).hexdigest()
        assert left_hash == right_hash, f"Dual-tree mismatch between {left_rel} and {right_rel}"

    # Verify zero hardcoded production IP or personal PII in all routers and templates
    forbidden = ["5.191.246.134", "+994776346310", "814CRM4"]
    for left_rel, _ in pairs:
        txt = (PROJECT_ROOT / left_rel).read_text(encoding="utf-8")
        for item in forbidden:
            assert item not in txt, f"Found forbidden leak {item} in {left_rel}"
