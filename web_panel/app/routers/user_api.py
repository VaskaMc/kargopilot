"""User Management, Personal Parcels, and Dynamic DGK Customs Quota API.

Enforces:
- Strict Tenant Scoping & Insecure Direct Object Reference (IDOR) protection.
- Input validation on parcels and profile parameters.
- Dynamic DGK 300 USD quota tracking per user session.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

try:
    from app.database import get_connection
    from app.security.rbac import AuthenticatedUser, get_current_user
except ImportError:
    from database import get_connection
    from security.rbac import AuthenticatedUser, get_current_user

logger = logging.getLogger("kargopilot.user.api")

router = APIRouter(prefix="/api/v1/user", tags=["User Dashboard & Personal Logistics"])


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
        # Strict user_id check
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
        # Fetch user's FIN
        u_row = conn.execute("SELECT fin FROM users WHERE id = ?", (current_user.id,)).fetchone()
        user_fin = (u_row["fin"] if u_row else None) or "814CRM4"

        # Calculate user's total spent USD from their orders
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
