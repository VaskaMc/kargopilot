"""Deterministic QA and Security Verification Test Suite for Etap 6 (KargoPilot v5.0):
1. Stores / Marketplaces Hub (Standard + Custom Stores, IDOR Protection, Domain Validation)
2. Carriers Hub & Dynamic Arbitrage (Standard + Custom Carriers, Rate Calculation, Arbitrage Matrix Injection)
3. Free AI Copilot (Context-Aware Reasoning, Hybrid LLM/Deterministic Azerbaijani NLP, History & Clear)
4. Advanced Profile & Family FIN Mesh (Password Verification & Rotation, 7-char FIN Validation, IDOR Protection)
5. Full Data Portability & Sovereignty (v5.0.0 Export, Wipe, and Import with Custom Ecosystems)
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


def register_test_user(client: TestClient, name: str = "Etap6 Test İstifadəçi") -> dict:
    """Helper to register an isolated test user and return credentials + token."""
    email = f"etap6_{uuid.uuid4().hex[:8]}@kargopilot.az"
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
# 1. Modul 1: Stores / Marketplaces Hub
# ==============================================================================

def test_user_stores_crud_and_idor_protection(client: TestClient):
    """Verifies standard stores listing, custom store creation, domain validation, and IDOR protection."""
    user_a = register_test_user(client, "Rauf Məmmədov")
    user_b = register_test_user(client, "Sevinc Əliyeva")

    # 1. List stores (should contain standard stores like Trendyol, Temu, Amazon)
    res = client.get("/api/v1/user/stores", headers=user_a["headers"])
    assert res.status_code == 200
    stores = res.json()
    assert len(stores) >= 8
    store_names = [s["name"] for s in stores]
    assert "Trendyol" in store_names
    assert "Temu" in store_names
    assert "Amazon" in store_names

    # 2. Add custom store invalid domain
    bad_res = client.post(
        "/api/v1/user/stores",
        json={"name": "Bad Store", "domain_url": "invalid_url_without_dot"},
        headers=user_a["headers"],
    )
    assert bad_res.status_code == 422

    # 3. Add valid custom store
    store_payload = {
        "name": "Morhipo VIP",
        "domain_url": "https://morhipo.com",
        "country_code": "TR",
        "default_currency": "TRY",
        "category": "Geyim",
        "icon_badge": "👗",
    }
    res_create = client.post("/api/v1/user/stores", json=store_payload, headers=user_a["headers"])
    assert res_create.status_code == 201
    created_store = res_create.json()
    store_id = created_store["id"]
    assert created_store["name"] == "Morhipo VIP"
    assert created_store["is_standard"] is False

    # 4. User A's list now includes Morhipo VIP
    res_a = client.get("/api/v1/user/stores", headers=user_a["headers"])
    assert any(s["id"] == store_id for s in res_a.json())

    # 5. User B's list DOES NOT include User A's custom store (Strict Isolation)
    res_b = client.get("/api/v1/user/stores", headers=user_b["headers"])
    assert not any(s["id"] == store_id for s in res_b.json())

    # 6. IDOR: User B attempts to delete User A's store -> 404
    res_idor = client.delete(f"/api/v1/user/stores/{store_id}", headers=user_b["headers"])
    assert res_idor.status_code == 404

    # 7. Standard store cannot be deleted
    std_store = next(s for s in stores if s["is_standard"])
    res_del_std = client.delete(f"/api/v1/user/stores/{std_store['id']}", headers=user_a["headers"])
    assert res_del_std.status_code == 404

    # 8. User A deletes own custom store -> 200
    res_del = client.delete(f"/api/v1/user/stores/{store_id}", headers=user_a["headers"])
    assert res_del.status_code == 200


# ==============================================================================
# 2. Modul 2: Carriers Hub & Dynamic Arbitrage Integration
# ==============================================================================

def test_user_carriers_crud_and_dynamic_arbitrage(client: TestClient):
    """Verifies standard carriers listing, custom carrier addition, and dynamic participation in Smart Arbitrage."""
    user = register_test_user(client, "Murad Babayev")

    # 1. List carriers (includes standard: Starex, Expargo, Dynamex, Limak, etc.)
    res = client.get("/api/v1/user/carriers", headers=user["headers"])
    assert res.status_code == 200
    carriers = res.json()
    assert len(carriers) >= 7
    c_names = [c["name"] for c in carriers]
    assert "Starex" in c_names

    # 2. Add custom carrier with a very competitive rate
    custom_c = {
        "name": "KargoPilot Super Ekspres",
        "website_url": "https://superekspres.az",
        "tracking_url_template": "https://superekspres.az/track/{tracking}",
        "origin_country": "TR",
        "rate_per_kg_usd": 2.20,  # $2.20 per kg
        "liquid_surcharge_usd": 1.00,
        "electronics_surcharge_usd": 1.50,
        "delivery_days_min": 2,
        "delivery_days_max": 4,
        "branch_address": "Gənclik Mall",
    }
    res_create = client.post("/api/v1/user/carriers", json=custom_c, headers=user["headers"])
    assert res_create.status_code == 201
    c_data = res_create.json()
    carrier_id = c_data["id"]
    assert c_data["name"] == "KargoPilot Super Ekspres"
    assert c_data["rate_per_kg_usd"] == 2.20

    # 3. Dynamic Arbitrage calculation with User Bearer Token
    arb_payload = {
        "origin_country": "TR",
        "weight_kg": 2.0,
        "parcel_type": "standard",
    }
    res_arb = client.post("/api/v1/user/arbitrage/calculate", json=arb_payload, headers=user["headers"])
    assert res_arb.status_code == 200
    arb_data = res_arb.json()

    # Verify custom carrier is present in calculated carriers list
    calculated_names = [c["carrier_name"] for c in arb_data["carriers"]]
    assert any("KargoPilot Super Ekspres" in n for n in calculated_names)

    # For 2.0 kg at $2.20/kg, rate is $4.40. Standard carriers are base + per_kg (~$9.00+).
    # Therefore, custom carrier should be ranked as the cheapest!
    assert "KargoPilot Super Ekspres" in arb_data["best_value_carrier"]

    # 4. Update custom carrier
    update_payload = {"rate_per_kg_usd": 2.10, "delivery_days_max": 3}
    res_update = client.put(f"/api/v1/user/carriers/{carrier_id}", json=update_payload, headers=user["headers"])
    assert res_update.status_code == 200
    assert res_update.json()["rate_per_kg_usd"] == 2.10

    # 5. IDOR test: another user cannot delete
    other_user = register_test_user(client, "Kənan Nəzərov")
    res_idor = client.delete(f"/api/v1/user/carriers/{carrier_id}", headers=other_user["headers"])
    assert res_idor.status_code == 404

    # 6. Delete custom carrier
    res_del = client.delete(f"/api/v1/user/carriers/{carrier_id}", headers=user["headers"])
    assert res_del.status_code == 200


# ==============================================================================
# 3. Modul 3: Free AI Copilot Reasoning & History
# ==============================================================================

def test_ai_copilot_chat_history_and_reasoning(client: TestClient):
    """Verifies AI Copilot context ingestion, quota math reasoning, history retention, and history wipe."""
    user = register_test_user(client, "Nərgiz Paşayeva")

    # Add parcel to establish quota spent ($80 USD)
    client.post(
        "/api/v1/user/parcels",
        json={
            "tracking_number": f"AI-TRK-{uuid.uuid4().hex[:6]}",
            "platform": "Trendyol",
            "carrier": "STAREX",
            "title": "Kosmetika dəsti",
            "invoice_amount_usd": 80.0,
        },
        headers=user["headers"],
    )

    # 1. Ask about remaining quota
    chat_req = {"message": "Salam Loyd, mənim bu ay nə qədər gömrük limitim qalıb?"}
    res_chat = client.post("/api/v1/user/ai/chat", json=chat_req, headers=user["headers"])
    assert res_chat.status_code == 200
    chat_resp = res_chat.json()
    reply = chat_resp["reply"]
    assert "300" in reply
    assert "220" in reply or "limit" in reply.lower()
    assert chat_resp["context_used"]["spent_usd"] == 80.0
    assert chat_resp["context_used"]["remaining_usd"] == 220.0

    # 2. Ask about cheapest carrier from Turkey
    chat_req2 = {"message": "Türkiyədən 2 kq bağlama üçün ən sərfəli kargo hansıdır?"}
    res_chat2 = client.post("/api/v1/user/ai/chat", json=chat_req2, headers=user["headers"])
    assert res_chat2.status_code == 200
    assert "kargo" in res_chat2.json()["reply"].lower() or "starex" in res_chat2.json()["reply"].lower()

    # 3. Retrieve history
    res_hist = client.get("/api/v1/user/ai/history", headers=user["headers"])
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) >= 4  # 2 user turns + 2 assistant turns
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"

    # 4. Clear history
    res_del_hist = client.delete("/api/v1/user/ai/history", headers=user["headers"])
    assert res_del_hist.status_code == 200

    # Verify history is now empty
    res_hist_after = client.get("/api/v1/user/ai/history", headers=user["headers"])
    assert len(res_hist_after.json()) == 0


# ==============================================================================
# 4. Modul 4: Profile Password & Family FIN Mesh
# ==============================================================================

def test_profile_password_rotation_and_family_fin_mesh(client: TestClient):
    """Verifies password rotation, 7-char FIN validation, family fin mesh CRUD, and IDOR protection."""
    user = register_test_user(client, "Cavidan Quliyev")

    # 1. Password update - wrong current password -> 400
    bad_pw_req = {
        "current_password": "WrongPassword!",
        "new_password": "NewStrongPassword2026!",
    }
    res_bad = client.put("/api/v1/user/profile/password", json=bad_pw_req, headers=user["headers"])
    assert res_bad.status_code == 400

    # 2. Password update - valid current password -> 200
    good_pw_req = {
        "current_password": user["password"],
        "new_password": "NewStrongPassword2026!",
    }
    res_good = client.put("/api/v1/user/profile/password", json=good_pw_req, headers=user["headers"])
    assert res_good.status_code == 200

    # 3. Login with new password
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": user["email"], "password": "NewStrongPassword2026!"},
    )
    assert login_res.status_code == 200

    # 4. Family FIN Mesh - Invalid FIN (< 7 chars) -> 422
    bad_fin = {"name_relation": "Qardaşım", "fin": "12345"}
    res_bad_fin = client.post("/api/v1/user/family-fins", json=bad_fin, headers=user["headers"])
    assert res_bad_fin.status_code == 422

    # 5. Family FIN Mesh - Valid FIN (7 chars) -> 201
    good_fin = {
        "name_relation": "Aygün Quliyeva (Həyat yoldaşı)",
        "fin": "7AY2026",
        "monthly_limit_usd": 300.0,
        "spent_usd": 45.0,
    }
    res_fin = client.post("/api/v1/user/family-fins", json=good_fin, headers=user["headers"])
    assert res_fin.status_code == 201
    fin_obj = res_fin.json()
    fin_id = fin_obj["id"]
    assert fin_obj["fin"] == "7AY2026"
    assert fin_obj["remaining_usd"] == 255.0

    # 6. List family FINs
    res_list = client.get("/api/v1/user/family-fins", headers=user["headers"])
    assert res_list.status_code == 200
    assert any(f["id"] == fin_id for f in res_list.json())

    # 7. IDOR: another user cannot delete
    other = register_test_user(client, "Eldar Rzayev")
    res_idor = client.delete(f"/api/v1/user/family-fins/{fin_id}", headers=other["headers"])
    assert res_idor.status_code == 404

    # 8. Delete family FIN
    res_del_fin = client.delete(f"/api/v1/user/family-fins/{fin_id}", headers=user["headers"])
    assert res_del_fin.status_code == 200


# ==============================================================================
# 5. Full Data Portability & Sovereignty Cycle (v5.0.0)
# ==============================================================================

def test_etap6_full_data_sovereignty_cycle(client: TestClient):
    """Verifies that Export bundles include stores, carriers, and family fins,
    Wipe completely purges them, and Import seamlessly restores them.
    """
    user = register_test_user(client, "Leyla Hacıyeva")

    # 1. Populate user data
    client.post(
        "/api/v1/user/stores",
        json={"name": "Hepsiburada TR", "domain_url": "https://hepsiburada.com", "country_code": "TR"},
        headers=user["headers"],
    )
    client.post(
        "/api/v1/user/carriers",
        json={"name": "Baku Ekspres", "origin_country": "TR", "rate_per_kg_usd": 3.10},
        headers=user["headers"],
    )
    client.post(
        "/api/v1/user/family-fins",
        json={"name_relation": "Anam", "fin": "5ANA260", "monthly_limit_usd": 300.0, "spent_usd": 0.0},
        headers=user["headers"],
    )
    client.post(
        "/api/v1/user/parcels",
        json={
            "tracking_number": f"PORT-{uuid.uuid4().hex[:6]}",
            "platform": "Trendyol",
            "carrier": "STAREX",
            "title": "Yazlıq don",
            "invoice_amount_usd": 50.0,
        },
        headers=user["headers"],
    )

    # 2. Export data (v5.0.0)
    export_res = client.get("/api/v1/user/export", headers=user["headers"])
    assert export_res.status_code == 200
    bundle = export_res.json()
    assert bundle["schema_version"] == "5.0.0"
    assert len(bundle["custom_stores"]) >= 1
    assert len(bundle["custom_carriers"]) >= 1
    assert len(bundle["family_fins"]) >= 1
    assert len(bundle["parcels"]) >= 1

    # 3. Wipe account data
    wipe_res = client.delete("/api/v1/user/account-data?confirm_wipe=true", headers=user["headers"])
    assert wipe_res.status_code == 200
    wipe_data = wipe_res.json()
    assert wipe_data["wiped_orders_count"] >= 1
    assert wipe_data["wiped_stores_count"] >= 1
    assert wipe_data["wiped_carriers_count"] >= 1
    assert wipe_data["wiped_family_fins_count"] >= 1

    # Verify data is wiped
    stores_after = client.get("/api/v1/user/stores", headers=user["headers"]).json()
    assert not any(s["name"] == "Hepsiburada TR" and not s["is_standard"] for s in stores_after)
    fins_after = client.get("/api/v1/user/family-fins", headers=user["headers"]).json()
    assert len(fins_after) == 0

    # 4. Import data back
    import_payload = {
        "schema_version": "5.0.0",
        "parcels": bundle["parcels"],
        "custom_stores": bundle["custom_stores"],
        "custom_carriers": bundle["custom_carriers"],
        "family_fins": bundle["family_fins"],
    }
    import_res = client.post("/api/v1/user/import", json=import_payload, headers=user["headers"])
    assert import_res.status_code == 200
    import_data = import_res.json()
    assert import_data["imported_count"] >= 1
    assert import_data["imported_stores_count"] >= 1
    assert import_data["imported_carriers_count"] >= 1
    assert import_data["imported_family_fins_count"] >= 1

    # Verify restored state
    fins_restored = client.get("/api/v1/user/family-fins", headers=user["headers"]).json()
    assert any(f["fin"] == "5ANA260" for f in fins_restored)
