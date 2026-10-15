"""Starex Carrier Adapter supporting both live api.starexglobal.com and v1 endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import httpx

from carriers.base_carrier import (
    BaseCarrier,
    CarrierAccountDTO,
    CarrierShipmentDTO,
    PreDeclarationRequest,
    ShipmentStatus,
)
from carriers.tariff_calculator import calculate_delivery_fee


class StarexCarrierAdapter(BaseCarrier):
    """Starex Azerbaijan API client (https://api.starexglobal.com and https://api.starex.az/v1)."""

    LIVE_BASE_URL = "https://api.starexglobal.com"
    LEGACY_BASE_URL = "https://api.starex.az/v1"
    WAREHOUSE_DEFAULTS = {
        "TR": "İstanbul, Avcılar, Cihangir mah. Şehit Jandarma Komando Er Hakan Öner sk.",
        "CN": "Guangzhou, Baiyun District, Jiahewanggang Warehouse No. 14",
        "US": "Delaware, New Castle, 2401 Ogletown Rd",
        "DE": "Frankfurt, Cargo City Süd, Building 537",
    }

    STATUS_MAP = {
        "waiting_for_arrival": ShipmentStatus.ON_THE_WAY.value,
        "yoldadır": ShipmentStatus.ON_THE_WAY.value,
        "on_the_way": ShipmentStatus.ON_THE_WAY.value,
        "yolda": ShipmentStatus.ON_THE_WAY.value,
        "declared": ShipmentStatus.PRE_DECLARED.value,
        "pre_declared": ShipmentStatus.PRE_DECLARED.value,
        "bəyan edilib": ShipmentStatus.PRE_DECLARED.value,
        "foreign_warehouse": ShipmentStatus.AT_FOREIGN_HUB.value,
        "xarici anbarda": ShipmentStatus.AT_FOREIGN_HUB.value,
        "customs": ShipmentStatus.CUSTOMS_INSPECTION.value,
        "gömrükdə": ShipmentStatus.CUSTOMS_INSPECTION.value,
        "baku_office": ShipmentStatus.AT_LOCAL_BRANCH.value,
        "filialda": ShipmentStatus.AT_LOCAL_BRANCH.value,
        "delivered": ShipmentStatus.DELIVERED.value,
        "təhvil verildi": ShipmentStatus.DELIVERED.value,
    }

    def __init__(
        self,
        account: CarrierAccountDTO,
        min_delay_sec: float = 0.05,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        if not account.warehouse_suites:
            account.warehouse_suites = dict(self.WAREHOUSE_DEFAULTS)
        super().__init__(
            carrier_name="STAREX",
            account=account,
            min_delay_sec=min_delay_sec,
            transport=transport,
        )
        self.base_url = self.LEGACY_BASE_URL if transport is not None else self.LIVE_BASE_URL
        self.is_live = transport is None

    async def authenticate(self) -> bool:
        if not self.account.auth_token:
            return False
        async with self._build_client(self.base_url) as client:
            endpoint = "/api/v1/starex/me" if self.is_live else "/user/profile"
            resp = await self._request_with_backoff(client, "GET", endpoint)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and isinstance(data["data"], dict):
                    data = data["data"]
                code = data.get("code") or data.get("customer_code")
                if code:
                    self.account.customer_id = code
                return bool(code or data.get("name") or self.account.customer_id)
            return False

    async def submit_pre_declaration(self, decl: PreDeclarationRequest) -> Dict[str, Any]:
        if not decl.invoice_pdf_path.exists():
            raise FileNotFoundError(f"Starex pre-declaration requires invoice PDF at {decl.invoice_pdf_path}")

        country_id = self.COUNTRY_MAP.get(decl.origin_country.upper(), 1)
        form_data = {
            "tracking_code": decl.origin_tracking,
            "order_ref": decl.order_ref,
            "country_id": str(country_id),
            "shop_name": decl.seller_name,
            "category_name": decl.dgk_main_cat,
            "category_id": str(decl.category_id or "101"),
            "product_title": decl.item_title,
            "quantity": str(decl.quantity),
            "price": f"{decl.invoice_amount:.2f}",
            "currency": decl.invoice_currency.upper(),
            "branch": decl.branch_id or self.account.default_branch,
        }
        pdf_bytes = decl.invoice_pdf_path.read_bytes()
        files = {
            "invoice_file": (
                decl.invoice_pdf_path.name,
                pdf_bytes,
                "application/pdf",
            )
        }

        async with self._build_client(self.base_url) as client:
            endpoint = "/api/v1/starex/declarations" if self.is_live else "/declarations/create"
            resp = await self._request_with_backoff(
                client,
                "POST",
                endpoint,
                data=form_data,
                files=files,
            )
            resp.raise_for_status()
            payload = resp.json()
            return {
                "carrier": "STAREX",
                "success": payload.get("success", True),
                "declaration_id": payload.get("declaration_id") or payload.get("id"),
                "destination_tracking": payload.get("awb") or payload.get("destination_tracking") or payload.get("tracking_number"),
                "status": ShipmentStatus.PRE_DECLARED.value,
                "raw": payload,
            }

    def _normalize_shipment(self, raw: Dict[str, Any]) -> CarrierShipmentDTO:
        raw_status = str(raw.get("status") or raw.get("status_name") or "PRE_DECLARED").lower().strip()
        norm_status = self.STATUS_MAP.get(raw_status, ShipmentStatus.PRE_DECLARED.value)
        country = str(raw.get("country_iso") or raw.get("origin_country") or "TR").upper()
        weight = float(raw["weight"]) if raw.get("weight") is not None else (float(raw["weight_kg"]) if raw.get("weight_kg") is not None else None)
        fee_usd, fee_azn = calculate_delivery_fee("STAREX", country, weight)
        if raw.get("shipping_usd_price") is not None and float(raw.get("shipping_usd_price") or 0) > 0:
            fee_usd = float(raw["shipping_usd_price"])
            fee_azn = round(fee_usd * 1.70, 2)
        elif raw.get("delivery_fee_usd") is not None:
            fee_usd = float(raw["delivery_fee_usd"])
            fee_azn = round(fee_usd * 1.70, 2)

        return CarrierShipmentDTO(
            carrier="STAREX",
            order_ref=str(raw.get("order_ref") or raw.get("external_order_id") or ""),
            origin_tracking=str(raw.get("tracking_code") or raw.get("origin_tracking") or raw.get("short_tracking_number") or ""),
            destination_tracking=raw.get("tracking_number") or raw.get("awb") or raw.get("destination_tracking"),
            smart_customs_no=raw.get("smart_customs_no"),
            status=norm_status,
            origin_country=country,
            seller_name=raw.get("store_name") or raw.get("shop_name") or raw.get("seller_name"),
            declared_amount=float(raw["product_price"]) if raw.get("product_price") is not None else (float(raw["price"]) if raw.get("price") is not None else None),
            declared_currency=raw.get("product_price_currency") or raw.get("currency"),
            weight_kg=weight,
            delivery_fee_usd=fee_usd if weight else None,
            delivery_fee_azn=fee_azn if weight else None,
            events=raw.get("events") or [],
        )

    async def fetch_active_shipments(self) -> List[CarrierShipmentDTO]:
        async with self._build_client(self.base_url) as client:
            endpoint = "/api/v1/starex/packages" if self.is_live else "/shipments/active"
            resp = await self._request_with_backoff(client, "GET", endpoint)
            resp.raise_for_status()
            body = resp.json()
            items = body.get("data") if isinstance(body, dict) else body
            return [self._normalize_shipment(item) for item in (items or [])]

    async def track_by_origin(self, origin_tracking: str) -> Optional[CarrierShipmentDTO]:
        shipments = await self.fetch_active_shipments()
        needle = origin_tracking.strip().upper()
        for sh in shipments:
            if sh.origin_tracking.strip().upper() == needle:
                return sh
        return None
