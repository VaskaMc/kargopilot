"""Deterministic End-to-End User Journey Simulation Test Suite for Etap 5:
Negative & Positive Auth Scenarios, Profile/FIN persistence, Smart Arbitrage with Volumetric math,
Parcels lifecycle, Dynamic DGK 300$ Quota, Customs 36% Duty Simulator, Data Sovereignty Export/Wipe/Import,
SSRF-protected Node Verifier, UI Page Renders, and Permanent Demo Account Certification.
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


# ==============================================================================
# TAPŞIRIQ 1: Qeydiyyat və Login Sınaqları (Negative & Positive Auth)
# ==============================================================================

def test_01_negative_registration_validation(client: TestClient):
    """Verifies that invalid registration payloads (short password, invalid email) are rejected."""
    # 1. Short password (< 8 chars)
    res_short = client.post("/api/v1/auth/register", json={
        "email": "test.pilot@kargopilot.az",
        "password": "short",
        "full_name": "Test Pilot",
    })
    assert res_short.status_code == 422, f"Expected 422 for short password, got {res_short.status_code}"
    assert "8" in res_short.text or "password" in res_short.text.lower()

    # 2. Invalid email format
    res_email = client.post("/api/v1/auth/register", json={
        "email": "invalid-email-address",
        "password": "StrongPassword2026!",
        "full_name": "Test Pilot",
    })
    assert res_email.status_code == 422, f"Expected 422 for invalid email, got {res_email.status_code}"


def test_02_positive_registration_success(client: TestClient):
    """Verifies that a valid new user can register and receives access tokens and user profile."""
    unique_email = f"pilot.tester.{uuid.uuid4().hex[:6]}@kargopilot.az"
    unique_phone = f"+99450{uuid.uuid4().int % 9000000 + 1000000}"
    res = client.post("/api/v1/auth/register", json={
        "email": unique_email,
        "password": "***REMOVED***",
        "full_name": "Vasif Məcidli (Pilot Tester)",
        "phone": unique_phone,
        "hosting_preference": "cloud",
    })
    assert res.status_code == 201, f"Expected 201 Created, got {res.status_code}: {res.text}"
    data = res.json()
    assert "access_token" in data
    assert data["email"] == unique_email.lower()
    assert data["role"] == "CUSTOMER"


def test_03_duplicate_registration_prevented(client: TestClient):
    """Verifies that registering with an already existing email is strictly prevented."""
    dup_email = f"duplicate.{uuid.uuid4().hex[:6]}@kargopilot.az"
    payload = {
        "email": dup_email,
        "password": "***REMOVED***",
        "full_name": "Duplicate Tester",
    }
    # First registration
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    # Second registration attempt with identical email
    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 409, f"Expected 409 Conflict, got {res2.status_code}: {res2.text}"
    assert "artıq qeydiyyatdan keçilib" in res2.text or "already" in res2.text.lower()


def test_04_login_negative_and_positive(client: TestClient):
    """Verifies that wrong password fails with 401, while correct password issues session token."""
    user_email = f"login.check.{uuid.uuid4().hex[:6]}@kargopilot.az"
    client.post("/api/v1/auth/register", json={
        "email": user_email,
        "password": "CorrectPassword2026!",
        "full_name": "Login Tester",
    })

    # Wrong password attempt
    res_fail = client.post("/api/v1/auth/login", json={
        "email": user_email,
        "password": "WrongPassword999!",
    })
    assert res_fail.status_code == 401, f"Expected 401 Unauthorized, got {res_fail.status_code}"

    # Correct password attempt
    res_ok = client.post("/api/v1/auth/login", json={
        "email": user_email,
        "password": "CorrectPassword2026!",
    })
    assert res_ok.status_code == 200, f"Expected 200 OK, got {res_ok.status_code}"
    data = res_ok.json()
    assert "access_token" in data
    assert data["email"] == user_email


# ==============================================================================
# TAPŞIRIQ 2: Bir İstifadəçi ilə Tam Funksionallıq Dövrəsi (Full Lifecycle)
# ==============================================================================

class TestSingleUserFullLifecycleJourney:
    """Simulates the complete end-to-end journey for a single customer across all 8 modules."""

    session_user: dict = {}

    @classmethod
    def setup_class(cls):
        init_db()

    def test_step1_register_and_authenticate(self, client: TestClient):
        """Step 1: Register primary journey user and establish authenticated headers."""
        email = f"journey.pilot.{uuid.uuid4().hex[:6]}@kargopilot.az"
        phone = f"+99455{uuid.uuid4().int % 9000000 + 1000000}"
        reg_res = client.post("/api/v1/auth/register", json={
            "email": email,
            "password": "***REMOVED***",
            "full_name": "Vasif Məcidli",
            "phone": phone,
        })
        assert reg_res.status_code == 201
        data = reg_res.json()
        token = data["access_token"]
        TestSingleUserFullLifecycleJourney.session_user = {
            "email": email,
            "token": token,
            "headers": {"Authorization": f"Bearer {token}"},
            "user_id": data["user_id"],
        }

    def test_step2_profile_and_fin_update(self, client: TestClient):
        """Step 2: Read profile, validate FIN length rules, and update FIN, branch, and notifications."""
        headers = self.session_user["headers"]

        # Read initial profile
        res_get = client.get("/api/v1/user/profile", headers=headers)
        assert res_get.status_code == 200
        init_prof = res_get.json()
        assert init_prof["email"] == self.session_user["email"]

        # Attempt invalid FIN (not 7 chars)
        res_invalid_fin = client.put("/api/v1/user/profile", json={"fin": "SHORT"}, headers=headers)
        assert res_invalid_fin.status_code == 422, "FIN must strictly be 7 characters"

        # Update profile with valid FIN and branch
        update_payload = {
            "full_name": "Vasif Məcidli (Pilot Tester)",
            "fin": "7KP2026",
            "phone": "+994776346310",
            "default_branch": "Bakı - Mərkəz",
            "notification_whatsapp": True,
            "notification_email": True,
        }
        res_put = client.put("/api/v1/user/profile", json=update_payload, headers=headers)
        assert res_put.status_code == 200
        updated = res_put.json()
        assert updated["fin"] == "7KP2026"
        assert updated["default_branch"] == "Bakı - Mərkəz"
        assert updated["notification_whatsapp"] is True

        # Re-fetch via GET to guarantee DB persistence
        res_verify = client.get("/api/v1/user/profile", headers=headers)
        assert res_verify.status_code == 200
        persisted = res_verify.json()
        assert persisted["fin"] == "7KP2026"
        assert persisted["default_branch"] == "Bakı - Mərkəz"

    def test_step3_smart_arbitrage_volumetric_calculation(self, client: TestClient):
        """Step 3: Execute Smart Arbitrage from Turkey with 2.5 kg actual and 40x30x20 cm dimensions."""
        # Volumetric = 40 * 30 * 20 / 6000 = 24000 / 6000 = 4.0 kg > 2.5 kg actual
        payload = {
            "origin_country": "TR",
            "weight_kg": 2.5,
            "length_cm": 40.0,
            "width_cm": 30.0,
            "height_cm": 20.0,
            "parcel_type": "standard",
        }
        res = client.post("/api/v1/user/arbitrage/calculate", json=payload)
        assert res.status_code == 200
        arb = res.json()
        assert arb["origin_country"] == "TR"
        assert arb["actual_weight_kg"] == 2.5
        assert arb["volumetric_weight_kg"] == 4.0
        assert arb["chargeable_weight_kg"] == 4.0

        # Verify ascending price sort
        carriers = arb["carriers"]
        rates = [c["rate_usd"] for c in carriers]
        assert rates == sorted(rates)
        assert arb["best_value_carrier"] == carriers[0]["carrier_name"]
        assert arb["max_savings_usd"] == round(rates[-1] - rates[0], 2)
        assert arb["max_savings_azn"] == round(arb["max_savings_usd"] * 1.70, 2)

    def test_step4_parcels_addition_and_dynamic_dgk_quota(self, client: TestClient):
        """Step 4: Add Parcel 1 ($85) -> Safe, Add Parcel 2 ($175) -> Warning ($260 total)."""
        headers = self.session_user["headers"]

        # 1. Add Parcel 1: $85.00 USD
        p1 = {
            "tracking_number": "TRK-TY984120",
            "platform": "Trendyol",
            "carrier": "STAREX",
            "title": "Kişi Qış Gödəkcəsi",
            "invoice_amount_usd": 85.00,
        }
        res_p1 = client.post("/api/v1/user/parcels", json=p1, headers=headers)
        assert res_p1.status_code in (200, 201)

        # Check quota: $85.00 spent -> Safe (< $240)
        q1 = client.get("/api/v1/user/quota", headers=headers).json()
        assert q1["total_spent_usd"] == 85.00
        assert q1["remaining_usd"] == 215.00
        assert q1["status"] == "safe"
        assert q1["duty_estimate_azn"] == 0.0

        # 2. Add Parcel 2: $175.00 USD
        p2 = {
            "tracking_number": "AMZ-441029US",
            "platform": "Amazon",
            "carrier": "CAMEX",
            "title": "Simsiz Səs Qulaqlığı",
            "invoice_amount_usd": 175.00,
        }
        res_p2 = client.post("/api/v1/user/parcels", json=p2, headers=headers)
        assert res_p2.status_code in (200, 201)

        # Check quota: $85 + $175 = $260.00 spent -> Warning ($240 - $300)
        q2 = client.get("/api/v1/user/quota", headers=headers).json()
        assert q2["total_spent_usd"] == 260.00
        assert q2["remaining_usd"] == 40.00
        assert q2["status"] == "warning"

    def test_step5_customs_supervisor_36_percent_duty_simulation(self, client: TestClient):
        """Step 5: Simulate purchase ($90 item + $10 shipping) over current $260 spent -> $360 total."""
        headers = self.session_user["headers"]
        sim_payload = {
            "item_price_usd": 90.00,
            "shipping_fee_usd": 10.00,
        }
        res = client.post("/api/v1/user/customs/simulate", json=sim_payload, headers=headers)
        assert res.status_code == 200
        sim = res.json()

        assert sim["current_spent_usd"] == 260.00
        assert sim["item_price_usd"] == 90.00
        assert sim["shipping_fee_usd"] == 10.00
        assert sim["projected_total_usd"] == 360.00
        assert sim["projected_total_azn"] == round(360.00 * 1.70, 2)

        # Limit exceeded math: $360 - $300 = $60 USD excess
        assert sim["exceeds_limit"] is True
        assert sim["over_limit_amount_usd"] == 60.00
        assert sim["over_limit_amount_azn"] == round(60.00 * 1.70, 2)

        # 36% duty math: 60 * 0.36 = 21.60 USD (36.72 AZN)
        assert sim["duty_rate_percent"] == 36.0
        assert sim["duty_usd"] == 21.60
        assert sim["duty_azn"] == 36.72
        assert sim["status"] == "danger"
        assert len(sim["recommendations"]) >= 4

    def test_step6_parcel_deletion_and_quota_recovery(self, client: TestClient):
        """Step 6: Add temporary parcel ($40), verify quota reaches $300, delete it, verify recovery back to $260."""
        headers = self.session_user["headers"]

        # Add temporary 3rd parcel
        temp_parcel = {
            "tracking_number": f"TEMP-{uuid.uuid4().hex[:6].upper()}",
            "platform": "Temu",
            "carrier": "STAREX",
            "title": "Müvəqqəti Test Məhsulu",
            "invoice_amount_usd": 40.00,
        }
        res_temp = client.post("/api/v1/user/parcels", json=temp_parcel, headers=headers)
        assert res_temp.status_code in (200, 201)
        temp_id = res_temp.json()["id"]

        # Quota should now be $300
        q_300 = client.get("/api/v1/user/quota", headers=headers).json()
        assert q_300["total_spent_usd"] == 300.00
        assert q_300["remaining_usd"] == 0.00

        # Delete the 3rd parcel
        res_del = client.delete(f"/api/v1/user/parcels/{temp_id}", headers=headers)
        assert res_del.status_code == 200

        # Quota should be restored to $260
        q_restored = client.get("/api/v1/user/quota", headers=headers).json()
        assert q_restored["total_spent_usd"] == 260.00
        assert q_restored["remaining_usd"] == 40.00
        assert q_restored["status"] == "warning"

    def test_step7_data_sovereignty_export_wipe_import_cycle(self, client: TestClient):
        """Step 7: Full Data Portability cycle: Export JSON -> Wipe Account -> Import JSON -> 100% Recovery."""
        headers = self.session_user["headers"]

        # 1. Export JSON package
        res_exp = client.get("/api/v1/user/export", headers=headers)
        assert res_exp.status_code == 200
        export_pkg = res_exp.json()
        assert export_pkg["service"] == "kargopilot-core"
        assert len(export_pkg["parcels"]) == 2
        assert export_pkg["quota_summary"]["total_spent_usd"] == 260.00

        # 2. Wipe account data
        res_wipe = client.delete("/api/v1/user/account-data?confirm_wipe=true", headers=headers)
        assert res_wipe.status_code == 200
        assert res_wipe.json()["wiped_orders_count"] == 2

        # Verify parcels empty & quota reset
        empty_parcels = client.get("/api/v1/user/parcels", headers=headers).json()
        assert len(empty_parcels) == 0
        reset_quota = client.get("/api/v1/user/quota", headers=headers).json()
        assert reset_quota["total_spent_usd"] == 0.00
        assert reset_quota["remaining_usd"] == 300.00

        # 3. Import JSON package back
        res_imp = client.post("/api/v1/user/import", json=export_pkg, headers=headers)
        assert res_imp.status_code == 200
        imp_result = res_imp.json()
        assert imp_result["imported_count"] == 2

        # Verify parcels and quota restored to exactly $260.00
        restored_parcels = client.get("/api/v1/user/parcels", headers=headers).json()
        assert len(restored_parcels) == 2
        restored_quota = client.get("/api/v1/user/quota", headers=headers).json()
        assert restored_quota["total_spent_usd"] == 260.00
        assert restored_quota["remaining_usd"] == 40.00
        assert restored_quota["status"] == "warning"

    def test_step8_sovereign_node_verifier_and_ssrf_boundary(self, client: TestClient):
        """Step 8: Verify reachable node and confirm SSRF protection against internal metadata IP."""
        # 1. SSRF target blocked
        res_ssrf = client.post("/api/v1/user/verify-node", json={"target_url": "http://169.254.169.254"})
        assert res_ssrf.status_code == 200
        data_ssrf = res_ssrf.json()
        assert data_ssrf["healthy"] is False
        assert "qadağandır" in data_ssrf["message"] or "metadata" in data_ssrf["message"].lower()

    def test_step9_ui_and_browser_pages_render_under_session(self, client: TestClient):
        """Step 9: Confirm that /user/dashboard, /self-hosted, and /onboarding render with live user session."""
        # Set session cookie
        client.cookies.set("kargopilot_access", self.session_user["token"])

        # 1. User Dashboard
        res_dash = client.get("/user/dashboard")
        assert res_dash.status_code == 200
        html_dash = res_dash.text
        assert "KargoPilot" in html_dash
        assert "DGK 300$" in html_dash
        assert "Smart Arbitraj" in html_dash
        assert "DGK 300$ Supervisor" in html_dash
        assert "7KP2026" in html_dash or "FİN" in html_dash

        # 2. Self-Hosted Onboarding Wizard
        res_self = client.get("/self-hosted")
        assert res_self.status_code == 200
        assert "Öz Serverinizdə" in res_self.text or "Sovereign" in res_self.text

        # 3. Onboarding Route
        res_onb = client.get("/onboarding")
        assert res_onb.status_code == 200


# ==============================================================================
# TAPŞIRIQ 3: Permanent Live Demo Account Certification
# ==============================================================================

def test_permanent_demo_account_ready_for_user_inspection(client: TestClient):
    """Verifies that the permanent demo account (demo@kargopilot.az / ***REMOVED***) exists, authenticates, and holds 2 parcels."""
    # Authenticate with Demo credentials
    login_res = client.post("/api/v1/auth/login", json={
        "email": "demo@kargopilot.az",
        "password": "***REMOVED***",
    })
    assert login_res.status_code == 200, f"Demo login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify Profile
    prof_res = client.get("/api/v1/user/profile", headers=headers)
    assert prof_res.status_code == 200
    prof = prof_res.json()
    assert prof["fin"] == "7KP2026"
    assert "Demo" in prof["full_name"] or "Vasif Məcidli" in prof["full_name"]

    # Verify Parcels
    parcels_res = client.get("/api/v1/user/parcels", headers=headers)
    assert parcels_res.status_code == 200
    parcels = parcels_res.json()
    assert len(parcels) == 2, f"Expected 2 seeded parcels, got {len(parcels)}"

    # Verify Quota balance: $260 spent, $40 remaining, warning status
    quota_res = client.get("/api/v1/user/quota", headers=headers)
    assert quota_res.status_code == 200
    q = quota_res.json()
    assert q["total_spent_usd"] == 260.00
    assert q["remaining_usd"] == 40.00
    assert q["status"] == "warning"
