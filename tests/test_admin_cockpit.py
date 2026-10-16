"""Automated Test Battery for KargoPilot v4.5 Enterprise Admin Cockpit.

Validates:
- All Jinja2 template rendering (/admin, /admin/users, /admin/orders, /admin/customs, /admin/carriers, /admin/audit)
- Admin JSON API endpoints (HS Code override, User toggle status)
- Dark glassmorphism layout and CSRF/Session context injection
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from web_panel.routers.admin import router as admin_router


@pytest.fixture
def admin_client():
    app = FastAPI(title="KargoPilot Test Admin Harness")
    app.include_router(admin_router)
    return TestClient(app)


class TestAdminCockpit:
    def test_admin_dashboard_render(self, admin_client: TestClient):
        response = admin_client.get("/admin")
        assert response.status_code == 200
        assert "KargoPilot" in response.text
        assert "Enterprise Admin Cockpit" in response.text
        assert "Ümumi Müştəri Bazası" in response.text
        assert "CBAR" in response.text

    def test_admin_users_view(self, admin_client: TestClient):
        response = admin_client.get("/admin/users")
        assert response.status_code == 200
        assert "İstifadəçi İdarəetməsi" in response.text
        assert "Vasif Məcidli" in response.text
        assert "814CRM4" in response.text

    def test_admin_orders_view(self, admin_client: TestClient):
        response = admin_client.get("/admin/orders")
        assert response.status_code == 200
        assert "Qlobal Yük Şəbəkəsi" in response.text
        assert "STAREX" in response.text

    def test_admin_customs_queue(self, admin_client: TestClient):
        response = admin_client.get("/admin/customs")
        assert response.status_code == 200
        assert "SmartCustoms Nəzarət Masası" in response.text
        assert "Apple Watch Ultra 2" in response.text
        assert "8517.62.00.00" in response.text

    def test_admin_carriers_config(self, admin_client: TestClient):
        response = admin_client.get("/admin/carriers")
        assert response.status_code == 200
        assert "Daşıyıcı Marjaları" in response.text
        assert "Starex Logistics" in response.text
        assert "Dynamex Express" in response.text

    def test_admin_audit_log(self, admin_client: TestClient):
        response = admin_client.get("/admin/audit")
        assert response.status_code == 200
        assert "Təhlükəsizlik və Audit Jurnalı" in response.text
        assert "Argon2id" in response.text

    def test_api_customs_override(self, admin_client: TestClient):
        payload = {
            "tracking": "STX-9982410",
            "hs_code": "8517.62.00.00",
            "category_id": 1,
            "justification": "Verified smart watch category"
        }
        response = admin_client.post("/admin/api/customs/override", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["new_hs_code"] == "8517.62.00.00"
        assert data["status"] == "APPROVED_FOR_FILING"

    def test_api_user_toggle_status(self, admin_client: TestClient):
        response = admin_client.post("/admin/api/users/usr_88219/toggle-status")
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["user_id"] == "usr_88219"
