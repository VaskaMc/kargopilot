"""Deterministic QA and Security Verification Test Suite for Etap 7 (KargoPilot v5.5):
1. Store Login Session Handshake & OTP Verification (Two-factor handshake, credentials vaulting)
2. Carrier Session Connect & Parcel Auto-Sync (Idempotent order ingestion, deduplication)
3. SmartCustoms Session Sync & 1-Click Declaration (DGK 305 compliance, declaration tracking)
4. Session Vault Strict IDOR, SSRF & No Secret Leak (Encrypted payload, token masking, cloud metadata rejection)
5. Live Demo Account Pre-Seeding Verification (demo@kargopilot.az active sessions and parcels)
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure web_panel takes precedence on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "web_panel"))

from web_panel.app.database import init_db
from web_panel.app.main import create_app


@pytest.fixture(scope="module")
def client():
    init_db()
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def register_test_user(client: TestClient, name: str = "Etap7 Test İstifadəçi") -> dict:
    """Helper to register an isolated test user and return credentials + token."""
    email = f"etap7_{uuid.uuid4().hex[:8]}@kargopilot.az"
    phone = f"+99477{uuid.uuid4().hex[:7]}"
    password = "StrongPassword2026!"
    payload = {
        "email": email,
        "password": password,
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
        "password": password,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
        "full_name": name,
        "user_id": data.get("user_id"),
    }


# ==============================================================================
# 1. Store Login Session Handshake & OTP Verification
# ==============================================================================

def test_store_login_session_handshake_and_otp_verification(client: TestClient):
    """Verifies connecting external store session, initial pending_otp status, and OTP verification to active."""
    user = register_test_user(client, "Nigar Məmmədova")

    # 1. Connect Store Session with credentials_otp
    connect_payload = {
        "provider_type": "store",
        "provider_key": "trendyol",
        "provider_name": "Trendyol TR",
        "login_url": "https://www.trendyol.com/giris",
        "account_identifier": "nigar.test@trendyol.com",
        "auth_method": "credentials_otp",
        "auth_secret": "SuperSecretPassword123!",
        "needs_otp": True,
    }
    res = client.post("/api/v1/user/sessions/connect", json=connect_payload, headers=user["headers"])
    assert res.status_code == 200, f"Connect session failed: {res.text}"
    sess = res.json()
    assert sess["provider_key"] == "trendyol"
    assert sess["session_status"] == "pending_otp"
    assert sess["account_identifier"] == "ni***t@trendyol.com"  # Masked!
    assert "auth_secret" not in sess
    assert "session_payload_encrypted" not in sess
    session_id = sess["id"]

    # 2. List sessions -> verify masked identifier and no secret leakage
    res = client.get("/api/v1/user/sessions", headers=user["headers"])
    assert res.status_code == 200
    sessions = res.json()
    assert len(sessions) == 1
    assert sessions[0]["id"] == session_id
    assert sessions[0]["session_status"] == "pending_otp"
    assert sessions[0]["account_identifier"] == "ni***t@trendyol.com"

    # 3. Verify OTP with invalid length
    res = client.post(f"/api/v1/user/sessions/{session_id}/verify-otp", json={"otp_code": "12"}, headers=user["headers"])
    assert res.status_code == 422

    # 4. Verify OTP with valid 6-digit code
    res = client.post(f"/api/v1/user/sessions/{session_id}/verify-otp", json={"otp_code": "123456"}, headers=user["headers"])
    assert res.status_code == 200
    verified = res.json()
    assert verified["session_status"] == "active"

    # 5. Verify stores hub reflects session_status == 'active'
    res = client.get("/api/v1/user/stores", headers=user["headers"])
    assert res.status_code == 200
    stores = res.json()
    ty_store = next((s for s in stores if s["name"].lower() == "trendyol"), None)
    assert ty_store is not None
    assert ty_store["session_status"] == "active"


# ==============================================================================
# 2. Carrier Session Connect & Parcel Auto-Sync
# ==============================================================================

def test_carrier_session_connect_and_parcel_sync(client: TestClient):
    """Verifies carrier session connection, parcel auto-sync, and idempotent upserts into user's orders."""
    user = register_test_user(client, "Kamran Qasımov")

    # 1. Connect Carrier Session via Browser Bridge (direct active)
    connect_payload = {
        "provider_type": "carrier",
        "provider_key": "starex",
        "provider_name": "Starex Global",
        "login_url": "https://starex.az/login",
        "account_identifier": "+994501234567",
        "auth_method": "browser_bridge",
        "auth_secret": "BRIDGE_SESSION_TOKEN_XYZ",
        "needs_otp": False,
    }
    res = client.post("/api/v1/user/sessions/connect", json=connect_payload, headers=user["headers"])
    assert res.status_code == 200
    sess = res.json()
    assert sess["session_status"] == "active"
    assert sess["account_identifier"] == "+9945***4567"  # Masked phone!
    session_id = sess["id"]

    # 2. Trigger Auto-Sync from Carrier
    res = client.post(f"/api/v1/user/sessions/{session_id}/sync", headers=user["headers"])
    assert res.status_code == 200
    sync_data = res.json()
    assert sync_data["synced_items_count"] == 2
    assert sync_data["orders_created"] == 2
    assert sync_data["orders_updated"] == 0

    # 3. Verify user's parcels list contains the newly synced parcels
    res = client.get("/api/v1/user/parcels", headers=user["headers"])
    assert res.status_code == 200
    parcels = res.json()
    assert len(parcels) == 2
    trackings = [p["tracking_number"] for p in parcels]
    assert "STRX-994021-AZ" in trackings
    assert "STRX-118834-AZ" in trackings

    # 4. Trigger Auto-Sync second time -> must be idempotent (0 created, 2 updated)
    res = client.post(f"/api/v1/user/sessions/{session_id}/sync", headers=user["headers"])
    assert res.status_code == 200
    sync_data2 = res.json()
    assert sync_data2["orders_created"] == 0
    assert sync_data2["orders_updated"] == 2

    # Verify parcel count is still exactly 2
    res = client.get("/api/v1/user/parcels", headers=user["headers"])
    assert len(res.json()) == 2


# ==============================================================================
# 3. SmartCustoms Session Sync & 1-Click Declaration
# ==============================================================================

def test_smartcustoms_session_sync_and_one_click_declaration(client: TestClient):
    """Verifies connecting SmartCustoms with FIN, syncing quota, and executing 1-click customs declaration."""
    user = register_test_user(client, "Aysel Əhmədova")

    # 1. Connect SmartCustoms with valid 7-char FIN
    connect_payload = {
        "fin": "7KP2026",
        "auth_type": "sima",
        "phone": "+994501234567",
        "credential_secret": "SIMA_CERT_FINGERPRINT_1234",
    }
    res = client.post("/api/v1/user/smartcustoms/connect", json=connect_payload, headers=user["headers"])
    assert res.status_code == 200
    sess = res.json()
    assert sess["provider_type"] == "smartcustoms"
    assert sess["session_status"] == "active"
    assert sess["account_identifier"] == "7KP****"  # Masked FIN!

    # 2. Sync SmartCustoms
    res = client.post("/api/v1/user/smartcustoms/sync", headers=user["headers"])
    assert res.status_code == 200
    sync_info = res.json()
    assert sync_info["fin"] == "7KP2026"
    assert sync_info["month_spent_usd"] == 0.0
    assert sync_info["remaining_quota_usd"] == 300.0

    # 3. Create a parcel for this user
    p_res = client.post(
        "/api/v1/user/parcels",
        json={
            "tracking_number": "TR-TEST-990123",
            "platform": "Trendyol",
            "carrier": "STAREX",
            "title": "Ziyafət Donu",
            "invoice_amount_usd": 65.0,
        },
        headers=user["headers"],
    )
    assert p_res.status_code == 201
    parcel = p_res.json()
    parcel_id = parcel["id"]
    assert parcel["declared_to_dgk"] is False
    assert parcel["dgk_declaration_id"] is None

    # 4. Perform 1-Click Customs Declaration to DGK
    res = client.post(f"/api/v1/user/smartcustoms/declare/{parcel_id}", headers=user["headers"])
    assert res.status_code == 200
    decl = res.json()
    assert decl["parcel_id"] == parcel_id
    assert decl["declaration_id"].startswith("DGK-2026-")
    assert decl["status"] == "Bəyan edildi (Təsdiqləndi)"
    assert "https://e.customs.gov.az" in decl["dgk_receipt_url"]

    # 5. Verify parcel detail and list now reflect declared status
    res = client.get(f"/api/v1/user/parcels/{parcel_id}", headers=user["headers"])
    assert res.status_code == 200
    p_updated = res.json()
    assert p_updated["declared_to_dgk"] is True
    assert p_updated["dgk_declaration_id"] == decl["declaration_id"]
    assert p_updated["declared_at"] is not None

    # 6. Idempotent re-declaration returns existing declaration
    res2 = client.post(f"/api/v1/user/smartcustoms/declare/{parcel_id}", headers=user["headers"])
    assert res2.status_code == 200
    assert res2.json()["declaration_id"] == decl["declaration_id"]


# ==============================================================================
# 4. Session Vault Strict IDOR, SSRF & No Secret Leak
# ==============================================================================

def test_session_vault_strict_idor_ssrf_and_no_secret_leak(client: TestClient):
    """Verifies SSRF prevention on cloud metadata, cross-user IDOR isolation, and zero plaintext secret leak."""
    user_a = register_test_user(client, "Murad Babayev")
    user_b = register_test_user(client, "Elmir Məcidli")

    # 1. SSRF Protection: Attempt to connect session with AWS/GCP cloud metadata URL
    bad_ssrf_payload = {
        "provider_type": "store",
        "provider_key": "malicious",
        "provider_name": "Malicious Portal",
        "login_url": "http://169.254.169.254/latest/meta-data/",
        "account_identifier": "attacker@evil.com",
        "auth_method": "cookie_token",
        "auth_secret": "raw_cookie_leak",
    }
    res = client.post("/api/v1/user/sessions/connect", json=bad_ssrf_payload, headers=user_a["headers"])
    assert res.status_code in (400, 422), f"Expected SSRF rejection, got {res.status_code}"

    # Google Cloud Metadata SSRF attempt
    bad_gcp_ssrf = {
        "provider_type": "store",
        "provider_key": "malicious2",
        "provider_name": "Malicious GCP",
        "login_url": "http://metadata.google.internal/computeMetadata/v1/",
        "account_identifier": "attacker@evil.com",
        "auth_method": "cookie_token",
    }
    res_gcp = client.post("/api/v1/user/sessions/connect", json=bad_gcp_ssrf, headers=user_a["headers"])
    assert res_gcp.status_code in (400, 422)

    # 2. Create legitimate session for User A
    legit_payload = {
        "provider_type": "store",
        "provider_key": "amazon",
        "provider_name": "Amazon US",
        "login_url": "https://www.amazon.com/ap/signin",
        "account_identifier": "murad.amazon@kargopilot.az",
        "auth_method": "credentials_otp",
        "auth_secret": "SuperSecretVaultKey$9988",
        "needs_otp": True,
    }
    res_legit = client.post("/api/v1/user/sessions/connect", json=legit_payload, headers=user_a["headers"])
    assert res_legit.status_code == 200
    session_a = res_legit.json()
    sess_id_a = session_a["id"]

    # 3. IDOR Defense: User B attempts to access, verify OTP, sync, or delete User A's session
    # 3.1 Verify OTP IDOR
    res = client.post(f"/api/v1/user/sessions/{sess_id_a}/verify-otp", json={"otp_code": "123456"}, headers=user_b["headers"])
    assert res.status_code == 404

    # 3.2 Sync IDOR
    res = client.post(f"/api/v1/user/sessions/{sess_id_a}/sync", headers=user_b["headers"])
    assert res.status_code == 404

    # 3.3 Delete IDOR
    res = client.delete(f"/api/v1/user/sessions/{sess_id_a}", headers=user_b["headers"])
    assert res.status_code == 404

    # 4. Zero Plaintext Secret Leakage Check
    # Verify that listing User A's sessions never reveals the raw secret
    res = client.get("/api/v1/user/sessions", headers=user_a["headers"])
    assert res.status_code == 200
    sessions_text = res.text
    assert "SuperSecretVaultKey$9988" not in sessions_text
    assert "murad.amazon@kargopilot.az" not in sessions_text
    assert "mu***n@kargopilot.az" in sessions_text  # properly masked


# ==============================================================================
# 5. Live Demo Account Pre-Seeding Verification
# ==============================================================================

def test_live_demo_account_seeded_with_active_sessions(client: TestClient):
    """Verifies that demo@kargopilot.az is seeded with active sessions (Trendyol, Starex, SmartCustoms) and declared parcels."""
    # 1. Login with demo credentials
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "demo@kargopilot.az", "password": "***REMOVED***"},
    )
    assert login_res.status_code == 200, f"Demo login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Query Sessions
    res = client.get("/api/v1/user/sessions", headers=headers)
    assert res.status_code == 200
    sessions = res.json()
    assert len(sessions) >= 3

    prov_keys = [s["provider_key"] for s in sessions]
    assert "trendyol" in prov_keys
    assert "starex" in prov_keys
    assert "smartcustoms" in prov_keys

    # Check all are active
    for s in sessions:
        assert s["session_status"] == "active"
        assert "****" in s["account_identifier"] or "***" in s["account_identifier"]

    # 3. Query Parcels
    p_res = client.get("/api/v1/user/parcels", headers=headers)
    assert p_res.status_code == 200
    parcels = p_res.json()
    assert len(parcels) >= 2

    declared = [p for p in parcels if p["declared_to_dgk"]]
    undeclared = [p for p in parcels if not p["declared_to_dgk"]]
    assert len(declared) >= 1
    assert len(undeclared) >= 1
    assert declared[0]["dgk_declaration_id"] is not None

    # 4. Check Stores and Carriers session_status mapping
    st_res = client.get("/api/v1/user/stores", headers=headers)
    assert st_res.status_code == 200
    ty_store = next((s for s in st_res.json() if s["name"].lower() == "trendyol"), None)
    assert ty_store is not None
    assert ty_store["session_status"] == "active"

    carr_res = client.get("/api/v1/user/carriers", headers=headers)
    assert carr_res.status_code == 200
    st_carr = next((c for c in carr_res.json() if c["name"].lower() == "starex"), None)
    assert st_carr is not None
    assert st_carr["session_status"] == "active"
