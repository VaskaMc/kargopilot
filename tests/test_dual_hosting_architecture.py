"""Tests for KargoPilot v4.5 Enterprise Universal Dual-Hosting Architecture.

Validates:
1. Health and discovery endpoints (/health, /api/health, /healthz).
2. Cross-Origin Resource Sharing (CORS) headers for custom server connection tests.
3. User Data Export endpoint (/api/export/data) and compliance schema.
4. Client integration of Dual-Hosting badges and modals in HTML templates.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

WEB_PANEL_DIR = Path(__file__).resolve().parent.parent / "web_panel"
if str(WEB_PANEL_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_PANEL_DIR))

from app.main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def test_health_and_discovery_endpoints(client: TestClient):
    """Verifies that all standard health endpoints return version and dual-hosting readiness."""
    for path in ["/health", "/api/health", "/healthz"]:
        response = client.get(path)
        assert response.status_code == 200, f"Failed on path {path}"
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "6.5.0"
        assert data["service"] == "kargopilot-core"
        assert data["dual_hosting_ready"] is True
        assert "capabilities" in data
        assert "multi_tenant" in data["capabilities"]
        assert "data_sovereignty" in data["capabilities"]
        assert "export_ready" in data["capabilities"]


def test_cors_headers_support(client: TestClient):
    """Verifies CORS headers so remote and local clients can test custom server URLs without browser blocks."""
    headers = {
        "Origin": "https://my-custom-client.company.az",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/health", headers=headers)
    assert response.status_code in [200, 204]
    assert response.headers.get("access-control-allow-origin") in ["*", "https://my-custom-client.company.az"]

    get_res = client.get("/health", headers={"Origin": "https://my-custom-client.company.az"})
    assert get_res.status_code == 200
    assert get_res.headers.get("access-control-allow-origin") in ["*", "https://my-custom-client.company.az"]


def test_user_data_export_endpoint(client: TestClient):
    """Verifies the /api/export/data endpoint for human-readable GDPR/AR Law compliant data portability."""
    response = client.get("/api/export/data")
    assert response.status_code == 200
    data = response.json()

    assert data["project"] == "KargoPilot v6.5 Enterprise"
    assert data["export_version"] == "1.0"
    assert "exported_at" in data
    assert "edition" in data
    assert "data" in data
    assert "orders" in data["data"]
    assert "customs_declarations" in data["data"]
    assert "fin_profiles" in data["data"]
    assert "compliance" in data
    assert "Fərdi məlumatlar haqqında" in data["compliance"]["law"]

    disp = response.headers.get("content-disposition", "")
    assert "attachment" in disp
    assert "kargopilot_export_" in disp


def test_dual_hosting_rendered_in_web_and_admin(client: TestClient):
    """Verifies that the dual hosting badge and modal are embedded in base and admin templates."""
    # Test Root / Dashboard
    res_root = client.get("/")
    assert res_root.status_code == 200
    assert "data-kp-connection-badge" in res_root.text
    assert "kp-dual-hosting-modal" in res_root.text
    assert "kargopilot-connection.js" in res_root.text

    # Test Admin Cockpit
    res_admin = client.get("/admin")
    assert res_admin.status_code == 200
    assert "data-kp-connection-badge" in res_admin.text
    assert "kp-dual-hosting-modal" in res_admin.text

    # Test Showcase / Landing Page
    res_showcase = client.get("/showcase")
    assert res_showcase.status_code == 200
    assert "dual-hosting" in res_showcase.text
    assert "kp-dual-hosting-modal" in res_showcase.text
    assert "logo_concept_6_infinity_loop.jpg" in res_showcase.text
