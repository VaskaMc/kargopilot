"""PCS v3.5 Dynamic Multi-Carrier Tariff Comparison and Rate Optimizer Engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class CarrierRateQuote(BaseModel):
    carrier: str
    origin_country: str
    weight_kg: float
    delivery_fee_usd: float
    delivery_fee_azn: float
    estimated_days: str
    is_cheapest: bool = False
    savings_vs_max_azn: float = 0.0
    liquid_supported: bool = True
    battery_supported: bool = True
    pickup_branches_count: int = 15
    branch_notes: str = "Bakı (28 May, Gənclik, Əhmədli, Xalqlar) və regionlar"


# Official 2026 tariff base (USD) for Azerbaijani forwarders
# Tier format: list of (max_weight, flat_fee_usd, rate_per_kg_usd)
TARIFF_SCHEDULES: Dict[str, Dict[str, List[Tuple[float, float, float]]]] = {
    "STAREX": {
        "TR": [(0.1, 1.00, 0.0), (0.25, 2.00, 0.0), (0.5, 3.00, 0.0), (0.7, 3.90, 0.0), (1.0, 4.50, 0.0), (999.0, 0.0, 4.50)],
        "CN": [(0.1, 2.50, 0.0), (0.25, 4.50, 0.0), (0.5, 6.50, 0.0), (1.0, 9.50, 0.0), (999.0, 0.0, 9.50)],
        "US": [(0.1, 1.90, 0.0), (0.25, 3.50, 0.0), (0.5, 5.00, 0.0), (1.0, 7.90, 0.0), (999.0, 0.0, 7.50)],
        "DE": [(0.1, 2.00, 0.0), (0.25, 3.50, 0.0), (0.5, 5.00, 0.0), (1.0, 8.00, 0.0), (999.0, 0.0, 8.00)],
    },
    "CAMEX": {
        "TR": [(0.1, 1.20, 0.0), (0.25, 2.20, 0.0), (0.5, 3.20, 0.0), (0.7, 4.00, 0.0), (1.0, 4.70, 0.0), (999.0, 0.0, 4.70)],
        "CN": [(0.1, 3.00, 0.0), (0.25, 5.00, 0.0), (0.5, 7.00, 0.0), (1.0, 10.00, 0.0), (999.0, 0.0, 10.00)],
        "US": [(0.1, 2.00, 0.0), (0.25, 3.80, 0.0), (0.5, 5.50, 0.0), (1.0, 8.20, 0.0), (999.0, 0.0, 7.90)],
        "DE": [(0.1, 2.20, 0.0), (0.25, 3.80, 0.0), (0.5, 5.50, 0.0), (1.0, 8.50, 0.0), (999.0, 0.0, 8.50)],
    },
    "DYNAMEX": {
        "TR": [(0.1, 0.99, 0.0), (0.25, 1.99, 0.0), (0.5, 2.99, 0.0), (0.7, 3.80, 0.0), (1.0, 4.40, 0.0), (999.0, 0.0, 4.40)],
        "CN": [(0.1, 2.90, 0.0), (0.25, 4.90, 0.0), (0.5, 6.90, 0.0), (1.0, 9.90, 0.0), (999.0, 0.0, 9.90)],
        "US": [(0.1, 1.80, 0.0), (0.25, 3.40, 0.0), (0.5, 4.90, 0.0), (1.0, 7.70, 0.0), (999.0, 0.0, 7.40)],
    },
    "LIMAK": {
        "TR": [(0.1, 1.10, 0.0), (0.25, 2.10, 0.0), (0.5, 3.10, 0.0), (0.7, 4.00, 0.0), (1.0, 4.60, 0.0), (999.0, 0.0, 4.60)],
        "US": [(0.1, 2.00, 0.0), (0.25, 3.60, 0.0), (0.5, 5.20, 0.0), (1.0, 8.00, 0.0), (999.0, 0.0, 7.80)],
    },
}

CARRIER_METADATA: Dict[str, Dict[str, Any]] = {
    "STAREX": {"days": "3-5 iş günü", "branches": 22, "liquid": True, "battery": True},
    "CAMEX": {"days": "4-6 iş günü", "branches": 18, "liquid": True, "battery": False},
    "DYNAMEX": {"days": "3-5 iş günü", "branches": 20, "liquid": True, "battery": True},
    "LIMAK": {"days": "3-6 iş günü", "branches": 16, "liquid": False, "battery": False},
}


class DynamicTariffEngine:
    """Calculates, compares and ranks freight forwarding costs across all carriers."""

    @classmethod
    def calculate_volumetric_weight(cls, length_cm: float, width_cm: float, height_cm: float, divisor: float = 6000.0) -> float:
        if length_cm <= 0 or width_cm <= 0 or height_cm <= 0:
            return 0.0
        return round((length_cm * width_cm * height_cm) / divisor, 3)

    @classmethod
    def calculate_single_carrier_fee(cls, carrier: str, country: str, weight_kg: float) -> float:
        carrier = carrier.upper()
        country = country.upper()
        if weight_kg <= 0:
            return 0.0

        sched = TARIFF_SCHEDULES.get(carrier, {}).get(country)
        if not sched:
            # Fallback default estimate
            return round(weight_kg * 5.0, 2)

        for max_w, flat_fee, per_kg in sched:
            if weight_kg <= max_w:
                if flat_fee > 0:
                    return flat_fee
                return round(weight_kg * per_kg, 2)
        # Exceeds highest tier: use last per_kg
        return round(weight_kg * sched[-1][2], 2)

    @classmethod
    def compare_all_carriers(
        cls,
        country: str,
        weight_kg: float,
        usd_to_azn: float = 1.70,
        is_liquid: bool = False,
    ) -> List[CarrierRateQuote]:
        country = country.upper()
        weight_kg = max(0.01, round(weight_kg, 3))
        quotes: List[CarrierRateQuote] = []

        for carrier in ("STAREX", "DYNAMEX", "CAMEX", "LIMAK"):
            if country not in TARIFF_SCHEDULES.get(carrier, {}):
                continue

            fee_usd = cls.calculate_single_carrier_fee(carrier, country, weight_kg)
            # Liquid surcharge if applicable
            if is_liquid and carrier in ("CAMEX", "STAREX"):
                fee_usd += 1.0  # standard $1.00 liquid packaging surcharge
            fee_azn = round(fee_usd * usd_to_azn, 2)
            meta = CARRIER_METADATA.get(carrier, {})

            quotes.append(
                CarrierRateQuote(
                    carrier=carrier,
                    origin_country=country,
                    weight_kg=weight_kg,
                    delivery_fee_usd=fee_usd,
                    delivery_fee_azn=fee_azn,
                    estimated_days=meta.get("days", "3-5 iş günü"),
                    is_cheapest=False,
                    liquid_supported=meta.get("liquid", True),
                    battery_supported=meta.get("battery", True),
                    pickup_branches_count=meta.get("branches", 15),
                )
            )

        if not quotes:
            return []

        # Sort by price ascending
        quotes.sort(key=lambda q: q.delivery_fee_azn)
        quotes[0].is_cheapest = True
        max_azn = max(q.delivery_fee_azn for q in quotes)

        for q in quotes:
            q.savings_vs_max_azn = round(max_azn - q.delivery_fee_azn, 2)

        return quotes
