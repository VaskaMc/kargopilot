"""Deterministic QA and Security Verification Test Suite for Etap 3:
Sovereign / Self-Hosted Dual-Hosting Architecture, Data Sovereignty Export/Import,
Strict Tenant-Isolated Account Wipe (Right to be Forgotten), and SSRF-Protected Node Verification.
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


def register_test_user(client: TestClient, name: str = "Sovereign Test User") -> dict:
    """Helper to register an isolated test user and return credentials + token."""
    email = f"sovereign_{uuid.uuid4().hex[:8]}@kargopilot.az"
    phone = f"+99477{uuid.uuid4().hex[:7]}"
    payload = {
        "email": email,
        "password": "StrongPassword2026!",
        "full_name": name,
        "phone": phone,
        "hosting_preference": "sovereign",
        "device_fingerprint": f"Pytest-Sovereign-{uuid.uuid4().hex[:4]}",
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


def test_data_export_structure_and_tenant_isolation(client: TestClient):
    """Verifies GET /api/v1/user/export:
    1. Returns standard schema 4.5.0 format.
    2. Packages user profile, parcels, and quota summary.
    3. Strictly isolates User A's export from User B's parcels.
    """
    user_a = register_test_user(client, name="Əli Həsənov")
    user_b = register_test_user(client, name="Nigar Kərimova")

    # User A creates 2 parcels
    p_a1 = {
        "tracking_number": f"TRK-A1-{uuid.uuid4().hex[:6]}",
        "platform": "Trendyol",
        "carrier": "STAREX",
        "title": "Ayaqqabı və idman malları",
        "invoice_amount_usd": 75.0,
    }
    p_a2 = {
        "tracking_number": f"TRK-A2-{uuid.uuid4().hex[:6]}",
        "platform": "Hepsiburada",
        "carrier": "LIMAK",
        "title": "Mexaniki saat",
        "invoice_amount_usd": 110.0,
    }
    client.post("/api/v1/user/parcels", json=p_a1, headers=user_a["headers"])
    client.post("/api/v1/user/parcels", json=p_a2, headers=user_a["headers"])

    # User B creates 1 confidential parcel
    p_b1 = {
        "tracking_number": f"TRK-B-CONFIDENTIAL-{uuid.uuid4().hex[:6]}",
        "platform": "Amazon",
        "carrier": "CAMEX",
        "title": "Məxfi sənədlər",
        "invoice_amount_usd": 40.0,
    }
    client.post("/api/v1/user/parcels", json=p_b1, headers=user_b["headers"])

    # User A requests Data Export
    res = client.get("/api/v1/user/export", headers=user_a["headers"])
    assert res.status_code == 200, f"Export failed: {res.text}"
    bundle = res.json()

    # Verify root bundle structure
    assert bundle["schema_version"] == "4.5.0"
    assert bundle["service"] == "kargopilot-core"
    assert "exported_at" in bundle

    # Verify profile structure
    profile = bundle["user_profile"]
    assert profile["email"] == user_a["email"]
    assert profile["full_name"] == "Əli Həsənov"

    # Verify parcel items and totals
    parcels = bundle["parcels"]
    assert len(parcels) == 2
    tracking_numbers = [p["tracking_number"] for p in parcels]
    assert p_a1["tracking_number"].upper() in tracking_numbers
    assert p_a2["tracking_number"].upper() in tracking_numbers

    # STRICT TENANT ISOLATION ASSERTION: User B's parcel MUST NOT exist in User A's export!
    assert p_b1["tracking_number"].upper() not in tracking_numbers

    # Verify quota summary inside bundle
    quota = bundle["quota_summary"]
    assert quota["total_spent_usd"] == 185.0
    assert quota["remaining_usd"] == 115.0
    assert quota["status"] == "safe"


def test_data_import_and_quota_recalculation(client: TestClient):
    """Verifies POST /api/v1/user/import:
    1. Successfully imports an exported parcel bundle into another user's account.
    2. Overrides owner tenant ID to the importing user.
    3. Handles duplicate tracking numbers gracefully (skips them without error).
    4. Automatically recalculates DGK 300$ quota upon import.
    """
    source_user = register_test_user(client, name="Source User")
    target_user = register_test_user(client, name="Target User")

    # Source user creates parcels
    p1_tracking = f"IMP-TRK-{uuid.uuid4().hex[:6]}"
    p2_tracking = f"IMP-TRK-{uuid.uuid4().hex[:6]}"
    client.post(
        "/api/v1/user/parcels",
        json={
            "tracking_number": p1_tracking,
            "platform": "Trendyol",
            "carrier": "STAREX",
            "title": "İdxal üçün bağlama 1",
            "invoice_amount_usd": 120.0,
        },
        headers=source_user["headers"],
    )
    client.post(
        "/api/v1/user/parcels",
        json={
            "tracking_number": p2_tracking,
            "platform": "Amazon",
            "carrier": "CAMEX",
            "title": "İdxal üçün bağlama 2",
            "invoice_amount_usd": 150.0,
        },
        headers=source_user["headers"],
    )

    # Export source user's bundle
    export_bundle = client.get("/api/v1/user/export", headers=source_user["headers"]).json()

    # Initial target user quota should be $0 spent
    init_quota = client.get("/api/v1/user/quota", headers=target_user["headers"]).json()
    assert init_quota["total_spent_usd"] == 0.0

    # 1. First Import into Target User
    import_payload = {
        "schema_version": export_bundle["schema_version"],
        "parcels": export_bundle["parcels"],
    }
    imp_res = client.post("/api/v1/user/import", json=import_payload, headers=target_user["headers"])
    assert imp_res.status_code == 200, f"Import failed: {imp_res.text}"
    imp_data = imp_res.json()
    assert imp_data["status"] == "success"
    assert imp_data["imported_count"] == 2
    assert imp_data["skipped_count"] == 0

    # Dynamic quota check on target user: $120 + $150 = $270 -> status warning (> $250)
    updated_quota = imp_data["updated_quota"]
    assert updated_quota["total_spent_usd"] == 270.0
    assert updated_quota["remaining_usd"] == 30.0
    assert updated_quota["status"] == "warning"

    # Verify target user's parcels in database
    target_parcels = client.get("/api/v1/user/parcels", headers=target_user["headers"]).json()
    assert len(target_parcels) == 2
    assert any(p["tracking_number"] == p1_tracking.upper() for p in target_parcels)
    assert any(p["tracking_number"] == p2_tracking.upper() for p in target_parcels)

    # 2. Second Import (Idempotency test): Re-importing exact same bundle should skip duplicates
    reimport_res = client.post("/api/v1/user/import", json=import_payload, headers=target_user["headers"])
    assert reimport_res.status_code == 200
    reimport_data = reimport_res.json()
    assert reimport_data["imported_count"] == 0
    assert reimport_data["skipped_count"] == 2
    assert reimport_data["total_parcels"] == 2


def test_account_data_wipe_isolation(client: TestClient):
    """Verifies DELETE /api/v1/user/account-data:
    1. Fails with 400 Bad Request if confirm_wipe=True is omitted.
    2. When confirm_wipe=True, strictly purges caller's personal parcels and resets quota.
    3. User profile and login capabilities remain active (Right to be Forgotten).
    4. STRICT TENANT ISOLATION: Other users' parcels are completely untouched.
    """
    user_to_wipe = register_test_user(client, name="Wipe Subject")
    innocent_user = register_test_user(client, name="Innocent Bystander")

    # Both create parcels
    w_tracking = f"WIPE-{uuid.uuid4().hex[:6]}"
    i_tracking = f"KEEP-{uuid.uuid4().hex[:6]}"

    client.post(
        "/api/v1/user/parcels",
        json={"tracking_number": w_tracking, "platform": "Trendyol", "carrier": "STAREX", "title": "Silinəcək", "invoice_amount_usd": 80.0},
        headers=user_to_wipe["headers"],
    )
    client.post(
        "/api/v1/user/parcels",
        json={"tracking_number": i_tracking, "platform": "Amazon", "carrier": "CAMEX", "title": "Qorunacaq", "invoice_amount_usd": 95.0},
        headers=innocent_user["headers"],
    )

    # 1. Attempt wipe without confirmation flag -> Expect 400
    fail_res = client.delete("/api/v1/user/account-data", headers=user_to_wipe["headers"])
    assert fail_res.status_code == 400
    assert "confirm_wipe=true" in fail_res.json()["detail"]

    # 2. Perform authorized wipe with confirm_wipe=true
    wipe_res = client.delete("/api/v1/user/account-data?confirm_wipe=true", headers=user_to_wipe["headers"])
    assert wipe_res.status_code == 200
    wipe_data = wipe_res.json()
    assert wipe_data["status"] == "success"
    assert wipe_data["wiped_orders_count"] >= 1
    assert wipe_data["remaining_quota_usd"] == 300.0

    # 3. Verify wiped user's parcels are empty and quota is reset
    wiped_parcels = client.get("/api/v1/user/parcels", headers=user_to_wipe["headers"]).json()
    assert len(wiped_parcels) == 0

    wiped_quota = client.get("/api/v1/user/quota", headers=user_to_wipe["headers"]).json()
    assert wiped_quota["total_spent_usd"] == 0.0
    assert wiped_quota["remaining_usd"] == 300.0

    # 4. Verify user profile is still valid and reachable
    profile = client.get("/api/v1/user/profile", headers=user_to_wipe["headers"]).json()
    assert profile["full_name"] == "Wipe Subject"

    # 5. STRICT ISOLATION: Innocent user's parcels are 100% intact!
    innocent_parcels = client.get("/api/v1/user/parcels", headers=innocent_user["headers"]).json()
    assert len(innocent_parcels) == 1
    assert innocent_parcels[0]["tracking_number"] == i_tracking.upper()

    innocent_quota = client.get("/api/v1/user/quota", headers=innocent_user["headers"]).json()
    assert innocent_quota["total_spent_usd"] == 95.0


def test_sovereign_onboarding_and_health_endpoints(client: TestClient):
    """Verifies:
    1. /self-hosted and /onboarding web routes return HTTP 200 with complete sovereign UI.
    2. /health endpoint reports service="kargopilot-core" and dual_hosting_ready=True.
    3. /api/v1/system/verify-node blocks SSRF attack vectors and handles connectivity checks.
    """
    # 1. Web Onboarding Routes
    sh_res = client.get("/self-hosted")
    assert sh_res.status_code == 200
    assert "Məlumat Müstəqilliyinizə" in sh_res.text
    assert "Öz Serverində İşlət" in sh_res.text
    assert "Sovereign" in sh_res.text
    assert "Quraşdırma" in sh_res.text

    ob_res = client.get("/onboarding")
    assert ob_res.status_code == 200
    assert "Məlumat Müstəqilliyinizə" in ob_res.text

    # 2. System Health Check
    health_res = client.get("/health")
    assert health_res.status_code == 200
    health_data = health_res.json()
    assert health_data["service"] == "kargopilot-core"
    assert health_data["dual_hosting_ready"] is True

    # 3. SSRF Protection on Node Verification
    # Attempt SSRF to AWS/GCP cloud metadata IP -> gracefully blocked
    ssrf_payload = {"target_url": "http://169.254.169.254/latest/meta-data/"}
    ssrf_res = client.post("/api/v1/system/verify-node", json=ssrf_payload)
    assert ssrf_res.status_code == 200
    res_data = ssrf_res.json()
    assert res_data["healthy"] is False
    assert any(w in res_data["message"].lower() for w in ["qadağandır", "bloklandı", "metadata"])

    # Attempt non-http protocol
    ftp_payload = {"target_url": "ftp://attacker.com/exploit"}
    ftp_res = client.post("/api/v1/system/verify-node", json=ftp_payload)
    assert ftp_res.status_code == 200
    assert ftp_res.json()["healthy"] is False

    # Verify unreachable external port returns graceful non-crashing response
    unreachable_payload = {"target_url": "http://192.0.2.1:5544"}
    unreachable_res = client.post("/api/v1/system/verify-node", json=unreachable_payload)
    assert unreachable_res.status_code == 200
    res_data = unreachable_res.json()
    assert res_data["healthy"] is False
