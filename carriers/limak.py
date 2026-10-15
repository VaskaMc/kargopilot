"""Limak (limak.az) Carrier Adapter for TR (Istanbul), CN (Guangzhou), and US hubs."""



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





class LimakCarrierAdapter(BaseCarrier):

    """Limak Azerbaijan API v1 client (https://limak.az/api/v1)."""



    BASE_URL = "https://limak.az/api/v1"

    WAREHOUSE_DEFAULTS = {

        "TR": "İstanbul, Halkalı Merkez Mah., Dereboyu Cad. Limak Lojistik",

        "CN": "Guangzhou, Limak Air Cargo Hub, Suite LMX",

        "US": "New Jersey, Carlstadt, 600 Washington Ave",

    }



    STATUS_MAP = {

        "sifariş verildi": ShipmentStatus.PRE_DECLARED.value,

        "bəyan edildi": ShipmentStatus.PRE_DECLARED.value,

        "pre_declared": ShipmentStatus.PRE_DECLARED.value,

        "xarici anbarda": ShipmentStatus.AT_FOREIGN_HUB.value,

        "at_foreign_hub": ShipmentStatus.AT_FOREIGN_HUB.value,

        "yolda": ShipmentStatus.ON_THE_WAY.value,

        "on_the_way": ShipmentStatus.ON_THE_WAY.value,

        "gömrük yoxlanışı": ShipmentStatus.CUSTOMS_INSPECTION.value,

        "filialda": ShipmentStatus.AT_LOCAL_BRANCH.value,

        "bakı anbarı": ShipmentStatus.AT_LOCAL_BRANCH.value,

        "təhvil verildi": ShipmentStatus.DELIVERED.value,

        "delivered": ShipmentStatus.DELIVERED.value,

    }



    CURRENCY_TYPE_MAP = {"TRY": "1", "USD": "2", "CNY": "3", "EUR": "4", "AZN": "5"}



    def __init__(

        self,

        account: CarrierAccountDTO,

        min_delay_sec: float = 0.05,

        transport: Optional[httpx.AsyncBaseTransport] = None,

    ) -> None:

        if not account.warehouse_suites:

            account.warehouse_suites = dict(self.WAREHOUSE_DEFAULTS)

        super().__init__(

            carrier_name="LIMAK",

            account=account,

            min_delay_sec=min_delay_sec,

            transport=transport,

        )



    async def authenticate(self) -> bool:

        if not self.account.auth_token:

            return False

        async with self._build_client(self.BASE_URL) as client:

            resp = await self._request_with_backoff(client, "GET", "/user/me")

            if resp.status_code == 200:

                data = resp.json()

                return bool(data.get("status") == "ok" or data.get("id") or data.get("customer_id"))

            return False



    async def submit_pre_declaration(self, decl: PreDeclarationRequest) -> Dict[str, Any]:

        if not decl.invoice_pdf_path.exists():

            raise FileNotFoundError(f"Limak pre-declaration requires invoice PDF at {decl.invoice_pdf_path}")



        currency_code = self.CURRENCY_TYPE_MAP.get(decl.invoice_currency.upper(), "2")

        form_data = {

            "tracking_no": decl.origin_tracking,

            "order_ref": decl.order_ref,

            "country": decl.origin_country.upper(),

            "store_name": decl.seller_name,

            "product_category_id": str(decl.category_id or "12"),

            "dgk_category": decl.dgk_main_cat,

            "product_name": decl.item_title,

            "quantity": str(decl.quantity),

            "invoice_price": f"{decl.invoice_amount:.2f}",

            "currency_type": currency_code,

            "currency_code": decl.invoice_currency.upper(),

            "branch_name": decl.branch_id or self.account.default_branch,

        }

        pdf_bytes = decl.invoice_pdf_path.read_bytes()

        files = {

            "file": (

                decl.invoice_pdf_path.name,

                pdf_bytes,

                "application/pdf",

            )

        }



        async with self._build_client(self.BASE_URL) as client:

            resp = await self._request_with_backoff(

                client,

                "POST",

                "/user/declarations",

                data=form_data,

                files=files,

            )

            resp.raise_for_status()

            payload = resp.json()

            return {

                "carrier": "LIMAK",

                "success": True,

                "declaration_id": payload.get("declaration_id") or payload.get("id"),

                "destination_tracking": payload.get("limak_track") or payload.get("destination_tracking"),

                "status": ShipmentStatus.PRE_DECLARED.value,

                "raw": payload,

            }



    def _normalize_shipment(self, raw: Dict[str, Any]) -> CarrierShipmentDTO:

        raw_status = str(raw.get("status_label") or raw.get("status") or "PRE_DECLARED").lower().strip()

        norm_status = self.STATUS_MAP.get(raw_status, ShipmentStatus.PRE_DECLARED.value)

        country = str(raw.get("country") or raw.get("origin_country") or "TR").upper()

        weight = float(raw["weight"]) if raw.get("weight") is not None else (

            float(raw["weight_kg"]) if raw.get("weight_kg") is not None else None

        )

        fee_usd, fee_azn = calculate_delivery_fee("LIMAK", country, weight)



        return CarrierShipmentDTO(

            carrier="LIMAK",

            order_ref=str(raw.get("order_ref") or ""),

            origin_tracking=str(raw.get("tracking_no") or raw.get("origin_tracking") or ""),

            destination_tracking=raw.get("limak_track") or raw.get("destination_tracking"),

            smart_customs_no=raw.get("smart_customs_no"),

            status=norm_status,

            origin_country=country,

            seller_name=raw.get("store_name") or raw.get("seller_name"),

            declared_amount=float(raw["invoice_price"]) if raw.get("invoice_price") is not None else None,

            declared_currency=raw.get("currency_code") or "TRY",

            weight_kg=weight,

            delivery_fee_usd=fee_usd if weight else None,

            delivery_fee_azn=fee_azn if weight else None,

            events=raw.get("history") or [],

        )



    async def fetch_active_shipments(self) -> List[CarrierShipmentDTO]:

        async with self._build_client(self.BASE_URL) as client:

            resp = await self._request_with_backoff(client, "GET", "/user/packages")

            resp.raise_for_status()

            body = resp.json()

            packages = body.get("packages") if isinstance(body, dict) else body

            return [self._normalize_shipment(pkg) for pkg in (packages or [])]



    async def track_by_origin(self, origin_tracking: str) -> Optional[CarrierShipmentDTO]:

        packages = await self.fetch_active_shipments()

        needle = origin_tracking.strip().upper()

        for pkg in packages:

            if pkg.origin_tracking.strip().upper() == needle:

                return pkg

        return None
