"""PCS v4.0 REST API Router — Omni-Commerce, Arbitrage, FinTech & Logistics Brain."""

from __future__ import annotations

import dataclasses
import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.pcs_v4_engines import (
    AutonomousPriceDropAndDisputeAgent,
    CrossPlatformArbitrageEngine,
    CustomsComplianceAndHazmatGuardian,
    FamilyFinMeshOrchestrator,
    FamilyMemberProfile,
    FintechCardAndAlipayOptimizer,
    FlightETAPredictor,
    InventoryResaleVault,
    LandedCostQuote,
    PickupPassEngine,
    PlatformOffer,
    PurchasedItemRecord,
    SelfHealingDOM,
    WarehouseQCAuditor,
)

logger = logging.getLogger("pcs.v4.router")

router = APIRouter(prefix="/v4/api", tags=["v4-innovations"])
DB_PATH = Path("/data/pcs/pcs.db")


# ---------------------------------------------------------------------------
# Pydantic Request Models
# ---------------------------------------------------------------------------

class ArbitrageOfferModel(BaseModel):
    platform: str
    origin_country: str = "TR"
    item_price: float
    currency: str = "TRY"
    domestic_shipping: float = 0.0
    estimated_weight_kg: float = 0.5
    direct_to_baku_free_ship: bool = False


class ArbitrageEvaluateRequest(BaseModel):
    offers: List[ArbitrageOfferModel]
    monthly_limit_usd: float = 300.0
    current_month_used_usd: float = 45.20
    cashback_rate: float = 0.05


class ComplianceInspectRequest(BaseModel):
    title: str
    quantity: int = 1
    unit_price_usd: float = 100.0


class AlipaySplitRequest(BaseModel):
    item_prices_cny: List[float]


class FamilyAllocateRequest(BaseModel):
    parcel_usd: float


class FlightETARequest(BaseModel):
    origin_country: str = "TR"
    carrier: str = "STAREX"
    hub_checkin_dt: Optional[datetime] = None


class FlightCollisionCheckRequest(BaseModel):
    parcels: List[Dict[str, Any]]
    monthly_limit_usd: float = 300.0


class WeightAuditRequest(BaseModel):
    category: str
    carrier_weight_kg: float
    carrier_rate_usd_per_kg: float = 4.0


class PriceAdjustmentItemModel(BaseModel):
    order_ref: str
    platform: str
    item_id: str
    title: str
    paid_unit_price: float
    current_live_price: float
    quantity: int = 1
    currency: str = "TRY"
    order_date: Optional[date] = None


class PriceAdjustmentScanRequest(BaseModel):
    items: List[PriceAdjustmentItemModel]


class PickupPassRequest(BaseModel):
    ready_shipments: List[Dict[str, Any]]


class ResaleListingRequest(BaseModel):
    title: str
    landed_cost_azn: float
    purchase_date: Optional[date] = None
    condition: str = "Yeni (İstifadə olunmayıb)"
    markup_pct: float = 0.20


class DOMResolveRequest(BaseModel):
    platform: str
    field_key: str
    available_classes: List[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/arbitrage/evaluate")
async def evaluate_arbitrage(req: ArbitrageEvaluateRequest):
    """Calculates true Baku landed cost across multiple e-commerce platforms."""
    offers = [
        PlatformOffer(
            platform=o.platform,
            origin_country=o.origin_country,
            item_price=o.item_price,
            currency=o.currency,
            domestic_shipping=o.domestic_shipping,
            estimated_weight_kg=o.estimated_weight_kg,
            direct_to_baku_free_ship=o.direct_to_baku_free_ship,
        )
        for o in req.offers
    ]
    quotes = CrossPlatformArbitrageEngine.evaluate_offers(
        offers=offers,
        current_month_used_usd=req.current_month_used_usd,
        monthly_limit_usd=req.monthly_limit_usd,
        cashback_rate=req.cashback_rate,
    )
    return {
        "status": "success",
        "total_evaluated": len(quotes),
        "quotes": [dataclasses.asdict(q) for q in quotes],
    }


@router.post("/compliance/inspect")
async def inspect_compliance(req: ComplianceInspectRequest):
    """Audits item title for restricted goods, IATA hazmat flight requirements, and official IMEI duties."""
    report = CustomsComplianceAndHazmatGuardian.inspect_item(
        title=req.title,
        quantity=req.quantity,
        unit_price_usd=req.unit_price_usd,
    )
    return {
        "status": "success",
        "report": dataclasses.asdict(report),
    }


@router.post("/fintech/alipay-split")
async def split_alipay_payments(req: AlipaySplitRequest):
    """Splits shopping cart into <=200 CNY sub-payments to eliminate the 3% international card fee."""
    res = FintechCardAndAlipayOptimizer.optimize_taobao_cart_split(req.item_prices_cny)
    return {
        "status": "success",
        "optimization": res,
    }


@router.get("/fintech/best-card")
async def get_best_bank_card(
    amount_azn: float = Query(100.0, description="Transaction amount in AZN"),
    merchant_type: str = Query("ecommerce", description="Merchant type: ecommerce or cargo"),
):
    """Selects the highest yielding Azerbaijani bank card cashback for the given purchase."""
    res = FintechCardAndAlipayOptimizer.select_best_bank_card(
        amount_azn=amount_azn, merchant_type=merchant_type
    )
    return {"status": "success", "recommendation": res}


@router.get("/family-fin/pool")
async def get_family_fin_pool():
    """Lists all active FIN profiles in the family mesh with monthly quotas and suite numbers."""
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail="Database not found")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        SELECT fin, full_name, phone, starex_suite, limak_suite, camex_suite, dynamex_suite,
               monthly_limit_usd, used_usd_current_month, in_flight_usd, is_primary, is_active
        FROM fin_profiles
        ORDER BY is_primary DESC, fin ASC
    """)
    rows = cur.fetchall()
    con.close()

    profiles = []
    total_quota = 0.0
    total_available = 0.0

    for r in rows:
        fin, name, phone, st, lmx, cam, dyn, limit_usd, used_usd, inflight_usd, is_prim, is_act = r
        avail = max(0.0, limit_usd - used_usd - inflight_usd)
        total_quota += limit_usd
        total_available += avail
        profiles.append({
            "fin_code": fin,
            "full_name": name,
            "phone": phone,
            "starex_suite": st or "ST123456",
            "limak_suite": lmx or "LMX99999",
            "camex_suite": cam or "CAM-11111",
            "dynamex_suite": dyn or "DYN-22222",
            "monthly_limit_usd": limit_usd,
            "used_usd_this_month": used_usd,
            "in_flight_usd": inflight_usd,
            "available_usd": round(avail, 2),
            "is_primary": bool(is_prim),
            "is_active": bool(is_act),
        })

    return {
        "status": "success",
        "mesh_size": len(profiles),
        "total_combined_quota_usd": round(total_quota, 2),
        "total_combined_available_usd": round(total_available, 2),
        "profiles": profiles,
    }


@router.post("/family-fin/allocate")
async def allocate_family_fin(req: FamilyAllocateRequest):
    """Allocates an incoming parcel to the best family FIN to preserve $0 customs duty."""
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail="Database not found")

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        SELECT fin, full_name, phone, starex_suite, limak_suite,
               used_usd_current_month, in_flight_usd, monthly_limit_usd
        FROM fin_profiles
        WHERE is_active = 1
    """)
    rows = cur.fetchall()
    con.close()

    if not rows:
        raise HTTPException(status_code=400, detail="No active FIN profiles found")

    members = [
        FamilyMemberProfile(
            fin_code=r[0],
            full_name=r[1],
            phone=r[2],
            starex_suite=r[3] or "ST123456",
            limak_suite=r[4] or "LMX99999",
            used_usd_this_month=r[5] or 0.0,
            in_flight_usd=r[6] or 0.0,
            monthly_limit_usd=r[7] or 300.0,
        )
        for r in rows
    ]

    orchestrator = FamilyFinMeshOrchestrator(members)
    decision = orchestrator.select_optimal_profile(parcel_usd=req.parcel_usd)
    return {"status": "success", "decision": decision}


@router.post("/flight/eta")
async def predict_flight_eta(req: FlightETARequest):
    """Predicts Baku local branch arrival ETA based on carrier flight schedules and cut-off windows."""
    checkin_dt = req.hub_checkin_dt or datetime.now()
    eta_res = FlightETAPredictor.predict_pickup_eta(
        carrier=req.carrier,
        origin_country=req.origin_country,
        hub_checkin_dt=checkin_dt,
    )
    return {"status": "success", "eta": eta_res}


@router.post("/flight/check-collision")
async def check_flight_collision(req: FlightCollisionCheckRequest):
    """Guards against multiple parcels accidentally boarding the same cargo flight breaching $300."""
    collision = FlightETAPredictor.detect_same_flight_collision(
        parcels=req.parcels,
        monthly_limit_usd=req.monthly_limit_usd,
    )
    return {"status": "success", "collision_analysis": collision}


@router.post("/qc/check-weight")
async def audit_weight_discrepancy(req: WeightAuditRequest):
    """Detects foreign hub weight inflation and generates instant Re-weigh Dispute claims."""
    audit_res = WarehouseQCAuditor.audit_weight(
        category=req.category,
        carrier_weight_kg=req.carrier_weight_kg,
        carrier_rate_usd_per_kg=req.carrier_rate_usd_per_kg,
    )
    return {"status": "success", "audit": audit_res}


@router.post("/refunds/price-drops")
async def scan_price_drops(req: PriceAdjustmentScanRequest):
    """Audits past 30 days orders for post-purchase price reductions on Temu and Trendyol."""
    records = [
        PurchasedItemRecord(
            order_ref=it.order_ref,
            platform=it.platform,
            item_id=it.item_id,
            title=it.title,
            paid_unit_price=it.paid_unit_price,
            current_live_price=it.current_live_price,
            quantity=it.quantity,
            currency=it.currency,
            order_date=it.order_date or date.today(),
        )
        for it in req.items
    ]
    scan_res = AutonomousPriceDropAndDisputeAgent.scan_price_adjustments(records)
    return {"status": "success", "results": scan_res}


@router.post("/pickup/route")
async def optimize_pickup_pass(req: PickupPassRequest):
    """Prepares the shortest pedestrian pickup itinerary and unified barcode pass for 28 May hub."""
    itinerary = PickupPassEngine.generate_unified_pass(req.ready_shipments)
    return {"status": "success", "itinerary": itinerary}


@router.get("/inventory")
async def list_digital_inventory():
    """Lists personal digital inventory with warranty and resale status."""
    if not DB_PATH.exists():
        return {"status": "success", "items": []}

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        SELECT id, order_ref, item_title, dgk_category, landed_cost_azn,
               suggested_resale_azn, warranty_expires_at, resale_status, ad_copy_az, created_at
        FROM inventory_vault
        ORDER BY created_at DESC
    """)
    rows = cur.fetchall()
    con.close()

    items = [
        {
            "id": r[0],
            "order_ref": r[1],
            "item_title": r[2],
            "dgk_category": r[3],
            "landed_cost_azn": r[4],
            "suggested_resale_azn": r[5],
            "warranty_expires_at": r[6],
            "resale_status": r[7],
            "ad_copy_az": r[8],
            "created_at": r[9],
        }
        for r in rows
    ]
    return {"status": "success", "count": len(items), "items": items}


@router.post("/inventory/resale-ad")
async def generate_resale_ad(req: ResaleListingRequest):
    """Generates a high-converting Azerbaijani resale listing with +20% margin for Tap.az / Lalafo."""
    listing = InventoryResaleVault.generate_resale_listing(
        title=req.title,
        landed_cost_azn=req.landed_cost_azn,
        purchase_date_val=req.purchase_date or date.today(),
        condition=req.condition,
        markup_pct=req.markup_pct,
    )
    return {"status": "success", "listing": listing}


@router.post("/dom/resolve")
async def resolve_dom_selector(req: DOMResolveRequest):
    """Resolves broken DOM selector using Self-Healing heuristics."""
    selector = SelfHealingDOM.resolve_selector(
        platform=req.platform,
        field_key=req.field_key,
        available_classes=req.available_classes,
    )
    return {
        "status": "success",
        "platform": req.platform,
        "field_key": req.field_key,
        "resolved_selector": selector,
    }
