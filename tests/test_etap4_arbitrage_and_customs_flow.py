"""Deterministic QA and Security Verification Test Suite for Etap 4:
Smart Arbitrage Engine (Carrier Rate Comparison, Volumetric Weight, Parcel Types, Max Savings)
Customs Supervisor Engine (DGK 300$ Quota Simulation, Statutory 36% Duty Math, Recommendations)
and Strict Multi-Tenant Isolation & Dashboard UI Integration.
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


def register_test_user(client: TestClient, name: str = "Etap4 Test İstifadəçi") -> dict:
    """Helper to register an isolated test user and return credentials + token."""
    email = f"etap4_{uuid.uuid4().hex[:8]}@kargopilot.az"
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


# ==============================================================================
# 1. Smart Arbitrage Tests
# ==============================================================================

def test_arbitrage_calculation_standard_weight(client: TestClient):
    """Verifies shipping rate calculation for standard parcel, ascending sort, and savings math."""
    payload = {
        "origin_country": "TR",
        "weight_kg": 1.5,
        "parcel_type": "standard",
    }
    res = client.post("/api/v1/user/arbitrage/calculate", json=payload)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    data = res.json()
    assert data["origin_country"] == "TR"
    assert data["actual_weight_kg"] == 1.5
    assert data["chargeable_weight_kg"] == 1.5
    assert data["volumetric_weight_kg"] is None
    assert data["parcel_type"] == "standard"

    carriers = data["carriers"]
    assert len(carriers) >= 5, "Expected at least 5 carriers for Turkey"

    # Verify ascending sort by rate_usd
    rates_usd = [c["rate_usd"] for c in carriers]
    assert rates_usd == sorted(rates_usd), "Carriers must be sorted from cheapest to most expensive"

    # Verify cheapest and fastest flags
    assert carriers[0]["is_cheapest"] is True
    assert data["best_value_carrier"] == carriers[0]["carrier_name"]
    assert any(c["is_fastest"] for c in carriers), "At least one carrier must be designated fastest"

    # Verify max savings formula: max - min
    expected_savings_usd = round(rates_usd[-1] - rates_usd[0], 2)
    assert data["max_savings_usd"] == expected_savings_usd
    assert data["max_savings_azn"] == round(expected_savings_usd * 1.70, 2)

    # Verify AZN currency conversion: 1 USD = 1.70 AZN
    for c in carriers:
        assert c["rate_azn"] == round(c["rate_usd"] * 1.70, 2)
        assert "iş günü" in c["delivery_eta"]


def test_arbitrage_volumetric_weight_override(client: TestClient):
    """Verifies that volumetric weight overrides actual weight when dimensions are provided."""
    # Box: 30cm x 20cm x 20cm = 12000 cm3 / 6000 = 2.0 kg > 0.5 kg actual
    payload = {
        "origin_country": "US",
        "weight_kg": 0.5,
        "length_cm": 30.0,
        "width_cm": 20.0,
        "height_cm": 20.0,
        "parcel_type": "standard",
    }
    res = client.post("/api/v1/user/arbitrage/calculate", json=payload)
    assert res.status_code == 200

    data = res.json()
    assert data["actual_weight_kg"] == 0.5
    assert data["volumetric_weight_kg"] == 2.0
    assert data["chargeable_weight_kg"] == 2.0

    # Rates must be calculated based on 2.0 kg, not 0.5 kg
    for c in data["carriers"]:
        assert c["chargeable_weight_kg"] == 2.0


def test_arbitrage_surcharges_liquid_and_electronics(client: TestClient):
    """Verifies that liquid (+$1.50) and electronics (+$1.00) surcharges are applied accurately."""
    base_payload = {"origin_country": "TR", "weight_kg": 1.0, "parcel_type": "standard"}
    liquid_payload = {"origin_country": "TR", "weight_kg": 1.0, "parcel_type": "liquid"}
    elec_payload = {"origin_country": "TR", "weight_kg": 1.0, "parcel_type": "electronics"}

    res_std = client.post("/api/v1/user/arbitrage/calculate", json=base_payload).json()
    res_liq = client.post("/api/v1/user/arbitrage/calculate", json=liquid_payload).json()
    res_elec = client.post("/api/v1/user/arbitrage/calculate", json=elec_payload).json()

    std_starex = next(c for c in res_std["carriers"] if c["carrier_code"] == "STAREX")
    liq_starex = next(c for c in res_liq["carriers"] if c["carrier_code"] == "STAREX")
    elec_starex = next(c for c in res_elec["carriers"] if c["carrier_code"] == "STAREX")

    # Liquid diff must be exactly 1.50 USD
    assert round(liq_starex["rate_usd"] - std_starex["rate_usd"], 2) == 1.50
    assert "Maye" in liq_starex["notes"]

    # Electronics diff must be exactly 1.00 USD
    assert round(elec_starex["rate_usd"] - std_starex["rate_usd"], 2) == 1.00
    assert "Elektronika" in elec_starex["notes"]


def test_arbitrage_all_origin_countries(client: TestClient):
    """Verifies rate calculations across all 4 key trading routes: TR, CN, US, EU."""
    for origin in ["TR", "CN", "US", "EU"]:
        res = client.post(
            "/api/v1/user/arbitrage/calculate",
            json={"origin_country": origin, "weight_kg": 2.0, "parcel_type": "standard"},
        )
        assert res.status_code == 200, f"Origin {origin} failed"
        data = res.json()
        assert data["origin_country"] == origin
        assert len(data["carriers"]) >= 4
        assert data["best_value_carrier"]
        assert data["fastest_carrier"]


# ==============================================================================
# 2. Customs Supervisor Tests
# ==============================================================================

def test_customs_simulation_unauthenticated_fails(client: TestClient):
    """Verifies that customs simulation requires an authenticated user session (Tenant Isolation)."""
    res = client.post(
        "/api/v1/user/customs/simulate",
        json={"item_price_usd": 100.0, "shipping_fee_usd": 10.0},
    )
    assert res.status_code == 401, f"Expected 401 Unauthorized, got {res.status_code}"


def test_customs_simulation_under_limit_safe(client: TestClient):
    """Verifies safe status when projected total is well under $300 limit (< $240)."""
    user = register_test_user(client, name="Kamran Əliyev")
    payload = {
        "item_price_usd": 120.0,
        "shipping_fee_usd": 15.0,
    }
    res = client.post("/api/v1/user/customs/simulate", json=payload, headers=user["headers"])
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

    data = res.json()
    assert data["user_id"] == user["user_id"]
    assert data["current_spent_usd"] == 0.0
    assert data["item_price_usd"] == 120.0
    assert data["shipping_fee_usd"] == 15.0
    assert data["projected_total_usd"] == 135.0
    assert data["projected_total_azn"] == round(135.0 * 1.70, 2)
    assert data["exceeds_limit"] is False
    assert data["remaining_allowance_usd"] == 165.0
    assert data["remaining_allowance_azn"] == round(165.0 * 1.70, 2)
    assert data["over_limit_amount_usd"] == 0.0
    assert data["duty_usd"] == 0.0
    assert data["duty_azn"] == 0.0
    assert data["status"] == "safe"
    assert len(data["recommendations"]) >= 2


def test_customs_simulation_warning_zone(client: TestClient):
    """Verifies warning status when projected total is close to limit ($240 - $300)."""
    user = register_test_user(client, name="Nərgiz Məmmədova")
    payload = {
        "item_price_usd": 260.0,
        "shipping_fee_usd": 10.0,
    }
    res = client.post("/api/v1/user/customs/simulate", json=payload, headers=user["headers"])
    assert res.status_code == 200

    data = res.json()
    assert data["projected_total_usd"] == 270.0
    assert data["exceeds_limit"] is False
    assert data["remaining_allowance_usd"] == 30.0
    assert data["duty_usd"] == 0.0
    assert data["status"] == "warning"


def test_customs_simulation_over_limit_danger_and_duty_math(client: TestClient):
    """Verifies statutory 36% duty math on the amount exceeding $300."""
    user = register_test_user(client, name="Elvin Həsənov")
    # Projected: $380 item + $20 shipping = $400 USD
    # Excess over $300 = $100 USD
    # Duty (36%): 100 * 0.36 = 36.00 USD
    # Duty AZN: 36 * 1.70 = 61.20 AZN
    payload = {
        "item_price_usd": 380.0,
        "shipping_fee_usd": 20.0,
    }
    res = client.post("/api/v1/user/customs/simulate", json=payload, headers=user["headers"])
    assert res.status_code == 200

    data = res.json()
    assert data["projected_total_usd"] == 400.0
    assert data["projected_total_azn"] == round(400.0 * 1.70, 2)
    assert data["exceeds_limit"] is True
    assert data["remaining_allowance_usd"] == 0.0
    assert data["over_limit_amount_usd"] == 100.0
    assert data["over_limit_amount_azn"] == round(100.0 * 1.70, 2)
    assert data["duty_rate_percent"] == 36.0
    assert data["duty_usd"] == 36.00
    assert data["duty_azn"] == 61.20
    assert data["status"] == "danger"
    assert any("36%" in r for r in data["recommendations"])


def test_customs_simulation_strict_tenant_isolation(client: TestClient):
    """Verifies strict tenant isolation: User A's real orders in DB must affect User A's simulation, but NEVER User B's."""
    user_a = register_test_user(client, name="User A (Aktiv Alıcı)")
    user_b = register_test_user(client, name="User B (Yeni İstifadəçi)")

    # User A creates a real parcel of $180 USD
    parcel_payload = {
        "tracking_number": f"TRK-{uuid.uuid4().hex[:6].upper()}",
        "platform": "Trendyol",
        "carrier": "STAREX",
        "title": "Dəri Görmüş Kurtka",
        "invoice_amount_usd": 180.0,
    }
    create_res = client.post("/api/v1/user/parcels", json=parcel_payload, headers=user_a["headers"])
    assert create_res.status_code in (200, 201), f"Parcel creation failed: {create_res.text}"

    # Both users simulate buying an identical item for $150 USD
    sim_payload = {"item_price_usd": 150.0, "shipping_fee_usd": 0.0}

    # User A: already spent $180. Projected = 180 + 150 = $330 > $300 -> OVER LIMIT!
    res_a = client.post("/api/v1/user/customs/simulate", json=sim_payload, headers=user_a["headers"]).json()
    assert res_a["current_spent_usd"] == 180.0
    assert res_a["projected_total_usd"] == 330.0
    assert res_a["exceeds_limit"] is True
    assert res_a["over_limit_amount_usd"] == 30.0
    assert res_a["duty_usd"] == round(30.0 * 0.36, 2)
    assert res_a["status"] == "danger"

    # User B: spent $0. Projected = 0 + 150 = $150 <= $300 -> SAFE!
    res_b = client.post("/api/v1/user/customs/simulate", json=sim_payload, headers=user_b["headers"]).json()
    assert res_b["current_spent_usd"] == 0.0
    assert res_b["projected_total_usd"] == 150.0
    assert res_b["exceeds_limit"] is False
    assert res_b["remaining_allowance_usd"] == 150.0
    assert res_b["duty_usd"] == 0.0
    assert res_b["status"] == "safe"


# ==============================================================================
# 3. User Dashboard UI Verification
# ==============================================================================

def test_user_dashboard_page_contains_arbitrage_and_customs_widgets(client: TestClient):
    """Verifies that /user/dashboard template renders both Smart Arbitrage and Customs Supervisor widgets."""
    user = register_test_user(client, name="Aytən Səfərova")

    # Access /user/dashboard via cookie session or bearer auth
    client.cookies.set("kargopilot_access", user["token"])
    res = client.get("/user/dashboard")
    assert res.status_code == 200, f"Dashboard failed: {res.status_code}"

    html = res.text
    # Check Smart Arbitrage components
    assert "Smart Arbitraj" in html
    assert "Tarif Analizatoru" in html
    assert "arb-country" in html
    assert "calculateArbitrage" in html
    assert "applyArbitrageToOrder" in html

    # Check Customs Supervisor components
    assert "DGK 300$ Supervisor" in html
    assert "305 № Qərar" in html
    assert "sim-price-usd" in html
    assert "simulateCustoms" in html
    assert "applyCustomsToOrder" in html
