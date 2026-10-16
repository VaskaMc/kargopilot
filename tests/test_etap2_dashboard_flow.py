"""Deterministic QA and Security Verification Test Suite for Etap 2:
Cloud/Managed User Dashboard, Profile Management, Personal Logistics & DGK 300$ Quota Engine,
and Strict IDOR Multi-Tenant Boundary Enforcement.
"""

import sys
import uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure web_panel takes precedence on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "web_panel"))

from web_panel.app.main import create_app
from web_panel.app.database import init_db


@pytest.fixture(scope="module")
def client():
    init_db()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def register_test_user(client: TestClient, name: str = "Test İstifadəçi") -> dict:
    """Helper to register an isolated test user and return credentials + token."""
    email = f"user_{uuid.uuid4().hex[:8]}@kargopilot.az"
    phone = f"+99477{uuid.uuid4().hex[:7]}"
    payload = {
        "email": email,
        "password": "StrongPassword2026!",
        "full_name": name,
        "phone": phone,
        "hosting_preference": "cloud",
        "device_fingerprint": f"Pytest-Agent-{uuid.uuid4().hex[:4]}",
    }
    res = client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201, f"User registration failed: {res.text}"
    data = res.json()
    token = data["access_token"]
    return {
        "email": email,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "full_name": name,
        "user_id": data.get("user_id"),
    }


def test_user_profile_get_and_update(client: TestClient):
    """Verifies that authenticated user can read and update profile details (FIN, branch, phone, notifications)."""
    user = register_test_user(client, name="Rəşad Quliyev")

    # 1. GET Profile
    res = client.get("/api/v1/user/profile", headers=user["headers"])
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    profile = res.json()
    assert profile["email"] == user["email"]
    assert profile["full_name"] == "Rəşad Quliyev"
    assert profile["tier"] == "cloud_managed"
    assert "fin" in profile
    assert "default_branch" in profile

    # 2. PUT Profile Update
    update_payload = {
        "full_name": "Rəşad M. Quliyev",
        "fin": "77ABC99",
        "default_branch": "Gənclik Filialı",
        "phone": "+994501234567",
        "notification_whatsapp": False,
        "notification_email": True,
    }
    put_res = client.put("/api/v1/user/profile", json=update_payload, headers=user["headers"])
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["full_name"] == "Rəşad M. Quliyev"
    assert updated["fin"] == "77ABC99"
    assert updated["default_branch"] == "Gənclik Filialı"
    assert updated["notification_whatsapp"] is False
    assert updated["notification_email"] is True

    # 3. GET Profile re-fetch confirms persistence
    refetch = client.get("/api/v1/user/profile", headers=user["headers"]).json()
    assert refetch["full_name"] == "Rəşad M. Quliyev"
    assert refetch["fin"] == "77ABC99"


def test_parcel_lifecycle_and_dynamic_quota(client: TestClient):
    """Verifies creating parcels, calculating dynamic DGK 300$ quota, and deleting parcels."""
    user = register_test_user(client, name="Aygün Məmmədova")

    # Initial Quota: 0 spent, 300 remaining, safe status
    init_quota = client.get("/api/v1/user/quota", headers=user["headers"]).json()
    assert init_quota["total_spent_usd"] == 0.0
    assert init_quota["remaining_usd"] == 300.0
    assert init_quota["status"] == "safe"

    # Add Parcel 1 ($65.00)
    p1_data = {
        "tracking_number": "TRK-990142",
        "platform": "Trendyol",
        "carrier": "STAREX",
        "title": "İdman kostyumu",
        "invoice_amount_usd": 65.0,
    }
    p1_res = client.post("/api/v1/user/parcels", json=p1_data, headers=user["headers"])
    assert p1_res.status_code == 201
    p1 = p1_res.json()
    assert p1["tracking_number"] == "TRK-990142"
    assert p1["invoice_amount_usd"] == 65.0
    assert p1["invoice_amount_azn"] == round(65.0 * 1.70, 2)
    parcel1_id = p1["id"]

    # Quota after Parcel 1
    q1 = client.get("/api/v1/user/quota", headers=user["headers"]).json()
    assert q1["total_spent_usd"] == 65.0
    assert q1["remaining_usd"] == 235.0
    assert q1["status"] == "safe"

    # Add Parcel 2 ($200.00) -> Total $265.00 -> Status warning (> $250)
    p2_data = {
        "tracking_number": "DW-551122",
        "platform": "Temu",
        "carrier": "CAMEX",
        "title": "Ağıllı saat və aksesuarlar",
        "invoice_amount_usd": 200.0,
    }
    p2_res = client.post("/api/v1/user/parcels", json=p2_data, headers=user["headers"])
    assert p2_res.status_code == 201

    q2 = client.get("/api/v1/user/quota", headers=user["headers"]).json()
    assert q2["total_spent_usd"] == 265.0
    assert q2["remaining_usd"] == 35.0
    assert q2["status"] == "warning"

    # List Parcels
    list_res = client.get("/api/v1/user/parcels", headers=user["headers"])
    assert list_res.status_code == 200
    parcels = list_res.json()
    assert len(parcels) == 2
    tracking_nums = [p["tracking_number"] for p in parcels]
    assert "TRK-990142" in tracking_nums
    assert "DW-551122" in tracking_nums

    # Delete Parcel 1
    del_res = client.delete(f"/api/v1/user/parcels/{parcel1_id}", headers=user["headers"])
    assert del_res.status_code == 200

    # Quota after deletion: $265 - $65 = $200 -> Status safe (< $250)
    q3 = client.get("/api/v1/user/quota", headers=user["headers"]).json()
    assert q3["total_spent_usd"] == 200.0
    assert q3["remaining_usd"] == 100.0
    assert q3["status"] == "safe"


def test_strict_idor_multi_tenant_protection(client: TestClient):
    """SECURITY AUDIT: Proves that User B cannot access, read, or delete User A's parcels.
    Enforces HTTP 404 (zero identifier enumeration leaks).
    """
    user_a = register_test_user(client, name="User A (Owner)")
    user_b = register_test_user(client, name="User B (Attacker/Intruder)")

    # User A creates a confidential parcel
    parcel_payload = {
        "tracking_number": "SECRET-A-888999",
        "platform": "Amazon",
        "carrier": "LIMAK",
        "title": "Məxfi Elektronika",
        "invoice_amount_usd": 120.0,
    }
    create_res = client.post("/api/v1/user/parcels", json=parcel_payload, headers=user_a["headers"])
    assert create_res.status_code == 201
    parcel_a_id = create_res.json()["id"]

    # 1. User B lists parcels -> MUST NOT contain User A's parcel
    user_b_parcels = client.get("/api/v1/user/parcels", headers=user_b["headers"]).json()
    assert not any(p["id"] == parcel_a_id for p in user_b_parcels), "IDOR Leak: User B saw User A's parcel in list!"

    # 2. User B attempts direct GET /parcels/{parcel_a_id} -> MUST return HTTP 404
    idor_get_res = client.get(f"/api/v1/user/parcels/{parcel_a_id}", headers=user_b["headers"])
    assert idor_get_res.status_code == 404, f"IDOR Vulnerability: Expected 404, got {idor_get_res.status_code}"

    # 3. User B attempts DELETE /parcels/{parcel_a_id} -> MUST return HTTP 404
    idor_del_res = client.delete(f"/api/v1/user/parcels/{parcel_a_id}", headers=user_b["headers"])
    assert idor_del_res.status_code == 404, f"IDOR Vulnerability: Expected 404, got {idor_del_res.status_code}"

    # 4. Verify User A's parcel is intact and untouched
    verify_res = client.get(f"/api/v1/user/parcels/{parcel_a_id}", headers=user_a["headers"])
    assert verify_res.status_code == 200
    assert verify_res.json()["tracking_number"] == "SECRET-A-888999"


def test_user_dashboard_page_routes(client: TestClient):
    """Verifies that /user/dashboard and /my-dashboard routes render successfully."""
    # Unauthenticated / guest fallback rendering
    res1 = client.get("/user/dashboard")
    assert res1.status_code == 200
    assert "KargoPilot" in res1.text
    assert "Şəxsi İdarəetmə Paneli" in res1.text
    assert "DGK 300$" in res1.text

    res2 = client.get("/my-dashboard")
    assert res2.status_code == 200
    assert "KargoPilot" in res2.text
