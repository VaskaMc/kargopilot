"""Dynamex (dynamex.az) Carrier Adapter for TR, US, and CN hubs."""

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


class DynamexCarrierAdapter(BaseCarrier):
    """Dynamex Azerbaijan client (https://dynamex.az)."""

    BASE_URL = "https://api.dynamex.az/v1"
    WAREHOUSE_DEFAULTS = {
        "TR": "İstanbul, Başakşehir, İkitelli OSB",
        "CN": "Guangzhou, Baiyun, Dynamex Depot",
        "US": "Delaware, New Castle",
    }

    STATUS_MAP = {
        "pre_declared": ShipmentStatus.PRE_DECLARED.value,
        "anbarda": ShipmentStatus.AT_FOREIGN_HUB.value,
        "yolda": ShipmentStatus.ON_THE_WAY.value,
        "gomrukde": ShipmentStatus.CUSTOMS_INSPECTION.value,
        "filialda": ShipmentStatus.AT_LOCAL_BRANCH.value,
        "catdirildi": ShipmentStatus.DELIVERED.value,
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
            carrier_name="DYNAMEX",
            account=account,
            min_delay_sec=min_delay_sec,
            transport=transport,
        )

    async def authenticate(self) -> bool:
        return bool(self.account.auth_token)

    async def submit_pre_declaration(self, decl: PreDeclarationRequest) -> Dict[str, Any]:
        return {
            "success": True,
            "carrier": "DYNAMEX",
            "declaration_id": f"DYN-{decl.origin_tracking[-6:]}",
            "tracking": decl.origin_tracking,
        }

    async def fetch_active_shipments(self) -> List[CarrierShipmentDTO]:
        return []

    async def track_by_origin(self, origin_tracking: str) -> Optional[CarrierShipmentDTO]:
        return None
