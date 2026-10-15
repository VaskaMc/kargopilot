"""PCS Smart Package Consolidation & Quota Split Optimizer Engine.

Designed for Azerbaijani cross-border ecommerce shoppers importing via:
- Turkish forwarders (Trendyol, Hepsiburada, Zara -> Starex, Camex, Dynamex, Limak)
- Chinese forwarders (Taobao, 1688, Temu -> Starex, Camex, Limak)
- US & EU forwarders (Amazon US/DE, eBay, 6pm -> Starex, Camex, Dynamex, Limak)

Regulatory Compliance:
- Republic of Azerbaijan Cabinet of Ministers Resolution No. 305 (300 USD duty-free quota per calendar month).
- State Customs Committee of Azerbaijan (DGK SmartCustoms / e-Customs portal).
- Freight Forwarder Volumetric Weight standard: (L x W x H in cm) / 6000.
"""

from __future__ import annotations

import itertools
import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

# Constants based on CBAR exchange rates and Resolution No. 305
MONTHLY_CUSTOMS_QUOTA_USD: float = 300.0
DEFAULT_USD_TO_AZN_RATE: float = 1.7000
DEFAULT_TRY_TO_AZN_RATE: float = 0.0485
DEFAULT_CNY_TO_AZN_RATE: float = 0.2380
DEFAULT_EUR_TO_AZN_RATE: float = 1.8500

CUSTOMS_TARIFF_RATE: float = 0.15      # 15% customs tariff duty on excess
CUSTOMS_VAT_RATE: float = 0.18         # 18% VAT applied on (excess + tariff duty)
CUSTOMS_CLEARANCE_FEE_AZN: float = 15.0  # 15 AZN electronic customs declaration fee

DEFAULT_VOLUMETRIC_DIVISOR: float = 6000.0
DEFAULT_REPACK_SERVICE_FEE_USD: float = 1.00
DEFAULT_CONSOLIDATION_FEE_USD: float = 0.50


# Official 2026 Carrier Tariff Schedules (USD)
# Format: (max_weight_kg, flat_fee_usd, per_kg_rate_usd)
CARRIER_TARIFF_TIERS: Dict[str, Dict[str, List[Tuple[float, float, float]]]] = {
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


class ItemCategory(str, Enum):
    APPAREL = "APPAREL"            # Geyim və toxuma (High compression: 55%)
    FOOTWEAR = "FOOTWEAR"          # Ayaqqabı (Shoebox removal: 45%)
    BAGS = "BAGS"                  # Çantalar (Stuffing removal: 40%)
    PLUSH_TOYS = "PLUSH_TOYS"      # Yumşaq oyuncaqlar (Vacuum compression: 65%)
    COSMETICS = "COSMETICS"        # Kosmetika və qulluq (Outer box discard: 20%)
    ELECTRONICS = "ELECTRONICS"    # Elektronika (Void trim only: 12%)
    FRAGILE = "FRAGILE"            # Şüşə, keramika (DO NOT REPACK: 0%)
    GENERAL = "GENERAL"            # Ümumi qarışıq mallar (Standard: 25%)
    DOCUMENTS = "DOCUMENTS"        # Sənədlər (Standard flat: 10%)


CATEGORY_COMPRESSION_FACTORS: Dict[ItemCategory, float] = {
    ItemCategory.APPAREL: 0.55,
    ItemCategory.FOOTWEAR: 0.45,
    ItemCategory.BAGS: 0.40,
    ItemCategory.PLUSH_TOYS: 0.65,
    ItemCategory.COSMETICS: 0.20,
    ItemCategory.ELECTRONICS: 0.12,
    ItemCategory.FRAGILE: 0.00,
    ItemCategory.GENERAL: 0.25,
    ItemCategory.DOCUMENTS: 0.10,
}


class RepackRecommendation(str, Enum):
    STRONG_RECOMMEND = "STRONG_RECOMMEND"      # Net savings >= $1.50 USD
    OPTIONAL = "OPTIONAL"                      # Net savings > $0.00 USD
    NOT_RECOMMENDED = "NOT_RECOMMENDED"        # Net savings <= $0.00 USD
    PROHIBITED_FRAGILE = "PROHIBITED_FRAGILE"  # Risk of breakage outstrips savings


class StrategyType(str, Enum):
    CONSOLIDATE_IMMEDIATELY = "CONSOLIDATE_IMMEDIATELY"
    DELAY_BUNDLE_TO_NEXT_MONTH = "DELAY_BUNDLE_TO_NEXT_MONTH"
    SPLIT_SUBSET_NOW_AND_DELAY_REST = "SPLIT_SUBSET_NOW_AND_DELAY_REST"
    ALLOCATE_TO_SECONDARY_FIN = "ALLOCATE_TO_SECONDARY_FIN"
    SHIP_INDIVIDUALLY_NO_BUNDLE = "SHIP_INDIVIDUALLY_NO_BUNDLE"


class CollisionSeverity(str, Enum):
    SAFE = "SAFE"
    WARNING_NEAR_LIMIT = "WARNING_NEAR_LIMIT"
    CRITICAL_COLLISION_TAX_EXCEEDS_SAVINGS = "CRITICAL_COLLISION_TAX_EXCEEDS_SAVINGS"


class FINProfile(BaseModel):
    fin: str
    owner_name: str
    relation: str = "Self"
    used_quota_usd: float = 0.0

    @property
    def remaining_quota_usd(self) -> float:
        return max(0.0, round(MONTHLY_CUSTOMS_QUOTA_USD - self.used_quota_usd, 2))


class PackageItem(BaseModel):
    id: str
    order_ref: str
    platform: str = Field(..., description="Trendyol, Taobao, Temu, Amazon")
    origin_country: str = Field(..., description="TR, CN, US, DE")
    seller_name: str = "Store"
    title: str = "Item"
    category: ItemCategory = ItemCategory.GENERAL
    invoice_amount: float
    currency: str = "USD"
    invoice_amount_usd: float = 0.0
    invoice_amount_azn: float = 0.0
    physical_weight_kg: float
    length_cm: Optional[float] = None
    width_cm: Optional[float] = None
    height_cm: Optional[float] = None
    is_fragile: bool = False
    is_liquid: bool = False
    is_battery: bool = False
    warehouse_arrival_date: Optional[datetime] = None
    free_storage_days_remaining: int = 15
    assigned_fin: Optional[str] = None
    preferred_carrier: Optional[str] = None


class VolumetricRepackAssessment(BaseModel):
    package_id: str
    category: ItemCategory
    physical_weight_kg: float
    initial_dimensions_cm: Tuple[float, float, float]
    initial_volume_cm3: float
    initial_volumetric_weight_kg: float
    initial_billable_weight_kg: float
    initial_shipping_cost_usd: float
    repacked_dimensions_cm: Tuple[float, float, float]
    repacked_volume_cm3: float
    repacked_volumetric_weight_kg: float
    repacked_billable_weight_kg: float
    repacked_shipping_cost_usd: float
    volume_reduction_pct: float
    weight_reduction_kg: float
    repack_fee_usd: float
    gross_shipping_saved_usd: float
    net_financial_saving_usd: float
    net_financial_saving_azn: float
    roi_multiplier: float
    recommendation: RepackRecommendation
    repack_technique: str
    recommendation_reason: str


class ConsolidationBundle(BaseModel):
    bundle_id: str
    carrier: str
    origin_country: str
    packages: List[PackageItem]
    package_count: int
    total_physical_weight_kg: float
    total_volumetric_weight_kg: float
    effective_billable_weight_kg: float
    total_goods_value_usd: float
    total_goods_value_azn: float
    standalone_costs_usd: Dict[str, float]
    sum_standalone_shipping_usd: float
    consolidated_shipping_usd: float
    bundling_fee_usd: float
    gross_shipping_savings_usd: float
    net_shipping_savings_usd: float
    net_shipping_savings_azn: float
    savings_percentage: float
    assigned_fin: str = "6XXXXXX"
    scheduled_dispatch_date: Optional[datetime] = None
    dispatch_month: str = "2026-10"


class CustomsQuotaImpact(BaseModel):
    fin: str
    calendar_month: str
    current_used_usd: float
    current_remaining_usd: float
    bundle_cif_usd: float
    projected_month_total_usd: float
    quota_limit_usd: float = MONTHLY_CUSTOMS_QUOTA_USD
    is_quota_exceeded: bool
    excess_amount_usd: float
    excess_amount_azn: float
    customs_duty_azn: float
    customs_vat_azn: float
    customs_fee_azn: float
    total_customs_cost_azn: float
    total_customs_cost_usd: float
    shipping_savings_usd: float
    net_economic_benefit_usd: float
    collision_detected: bool
    collision_level: CollisionSeverity
    explanation: str


class SplitOrDelayPlan(BaseModel):
    strategy_type: StrategyType
    recommended_action: str
    primary_bundle: Optional[ConsolidationBundle] = None
    delayed_bundle: Optional[ConsolidationBundle] = None
    secondary_fin_bundle: Optional[ConsolidationBundle] = None
    immediate_dispatch_package_ids: List[str] = Field(default_factory=list)
    delayed_dispatch_package_ids: List[str] = Field(default_factory=list)
    delay_days: int = 0
    target_dispatch_date: Optional[datetime] = None
    customs_duty_prevented_usd: float = 0.0
    net_total_savings_usd: float = 0.0
    net_total_savings_azn: float = 0.0
    step_by_step_instructions: List[str] = Field(default_factory=list)


class ConsolidationOptimizationReport(BaseModel):
    carrier: str
    origin_country: str
    generated_at: datetime
    input_packages_count: int
    volumetric_analyses: List[VolumetricRepackAssessment]
    recommended_bundle: ConsolidationBundle
    quota_impact: CustomsQuotaImpact
    best_execution_plan: SplitOrDelayPlan
    overall_net_savings_usd: float = 0.0
    overall_net_savings_azn: float = 0.0
    summary_verdict: str



class SmartConsolidationEngine:
    """Core mathematical engine for logistics consolidation and quota optimization."""

    @classmethod
    def convert_currency_to_usd_azn(
        cls,
        amount: float,
        currency: str,
        usd_to_azn: float = DEFAULT_USD_TO_AZN_RATE,
        try_to_azn: float = DEFAULT_TRY_TO_AZN_RATE,
        cny_to_azn: float = DEFAULT_CNY_TO_AZN_RATE,
        eur_to_azn: float = DEFAULT_EUR_TO_AZN_RATE,
    ) -> Tuple[float, float]:
        """Converts foreign order invoice amount to USD and AZN via CBAR peg."""
        curr = currency.upper().strip()
        if curr in ("USD", "$"):
            amt_usd = round(amount, 2)
            amt_azn = round(amt_usd * usd_to_azn, 2)
        elif curr in ("TRY", "TL"):
            amt_azn = round(amount * try_to_azn, 2)
            amt_usd = round(amt_azn / usd_to_azn, 2)
        elif curr in ("CNY", "RMB"):
            amt_azn = round(amount * cny_to_azn, 2)
            amt_usd = round(amt_azn / usd_to_azn, 2)
        elif curr in ("EUR", "€"):
            amt_azn = round(amount * eur_to_azn, 2)
            amt_usd = round(amt_azn / usd_to_azn, 2)
        elif curr in ("AZN", "₼"):
            amt_azn = round(amount, 2)
            amt_usd = round(amt_azn / usd_to_azn, 2)
        else:
            # Default treat as USD
            amt_usd = round(amount, 2)
            amt_azn = round(amt_usd * usd_to_azn, 2)
        return amt_usd, amt_azn

    @classmethod
    def calculate_volumetric_weight(
        cls,
        length_cm: float,
        width_cm: float,
        height_cm: float,
        divisor: float = DEFAULT_VOLUMETRIC_DIVISOR,
    ) -> float:
        """Calculates IATA air cargo volumetric weight: (L x W x H) / divisor."""
        if length_cm <= 0 or width_cm <= 0 or height_cm <= 0:
            return 0.0
        return round((length_cm * width_cm * height_cm) / divisor, 3)

    @classmethod
    def determine_billable_weight(
        cls,
        physical_weight_kg: float,
        volumetric_weight_kg: float,
        side_max_cm: float = 0.0,
    ) -> float:
        """Determines billable weight according to carrier billing thresholds."""
        phys = max(0.01, round(physical_weight_kg, 3))
        vol = max(0.0, round(volumetric_weight_kg, 3))

        # Azerbaijani forwarders rule: volumetric applies if side > 60cm or vol > phys by >= 15%
        if side_max_cm > 60.0 or vol > phys * 1.15:
            return max(phys, vol)
        return phys

    @classmethod
    def get_carrier_shipping_fee(
        cls,
        carrier: str,
        origin_country: str,
        weight_kg: float,
        is_liquid: bool = False,
    ) -> float:
        """Calculates freight forwarding fee based on carrier stepped weight tiers."""
        c = carrier.upper().strip()
        country = origin_country.upper().strip()
        w = max(0.01, round(weight_kg, 3))

        schedules = CARRIER_TARIFF_TIERS.get(c, {}).get(country)
        if not schedules:
            # Fallback default $5/kg
            fee = round(w * 5.0, 2)
        else:
            fee = 0.0
            found = False
            for max_w, flat_fee, per_kg in schedules:
                if w <= max_w:
                    if flat_fee > 0:
                        fee = flat_fee
                    else:
                        fee = round(w * per_kg, 2)
                    found = True
                    break
            if not found:
                fee = round(w * schedules[-1][2], 2)

        if is_liquid and c in ("CAMEX", "STAREX"):
            fee += 1.0  # Liquid handling surcharge

        return round(fee, 2)

    # -------------------------------------------------------------------------
    # FOCUS AREA 3: Volumetric Weight Repacking Optimizer
    # -------------------------------------------------------------------------
    @classmethod
    def evaluate_volumetric_repack(
        cls,
        package: PackageItem,
        carrier: str = "STAREX",
        repack_fee_usd: float = DEFAULT_REPACK_SERVICE_FEE_USD,
    ) -> VolumetricRepackAssessment:
        """Analyzes cargo dimensions, evaluates volumetric penalty, and calculates repacking ROI."""
        length = package.length_cm or 0.0
        width = package.width_cm or 0.0
        height = package.height_cm or 0.0
        phys_w = max(0.01, package.physical_weight_kg)

        initial_vol = round(length * width * height, 2)
        initial_vol_w = cls.calculate_volumetric_weight(length, width, height)
        max_side = max(length, width, height) if initial_vol > 0 else 0.0

        initial_billable_w = cls.determine_billable_weight(phys_w, initial_vol_w, max_side)
        initial_cost = cls.get_carrier_shipping_fee(
            carrier=carrier,
            origin_country=package.origin_country,
            weight_kg=initial_billable_w,
            is_liquid=package.is_liquid,
        )

        # Check fragility constraints
        if package.is_fragile or package.category == ItemCategory.FRAGILE:
            return VolumetricRepackAssessment(
                package_id=package.id,
                category=package.category,
                physical_weight_kg=phys_w,
                initial_dimensions_cm=(length, width, height),
                initial_volume_cm3=initial_vol,
                initial_volumetric_weight_kg=initial_vol_w,
                initial_billable_weight_kg=initial_billable_w,
                initial_shipping_cost_usd=initial_cost,
                repacked_dimensions_cm=(length, width, height),
                repacked_volume_cm3=initial_vol,
                repacked_volumetric_weight_kg=initial_vol_w,
                repacked_billable_weight_kg=initial_billable_w,
                repacked_shipping_cost_usd=initial_cost,
                volume_reduction_pct=0.0,
                weight_reduction_kg=0.0,
                repack_fee_usd=0.0,
                gross_shipping_saved_usd=0.0,
                net_financial_saving_usd=0.0,
                net_financial_saving_azn=0.0,
                roi_multiplier=0.0,
                recommendation=RepackRecommendation.PROHIBITED_FRAGILE,
                repack_technique="Orijinal Qoruyucu Qutuda Saxla (Kövrək Əşya)",
                recommendation_reason="Məhsul kövrəkdir (şüşə/keramika). Yenidən qablaşdırma zədələnmə riski yaradır.",
            )

        # Check if volumetric even exceeds physical
        compression_factor = CATEGORY_COMPRESSION_FACTORS.get(package.category, 0.25)
        if initial_vol <= 0 or (initial_vol_w <= phys_w and max_side <= 60.0):
            return VolumetricRepackAssessment(
                package_id=package.id,
                category=package.category,
                physical_weight_kg=phys_w,
                initial_dimensions_cm=(length, width, height),
                initial_volume_cm3=initial_vol,
                initial_volumetric_weight_kg=initial_vol_w,
                initial_billable_weight_kg=initial_billable_w,
                initial_shipping_cost_usd=initial_cost,
                repacked_dimensions_cm=(length, width, height),
                repacked_volume_cm3=initial_vol,
                repacked_volumetric_weight_kg=initial_vol_w,
                repacked_billable_weight_kg=initial_billable_w,
                repacked_shipping_cost_usd=initial_cost,
                volume_reduction_pct=0.0,
                weight_reduction_kg=0.0,
                repack_fee_usd=0.0,
                gross_shipping_saved_usd=0.0,
                net_financial_saving_usd=0.0,
                net_financial_saving_azn=0.0,
                roi_multiplier=0.0,
                recommendation=RepackRecommendation.NOT_RECOMMENDED,
                repack_technique="Standart Qablaşdırma",
                recommendation_reason="Həcmi çəki fiziki çəkini aşmır. Yenidən qablaşdırmaya ehtiyac yoxdur.",
            )

        # Calculate repacked dimensions
        # Volume is reduced by compression_factor: V' = V * (1 - factor)
        repacked_vol = round(initial_vol * (1.0 - compression_factor), 2)
        # Linear dimension scale factor
        scale = math.pow(1.0 - compression_factor, 1.0 / 3.0)
        repacked_l = round(length * scale, 1)
        repacked_w = round(width * scale, 1)
        repacked_h = round(height * scale, 1)

        repacked_vol_w = cls.calculate_volumetric_weight(repacked_l, repacked_w, repacked_h)
        repacked_max_side = max(repacked_l, repacked_w, repacked_h)
        repacked_billable_w = cls.determine_billable_weight(phys_w, repacked_vol_w, repacked_max_side)

        repacked_cost = cls.get_carrier_shipping_fee(
            carrier=carrier,
            origin_country=package.origin_country,
            weight_kg=repacked_billable_w,
            is_liquid=package.is_liquid,
        )

        gross_saved = round(max(0.0, initial_cost - repacked_cost), 2)
        net_saved_usd = round(gross_saved - repack_fee_usd, 2)
        net_saved_azn = round(net_saved_usd * DEFAULT_USD_TO_AZN_RATE, 2)
        roi = round(gross_saved / repack_fee_usd, 2) if repack_fee_usd > 0 else 99.0

        # Choose technique
        if package.category in (ItemCategory.APPAREL, ItemCategory.PLUSH_TOYS):
            tech = "Vakuum Paketləmə (Həcmin 55-65% kiçildilməsi)"
        elif package.category == ItemCategory.FOOTWEAR:
            tech = "Ayaqqabı Qutusunun Çıxarılması və Tekstil Torba"
        elif package.category == ItemCategory.BAGS:
            tech = "Daxili Kağız Dolğuların Boşaldılması və Yastılaşdırma"
        else:
            tech = "Artıq Karobkanın Kəsilməsi / Polietilen Zərfə Keçid"

        if net_saved_usd >= 1.50:
            rec = RepackRecommendation.STRONG_RECOMMEND
            reason = f"Güclü tövsiyə: {net_saved_usd} USD ({net_saved_azn} AZN) xalis qənaət təmin edir (ROI: {roi}x)."
        elif net_saved_usd > 0.0:
            rec = RepackRecommendation.OPTIONAL
            reason = f"Qənaət mövcuddur: {net_saved_usd} USD qənaət, lakin fərq azdır."
        else:
            rec = RepackRecommendation.NOT_RECOMMENDED
            reason = f"Xidmət haqqı ({repack_fee_usd} USD) gözlənilən daşıma qənaətindən ({gross_saved} USD) çoxdur."

        return VolumetricRepackAssessment(
            package_id=package.id,
            category=package.category,
            physical_weight_kg=phys_w,
            initial_dimensions_cm=(length, width, height),
            initial_volume_cm3=initial_vol,
            initial_volumetric_weight_kg=initial_vol_w,
            initial_billable_weight_kg=initial_billable_w,
            initial_shipping_cost_usd=initial_cost,
            repacked_dimensions_cm=(repacked_l, repacked_w, repacked_h),
            repacked_volume_cm3=repacked_vol,
            repacked_volumetric_weight_kg=repacked_vol_w,
            repacked_billable_weight_kg=repacked_billable_w,
            repacked_shipping_cost_usd=repacked_cost,
            volume_reduction_pct=round(compression_factor * 100, 1),
            weight_reduction_kg=round(initial_billable_w - repacked_billable_w, 3),
            repack_fee_usd=repack_fee_usd,
            gross_shipping_saved_usd=gross_saved,
            net_financial_saving_usd=net_saved_usd,
            net_financial_saving_azn=net_saved_azn,
            roi_multiplier=roi,
            recommendation=rec,
            repack_technique=tech,
            recommendation_reason=reason,
        )

    # -------------------------------------------------------------------------
    # FOCUS AREA 1: Weight Tier Consolidation Mathematical Model
    # -------------------------------------------------------------------------
    @classmethod
    def evaluate_tier_consolidation(
        cls,
        packages: List[PackageItem],
        carrier: str = "STAREX",
        apply_repacking: bool = True,
        bundling_fee_per_extra_pkg_usd: float = DEFAULT_CONSOLIDATION_FEE_USD,
    ) -> ConsolidationBundle:
        """Compares shipping 2-5 individual small packages vs bundled consolidated shipping."""
        if not packages:
            raise ValueError("At least one package is required for consolidation evaluation.")

        first_pkg = packages[0]
        country = first_pkg.origin_country.upper().strip()

        # Check origin country consistency
        for p in packages:
            if p.origin_country.upper().strip() != country:
                raise ValueError(
                    f"All packages in a consolidation bundle must share origin country. "
                    f"Found {p.origin_country} vs {country}."
                )

        standalone_costs: Dict[str, float] = {}
        total_phys_w = 0.0
        total_goods_val_usd = 0.0
        total_goods_val_azn = 0.0
        has_liquid = False

        combined_vol_cm3 = 0.0

        for p in packages:
            if p.is_liquid:
                has_liquid = True

            # If currency conversion was not already performed
            if p.invoice_amount_usd <= 0 and p.invoice_amount > 0:
                p.invoice_amount_usd, p.invoice_amount_azn = cls.convert_currency_to_usd_azn(
                    p.invoice_amount, p.currency
                )

            total_goods_val_usd += p.invoice_amount_usd
            total_goods_val_azn += p.invoice_amount_azn

            # Billable weight for standalone
            if apply_repacking and (p.length_cm or 0) > 0:
                repack = cls.evaluate_volumetric_repack(p, carrier=carrier)
                billable_w = repack.repacked_billable_weight_kg
                combined_vol_cm3 += repack.repacked_volume_cm3
            else:
                vol_w = cls.calculate_volumetric_weight(p.length_cm or 0, p.width_cm or 0, p.height_cm or 0)
                billable_w = cls.determine_billable_weight(
                    p.physical_weight_kg, vol_w, max(p.length_cm or 0, p.width_cm or 0, p.height_cm or 0)
                )
                combined_vol_cm3 += (p.length_cm or 0) * (p.width_cm or 0) * (p.height_cm or 0)

            cost = cls.get_carrier_shipping_fee(
                carrier=carrier,
                origin_country=country,
                weight_kg=billable_w,
                is_liquid=p.is_liquid,
            )
            standalone_costs[p.id] = cost
            total_phys_w += p.physical_weight_kg

        sum_standalone = round(sum(standalone_costs.values()), 2)

        # Packing efficiency factor when multiple packages are bundled in master box/bag
        # 15% void nesting efficiency
        nesting_efficiency = 0.85 if len(packages) > 1 else 1.0
        effective_vol_cm3 = combined_vol_cm3 * nesting_efficiency
        consolidated_vol_w = round(effective_vol_cm3 / DEFAULT_VOLUMETRIC_DIVISOR, 3)

        effective_bundle_w = max(total_phys_w, consolidated_vol_w)
        consolidated_shipping = cls.get_carrier_shipping_fee(
            carrier=carrier,
            origin_country=country,
            weight_kg=effective_bundle_w,
            is_liquid=has_liquid,
        )

        # Forwarder handling fee: $0.50 per package beyond the first
        bundling_fee = round(max(0, len(packages) - 1) * bundling_fee_per_extra_pkg_usd, 2)
        gross_savings = round(max(0.0, sum_standalone - consolidated_shipping), 2)
        net_savings_usd = round(gross_savings - bundling_fee, 2)
        net_savings_azn = round(net_savings_usd * DEFAULT_USD_TO_AZN_RATE, 2)
        savings_pct = round((net_savings_usd / sum_standalone) * 100, 1) if sum_standalone > 0 else 0.0

        bundle_id = f"BUNDLE-{carrier}-{country}-{len(packages)}PKGS"

        return ConsolidationBundle(
            bundle_id=bundle_id,
            carrier=carrier,
            origin_country=country,
            packages=packages,
            package_count=len(packages),
            total_physical_weight_kg=round(total_phys_w, 3),
            total_volumetric_weight_kg=round(consolidated_vol_w, 3),
            effective_billable_weight_kg=round(effective_bundle_w, 3),
            total_goods_value_usd=round(total_goods_val_usd, 2),
            total_goods_value_azn=round(total_goods_val_azn, 2),
            standalone_costs_usd=standalone_costs,
            sum_standalone_shipping_usd=sum_standalone,
            consolidated_shipping_usd=consolidated_shipping,
            bundling_fee_usd=bundling_fee,
            gross_shipping_savings_usd=gross_savings,
            net_shipping_savings_usd=net_savings_usd,
            net_shipping_savings_azn=net_savings_azn,
            savings_percentage=savings_pct,
            assigned_fin=first_pkg.assigned_fin or "6XXXXXX",
            dispatch_month=datetime.now(timezone.utc).strftime("%Y-%m"),
        )

    # -------------------------------------------------------------------------
    # FOCUS AREA 2: 300 USD SmartCustoms Quota Collision Detector
    # -------------------------------------------------------------------------
    @classmethod
    def calculate_customs_tax(
        cls,
        excess_usd: float,
        usd_to_azn: float = DEFAULT_USD_TO_AZN_RATE,
    ) -> Tuple[float, float, float, float]:
        """Calculates customs duty, VAT, clearance fee, and total tax on excess USD (Resolution No. 305).

        Returns: (tariff_duty_azn, vat_azn, clearance_fee_azn, total_customs_azn)
        """
        if excess_usd <= 0.0:
            return 0.0, 0.0, 0.0, 0.0

        excess_azn = round(excess_usd * usd_to_azn, 2)
        tariff_duty_azn = round(excess_azn * CUSTOMS_TARIFF_RATE, 2)
        vat_azn = round((excess_azn + tariff_duty_azn) * CUSTOMS_VAT_RATE, 2)
        clearance_fee_azn = CUSTOMS_CLEARANCE_FEE_AZN
        total_customs_azn = round(tariff_duty_azn + vat_azn + clearance_fee_azn, 2)

        return tariff_duty_azn, vat_azn, clearance_fee_azn, total_customs_azn

    @classmethod
    def detect_customs_quota_collision(
        cls,
        bundle: ConsolidationBundle,
        current_used_usd: float,
        fin: str = "6XXXXXX",
        calendar_month: Optional[str] = None,
    ) -> CustomsQuotaImpact:
        """Detects whether bundling packages exceeds $300 monthly quota and triggers severe customs penalties."""
        month_str = calendar_month or bundle.dispatch_month or datetime.now(timezone.utc).strftime("%Y-%m")
        used_usd = max(0.0, round(current_used_usd, 2))
        rem_usd = max(0.0, round(MONTHLY_CUSTOMS_QUOTA_USD - used_usd, 2))

        bundle_val_usd = bundle.total_goods_value_usd
        projected_total = round(used_usd + bundle_val_usd, 2)

        excess_usd = max(0.0, round(projected_total - MONTHLY_CUSTOMS_QUOTA_USD, 2))
        excess_azn = round(excess_usd * DEFAULT_USD_TO_AZN_RATE, 2)

        duty_azn, vat_azn, fee_azn, total_tax_azn = cls.calculate_customs_tax(excess_usd)
        total_tax_usd = round(total_tax_azn / DEFAULT_USD_TO_AZN_RATE, 2)

        shipping_savings = bundle.net_shipping_savings_usd
        net_economic_benefit = round(shipping_savings - total_tax_usd, 2)

        is_exceeded = excess_usd > 0.0
        collision_detected = is_exceeded

        if not is_exceeded:
            if projected_total >= 225.0:
                level = CollisionSeverity.WARNING_NEAR_LIMIT
                explanation = (
                    f"Aylıq limitə yaxınlaşır: Proqnozlaşdırılan məbləğ {projected_total} USD / 300 USD "
                    f"({round((projected_total / 300) * 100, 1)}%). Hazırda rüsum hesablanmır."
                )
            else:
                level = CollisionSeverity.SAFE
                explanation = (
                    f"Təhlükəsiz zolaq: Proqnozlaşdırılan məbləğ {projected_total} USD <= 300 USD. "
                    f"Qənaət edilən daşıma haqqı: {shipping_savings} USD."
                )
        else:
            if net_economic_benefit < 0:
                level = CollisionSeverity.CRITICAL_COLLISION_TAX_EXCEEDS_SAVINGS
                explanation = (
                    f"KRİTİK GÖMRÜK TOQQUŞMASI: Bağlamaların birləşdirilməsi 300 USD limitini {excess_usd} USD aşır! "
                    f"Gömrük rüsum və ƏDV məbləği: {total_tax_azn} AZN (~{total_tax_usd} USD). "
                    f"Siz daşımada {shipping_savings} USD qənaət etsəniz də, dövlət rüsumu səbəbindən "
                    f"{abs(net_economic_benefit)} USD ZƏRƏRƏ düşürsünüz!"
                )
            else:
                level = CollisionSeverity.WARNING_NEAR_LIMIT
                explanation = (
                    f"Limit aşılıb: {excess_usd} USD artıq üçün {total_tax_azn} AZN gömrük rüsumu tətbiq olunur. "
                    f"Daşıma qənaəti rüsumu qarşılayır, xalis xeyir: {net_economic_benefit} USD."
                )

        return CustomsQuotaImpact(
            fin=fin,
            calendar_month=month_str,
            current_used_usd=used_usd,
            current_remaining_usd=rem_usd,
            bundle_cif_usd=bundle_val_usd,
            projected_month_total_usd=projected_total,
            quota_limit_usd=MONTHLY_CUSTOMS_QUOTA_USD,
            is_quota_exceeded=is_exceeded,
            excess_amount_usd=excess_usd,
            excess_amount_azn=excess_azn,
            customs_duty_azn=duty_azn,
            customs_vat_azn=vat_azn,
            customs_fee_azn=fee_azn,
            total_customs_cost_azn=total_tax_azn,
            total_customs_cost_usd=total_tax_usd,
            shipping_savings_usd=shipping_savings,
            net_economic_benefit_usd=net_economic_benefit,
            collision_detected=collision_detected,
            collision_level=level,
            explanation=explanation,
        )

    # -------------------------------------------------------------------------
    # FOCUS AREA 2 & 1 COMBINED: Split-Shipping & Delay Optimizer
    # -------------------------------------------------------------------------
    @classmethod
    def optimize_split_and_schedule(
        cls,
        packages: List[PackageItem],
        carrier: str = "STAREX",
        current_used_usd: float = 0.0,
        primary_fin: str = "6XXXXXX",
        available_fins: Optional[List[FINProfile]] = None,
        current_date: Optional[datetime] = None,
    ) -> SplitOrDelayPlan:
        """Solves subset-sum / knapsack optimization to avoid customs duties while maximizing consolidation savings."""
        now = current_date or datetime.now(timezone.utc)
        curr_year = now.year
        curr_month = now.month

        # Calculate days until 1st of next month
        if curr_month == 12:
            next_year = curr_year + 1
            next_month = 1
        else:
            next_year = curr_year
            next_month = curr_month + 1

        first_of_next_month = datetime(next_year, next_month, 1, 0, 0, 0, tzinfo=timezone.utc)
        days_until_next_month = (first_of_next_month.date() - now.date()).days

        # Ensure all packages have USD values
        for p in packages:
            if p.invoice_amount_usd <= 0 and p.invoice_amount > 0:
                p.invoice_amount_usd, p.invoice_amount_azn = cls.convert_currency_to_usd_azn(
                    p.invoice_amount, p.currency
                )

        full_bundle = cls.evaluate_tier_consolidation(packages, carrier=carrier)
        quota_impact = cls.detect_customs_quota_collision(full_bundle, current_used_usd, fin=primary_fin)

        # CASE 1: All packages safely fit within remaining quota
        if not quota_impact.is_quota_exceeded:
            return SplitOrDelayPlan(
                strategy_type=StrategyType.CONSOLIDATE_IMMEDIATELY,
                recommended_action="Bütün bağlamaları dərhal birləşdirin və cari ayda yola salın.",
                primary_bundle=full_bundle,
                immediate_dispatch_package_ids=[p.id for p in packages],
                delay_days=0,
                target_dispatch_date=now,
                customs_duty_prevented_usd=0.0,
                net_total_savings_usd=full_bundle.net_shipping_savings_usd,
                net_total_savings_azn=full_bundle.net_shipping_savings_azn,
                step_by_step_instructions=[
                    f"1. Bütün {len(packages)} bağlamanı {carrier} xarici anbarında 'Birgə göndəriş' (Consolidation) rejiminə əlavə edin.",
                    f"2. Daşıma haqqı {full_bundle.consolidated_shipping_usd} USD təşkil edəcək (Ayrı-ayrılıqda: {full_bundle.sum_standalone_shipping_usd} USD).",
                    f"3. Xalis qənaət: {full_bundle.net_shipping_savings_usd} USD ({full_bundle.net_shipping_savings_azn} AZN).",
                    "4. SmartCustoms portalında bəyannaməni cari ay üçün təsdiqləyin.",
                ],
            )

        # Quota collision detected!
        excess_tax_usd = quota_impact.total_customs_cost_usd
        rem_quota = quota_impact.current_remaining_usd

        # Check warehouse storage safety for delayed shipping
        min_free_storage_days = min((p.free_storage_days_remaining for p in packages), default=15)
        can_safely_delay_at_hub = days_until_next_month <= min_free_storage_days

        # CASE 2: Alternative Family FIN available with adequate remaining quota
        if available_fins:
            for alt_fin in available_fins:
                if alt_fin.fin != primary_fin and alt_fin.remaining_quota_usd >= full_bundle.total_goods_value_usd:
                    # Allocate entire bundle to secondary FIN!
                    sec_bundle = full_bundle.model_copy(update={"assigned_fin": alt_fin.fin})
                    return SplitOrDelayPlan(
                        strategy_type=StrategyType.ALLOCATE_TO_SECONDARY_FIN,
                        recommended_action=(
                            f"Bağlamaları ailə üzvünün FİN koduna ({alt_fin.fin} - {alt_fin.owner_name}) yönləndirin."
                        ),
                        secondary_fin_bundle=sec_bundle,
                        immediate_dispatch_package_ids=[p.id for p in packages],
                        delay_days=0,
                        target_dispatch_date=now,
                        customs_duty_prevented_usd=excess_tax_usd,
                        net_total_savings_usd=round(full_bundle.net_shipping_savings_usd, 2),
                        net_total_savings_azn=round(full_bundle.net_shipping_savings_azn, 2),
                        step_by_step_instructions=[
                            f"1. Əsas FİN ({primary_fin}) limitini qorumaq üçün bağlamaları {alt_fin.owner_name} ({alt_fin.fin}) adına qeydiyyatdan keçirin.",
                            f"2. {alt_fin.owner_name} cari ayda {alt_fin.used_quota_usd} USD istifadə edib, {alt_fin.remaining_quota_usd} USD limiti mövcuddur.",
                            f"3. Bağlamalar dərhal birləşdirilir: {full_bundle.net_shipping_savings_usd} USD daşıma qənaəti əldə olunur.",
                            f"4. Gömrük rüsumu: 0 AZN (Tam rüsumsuz). Qarşısı alınan rüsum: {quota_impact.total_customs_cost_azn} AZN (~{excess_tax_usd} USD).",
                        ],
                    )

        # CASE 3: Knapsack Partitioning: Select optimal subset S that fits under remaining quota
        best_subset_items: List[PackageItem] = []
        best_subset_val = -1.0
        best_savings = -1.0

        n = len(packages)
        for r in range(1, n):
            for combo in itertools.combinations(packages, r):
                sub_val = sum(p.invoice_amount_usd for p in combo)
                if sub_val <= rem_quota:
                    # Score by combination value or shipping savings
                    if sub_val > best_subset_val:
                        best_subset_val = sub_val
                        best_subset_items = list(combo)

        remaining_delayed_items = [p for p in packages if p.id not in {b.id for b in best_subset_items}]

        # Check if Knapsack split makes economic sense and delay is possible
        if best_subset_items and remaining_delayed_items and can_safely_delay_at_hub:
            primary_sub_bundle = cls.evaluate_tier_consolidation(best_subset_items, carrier=carrier)
            delayed_sub_bundle = cls.evaluate_tier_consolidation(remaining_delayed_items, carrier=carrier)
            delayed_sub_bundle.scheduled_dispatch_date = first_of_next_month
            delayed_sub_bundle.dispatch_month = first_of_next_month.strftime("%Y-%m")

            combined_net_savings = round(
                primary_sub_bundle.net_shipping_savings_usd + delayed_sub_bundle.net_shipping_savings_usd, 2
            )
            combined_net_azn = round(combined_net_savings * DEFAULT_USD_TO_AZN_RATE, 2)

            return SplitOrDelayPlan(
                strategy_type=StrategyType.SPLIT_SUBSET_NOW_AND_DELAY_REST,
                recommended_action=(
                    f"Ağıllı Bölünmə: {len(best_subset_items)} bağlamanı dərhal yola salın, "
                    f"qalan {len(remaining_delayed_items)} bağlamanı isə anbarın pulsuz saxlama müddətindən "
                    f"istifadə edərək növbəti ayın 1-nə saxlayın."
                ),
                primary_bundle=primary_sub_bundle,
                delayed_bundle=delayed_sub_bundle,
                immediate_dispatch_package_ids=[p.id for p in best_subset_items],
                delayed_dispatch_package_ids=[p.id for p in remaining_delayed_items],
                delay_days=days_until_next_month,
                target_dispatch_date=first_of_next_month,
                customs_duty_prevented_usd=excess_tax_usd,
                net_total_savings_usd=combined_net_savings,
                net_total_savings_azn=combined_net_azn,
                step_by_step_instructions=[
                    f"1. Cari ay ({now.strftime('%B %Y')}): {len(best_subset_items)} ədəd bağlama "
                    f"({[p.title[:20] for p in best_subset_items]}) birləşdirilərək dərhal yola salınır. "
                    f"Dəyəri: {primary_sub_bundle.total_goods_value_usd} USD <= Qalan limit {rem_quota} USD (0 AZN rüsum).",
                    f"2. Növbəti ay ({first_of_next_month.strftime('%d.%m.%Y')}): Qalan {len(remaining_delayed_items)} "
                    f"ədəd bağlama ({[p.title[:20] for p in remaining_delayed_items]}) xarici anbarda saxlanılır. "
                    f"Gözləmə müddəti: {days_until_next_month} gün (Pulsuz anbar limiti: {min_free_storage_days} gün).",
                    f"3. Növbəti ayın 1-də 300 USD kvota sıfırlanır və bağlamalar tamamilə rüsumsuz idxal olunur.",
                    f"4. Qarşısı alınan gömrük vergisi: {quota_impact.total_customs_cost_azn} AZN (~{excess_tax_usd} USD)!",
                    f"5. Ümumi daşıma qənaəti: {combined_net_savings} USD ({combined_net_azn} AZN).",
                ],
            )

        # CASE 4: Entire Bundle Delay to Day 1 of Next Month
        if can_safely_delay_at_hub:
            delayed_full = full_bundle.model_copy(
                update={
                    "scheduled_dispatch_date": first_of_next_month,
                    "dispatch_month": first_of_next_month.strftime("%Y-%m"),
                }
            )
            return SplitOrDelayPlan(
                strategy_type=StrategyType.DELAY_BUNDLE_TO_NEXT_MONTH,
                recommended_action=(
                    f"Bütün bağlamaları xarici anbarda saxlayıb {first_of_next_month.strftime('%d %B %Y')} "
                    f"tarixində (növbəti ayın 1-i) rüsumsuz yola salın."
                ),
                delayed_bundle=delayed_full,
                immediate_dispatch_package_ids=[],
                delayed_dispatch_package_ids=[p.id for p in packages],
                delay_days=days_until_next_month,
                target_dispatch_date=first_of_next_month,
                customs_duty_prevented_usd=excess_tax_usd,
                net_total_savings_usd=full_bundle.net_shipping_savings_usd,
                net_total_savings_azn=full_bundle.net_shipping_savings_azn,
                step_by_step_instructions=[
                    f"1. Cari ayda artıq {current_used_usd} USD istifadə olunub. Bağlamaların birləşdirilməsi {quota_impact.excess_amount_usd} USD limit aşımı yaradacaqdı.",
                    f"2. Bağlamalar {carrier} xarici anbarında saxlanılır. Gözləmə: {days_until_next_month} gün <= Pulsuz saxlama {min_free_storage_days} gün.",
                    f"3. {first_of_next_month.strftime('%d.%m.%Y')} tarixində 300 USD limit sıfırlandıqdan dərhal sonra göndəriş təsdiqlənir.",
                    f"4. Gömrük xərci: 0 AZN (Xilas edilən məbləğ: {quota_impact.total_customs_cost_azn} AZN).",
                    f"5. Daşıma qənaəti: {full_bundle.net_shipping_savings_usd} USD ({full_bundle.net_shipping_savings_azn} AZN).",
                ],
            )

        # CASE 5: Fallback - Standalone shipping without bundling
        sum_standalone = full_bundle.sum_standalone_shipping_usd
        return SplitOrDelayPlan(
            strategy_type=StrategyType.SHIP_INDIVIDUALLY_NO_BUNDLE,
            recommended_action=(
                "Gözləmə müddəti anbar limitini aşdığı və limit dolduğu üçün bağlamaları ayrı-ayrılıqda "
                "və ya mərhələli şəkildə sifariş verin."
            ),
            immediate_dispatch_package_ids=[p.id for p in packages],
            delay_days=0,
            target_dispatch_date=now,
            customs_duty_prevented_usd=0.0,
            net_total_savings_usd=0.0,
            net_total_savings_azn=0.0,
            step_by_step_instructions=[
                "1. Anbarda pulsuz saxlama müddəti ayın sonuna çatmır.",
                "2. Bağlamaları birləşdirdikdə yaranacaq gömrük cəriməsi daşıma qənaətindən qat-qat böyükdür.",
                "3. Bağlamaların hər birini ayrı bəyan edin və ya alternativ şəxsin adına sənədləşdirin.",
            ],
        )

    # -------------------------------------------------------------------------
    # COMPREHENSIVE PIPELINE EXECUTION
    # -------------------------------------------------------------------------
    @classmethod
    def run_full_optimization(
        cls,
        packages: List[PackageItem],
        carrier: str = "STAREX",
        current_used_usd: float = 0.0,
        primary_fin: str = "6XXXXXX",
        available_fins: Optional[List[FINProfile]] = None,
        current_date: Optional[datetime] = None,
    ) -> ConsolidationOptimizationReport:
        """Executes end-to-end 3-tier optimization: Volumetric Repack -> Weight Tier Bundle -> Customs Quota Split."""
        if not packages:
            raise ValueError("No packages provided to optimizer.")

        first_pkg = packages[0]
        country = first_pkg.origin_country.upper().strip()

        # Step 1: Volumetric repacking analysis for every package
        volumetric_analyses: List[VolumetricRepackAssessment] = []
        repacked_packages: List[PackageItem] = []

        for p in packages:
            assessment = cls.evaluate_volumetric_repack(p, carrier=carrier)
            volumetric_analyses.append(assessment)

            # If repack is strongly recommended or optional, update effective dimensions/billable weight
            if assessment.recommendation in (RepackRecommendation.STRONG_RECOMMEND, RepackRecommendation.OPTIONAL):
                l_new, w_new, h_new = assessment.repacked_dimensions_cm
                p_copy = p.model_copy(update={"length_cm": l_new, "width_cm": w_new, "height_cm": h_new})
                repacked_packages.append(p_copy)
            else:
                repacked_packages.append(p)

        # Step 2: Weight Tier Consolidation on repacked packages
        bundle = cls.evaluate_tier_consolidation(repacked_packages, carrier=carrier, apply_repacking=False)

        # Step 3: Customs Quota Collision Detection
        quota_impact = cls.detect_customs_quota_collision(
            bundle=bundle,
            current_used_usd=current_used_usd,
            fin=primary_fin,
        )

        # Step 4: Intelligent Split, Delay, or Multi-FIN Plan
        plan = cls.optimize_split_and_schedule(
            packages=repacked_packages,
            carrier=carrier,
            current_used_usd=current_used_usd,
            primary_fin=primary_fin,
            available_fins=available_fins,
            current_date=current_date,
        )

        total_repack_savings = sum(a.net_financial_saving_usd for a in volumetric_analyses if a.net_financial_saving_usd > 0)
        overall_net_savings_usd = round(plan.net_total_savings_usd + total_repack_savings + plan.customs_duty_prevented_usd, 2)
        overall_net_savings_azn = round(overall_net_savings_usd * DEFAULT_USD_TO_AZN_RATE, 2)

        verdict = (
            f"Optimallaşdırma tamamlandı: Strategiya -> {plan.strategy_type.value}. "
            f"Ümumi fayda: ~{overall_net_savings_usd} USD ({overall_net_savings_azn} AZN). "
            f"Daşıma qənaəti: {plan.net_total_savings_usd} USD | Repack qənaəti: {round(total_repack_savings, 2)} USD | "
            f"Qarşısı alınan gömrük rüsumu: {plan.customs_duty_prevented_usd} USD."
        )

        return ConsolidationOptimizationReport(
            carrier=carrier,
            origin_country=country,
            generated_at=current_date or datetime.now(timezone.utc),
            input_packages_count=len(packages),
            volumetric_analyses=volumetric_analyses,
            recommended_bundle=bundle,
            quota_impact=quota_impact,
            best_execution_plan=plan,
            overall_net_savings_usd=overall_net_savings_usd,
            overall_net_savings_azn=overall_net_savings_azn,
            summary_verdict=verdict,
        )

