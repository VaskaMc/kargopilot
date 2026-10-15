"""Automated Verification Battery for PCS v4.0 Autonomous Commerce & Customs Intelligence OS."""

from __future__ import annotations

import unittest
from datetime import date

try:
    from app.pcs_v4_engines import (
        AutonomousPriceDropAndDisputeAgent,
        CrossPlatformArbitrageEngine,
        CustomsComplianceAndHazmatGuardian,
        FamilyFinMeshOrchestrator,
        FamilyMemberProfile,
        FintechCardAndAlipayOptimizer,
        FlightETAPredictor,
        InventoryResaleVault,
        PickupPassEngine,
        PlatformOffer,
        PurchasedItemRecord,
        RiskSeverity,
        SelfHealingDOM,
        WarehouseQCAuditor,
    )
except ImportError:
    from pcs_v4_engines import (
        AutonomousPriceDropAndDisputeAgent,
        CrossPlatformArbitrageEngine,
        CustomsComplianceAndHazmatGuardian,
        FamilyFinMeshOrchestrator,
        FamilyMemberProfile,
        FintechCardAndAlipayOptimizer,
        FlightETAPredictor,
        InventoryResaleVault,
        PickupPassEngine,
        PlatformOffer,
        PurchasedItemRecord,
        RiskSeverity,
        SelfHealingDOM,
        WarehouseQCAuditor,
    )


class TestPCSV4Innovations(unittest.TestCase):
    def test_01_cross_platform_arbitrage_landed_cost(self) -> None:
        """Verifies True Landed Cost comparison across 1688, Taobao, Trendyol, and Temu Direct."""
        offers = [
            PlatformOffer(
                platform="1688",
                origin_country="CN",
                item_price=160.0,
                currency="CNY",
                domestic_shipping=10.0,
                estimated_weight_kg=0.80,
            ),
            PlatformOffer(
                platform="Trendyol",
                origin_country="TR",
                item_price=1450.0,
                currency="TRY",
                domestic_shipping=0.0,
                estimated_weight_kg=0.80,
            ),
            PlatformOffer(
                platform="Temu",
                origin_country="DIRECT_AZ",
                item_price=64.0,
                currency="AZN",
                estimated_weight_kg=0.80,
                direct_to_baku_free_ship=True,
            ),
        ]
        quotes = CrossPlatformArbitrageEngine.evaluate_offers(offers, current_month_used_usd=68.54)
        self.assertEqual(len(quotes), 3)
        self.assertTrue(quotes[0].is_best_value)
        # 1688 item is 170 CNY (~40.46 AZN) + Camex CN 0.8kg ($5.60 = 9.52 AZN) - 5% cashback = ~47.48 AZN (cheapest!)
        self.assertEqual(quotes[0].platform, "1688")
        self.assertEqual(quotes[0].recommended_carrier, "CAMEX")
        self.assertLess(quotes[0].net_landed_cost_azn, quotes[1].net_landed_cost_azn)

    def test_02_compliance_imei_hazmat_and_commercial_lot_guardian(self) -> None:
        """Verifies restricted item detection, liquid/battery special flight routing, and IMEI fee calculation."""
        # 1. Restricted radio/drone item
        r_drone = CustomsComplianceAndHazmatGuardian.inspect_item("Baofeng UV-5R Walkie-Talkie Ratsiya", 1, 25.0)
        self.assertEqual(r_drone.severity, RiskSeverity.RESTRICTED_PERMIT_REQUIRED.value)
        self.assertFalse(r_drone.allowed_standard_air)

        # 2. Powerbank / Perfume Hazmat routing
        r_pb = CustomsComplianceAndHazmatGuardian.inspect_item("Anker 20000mAh Powerbank 充电宝", 1, 35.0)
        self.assertTrue(r_pb.requires_special_hazmat_flight)
        self.assertEqual(r_pb.severity, RiskSeverity.SPECIAL_FLIGHT_REQUIRED.value)

        # 3. Smartphone IMEI fee + commercial lot (>3 units)
        r_phone = CustomsComplianceAndHazmatGuardian.inspect_item("Xiaomi Redmi Note 14 Smartphone", 1, 250.0)
        self.assertEqual(r_phone.imei_registration_fee_azn, 70.0)

        r_lot = CustomsComplianceAndHazmatGuardian.inspect_item("Cosmetic Face Serum 30ml", 5, 8.0)
        self.assertTrue(r_lot.commercial_lot_risk)

    def test_03_family_fin_mesh_orchestrator(self) -> None:
        """Verifies automatic routing to a secondary family member FIN when primary FIN nears $300."""
        mesh = FamilyFinMeshOrchestrator(
            [
                FamilyMemberProfile(
                    fin_code="5XY991A",
                    full_name="Vasif Məcidli",
                    phone="994501234567",
                    starex_suite="ST123456",
                    limak_suite="LMX99999",
                    used_usd_this_month=265.0,
                    in_flight_usd=15.0,
                ),
                FamilyMemberProfile(
                    fin_code="7AB442C",
                    full_name="Ailə Üzvü #2",
                    phone="994501112233",
                    starex_suite="ST099120",
                    limak_suite="LMX88412",
                    used_usd_this_month=40.0,
                    in_flight_usd=0.0,
                ),
            ]
        )
        # New $85 USD parcel would breach Vasif's remaining $20 quota, so mesh selects Family Member #2 ($260 free)
        allocation = mesh.select_optimal_profile(parcel_usd=85.0)
        self.assertEqual(allocation["status"], "DUTY_FREE_MATCH")
        self.assertEqual(allocation["fin_code"], "7AB442C")
        self.assertEqual(allocation["estimated_duty_azn"], 0.0)
        self.assertEqual(allocation["remaining_after_usd"], 175.0)

    def test_04_price_drop_refund_hunter(self) -> None:
        """Verifies 30-day price adjustment scanning across recent orders."""
        items = [
            PurchasedItemRecord(
                order_ref="PO-014-10523162706552716",
                platform="Temu",
                item_id="IT-01",
                title="Wireless Mechanical Keyboard",
                paid_unit_price=45.00,
                current_live_price=32.50,
                quantity=1,
                currency="AZN",
                order_date=date(2026, 10, 4),
            ),
            PurchasedItemRecord(
                order_ref="PO-014-10523162706552716",
                platform="Temu",
                item_id="IT-02",
                title="USB-C Hub 8-in-1",
                paid_unit_price=19.00,
                current_live_price=14.00,
                quantity=2,
                currency="AZN",
                order_date=date(2026, 10, 4),
            ),
        ]
        res = AutonomousPriceDropAndDisputeAgent.scan_price_adjustments(items, today=date(2026, 10, 15))
        self.assertEqual(res["eligible_claims_count"], 2)
        self.assertEqual(res["total_claimable_azn"], 22.50)

    def test_05_alipay_200_cny_fee_splitter(self) -> None:
        """Verifies that splitting a 360 CNY Taobao cart into <=200 CNY batches eliminates the 3% Alipay fee."""
        split = FintechCardAndAlipayOptimizer.optimize_taobao_cart_split([140.0, 120.0, 60.0, 40.0])
        self.assertEqual(split["total_cny"], 360.0)
        self.assertEqual(split["naive_fee_cny"], 10.80)
        self.assertEqual(split["optimized_fee_cny"], 0.0)
        self.assertEqual(split["saved_cny"], 10.80)
        self.assertGreater(split["saved_azn"], 2.50)


    def test_06_flight_schedule_eta_prediction(self) -> None:
        """Verifies flight schedule ETA calculation from warehouse arrival to 28 May pickup."""
        from datetime import datetime, timezone
        hub_dt = datetime(2026, 10, 15, 11, 0, 0, tzinfo=timezone.utc)  # Thursday 11:00 UTC
        eta = FlightETAPredictor.predict_pickup_eta("STAREX", "TR", hub_dt)
        self.assertEqual(eta["carrier"], "STAREX")
        self.assertEqual(eta["origin_country"], "TR")
        self.assertIn("baku_pickup_eta", eta)
        self.assertGreater(eta["total_transit_days"], 0)

    def test_07_same_flight_customs_collision_detection(self) -> None:
        """Verifies detection of multiple parcels converging on the same cargo flight breaching $300."""
        parcels = [
            {"carrier": "STAREX", "origin_country": "TR", "flight_departure_date": "2026-10-17", "declared_usd": 180.0, "order_ref": "TY-01"},
            {"carrier": "STAREX", "origin_country": "TR", "flight_departure_date": "2026-10-17", "declared_usd": 160.0, "order_ref": "TY-02"},
        ]
        res = FlightETAPredictor.detect_same_flight_collision(parcels, monthly_limit_usd=300.0)
        self.assertTrue(res["has_collision"])
        self.assertEqual(res["collision_count"], 1)
        self.assertGreater(res["collisions"][0]["potential_duty_azn"], 0.0)
        self.assertEqual(res["collisions"][0]["held_parcel_order_ref"], "TY-01")

    def test_08_warehouse_weight_anomaly_and_reweigh_dispute(self) -> None:
        """Verifies weight anomaly alert when carrier weight exceeds category baseline by >35%."""
        # T-Shirt expected 0.15-0.35kg; carrier logged 1.25kg!
        audit = WarehouseQCAuditor.audit_weight(category="T-SHIRT", carrier_weight_kg=1.25, carrier_rate_usd_per_kg=3.80)
        self.assertTrue(audit["anomaly_detected"])
        self.assertTrue(audit["reweigh_dispute_recommended"])
        self.assertGreater(audit["potential_overcharge_usd"], 3.0)
        self.assertIn("Re-weigh request", audit["dispute_letter_az"])

    def test_09_pickup_pass_28may_route_optimization(self) -> None:
        """Verifies 28 May pedestrian pickup route and unified QR pass generation."""
        ready_shipments = [
            {"carrier": "STAREX", "tracking_code": "STRAZ838434852456", "customer_suite": "ST123456", "delivery_fee_azn": 4.50},
            {"carrier": "CAMEX", "tracking_code": "CAM982144", "customer_suite": "CAM-11111", "delivery_fee_azn": 5.20},
        ]
        pass_res = PickupPassEngine.generate_unified_pass(ready_shipments)
        self.assertEqual(pass_res["total_packages"], 2)
        self.assertEqual(pass_res["total_delivery_fee_azn"], 9.70)
        self.assertGreater(pass_res["estimated_pedestrian_time_mins"], 0)
        self.assertIn("PCS-PASS-28MAY", pass_res["cashier_qr_payload"])

    def test_10_inventory_resale_vault_and_ad_generator(self) -> None:
        """Verifies digital inventory storage, warranty calculation, and 1-click Tap.az listing generation."""
        ad = InventoryResaleVault.generate_resale_listing(
            title="Mechanical Gaming Keyboard RGB",
            landed_cost_azn=45.0,
            purchase_date_val=date(2026, 10, 4),
            condition="Yeni",
            markup_pct=0.20,
        )
        self.assertEqual(ad["suggested_resale_price_azn"], 54.00)
        self.assertEqual(ad["profit_azn"], 9.00)
        self.assertGreater(ad["warranty_days_remaining"], 300)
        self.assertIn("54.00 AZN", ad["ad_copy_az"])
        self.assertIn("#tapaz", ad["ad_copy_az"])

    def test_11_self_healing_dom_selector_resolution(self) -> None:
        """Verifies self-healing selector resolution and heuristic fallback."""
        sel = SelfHealingDOM.resolve_selector(
            platform="starex",
            field_key="suite_code",
            available_classes=["suite-badge", "unrelated-div"],
        )
        self.assertIn("suite-badge", sel)

    def test_12_bank_mcc_card_cashback_optimizer(self) -> None:
        """Verifies bank MCC cashback optimization for e-commerce vs cargo payments."""
        rec_ecom = FintechCardAndAlipayOptimizer.select_best_bank_card(100.0, merchant_type="ecommerce")
        self.assertEqual(rec_ecom["recommended_card"], "Birbank Cashback")
        self.assertEqual(rec_ecom["cashback_earned_azn"], 5.0)

        rec_cargo = FintechCardAndAlipayOptimizer.select_best_bank_card(50.0, merchant_type="cargo")
        self.assertEqual(rec_cargo["recommended_card"], "ABB TamKart")
        self.assertEqual(rec_cargo["cashback_earned_azn"], 2.50)


if __name__ == "__main__":
    unittest.main(verbosity=2)