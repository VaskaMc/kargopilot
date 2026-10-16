"""User Management, Personal Parcels, Dynamic DGK Quota, and Data Sovereignty (Export/Import/Wipe) API.

Enforces:
- Strict Tenant Scoping & Insecure Direct Object Reference (IDOR) protection.
- Data Sovereignty: Full JSON portability export, duplicate-tolerant import, and Right-to-be-Forgotten wipe.
- Node Verification: Safe SSRF-protected health checking for self-hosted sovereign nodes.
- Dynamic DGK 300 USD quota tracking per user session.
"""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

try:
    from app.database import get_connection
    from app.security.rbac import AuthenticatedUser, get_current_user
except ImportError:
    from database import get_connection
    from security.rbac import AuthenticatedUser, get_current_user

logger = logging.getLogger("kargopilot.user.api")

router = APIRouter(prefix="/api/v1/user", tags=["User Dashboard & Personal Logistics"])
system_router = APIRouter(prefix="/api/v1/system", tags=["Node Verification & Sovereignty"])


# ==============================================================================
# Pydantic Schemas
# ==============================================================================

class UserProfileDetailResponse(BaseModel):
    id: str
    email: str
    full_name: str
    phone: Optional[str]
    role: str
    status: str
    tier: str
    fin: str
    default_branch: str
    notification_whatsapp: bool
    notification_email: bool
    created_at: str


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=120)
    phone: Optional[str] = Field(None, max_length=32)
    fin: Optional[str] = Field(None, min_length=7, max_length=7)
    default_branch: Optional[str] = Field(None, max_length=64)
    notification_whatsapp: Optional[bool] = None
    notification_email: Optional[bool] = None


class CreateParcelRequest(BaseModel):
    tracking_number: str = Field(..., min_length=3, max_length=64, json_schema_extra={"example": "TRK-984102"})
    platform: str = Field(..., json_schema_extra={"example": "Trendyol"})
    carrier: str = Field(..., json_schema_extra={"example": "STAREX"})
    title: str = Field(..., min_length=2, max_length=255, json_schema_extra={"example": "Kişi İdman Ayaqqabısı"})
    invoice_amount_usd: float = Field(..., gt=0.0, json_schema_extra={"example": 45.0})
    invoice_amount_azn: Optional[float] = Field(None, gt=0.0)


class ParcelResponse(BaseModel):
    id: str
    user_id: str
    platform: str
    tracking_number: str
    carrier: str
    title: str
    invoice_amount_usd: float
    invoice_amount_azn: float
    status: str
    created_at: str


class QuotaResponse(BaseModel):
    user_id: str
    fin: str
    monthly_limit_usd: float
    total_spent_usd: float
    remaining_usd: float
    spent_azn: float
    remaining_azn: float
    status: str  # safe | warning | danger
    duty_estimate_azn: float
    reassurance_message: str


# --- Data Sovereignty & Portability Schemas ---

class ExportedParcelItem(BaseModel):
    title: str
    main_cat: Optional[str] = "Geyim aksesuarları"
    sub_cat: Optional[str] = "Digər"
    quantity: int = 1
    unit_price: float = 0.0
    total_price: float = 0.0
    currency: str = "AZN"
    unit_price_azn: Optional[float] = None
    total_price_azn: float = 0.0
    total_price_usd: float = 0.0


class ExportedParcel(BaseModel):
    id: Optional[str] = None
    platform: str = "Digər"
    tracking_number: str
    carrier: str = "STAREX"
    title: str
    receiver_name: Optional[str] = None
    receiver_phone: Optional[str] = None
    fin: Optional[str] = None
    invoice_amount_usd: float
    invoice_amount_azn: Optional[float] = None
    status: Optional[str] = "Yoldadır"
    created_at: Optional[str] = None
    items: List[ExportedParcelItem] = Field(default_factory=list)


class DataExportBundle(BaseModel):
    schema_version: str = "4.5.0"
    service: str = "kargopilot-core"
    exported_at: str
    user_profile: Dict[str, Any]
    parcels: List[ExportedParcel]
    quota_summary: Dict[str, Any]


class ImportDataRequest(BaseModel):
    schema_version: Optional[str] = "4.5.0"
    service: Optional[str] = "kargopilot-core"
    user_profile: Optional[Dict[str, Any]] = None
    parcels: List[ExportedParcel] = Field(default_factory=list)


class ImportDataResponse(BaseModel):
    status: str
    message: str
    imported_count: int
    skipped_count: int
    total_parcels: int
    updated_quota: QuotaResponse


class WipeDataResponse(BaseModel):
    status: str
    message: str
    wiped_orders_count: int
    remaining_quota_usd: float


# --- Node Verification Schemas ---

class VerifyNodeRequest(BaseModel):
    target_url: str = Field(..., json_schema_extra={"example": "http://127.0.0.1:48481"})


class VerifyNodeResponse(BaseModel):
    healthy: bool
    target_url: str
    service: Optional[str] = None
    edition: Optional[str] = None
    version: Optional[str] = None
    latency_ms: Optional[float] = None
    message: str


# --- Smart Arbitrage & Customs Supervisor Schemas (Etap 4) ---

class ArbitrageCalculateRequest(BaseModel):
    origin_country: str = Field("TR", description="Mənşə ölkəsi: TR, US, CN, EU")
    weight_kg: float = Field(..., gt=0.0, description="Faktiki çəki (kq)")
    length_cm: Optional[float] = Field(None, ge=0.0, description="Uzunluq (sm)")
    width_cm: Optional[float] = Field(None, ge=0.0, description="En (sm)")
    height_cm: Optional[float] = Field(None, ge=0.0, description="Hündürlük (sm)")
    parcel_type: str = Field("standard", description="standard, liquid, electronics")


class CarrierRateDetail(BaseModel):
    carrier_name: str
    carrier_code: str
    chargeable_weight_kg: float
    rate_usd: float
    rate_azn: float
    delivery_days_min: int
    delivery_days_max: int
    delivery_eta: str
    notes: str
    is_cheapest: bool
    is_fastest: bool


class ArbitrageResponse(BaseModel):
    origin_country: str
    actual_weight_kg: float
    volumetric_weight_kg: Optional[float] = None
    chargeable_weight_kg: float
    parcel_type: str
    best_value_carrier: str
    fastest_carrier: str
    max_savings_usd: float
    max_savings_azn: float
    carriers: List[CarrierRateDetail]


class CustomsSimulateRequest(BaseModel):
    item_price_usd: float = Field(..., ge=0.0, description="Məhsulun invoys qiyməti (USD)")
    shipping_fee_usd: float = Field(0.0, ge=0.0, description="Xarici daşıma haqqı (USD)")
    month: Optional[str] = Field(None, description="Təqvim ayı (YYYY-MM), default cari ay")


class CustomsSimulateResponse(BaseModel):
    user_id: str
    month: str
    current_spent_usd: float
    item_price_usd: float
    shipping_fee_usd: float
    projected_total_usd: float
    projected_total_azn: float
    exceeds_limit: bool
    remaining_allowance_usd: float
    remaining_allowance_azn: float
    over_limit_amount_usd: float
    over_limit_amount_azn: float
    duty_rate_percent: float = 36.0
    duty_usd: float
    duty_azn: float
    status: str  # safe | warning | danger
    status_message: str
    recommendations: List[str]


# ==============================================================================
# Profile Management Routes
# ==============================================================================

@router.get("/profile", response_model=UserProfileDetailResponse)
async def get_user_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserProfileDetailResponse:
    """Retrieves full profile details for the authenticated user."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (current_user.id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İstifadəçi profili tapılmadı.")

        user_data = dict(row)
        return UserProfileDetailResponse(
            id=user_data["id"],
            email=user_data["email"],
            full_name=user_data["full_name"],
            phone=user_data.get("phone"),
            role=user_data["role"],
            status=user_data.get("status", "active"),
            tier=user_data.get("tier", "cloud_managed"),
            fin=user_data.get("fin") or "814CRM4",
            default_branch=user_data.get("default_branch") or "28 May",
            notification_whatsapp=bool(user_data.get("notification_whatsapp", 1)),
            notification_email=bool(user_data.get("notification_email", 1)),
            created_at=str(user_data.get("created_at")),
        )


@router.put("/profile", response_model=UserProfileDetailResponse)
async def update_user_profile(
    req: UpdateProfileRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> UserProfileDetailResponse:
    """Updates non-sensitive profile parameters (name, phone, FIN, branch, notifications)."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (current_user.id,)).fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İstifadəçi profili tapılmadı.")

        user_data = dict(row)

        full_name = req.full_name.strip() if req.full_name is not None else user_data["full_name"]
        phone = req.phone.strip() if req.phone is not None else user_data.get("phone")
        fin = req.fin.strip().upper() if req.fin is not None else (user_data.get("fin") or "814CRM4")
        branch = req.default_branch.strip() if req.default_branch is not None else (user_data.get("default_branch") or "28 May")
        notif_wa = int(req.notification_whatsapp) if req.notification_whatsapp is not None else user_data.get("notification_whatsapp", 1)
        notif_em = int(req.notification_email) if req.notification_email is not None else user_data.get("notification_email", 1)
        now_str = datetime.now(timezone.utc).isoformat()

        conn.execute(
            """UPDATE users 
               SET full_name = ?, phone = ?, fin = ?, default_branch = ?, 
                   notification_whatsapp = ?, notification_email = ?, updated_at = ?
               WHERE id = ?""",
            (full_name, phone, fin, branch, notif_wa, notif_em, now_str, current_user.id),
        )
        conn.commit()

        # Update fin_profiles table if FIN changed
        conn.execute(
            """INSERT INTO fin_profiles (fin, full_name, phone, is_active, monthly_limit_usd, notes)
               VALUES (?, ?, ?, 1, 300.0, 'İstifadəçi tərəfindən yeniləndi')
               ON CONFLICT(fin) DO UPDATE SET full_name = excluded.full_name, phone = excluded.phone""",
            (fin, full_name, phone),
        )
        conn.commit()

        return UserProfileDetailResponse(
            id=current_user.id,
            email=user_data["email"],
            full_name=full_name,
            phone=phone,
            role=user_data["role"],
            status=user_data.get("status", "active"),
            tier=user_data.get("tier", "cloud_managed"),
            fin=fin,
            default_branch=branch,
            notification_whatsapp=bool(notif_wa),
            notification_email=bool(notif_em),
            created_at=str(user_data.get("created_at")),
        )


# ==============================================================================
# Personal Parcels & DGK Tracking (Strict IDOR Isolation)
# ==============================================================================

@router.get("/parcels", response_model=List[ParcelResponse])
async def list_user_parcels(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> List[ParcelResponse]:
    """Retrieves all parcels scoped strictly to the authenticated user."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT o.id, o.user_id, o.platform, o.tracking_number, o.carrier, 
                      COALESCE(i.title, 'Xarici bağlama') as title,
                      COALESCE(o.invoice_amount_usd, 0.0) as invoice_amount_usd,
                      COALESCE(o.invoice_amount_azn, 0.0) as invoice_amount_azn,
                      o.status, o.created_at
               FROM orders o
               LEFT JOIN order_items i ON o.id = i.order_id
               WHERE o.user_id = ?
               GROUP BY o.id
               ORDER BY o.created_at DESC""",
            (current_user.id,),
        ).fetchall()

        parcels: List[ParcelResponse] = []
        for r in rows:
            parcels.append(
                ParcelResponse(
                    id=r["id"],
                    user_id=r["user_id"] or current_user.id,
                    platform=r["platform"] or "Digər",
                    tracking_number=r["tracking_number"] or "Yoxdur",
                    carrier=r["carrier"] or "STAREX",
                    title=r["title"],
                    invoice_amount_usd=round(float(r["invoice_amount_usd"]), 2),
                    invoice_amount_azn=round(float(r["invoice_amount_azn"]), 2),
                    status=r["status"] or "Yoldadır",
                    created_at=str(r["created_at"]),
                )
            )
        return parcels


@router.post("/parcels", response_model=ParcelResponse, status_code=status.HTTP_201_CREATED)
async def create_user_parcel(
    req: CreateParcelRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ParcelResponse:
    """Creates a new tracking parcel under the authenticated user's scope and recalculates quota."""
    parcel_id = str(uuid.uuid4())
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    amount_usd = round(req.invoice_amount_usd, 2)
    amount_azn = round(req.invoice_amount_azn if req.invoice_amount_azn else req.invoice_amount_usd * 1.70, 2)
    clean_tracking = req.tracking_number.strip().upper()
    platform = req.platform.strip()
    carrier = req.carrier.strip().upper()

    with get_connection() as conn:
        # Check user details
        u_row = conn.execute("SELECT full_name, phone, fin FROM users WHERE id = ?", (current_user.id,)).fetchone()
        user_name = (u_row["full_name"] if u_row and u_row["full_name"] else None) or "Müştəri"
        user_phone = (u_row["phone"] if u_row and u_row["phone"] else None) or "+994776346310"
        user_fin = (u_row["fin"] if u_row and u_row["fin"] else None) or "814CRM4"

        # Insert order
        conn.execute(
            """INSERT INTO orders 
               (id, user_id, platform, temu_order_ref, tracking_number, carrier, receiver_name, 
                receiver_phone, fin, original_amount, original_currency, fx_rate_to_azn, 
                fx_rate_to_usd, invoice_amount_azn, invoice_amount_usd, temu_invoice_amount,
                temu_invoice_currency, status, extra, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'AZN', 1.0, 0.5882, ?, ?, ?, 'AZN', 'Yoldadır', '{}', ?, ?)""",
            (
                parcel_id,
                current_user.id,
                platform,
                f"KP-{uuid.uuid4().hex[:8]}",
                clean_tracking,
                carrier,
                user_name,
                user_phone,
                user_fin,
                amount_azn,
                amount_azn,
                amount_usd,
                amount_azn,
                now_str,
                now_str,
            ),
        )

        # Insert primary order item
        item_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO order_items 
               (id, order_id, title, main_cat, sub_cat, quantity, unit_price, price_unknown, total_price, currency, unit_price_azn, total_price_azn, total_price_usd, extra)
               VALUES (?, ?, ?, 'Geyim aksesuarları', 'Digər', 1, ?, 0, ?, 'AZN', ?, ?, ?, '{}')""",
            (
                item_id,
                parcel_id,
                req.title.strip(),
                amount_azn,
                amount_azn,
                amount_azn,
                amount_azn,
                amount_usd,
            ),
        )
        conn.commit()

        return ParcelResponse(
            id=parcel_id,
            user_id=current_user.id,
            platform=platform,
            tracking_number=clean_tracking,
            carrier=carrier,
            title=req.title.strip(),
            invoice_amount_usd=amount_usd,
            invoice_amount_azn=amount_azn,
            status="Yoldadır",
            created_at=now_str,
        )


@router.get("/parcels/{parcel_id}", response_model=ParcelResponse)
async def get_user_parcel_detail(
    parcel_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ParcelResponse:
    """Fetches single parcel ensuring strict IDOR isolation (only owner can access)."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT o.id, o.user_id, o.platform, o.tracking_number, o.carrier, 
                      COALESCE(i.title, 'Xarici bağlama') as title,
                      COALESCE(o.invoice_amount_usd, 0.0) as invoice_amount_usd,
                      COALESCE(o.invoice_amount_azn, 0.0) as invoice_amount_azn,
                      o.status, o.created_at
               FROM orders o
               LEFT JOIN order_items i ON o.id = i.order_id
               WHERE o.id = ? AND o.user_id = ?
               LIMIT 1""",
            (parcel_id, current_user.id),
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bağlama tapılmadı və ya bu hesaba aid deyil.",
            )

        return ParcelResponse(
            id=row["id"],
            user_id=row["user_id"],
            platform=row["platform"] or "Digər",
            tracking_number=row["tracking_number"] or "Yoxdur",
            carrier=row["carrier"] or "STAREX",
            title=row["title"],
            invoice_amount_usd=round(float(row["invoice_amount_usd"]), 2),
            invoice_amount_azn=round(float(row["invoice_amount_azn"]), 2),
            status=row["status"] or "Yoldadır",
            created_at=str(row["created_at"]),
        )


@router.delete("/parcels/{parcel_id}")
async def delete_user_parcel(
    parcel_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Deletes a parcel owned by the user (IDOR protected)."""
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT id FROM orders WHERE id = ? AND user_id = ?",
            (parcel_id, current_user.id),
        ).fetchone()

        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bağlama tapılmadı və ya bu hesaba aid deyil.",
            )

        conn.execute("DELETE FROM order_items WHERE order_id = ?", (parcel_id,))
        conn.execute("DELETE FROM orders WHERE id = ? AND user_id = ?", (parcel_id, current_user.id))
        conn.commit()

        return {"status": "success", "message": "Bağlama uğurla silindi."}


# ==============================================================================
# Dynamic DGK 300$ Quota Calculation
# ==============================================================================

@router.get("/quota", response_model=QuotaResponse)
async def get_user_quota(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> QuotaResponse:
    """Calculates real-time DGK 300 USD monthly quota usage dynamically for the authenticated user."""
    monthly_limit = 300.0

    with get_connection() as conn:
        u_row = conn.execute("SELECT fin FROM users WHERE id = ?", (current_user.id,)).fetchone()
        user_fin = (u_row["fin"] if u_row else None) or "814CRM4"

        total_spent = conn.execute(
            "SELECT COALESCE(SUM(invoice_amount_usd), 0.0) FROM orders WHERE user_id = ?",
            (current_user.id,),
        ).fetchone()[0] or 0.0

    total_spent_usd = round(float(total_spent), 2)
    remaining_usd = round(max(0.0, monthly_limit - total_spent_usd), 2)
    spent_azn = round(total_spent_usd * 1.70, 2)
    remaining_azn = round(remaining_usd * 1.70, 2)

    if total_spent_usd < 250.0:
        quota_status = "safe"
    elif total_spent_usd <= 290.0:
        quota_status = "warning"
    else:
        quota_status = "danger"

    duty_estimate_azn = 0.0
    if total_spent_usd > 300.0:
        excess_usd = total_spent_usd - 300.0
        duty_estimate_azn = round(excess_usd * 1.70 * 0.36 + 15.0, 2)

    return QuotaResponse(
        user_id=current_user.id,
        fin=user_fin,
        monthly_limit_usd=monthly_limit,
        total_spent_usd=total_spent_usd,
        remaining_usd=remaining_usd,
        spent_azn=spent_azn,
        remaining_azn=remaining_azn,
        status=quota_status,
        duty_estimate_azn=duty_estimate_azn,
        reassurance_message="✓ Bağlamanız müsadirə olunmur. 300 USD limiti aşıldıqda yalnız fərq hissəsinə 36% rüsum və 15 AZN gömrük xərci hesablanır.",
    )


# ==============================================================================
# Data Sovereignty: Export / Import / Wipe (Portability & Right to be Forgotten)
# ==============================================================================

@router.get("/export", response_model=DataExportBundle)
async def export_user_data(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> DataExportBundle:
    """Exports all personal profile, parcels, and customs quota history for the authenticated user.
    Strict tenant isolation is guaranteed.
    """
    now_str = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        # 1. Profile
        u_row = conn.execute("SELECT * FROM users WHERE id = ?", (current_user.id,)).fetchone()
        if not u_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="İstifadəçi profili tapılmadı.")
        user_data = dict(u_row)
        profile_dict = {
            "id": user_data["id"],
            "email": user_data["email"],
            "full_name": user_data["full_name"],
            "phone": user_data.get("phone"),
            "role": user_data["role"],
            "status": user_data.get("status", "active"),
            "tier": user_data.get("tier", "cloud_managed"),
            "fin": user_data.get("fin") or "814CRM4",
            "default_branch": user_data.get("default_branch") or "28 May",
            "notification_whatsapp": bool(user_data.get("notification_whatsapp", 1)),
            "notification_email": bool(user_data.get("notification_email", 1)),
            "created_at": str(user_data.get("created_at")),
        }

        # 2. Parcels
        order_rows = conn.execute(
            """SELECT id, user_id, platform, temu_order_ref, tracking_number, carrier, receiver_name, 
                      receiver_phone, fin, original_amount, original_currency, fx_rate_to_azn, 
                      fx_rate_to_usd, invoice_amount_azn, invoice_amount_usd, status, created_at
               FROM orders 
               WHERE user_id = ? 
               ORDER BY created_at DESC""",
            (current_user.id,),
        ).fetchall()

        parcels: List[ExportedParcel] = []
        for o in order_rows:
            item_rows = conn.execute(
                """SELECT title, main_cat, sub_cat, quantity, unit_price, total_price, currency, 
                          unit_price_azn, total_price_azn, total_price_usd 
                   FROM order_items 
                   WHERE order_id = ?""",
                (o["id"],),
            ).fetchall()

            items = [
                ExportedParcelItem(
                    title=it["title"],
                    main_cat=it["main_cat"] or "Geyim aksesuarları",
                    sub_cat=it["sub_cat"] or "Digər",
                    quantity=int(it["quantity"] or 1),
                    unit_price=float(it["unit_price"] or 0.0),
                    total_price=float(it["total_price"] or 0.0),
                    currency=it["currency"] or "AZN",
                    total_price_azn=float(it["total_price_azn"] or 0.0),
                    total_price_usd=float(it["total_price_usd"] or 0.0),
                )
                for it in item_rows
            ]

            first_title = items[0].title if items else (o["tracking_number"] or "Xarici bağlama")
            parcels.append(
                ExportedParcel(
                    id=o["id"],
                    platform=o["platform"] or "Digər",
                    tracking_number=o["tracking_number"] or "Yoxdur",
                    carrier=o["carrier"] or "STAREX",
                    title=first_title,
                    receiver_name=o["receiver_name"],
                    receiver_phone=o["receiver_phone"],
                    fin=o["fin"],
                    invoice_amount_usd=round(float(o["invoice_amount_usd"] or 0.0), 2),
                    invoice_amount_azn=round(float(o["invoice_amount_azn"] or 0.0), 2),
                    status=o["status"] or "Yoldadır",
                    created_at=str(o["created_at"]),
                    items=items,
                )
            )

        # 3. Quota Summary
        total_spent = conn.execute(
            "SELECT COALESCE(SUM(invoice_amount_usd), 0.0) FROM orders WHERE user_id = ?",
            (current_user.id,),
        ).fetchone()[0] or 0.0
        total_spent_usd = round(float(total_spent), 2)
        remaining_usd = round(max(0.0, 300.0 - total_spent_usd), 2)
        quota_dict = {
            "monthly_limit_usd": 300.0,
            "total_spent_usd": total_spent_usd,
            "remaining_usd": remaining_usd,
            "spent_azn": round(total_spent_usd * 1.70, 2),
            "remaining_azn": round(remaining_usd * 1.70, 2),
            "status": "safe" if total_spent_usd < 250.0 else ("warning" if total_spent_usd <= 290.0 else "danger"),
        }

    return DataExportBundle(
        schema_version="4.5.0",
        service="kargopilot-core",
        exported_at=now_str,
        user_profile=profile_dict,
        parcels=parcels,
        quota_summary=quota_dict,
    )


@router.post("/import", response_model=ImportDataResponse)
async def import_user_data(
    req: ImportDataRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> ImportDataResponse:
    """Imports an exported KargoPilot JSON dataset into the authenticated user's account.
    Prevents duplicate tracking records and updates the quota dynamically.
    """
    if not req.parcels:
        return ImportDataResponse(
            status="success",
            message="İdxal ediləcək bağlama tapılmadı.",
            imported_count=0,
            skipped_count=0,
            total_parcels=0,
            updated_quota=await get_user_quota(current_user),
        )

    imported_count = 0
    skipped_count = 0
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        u_row = conn.execute("SELECT full_name, phone, fin FROM users WHERE id = ?", (current_user.id,)).fetchone()
        fallback_name = (u_row["full_name"] if u_row and u_row["full_name"] else None) or "Müştəri"
        fallback_phone = (u_row["phone"] if u_row and u_row["phone"] else None) or "+994776346310"
        fallback_fin = (u_row["fin"] if u_row and u_row["fin"] else None) or "814CRM4"

        for p in req.parcels:
            clean_tracking = p.tracking_number.strip().upper()
            existing = conn.execute(
                "SELECT id FROM orders WHERE user_id = ? AND UPPER(tracking_number) = ?",
                (current_user.id, clean_tracking),
            ).fetchone()
            if existing:
                skipped_count += 1
                continue

            order_id = str(uuid.uuid4())
            amount_usd = round(p.invoice_amount_usd, 2)
            amount_azn = round(p.invoice_amount_azn if p.invoice_amount_azn else amount_usd * 1.70, 2)
            platform = p.platform.strip() or "Digər"
            carrier = p.carrier.strip().upper() or "STAREX"
            title = p.title.strip() or "İdxal edilmiş bağlama"
            r_name = p.receiver_name or fallback_name
            r_phone = p.receiver_phone or fallback_phone
            r_fin = p.fin or fallback_fin

            conn.execute(
                """INSERT INTO orders 
                   (id, user_id, platform, temu_order_ref, tracking_number, carrier, receiver_name, 
                    receiver_phone, fin, original_amount, original_currency, fx_rate_to_azn, 
                    fx_rate_to_usd, invoice_amount_azn, invoice_amount_usd, temu_invoice_amount,
                    temu_invoice_currency, status, extra, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'AZN', 1.0, 0.5882, ?, ?, ?, 'AZN', ?, '{}', ?, ?)""",
                (
                    order_id,
                    current_user.id,
                    platform,
                    f"KP-{uuid.uuid4().hex[:8]}",
                    clean_tracking,
                    carrier,
                    r_name,
                    r_phone,
                    r_fin,
                    amount_azn,
                    amount_azn,
                    amount_usd,
                    amount_azn,
                    p.status or "Yoldadır",
                    now_str,
                    now_str,
                ),
            )

            if p.items:
                for it in p.items:
                    item_id = str(uuid.uuid4())
                    it_usd = float(it.total_price_usd) if it.total_price_usd else amount_usd
                    it_azn = float(it.total_price_azn) if it.total_price_azn else amount_azn
                    unit_azn = it.unit_price_azn if it.unit_price_azn is not None else (it.unit_price or it_azn)
                    conn.execute(
                        """INSERT INTO order_items 
                           (id, order_id, title, main_cat, sub_cat, quantity, unit_price, price_unknown, total_price, currency, unit_price_azn, total_price_azn, total_price_usd, extra)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, '{}')""",
                        (
                            item_id,
                            order_id,
                            it.title.strip(),
                            it.main_cat or "Geyim aksesuarları",
                            it.sub_cat or "Digər",
                            it.quantity,
                            it.unit_price or it_azn,
                            it_azn,
                            it.currency or "AZN",
                            unit_azn,
                            it_azn,
                            it_usd,
                        ),
                    )
            else:
                item_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO order_items 
                       (id, order_id, title, main_cat, sub_cat, quantity, unit_price, price_unknown, total_price, currency, unit_price_azn, total_price_azn, total_price_usd, extra)
                       VALUES (?, ?, ?, 'Geyim aksesuarları', 'Digər', 1, ?, 0, ?, 'AZN', ?, ?, ?, '{}')""",
                    (
                        item_id,
                        order_id,
                        title,
                        amount_azn,
                        amount_azn,
                        amount_azn,
                        amount_azn,
                        amount_usd,
                    ),
                )
            imported_count += 1

        conn.commit()

        if req.user_profile:
            fin = req.user_profile.get("fin")
            branch = req.user_profile.get("default_branch")
            if fin or branch:
                conn.execute(
                    """UPDATE users SET fin = COALESCE(?, fin), default_branch = COALESCE(?, default_branch) WHERE id = ?""",
                    (fin, branch, current_user.id),
                )
                conn.commit()

    updated_quota = await get_user_quota(current_user)

    return ImportDataResponse(
        status="success",
        message=f"{imported_count} bağlama uğurla idxal edildi ({skipped_count} dublikat saxlanıldı).",
        imported_count=imported_count,
        skipped_count=skipped_count,
        total_parcels=imported_count + skipped_count,
        updated_quota=updated_quota,
    )


@router.delete("/account-data", response_model=WipeDataResponse)
async def wipe_user_account_data(
    confirm_wipe: bool = Query(False, description="Məlumatların silinməsini təsdiqləyən flag"),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> WipeDataResponse:
    """Wipes all personal parcels and customs data for the current user (Right to be Forgotten)."""
    if not confirm_wipe:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Məlumatların silinməsini təsdiqləmək üçün confirm_wipe=true parametri tələb olunur.",
        )

    with get_connection() as conn:
        orders = conn.execute("SELECT id FROM orders WHERE user_id = ?", (current_user.id,)).fetchall()
        order_ids = [r["id"] for r in orders]
        count = len(order_ids)

        if order_ids:
            placeholders = ",".join("?" for _ in order_ids)
            conn.execute(f"DELETE FROM order_items WHERE order_id IN ({placeholders})", order_ids)
            conn.execute("DELETE FROM orders WHERE user_id = ?", (current_user.id,))
            conn.commit()

    return WipeDataResponse(
        status="success",
        message="Bütün şəxsi bağlama və gömrük məlumatlarınız bulud serverindən tam silindi.",
        wiped_orders_count=count,
        remaining_quota_usd=300.0,
    )


# ==============================================================================
# Sovereign Node Health & Connection Verification (SSRF Protected)
# ==============================================================================

def validate_target_url(raw_url: str) -> str:
    cleaned = raw_url.strip()
    if not cleaned.startswith(("http://", "https://")):
        cleaned = "http://" + cleaned
    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Yalnız HTTP və ya HTTPS protokolu dəstəklənir.")
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("Server ünvanı təyin edilə bilmədi.")
    # Block cloud metadata addresses to prevent SSRF
    blocked = ("169.254.169.254", "metadata.google.internal", "100.100.100.200")
    if hostname in blocked or hostname.endswith(".internal"):
        raise ValueError("Təhlükəsizlik qaydalarına əsasən daxili metadata ünvanları qadağandır.")
    port_part = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{hostname}{port_part}"


async def verify_node_connection(target_url: str) -> VerifyNodeResponse:
    try:
        clean_url = validate_target_url(target_url)
    except ValueError as e:
        return VerifyNodeResponse(
            healthy=False,
            target_url=target_url,
            message=str(e),
        )

    health_url = f"{clean_url}/health"
    start_t = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=3.0, verify=False) as client:
            resp = await client.get(health_url)
            latency_ms = round((time.perf_counter() - start_t) * 1000, 1)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                return VerifyNodeResponse(
                    healthy=True,
                    target_url=clean_url,
                    service=data.get("service", "kargopilot-core"),
                    edition=data.get("edition", "sovereign"),
                    version=data.get("version", "4.5.0"),
                    latency_ms=latency_ms,
                    message="KargoPilot düyünü uğurla aşkarlandı və aktivdir.",
                )
            else:
                return VerifyNodeResponse(
                    healthy=False,
                    target_url=clean_url,
                    latency_ms=latency_ms,
                    message=f"Server cavab verdi, lakin status HTTP {resp.status_code} oldu.",
                )
    except Exception as exc:
        return VerifyNodeResponse(
            healthy=False,
            target_url=clean_url,
            message=f"Serverlə əlaqə qurula bilmədi ({type(exc).__name__}). Ünvanın və portun açıq olduğunu yoxlayın.",
        )


@router.post("/verify-node", response_model=VerifyNodeResponse)
async def verify_node_user_route(req: VerifyNodeRequest) -> VerifyNodeResponse:
    """Verifies reachability and version of a local or remote KargoPilot instance via user prefix."""
    return await verify_node_connection(req.target_url)


@system_router.post("/verify-node", response_model=VerifyNodeResponse)
async def verify_node_system_route(req: VerifyNodeRequest) -> VerifyNodeResponse:
    """Verifies reachability and version of a local or remote KargoPilot instance via system prefix."""
    return await verify_node_connection(req.target_url)


# ==============================================================================
# Smart Arbitrage & Customs Supervisor Engines (Etap 4)
# ==============================================================================

CARRIER_TARIFF_MATRIX = {
    "TR": [
        {"name": "Starex", "code": "STAREX", "base": 0.80, "per_kg": 4.20, "days_min": 3, "days_max": 5},
        {"name": "Expargo", "code": "EXPARGO", "base": 0.90, "per_kg": 4.10, "days_min": 4, "days_max": 6},
        {"name": "Dynamex", "code": "DYNAMEX", "base": 1.00, "per_kg": 4.50, "days_min": 3, "days_max": 4},
        {"name": "Camex", "code": "CAMEX", "base": 1.10, "per_kg": 4.30, "days_min": 4, "days_max": 5},
        {"name": "Mover", "code": "MOVER", "base": 1.20, "per_kg": 4.60, "days_min": 3, "days_max": 5},
        {"name": "KoliPlus", "code": "KOLIPLUS", "base": 1.00, "per_kg": 4.40, "days_min": 4, "days_max": 6},
    ],
    "CN": [
        {"name": "Camex", "code": "CAMEX", "base": 2.00, "per_kg": 9.00, "days_min": 8, "days_max": 12},
        {"name": "Starex", "code": "STAREX", "base": 2.50, "per_kg": 9.50, "days_min": 7, "days_max": 10},
        {"name": "Expargo", "code": "EXPARGO", "base": 2.80, "per_kg": 9.20, "days_min": 7, "days_max": 11},
        {"name": "KoliPlus", "code": "KOLIPLUS", "base": 2.60, "per_kg": 9.80, "days_min": 8, "days_max": 12},
        {"name": "Dynamex", "code": "DYNAMEX", "base": 3.00, "per_kg": 10.00, "days_min": 6, "days_max": 9},
        {"name": "Mover", "code": "MOVER", "base": 3.20, "per_kg": 10.50, "days_min": 6, "days_max": 10},
    ],
    "US": [
        {"name": "Camex", "code": "CAMEX", "base": 3.00, "per_kg": 8.50, "days_min": 5, "days_max": 8},
        {"name": "Expargo", "code": "EXPARGO", "base": 3.20, "per_kg": 8.80, "days_min": 6, "days_max": 9},
        {"name": "KoliPlus", "code": "KOLIPLUS", "base": 3.40, "per_kg": 8.90, "days_min": 6, "days_max": 9},
        {"name": "Starex", "code": "STAREX", "base": 3.50, "per_kg": 9.00, "days_min": 5, "days_max": 7},
        {"name": "Dynamex", "code": "DYNAMEX", "base": 3.80, "per_kg": 9.50, "days_min": 4, "days_max": 7},
        {"name": "Mover", "code": "MOVER", "base": 4.00, "per_kg": 9.20, "days_min": 5, "days_max": 8},
    ],
    "EU": [
        {"name": "Dynamex", "code": "DYNAMEX", "base": 2.50, "per_kg": 7.50, "days_min": 5, "days_max": 7},
        {"name": "Expargo", "code": "EXPARGO", "base": 2.70, "per_kg": 7.70, "days_min": 6, "days_max": 9},
        {"name": "Camex", "code": "CAMEX", "base": 2.80, "per_kg": 7.80, "days_min": 6, "days_max": 8},
        {"name": "KoliPlus", "code": "KOLIPLUS", "base": 2.90, "per_kg": 7.90, "days_min": 6, "days_max": 8},
        {"name": "Starex", "code": "STAREX", "base": 3.00, "per_kg": 7.60, "days_min": 5, "days_max": 8},
        {"name": "Mover", "code": "MOVER", "base": 3.10, "per_kg": 8.00, "days_min": 5, "days_max": 7},
    ],
}


@router.post("/arbitrage/calculate", response_model=ArbitrageResponse)
async def calculate_smart_arbitrage(
    req: ArbitrageCalculateRequest,
) -> ArbitrageResponse:
    """Calculates shipping tariffs across all major carriers with volumetric weight, surcharges, and savings optimization."""
    # Volumetric weight calculation: (L * W * H) / 6000
    volumetric_weight_kg: Optional[float] = None
    if (
        req.length_cm is not None
        and req.width_cm is not None
        and req.height_cm is not None
        and req.length_cm > 0
        and req.width_cm > 0
        and req.height_cm > 0
    ):
        volumetric_weight_kg = round((req.length_cm * req.width_cm * req.height_cm) / 6000.0, 3)
        chargeable_weight_kg = round(max(req.weight_kg, volumetric_weight_kg), 2)
    else:
        chargeable_weight_kg = round(req.weight_kg, 2)

    # Type surcharges
    parcel_type_norm = req.parcel_type.lower().strip()
    if parcel_type_norm == "liquid":
        surcharge_usd = 1.50
        type_note = "Maye/kosmetika əlavəsi daxildir (+$1.50)"
    elif parcel_type_norm == "electronics":
        surcharge_usd = 1.00
        type_note = "Elektronika/batareya əlavəsi daxildir (+$1.00)"
    else:
        parcel_type_norm = "standard"
        surcharge_usd = 0.0
        type_note = "Standart tarif"

    origin = req.origin_country.upper().strip()
    tariff_list = CARRIER_TARIFF_MATRIX.get(origin, CARRIER_TARIFF_MATRIX["TR"])

    computed_carriers: List[Dict[str, Any]] = []
    for c in tariff_list:
        raw_usd = c["base"] + (c["per_kg"] * chargeable_weight_kg) + surcharge_usd
        rate_usd = round(raw_usd, 2)
        rate_azn = round(rate_usd * 1.70, 2)
        computed_carriers.append({
            "carrier_name": c["name"],
            "carrier_code": c["code"],
            "chargeable_weight_kg": chargeable_weight_kg,
            "rate_usd": rate_usd,
            "rate_azn": rate_azn,
            "delivery_days_min": c["days_min"],
            "delivery_days_max": c["days_max"],
            "delivery_eta": f"{c['days_min']}-{c['days_max']} iş günü",
            "notes": type_note,
        })

    # Sort cheapest to most expensive
    computed_carriers.sort(key=lambda x: (x["rate_usd"], x["delivery_days_max"]))
    cheapest = computed_carriers[0]

    # Fastest carrier
    fastest = min(computed_carriers, key=lambda x: (x["delivery_days_max"], x["delivery_days_min"], x["rate_usd"]))

    max_usd = max(c["rate_usd"] for c in computed_carriers)
    min_usd = min(c["rate_usd"] for c in computed_carriers)
    max_savings_usd = round(max_usd - min_usd, 2)
    max_savings_azn = round(max_savings_usd * 1.70, 2)

    carrier_details: List[CarrierRateDetail] = []
    for c in computed_carriers:
        carrier_details.append(
            CarrierRateDetail(
                carrier_name=c["carrier_name"],
                carrier_code=c["carrier_code"],
                chargeable_weight_kg=c["chargeable_weight_kg"],
                rate_usd=c["rate_usd"],
                rate_azn=c["rate_azn"],
                delivery_days_min=c["delivery_days_min"],
                delivery_days_max=c["delivery_days_max"],
                delivery_eta=c["delivery_eta"],
                notes=c["notes"],
                is_cheapest=(c["carrier_code"] == cheapest["carrier_code"]),
                is_fastest=(c["carrier_code"] == fastest["carrier_code"]),
            )
        )

    return ArbitrageResponse(
        origin_country=origin,
        actual_weight_kg=round(req.weight_kg, 2),
        volumetric_weight_kg=volumetric_weight_kg,
        chargeable_weight_kg=chargeable_weight_kg,
        parcel_type=parcel_type_norm,
        best_value_carrier=cheapest["carrier_name"],
        fastest_carrier=fastest["carrier_name"],
        max_savings_usd=max_savings_usd,
        max_savings_azn=max_savings_azn,
        carriers=carrier_details,
    )


@router.post("/customs/simulate", response_model=CustomsSimulateResponse)
async def simulate_customs_supervisor(
    req: CustomsSimulateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> CustomsSimulateResponse:
    """Simulates monthly DGK 300$ quota impact, potential 36% customs duties, and compliance recommendations."""
    target_month = req.month.strip() if req.month and req.month.strip() else datetime.now(timezone.utc).strftime("%Y-%m")

    # Strict Tenant Scoping: query orders solely belonging to current_user.id in target_month
    with get_connection() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(invoice_amount_usd), 0.0)
               FROM orders
               WHERE user_id = ? AND (strftime('%Y-%m', created_at) = ? OR created_at LIKE ?)""",
            (current_user.id, target_month, f"{target_month}%"),
        ).fetchone()
        current_spent = float(row[0]) if row and row[0] is not None else 0.0

    current_spent_usd = round(current_spent, 2)
    item_usd = round(req.item_price_usd, 2)
    shipping_usd = round(req.shipping_fee_usd, 2)
    projected_total_usd = round(current_spent_usd + item_usd + shipping_usd, 2)
    projected_total_azn = round(projected_total_usd * 1.70, 2)

    MONTHLY_LIMIT = 300.0

    if projected_total_usd <= MONTHLY_LIMIT:
        exceeds_limit = False
        over_limit_usd = 0.0
        over_limit_azn = 0.0
        duty_usd = 0.0
        duty_azn = 0.0
        rem_usd = round(MONTHLY_LIMIT - projected_total_usd, 2)
        rem_azn = round(rem_usd * 1.70, 2)

        if projected_total_usd < 240.0:
            status_val = "safe"
            status_msg = f"Limit daxilindədir. 0% gömrük rüsumu. Aylıq 300$ limitindən {rem_usd:.2f} USD ({rem_azn:.2f} AZN) qalıq ehtiyatınız var."
            recs = [
                "Sifarişinizi təhlükəsiz şəkildə bəyan edə bilərsiniz.",
                f"300 USD limitinə çatmağa hələ ${rem_usd:.2f} USD qalıb.",
                "SmartCustoms və ya KargoPilot avtomatik bəyannaməsi ilə rüsumsuz keçəcək.",
            ]
        else:
            status_val = "warning"
            status_msg = f"Diqqət! Aylıq 300$ limitinə yaxınlaşırsınız. Qalan limit: {rem_usd:.2f} USD ({rem_azn:.2f} AZN)."
            recs = [
                "Bu sifariş hələlik rüsumsuzdur, lakin cari ayda növbəti sifarişlər 36% gömrük rüsumuna cəlb oluna bilər.",
                f"Ayın sonunadək əlavə sifariş edərkən ${rem_usd:.2f} USD ehtiyatınızı nəzərə alın.",
                "Növbəti bağlamaları gələn ayın 1-dən sonra çatdırılacaq şəkildə planlaşdırın.",
            ]
    else:
        exceeds_limit = True
        over_limit_usd = round(projected_total_usd - MONTHLY_LIMIT, 2)
        over_limit_azn = round(over_limit_usd * 1.70, 2)
        rem_usd = 0.0
        rem_azn = 0.0
        duty_usd = round(over_limit_usd * 0.36, 2)
        duty_azn = round(duty_usd * 1.70, 2)
        status_val = "danger"
        status_msg = f"300 USD limiti {over_limit_usd:.2f} USD aşıldı! Təxmini 36% vahid gömrük rüsumu: {duty_azn:.2f} AZN ({duty_usd:.2f} USD)."
        recs = [
            f"Limit aşımı: {over_limit_usd:.2f} USD. Hesablanmış 36% rüsum: {duty_azn:.2f} AZN ({duty_usd:.2f} USD).",
            "Sifarişi 2 hissəyə bölərək fərqli bağlamalarda göndərin.",
            "Sifarişi növbəti təqvim ayının 1-dən sonra bəyan edin.",
            "Və ya ailə üzvünün FİN kodu adına sifariş edin (KargoPilot Ailə Mesh).",
            "Əgər indi bəyan etsəniz, SmartCustoms portalında rüsumu onlayn ödəyə bilərsiniz.",
        ]

    return CustomsSimulateResponse(
        user_id=current_user.id,
        month=target_month,
        current_spent_usd=current_spent_usd,
        item_price_usd=item_usd,
        shipping_fee_usd=shipping_usd,
        projected_total_usd=projected_total_usd,
        projected_total_azn=projected_total_azn,
        exceeds_limit=exceeds_limit,
        remaining_allowance_usd=rem_usd,
        remaining_allowance_azn=rem_azn,
        over_limit_amount_usd=over_limit_usd,
        over_limit_amount_azn=over_limit_azn,
        duty_rate_percent=36.0,
        duty_usd=duty_usd,
        duty_azn=duty_azn,
        status=status_val,
        status_message=status_msg,
        recommendations=recs,
    )
