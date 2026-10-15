"""PCS v4.0 — Flagship Autonomous Commerce, Compliance, Multi-FIN & Refund Intelligence Engines.

Includes:
1. CrossPlatformArbitrageEngine (True Landed Cost in Baku across Taobao, 1688, Trendyol, Temu, Amazon)
2. CustomsComplianceAndHazmatGuardian (IMEI fee calculator, RINN/AQTA restricted item blocker, IATA Hazmat flight router, commercial lot splitter)
3. FamilyFinMeshOrchestrator (Multi-FIN $300/month pool balancer & Same-Flight Collision detector)
4. AutonomousPriceDropAndDisputeAgent (30-day Temu/Trendyol price adjustment hunter & claim evidence generator)
5. FintechCardAndAlipayOptimizer (200 CNY Alipay 3% fee splitter & Azerbaijan bank MCC cashback router)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# Official CBAR reference rates (AZN)
CBAR_RATES: Dict[str, float] = {
    "AZN": 1.0000,
    "USD": 1.7000,
    "EUR": 1.8500,
    "TRY": 0.0485,
    "CNY": 0.2380,
    "RMB": 0.2380,
}

# Carrier per-kg base rates (USD) and average transit days to Baku (28 May)
CARRIER_BENCHMARKS: Dict[str, Dict[str, Tuple[float, int]]] = {
    "STAREX": {"TR": (3.80, 4), "CN": (7.50, 8), "US": (7.90, 10), "DE": (6.50, 9)},
    "LIMAK": {"TR": (3.50, 5), "CN": (7.20, 9), "US": (7.50, 11)},
    "CAMEX": {"CN": (7.00, 8), "US": (7.40, 10), "TR": (3.90, 5)},
    "DYNAMEX": {"TR": (3.70, 4), "CN": (7.30, 9), "US": (7.80, 11)},
}


# ============================================================================
# 1. CROSS-PLATFORM ARBITRAGE & TRUE LANDED COST ENGINE
# ============================================================================

@dataclass
class PlatformOffer:
    platform: str               # "Taobao", "1688", "Trendyol", "Temu", "Amazon"
    origin_country: str         # "CN", "TR", "US", "DIRECT_AZ"
    item_price: float
    currency: str               # "CNY", "TRY", "USD", "AZN"
    domestic_shipping: float = 0.0
    estimated_weight_kg: float = 0.5
    dimensions_cm: Optional[Tuple[float, float, float]] = None
    direct_to_baku_free_ship: bool = False


@dataclass
class LandedCostQuote:
    platform: str
    origin_country: str
    recommended_carrier: str
    item_cost_azn: float
    domestic_ship_azn: float
    payment_fee_azn: float
    international_cargo_azn: float
    customs_duty_azn: float
    cashback_saved_azn: float
    net_landed_cost_azn: float
    net_landed_cost_usd: float
    estimated_days: int
    billable_weight_kg: float
    is_best_value: bool = False
    is_fastest: bool = False


class CrossPlatformArbitrageEngine:
    """Computes True Landed Cost in Baku across global marketplaces and ranks the best option."""

    @staticmethod
    def compute_billable_weight(
        physical_kg: float, dimensions_cm: Optional[Tuple[float, float, float]] = None
    ) -> float:
        vol_kg = 0.0
        if dimensions_cm:
            l, w, h = dimensions_cm
            vol_kg = (l * w * h) / 6000.0
        return round(max(physical_kg, vol_kg, 0.10), 3)

    @classmethod
    def evaluate_offers(
        cls,
        offers: List[PlatformOffer],
        current_month_used_usd: float = 68.54,
        monthly_limit_usd: float = 300.0,
        cashback_rate: float = 0.05,
    ) -> List[LandedCostQuote]:
        quotes: List[LandedCostQuote] = []
        for off in offers:
            rate = CBAR_RATES.get(off.currency.upper(), 1.0)
            item_azn = round(off.item_price * rate, 2)
            dom_azn = round(off.domestic_shipping * rate, 2)
            bill_wt = cls.compute_billable_weight(off.estimated_weight_kg, off.dimensions_cm)

            # Alipay/Taobao >200 CNY 3% international card fee check
            pay_fee_azn = 0.0
            if off.platform.lower() in ("taobao", "1688") and off.item_price > 200.0:
                pay_fee_azn = round(item_azn * 0.03, 2)

            if off.direct_to_baku_free_ship or off.origin_country == "DIRECT_AZ":
                best_carrier = "TEMU_DIRECT"
                cargo_azn = 0.0
                est_days = 11
            else:
                best_carrier = "STAREX"
                best_usd = 9999.0
                est_days = 7
                for c_name, c_map in CARRIER_BENCHMARKS.items():
                    if off.origin_country.upper() in c_map:
                        per_kg_usd, days = c_map[off.origin_country.upper()]
                        cost_usd = round(bill_wt * per_kg_usd, 2)
                        if cost_usd < best_usd:
                            best_usd = cost_usd
                            best_carrier = c_name
                            est_days = days
                cargo_azn = round(best_usd * CBAR_RATES["USD"], 2)

            declaration_base_usd = round((item_azn + dom_azn + cargo_azn) / CBAR_RATES["USD"], 2)
            projected_total_usd = current_month_used_usd + declaration_base_usd
            duty_azn = 0.0
            if projected_total_usd > monthly_limit_usd:
                excess_usd = projected_total_usd - monthly_limit_usd
                excess_azn = excess_usd * CBAR_RATES["USD"]
                # Statutory 15% duty + 18% VAT on (base + duty) = 35.70% + 15 AZN fee
                duty_azn = round(excess_azn * 0.357 + 15.0, 2)

            cb_azn = round((item_azn + cargo_azn) * cashback_rate, 2)
            net_azn = round(item_azn + dom_azn + pay_fee_azn + cargo_azn + duty_azn - cb_azn, 2)
            net_usd = round(net_azn / CBAR_RATES["USD"], 2)

            quotes.append(
                LandedCostQuote(
                    platform=off.platform,
                    origin_country=off.origin_country,
                    recommended_carrier=best_carrier,
                    item_cost_azn=item_azn,
                    domestic_ship_azn=dom_azn,
                    payment_fee_azn=pay_fee_azn,
                    international_cargo_azn=cargo_azn,
                    customs_duty_azn=duty_azn,
                    cashback_saved_azn=cb_azn,
                    net_landed_cost_azn=net_azn,
                    net_landed_cost_usd=net_usd,
                    estimated_days=est_days,
                    billable_weight_kg=bill_wt,
                )
            )

        if quotes:
            quotes.sort(key=lambda q: q.net_landed_cost_azn)
            quotes[0].is_best_value = True
            fastest = min(quotes, key=lambda q: q.estimated_days)
            fastest.is_fastest = True
        return quotes


# ============================================================================
# 2. CUSTOMS COMPLIANCE, IMEI FEE & HAZMAT FLIGHT GUARDIAN
# ============================================================================

class RiskSeverity(str, Enum):
    CLEAR = "CLEAR"
    SPECIAL_FLIGHT_REQUIRED = "SPECIAL_FLIGHT_REQUIRED"
    IMEI_FEE_APPLICABLE = "IMEI_FEE_APPLICABLE"
    COMMERCIAL_LOT_WARNING = "COMMERCIAL_LOT_WARNING"
    RESTRICTED_PERMIT_REQUIRED = "RESTRICTED_PERMIT_REQUIRED"


@dataclass
class ComplianceReport:
    title: str
    severity: str
    allowed_standard_air: bool
    requires_special_hazmat_flight: bool
    imei_registration_fee_azn: float
    commercial_lot_risk: bool
    warnings: List[str] = field(default_factory=list)
    recommended_action: str = ""


class CustomsComplianceAndHazmatGuardian:
    """Detects restricted items (RINN/AQTA/DGK), calculates IMEI fees, and routes hazmat (liquid/battery) cargo."""

    RESTRICTED_KEYWORDS = [
        "walkie-talkie", "ratsiya", "baofeng", "dron", "drone", "fpv",
        "gizli kamera", "spy camera", "tazer", "elektroşok", "ov bıçağı",
        "külliyat", "sikkə", "toz", "aerosol", "sprey", "flammable",
    ]
    HAZMAT_BATTERY_LIQUID_KEYWORDS = [
        "powerbank", "power bank", "batareya", "battery", "li-ion", "充电宝",
        "parfüm", "ətir", "perfume", "losyon", "serum", "şampun", "sprey", "香水", "精华液",
    ]
    PHONE_IMEI_KEYWORDS = [
        "iphone", "samsung galaxy", "xiaomi redmi", "pixel", "smartfon", "smartphone", "智能手机",
    ]

    @classmethod
    def inspect_item(
        cls, title: str, quantity: int, unit_price_usd: float
    ) -> ComplianceReport:
        t = (title or "").lower()
        warnings: List[str] = []
        severity = RiskSeverity.CLEAR.value
        allowed_std = True
        hazmat_flight = False
        imei_fee_azn = 0.0
        comm_risk = False

        # 1. Restricted / Civil circulation permit check
        for kw in cls.RESTRICTED_KEYWORDS:
            if kw in t:
                severity = RiskSeverity.RESTRICTED_PERMIT_REQUIRED.value
                allowed_std = False
                warnings.append(
                    f"DİQQƏT: '{kw}' aşkarlandı — Mülki dövriyyəsi məhdudlaşdırılmış və ya xüsusi icazə (RİNN/DGK) tələb edən kateqoriya!"
                )

        # 2. Hazmat (Battery / Liquid / Perfume) check
        for kw in cls.HAZMAT_BATTERY_LIQUID_KEYWORDS:
            if kw in t:
                hazmat_flight = True
                if severity == RiskSeverity.CLEAR.value:
                    severity = RiskSeverity.SPECIAL_FLIGHT_REQUIRED.value
                warnings.append(
                    f"Maye/Batareya ('{kw}') aşkarlandı: Adi reyslə göndərilə bilməz! Yalnız həftəlik Xüsusi (Maye/Batareya) reysi seçilməlidir."
                )
                break

        # 3. Smartphone IMEI registration fee (Republic of Azerbaijan statutory tariffs)
        for kw in cls.PHONE_IMEI_KEYWORDS:
            if kw in t and "kılıf" not in t and "keys" not in t and "手机壳" not in t and "case" not in t:
                if unit_price_usd <= 100:
                    imei_fee_azn = 30.0
                elif unit_price_usd <= 200:
                    imei_fee_azn = 50.0
                elif unit_price_usd <= 400:
                    imei_fee_azn = 70.0
                elif unit_price_usd <= 700:
                    imei_fee_azn = 100.0
                else:
                    imei_fee_azn = 150.0
                if severity == RiskSeverity.CLEAR.value:
                    severity = RiskSeverity.IMEI_FEE_APPLICABLE.value
                warnings.append(
                    f"Mobil cihaz aşkarlandı: Bakıda əlavə {imei_fee_azn:.0f} AZN rəsmi IMEI qeydiyyat rüsumu (portal.rinn.az) ödəniləcək."
                )
                break

        # 4. Commercial lot threshold check (>3 identical items)
        if quantity >= 4:
            comm_risk = True
            if severity == RiskSeverity.CLEAR.value:
                severity = RiskSeverity.COMMERCIAL_LOT_WARNING.value
            warnings.append(
                f"Eyni məhsuldan {quantity} ədəd: DGK tərəfindən 'Kommersiya partiyası' sayıla bilər. Sifarişi 2 fərqli bağlamaya/FİN-ə bölmək tövsiyə olunur."
            )

        action = "Standart avto-bəyan üçün tam təhlükəsizdir."
        if severity == RiskSeverity.RESTRICTED_PERMIT_REQUIRED.value:
            action = "Sifarişi dayandırın və ya daşıyıcıdan yazılı təsdiq alın."
        elif hazmat_flight:
            action = "Daşıyıcıda 'Maye və Batareyalı məhsul' qutusunu işarələyin."
        elif comm_risk:
            action = "Miqdarı <=3 ədəd olmaqla 2 sifarişə bölün."

        return ComplianceReport(
            title=title,
            severity=severity,
            allowed_standard_air=allowed_std,
            requires_special_hazmat_flight=hazmat_flight,
            imei_registration_fee_azn=imei_fee_azn,
            commercial_lot_risk=comm_risk,
            warnings=warnings,
            recommended_action=action,
        )


# ============================================================================
# 3. MULTI-FIN FAMILY MESH & SAME-FLIGHT COLLISION GUARD
# ============================================================================

@dataclass
class FamilyMemberProfile:
    fin_code: str
    full_name: str
    phone: str
    starex_suite: str
    limak_suite: str
    used_usd_this_month: float = 0.0
    in_flight_usd: float = 0.0
    monthly_limit_usd: float = 300.0

    @property
    def available_usd(self) -> float:
        return round(max(0.0, self.monthly_limit_usd - self.used_usd_this_month - self.in_flight_usd), 2)


class FamilyFinMeshOrchestrator:
    """Routes incoming orders across family FIN profiles to guarantee $0 customs duty and zero flight collisions."""

    def __init__(self, members: List[FamilyMemberProfile]) -> None:
        self.members = members

    def select_optimal_profile(self, parcel_usd: float) -> Dict[str, Any]:
        # Sort members by highest available quota
        ranked = sorted(self.members, key=lambda m: m.available_usd, reverse=True)
        for member in ranked:
            if member.available_usd >= parcel_usd:
                return {
                    "status": "DUTY_FREE_MATCH",
                    "fin_code": member.fin_code,
                    "full_name": member.full_name,
                    "starex_suite": member.starex_suite,
                    "limak_suite": member.limak_suite,
                    "remaining_after_usd": round(member.available_usd - parcel_usd, 2),
                    "estimated_duty_azn": 0.0,
                }
        # Fallback if even the best member exceeds $300
        best = ranked[0]
        excess_usd = parcel_usd - best.available_usd
        duty_azn = round(excess_usd * CBAR_RATES["USD"] * 0.357 + 15.0, 2)
        return {
            "status": "DELAY_TO_NEXT_MONTH_RECOMMENDED",
            "fin_code": best.fin_code,
            "full_name": best.full_name,
            "starex_suite": best.starex_suite,
            "limak_suite": best.limak_suite,
            "remaining_after_usd": 0.0,
            "estimated_duty_azn": duty_azn,
        }


# ============================================================================
# 4. AUTONOMOUS PRICE-DROP REFUND HUNTER & FINTECH CARD OPTIMIZER
# ============================================================================

@dataclass
class PurchasedItemRecord:
    order_ref: str
    platform: str
    item_id: str
    title: str
    paid_unit_price: float
    current_live_price: float
    quantity: int
    currency: str
    order_date: date


class AutonomousPriceDropAndDisputeAgent:
    """Scans last 30 days of orders for Temu/Trendyol price drops and calculates claimable refunds."""

    @staticmethod
    def scan_price_adjustments(
        items: List[PurchasedItemRecord], today: Optional[date] = None
    ) -> Dict[str, Any]:
        ref_date = today or date(2026, 10, 15)
        eligible_claims: List[Dict[str, Any]] = []
        total_refund_azn = 0.0

        for it in items:
            days_elapsed = (ref_date - it.order_date).days
            if 0 <= days_elapsed <= 30 and it.current_live_price < it.paid_unit_price:
                diff_native = round((it.paid_unit_price - it.current_live_price) * it.quantity, 2)
                diff_azn = round(diff_native * CBAR_RATES.get(it.currency.upper(), 1.0), 2)
                total_refund_azn = round(total_refund_azn + diff_azn, 2)
                eligible_claims.append(
                    {
                        "order_ref": it.order_ref,
                        "platform": it.platform,
                        "item_id": it.item_id,
                        "title": it.title,
                        "days_since_order": days_elapsed,
                        "refund_native": diff_native,
                        "currency": it.currency,
                        "refund_azn": diff_azn,
                        "action_endpoint": f"https://www.temu.com/bgt_price_adjust.html?parent_order_sn={it.order_ref}",
                    }
                )

        return {
            "scanned_items": len(items),
            "eligible_claims_count": len(eligible_claims),
            "total_claimable_azn": total_refund_azn,
            "total_claimable_usd": round(total_refund_azn / CBAR_RATES["USD"], 2),
            "claims": eligible_claims,
        }


class FintechCardAndAlipayOptimizer:
    """Optimizes Taobao/Alipay <=200 CNY splits (saving 3% fee) and selects optimal AZ bank card."""

    @staticmethod
    def optimize_taobao_cart_split(item_prices_cny: List[float]) -> Dict[str, Any]:
        """Splits items into batches <= 200 CNY so Alipay waives the 3% international card surcharge."""
        total_cny = round(sum(item_prices_cny), 2)
        naive_fee_cny = round(total_cny * 0.03, 2) if total_cny > 200.0 else 0.0

        batches: List[List[float]] = []
        for price in sorted(item_prices_cny, reverse=True):
            placed = False
            for b in batches:
                if sum(b) + price <= 200.0:
                    b.append(price)
                    placed = True
                    break
            if not placed:
                batches.append([price])

        optimized_fee_cny = round(
            sum(sum(b) * 0.03 for b in batches if sum(b) > 200.0), 2
        )
        saved_cny = round(naive_fee_cny - optimized_fee_cny, 2)
        saved_azn = round(saved_cny * CBAR_RATES["CNY"], 2)

        return {
            "total_cny": total_cny,
            "batches": batches,
            "naive_fee_cny": naive_fee_cny,
            "optimized_fee_cny": optimized_fee_cny,
            "saved_cny": saved_cny,
            "saved_azn": saved_azn,
        }

    @staticmethod
    def select_best_bank_card(amount_azn: float, merchant_type: str = "ecommerce") -> Dict[str, Any]:
        """Selects the highest cashback Azerbaijan bank card for e-commerce and cargo payments."""
        # Cards: Birbank, ABB TamKart, Leobank, UCard
        rates = {
            "ecommerce": {
                "Birbank Cashback": 0.05,
                "ABB TamKart": 0.04,
                "Leobank": 0.03,
                "UCard": 0.02,
            },
            "cargo": {
                "ABB TamKart": 0.05,
                "Birbank Cashback": 0.03,
                "Leobank": 0.03,
                "UCard": 0.02,
            },
        }
        category_rates = rates.get(merchant_type.lower(), rates["ecommerce"])
        best_card, best_rate = max(category_rates.items(), key=lambda x: x[1])
        saved_azn = round(amount_azn * best_rate, 2)

        return {
            "amount_azn": amount_azn,
            "merchant_type": merchant_type,
            "recommended_card": best_card,
            "cashback_rate_pct": round(best_rate * 100, 1),
            "cashback_earned_azn": saved_azn,
            "all_card_quotes": {
                card: round(amount_azn * r, 2) for card, r in category_rates.items()
            },
        }


# ============================================================================
# 5. FLIGHT SCHEDULE ETA & SAME-FLIGHT CUSTOMS COLLISION GUARD
# ============================================================================

@dataclass
class FlightSchedule:
    carrier: str
    origin_country: str
    flight_days: List[int]      # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    cutoff_hour_utc: int        # Cutoff hour at foreign warehouse (UTC)
    transit_days_to_baku: int   # Flight + airport customs clearance days


FLIGHT_SCHEDULES: Dict[Tuple[str, str], FlightSchedule] = {
    ("STAREX", "TR"): FlightSchedule("STAREX", "TR", [2, 5], 14, 2),    # Wed, Sat (Avcılar)
    ("STAREX", "CN"): FlightSchedule("STAREX", "CN", [1, 4], 10, 4),    # Tue, Fri (Guangzhou)
    ("LIMAK", "TR"): FlightSchedule("LIMAK", "TR", [1, 4], 14, 2),      # Tue, Fri
    ("CAMEX", "CN"): FlightSchedule("CAMEX", "CN", [0, 3], 12, 4),      # Mon, Thu
    ("DYNAMEX", "TR"): FlightSchedule("DYNAMEX", "TR", [2, 6], 15, 2),   # Wed, Sun
}


class FlightETAPredictor:
    """Predicts precise flight departure, airport customs release, and local branch pickup ETA."""

    @classmethod
    def predict_pickup_eta(
        cls, carrier: str, origin_country: str, hub_checkin_dt: datetime
    ) -> Dict[str, Any]:
        key = (carrier.upper(), origin_country.upper())
        sched = FLIGHT_SCHEDULES.get(key, FlightSchedule(carrier, origin_country, [2, 5], 12, 3))

        # Determine next flight departure day
        current_weekday = hub_checkin_dt.weekday()
        days_ahead = None
        for d in sched.flight_days:
            diff = d - current_weekday
            if diff > 0 or (diff == 0 and hub_checkin_dt.hour < sched.cutoff_hour_utc):
                days_ahead = diff
                break
        if days_ahead is None:
            # Wrap to next week
            days_ahead = (sched.flight_days[0] + 7) - current_weekday

        flight_departure_date = (hub_checkin_dt + timedelta(days=days_ahead)).date()
        baku_arrival_date = flight_departure_date + timedelta(days=sched.transit_days_to_baku)
        pickup_ready_dt = datetime.combine(baku_arrival_date, datetime.min.time()).replace(
            hour=15, minute=0, tzinfo=hub_checkin_dt.tzinfo
        )

        return {
            "carrier": carrier.upper(),
            "origin_country": origin_country.upper(),
            "hub_checkin_date": hub_checkin_dt.date().isoformat(),
            "flight_departure_date": flight_departure_date.isoformat(),
            "baku_pickup_eta": pickup_ready_dt.isoformat(),
            "estimated_pickup_hour": "15:00 - 19:00",
            "total_transit_days": (baku_arrival_date - hub_checkin_dt.date()).days,
        }

    @classmethod
    def detect_same_flight_collision(
        cls, parcels: List[Dict[str, Any]], monthly_limit_usd: float = 300.0
    ) -> Dict[str, Any]:
        """Detects whether multiple parcels are slated for the same cargo flight breaching $300."""
        flight_groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
        for p in parcels:
            key = (p["carrier"].upper(), p["origin_country"].upper(), p.get("flight_departure_date", "DEFAULT"))
            flight_groups.setdefault(key, []).append(p)

        collisions: List[Dict[str, Any]] = []
        for (carrier, country, f_date), group in flight_groups.items():
            tot_usd = round(sum(p["declared_usd"] for p in group), 2)
            if tot_usd > monthly_limit_usd:
                excess = round(tot_usd - monthly_limit_usd, 2)
                duty_azn = round(excess * CBAR_RATES["USD"] * 0.357 + 15.0, 2)
                # Recommend holding back the second parcel to the subsequent flight
                hold_parcel = max(group, key=lambda x: x["declared_usd"])
                collisions.append(
                    {
                        "carrier": carrier,
                        "origin_country": country,
                        "flight_departure_date": f_date,
                        "parcels_count": len(group),
                        "total_declared_usd": tot_usd,
                        "excess_usd": excess,
                        "potential_duty_azn": duty_azn,
                        "recommended_action": f"Bağlama '{hold_parcel['order_ref']}' növbəti reysə saxlanmalıdır (Hold Dispatch).",
                        "held_parcel_order_ref": hold_parcel["order_ref"],
                    }
                )

        return {
            "has_collision": len(collisions) > 0,
            "collision_count": len(collisions),
            "collisions": collisions,
        }


# ============================================================================
# 6. WAREHOUSE WEIGHT ANOMALY & PHOTO-QC AUDITOR
# ============================================================================

CATEGORY_WEIGHT_BASELINES: Dict[str, Tuple[float, float]] = {
    "T-SHIRT": (0.15, 0.35),
    "JEANS": (0.45, 0.75),
    "JACKET": (0.70, 1.30),
    "SNEAKERS": (0.60, 1.10),
    "PHONE_ACCESSORIES": (0.05, 0.25),
    "KEYBOARD": (0.60, 1.10),
}


class WarehouseQCAuditor:
    """Audits carrier foreign warehouse recorded weight against product baseline to prevent overcharges."""

    @classmethod
    def audit_weight(
        cls,
        category: str,
        carrier_weight_kg: float,
        carrier_rate_usd_per_kg: float = 4.0,
    ) -> Dict[str, Any]:
        cat_key = category.upper().replace(" ", "_")
        min_wt, max_wt = CATEGORY_WEIGHT_BASELINES.get(cat_key, (0.20, 0.80))
        threshold_wt = round(max_wt * 1.35, 3)  # 35% above max expected

        is_anomaly = carrier_weight_kg > threshold_wt
        excess_wt = round(max(0.0, carrier_weight_kg - max_wt), 3) if is_anomaly else 0.0
        overcharge_usd = round(excess_wt * carrier_rate_usd_per_kg, 2)
        overcharge_azn = round(overcharge_usd * CBAR_RATES["USD"], 2)

        dispute_text = ""
        if is_anomaly:
            dispute_text = (
                f"Hörmətli müştəri xidmətləri, bağlamam üçün qeyd edilən {carrier_weight_kg:.2f} kq çəki "
                f"məhsulun standart etalon çəkisindən ({max_wt:.2f} kq) 35%-dən artıqdır. Xahiş edirik bağlamanı "
                f"tərəzidə yenidən çəkib foto-sübut təqdim edəsiniz (Re-weigh request)."
            )

        return {
            "category": category,
            "carrier_weight_kg": carrier_weight_kg,
            "expected_max_weight_kg": max_wt,
            "anomaly_detected": is_anomaly,
            "excess_weight_kg": excess_wt,
            "potential_overcharge_usd": overcharge_usd,
            "potential_overcharge_azn": overcharge_azn,
            "reweigh_dispute_recommended": is_anomaly,
            "dispute_letter_az": dispute_text,
        }


# ============================================================================
# 7. "28 MAY EKSPRES TƏHVİL" ROUTE & UNIFIED QR PASS ENGINE
# ============================================================================

BRANCH_LOCATIONS_28MAY: Dict[str, Dict[str, Any]] = {
    "STAREX_28MAY": {"name": "Starex 28 May", "lat": 40.3798, "lon": 49.8488, "address": "Dilarə Əliyeva 235"},
    "CAMEX_28MAY": {"name": "Camex 28 May", "lat": 40.3812, "lon": 49.8510, "address": "Süleyman Rəhimov 195"},
    "DYNAMEX_28MAY": {"name": "Dynamex 28 May", "lat": 40.3785, "lon": 49.8465, "address": "Fikrət Əmirov 12"},
    "LIMAK_28MAY": {"name": "Limak 28 May", "lat": 40.3820, "lon": 49.8475, "address": "Mirzəağa Əliyev 245"},
}


class PickupPassEngine:
    """Optimizes pedestrian pickup route across 28 May branches and generates a single unified QR pass."""

    @classmethod
    def generate_unified_pass(
        cls, ready_shipments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        stops: List[Dict[str, Any]] = []
        total_fee_azn = 0.0

        for s in ready_shipments:
            b_key = f"{s['carrier'].upper()}_28MAY"
            b_info = BRANCH_LOCATIONS_28MAY.get(b_key, {"name": f"{s['carrier']} 28 May", "address": "28 May yaxınlığı"})
            fee = round(s.get("delivery_fee_azn", 0.0), 2)
            total_fee_azn = round(total_fee_azn + fee, 2)
            stops.append(
                {
                    "carrier": s["carrier"].upper(),
                    "branch_name": b_info["name"],
                    "branch_address": b_info["address"],
                    "tracking_code": s["tracking_code"],
                    "customer_suite": s["customer_suite"],
                    "delivery_fee_azn": fee,
                    "barcode_data": f"{s['customer_suite']}:{s['tracking_code']}",
                }
            )

        # Estimate pedestrian walking time: ~300 meters per stop = ~4 minutes walking per stop
        walk_minutes = len(stops) * 4
        walk_meters = len(stops) * 320

        return {
            "pickup_hub": "28 May / Dəmiryol Vağzalı Qovşağı",
            "total_packages": len(stops),
            "total_delivery_fee_azn": total_fee_azn,
            "estimated_pedestrian_time_mins": walk_minutes,
            "estimated_pedestrian_distance_meters": walk_meters,
            "stops_sequence": stops,
            "cashier_qr_payload": f"PCS-PASS-28MAY:{len(stops)}PKGS:{total_fee_azn}AZN",
        }


# ============================================================================
# 8. PERSONAL DIGITAL INVENTORY, WARRANTY & RESALE GENERATOR
# ============================================================================

class InventoryResaleVault:
    """Stores delivered items, tracks warranties, and generates 1-click Tap.az / Lalafo listings."""

    @classmethod
    def generate_resale_listing(
        cls,
        title: str,
        landed_cost_azn: float,
        purchase_date_val: date,
        condition: str = "Yeni (İstifadə olunmayıb)",
        markup_pct: float = 0.20,
    ) -> Dict[str, Any]:
        suggested_price = round(landed_cost_azn * (1.0 + markup_pct), 2)
        profit_azn = round(suggested_price - landed_cost_azn, 2)

        # Standard 1-year warranty countdown
        warranty_expires = purchase_date_val + timedelta(days=365)
        days_left = max(0, (warranty_expires - date.today()).days)

        ad_text = (
            f"🏷️ Məhsul: {title}\n"
            f"✨ Vəziyyəti: {condition}\n"
            f"💰 Qiymət: {suggested_price:.2f} AZN (Orijinal maya dəyəri: {landed_cost_azn:.2f} AZN)\n"
            f"🛡️ Rəsmi Zəmanət müddəti: {days_left} gün qalır\n"
            f"📍 Təhvil: Bakı daxili (28 May və ya metro stansiyaları üzrə)\n"
            f"📦 Orijinal qablaşdırması ilə birgə verilir. Real alıcıya cüzi endirim mümkündür.\n"
            f"#elan #bakushopping #tapaz #lalafo"
        )

        return {
            "title": title,
            "landed_cost_azn": landed_cost_azn,
            "suggested_resale_price_azn": suggested_price,
            "profit_azn": profit_azn,
            "markup_percentage": round(markup_pct * 100, 1),
            "warranty_days_remaining": days_left,
            "ad_copy_az": ad_text,
        }


# ============================================================================
# 9. SELF-HEALING DOM SELECTOR REGISTRY
# ============================================================================

class SelfHealingDOM:
    """Maintains resilient selectors and auto-heals when carrier/customs DOM changes."""

    REGISTRY: Dict[str, Dict[str, str]] = {
        "starex": {
            "suite_code": "#customer-suite, .suite-badge, [data-field='suite']",
            "active_parcels": ".parcel-item, tr.shipment-row, [data-role='parcel']",
        },
        "trendyol": {
            "first_name": "input[name='firstName'], #name, [data-testid='first-name']",
            "last_name": "input[name='lastName'], #surname, [data-testid='last-name']",
            "address_line": "textarea[name='address'], #address-line-1, [data-testid='address-input']",
        },
    }

    @classmethod
    def resolve_selector(cls, platform: str, field_key: str, available_classes: List[str]) -> str:
        plat_selectors = cls.REGISTRY.get(platform.lower(), {})
        candidates = [c.strip() for c in plat_selectors.get(field_key, "").split(",") if c.strip()]

        for cand in candidates:
            clean_cls = cand.replace(".", "").replace("#", "").split("[")[0]
            if clean_cls in available_classes:
                return cand

        # Fallback to first available or synthesized selector
        return candidates[0] if candidates else f"[data-key='{field_key}']"