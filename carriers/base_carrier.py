"""BaseCarrier abstract interface, DTOs, and HTTP retry/backoff utilities for Azerbaijani cargo carriers."""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger("pcs.carriers")


class ShipmentStatus(str, Enum):
    PRE_DECLARED = "PRE_DECLARED"
    AT_FOREIGN_HUB = "AT_FOREIGN_HUB"
    ON_THE_WAY = "ON_THE_WAY"
    CUSTOMS_INSPECTION = "CUSTOMS_INSPECTION"
    AT_LOCAL_BRANCH = "AT_LOCAL_BRANCH"
    DELIVERED = "DELIVERED"
    ERROR = "ERROR"


class CarrierAccountDTO(BaseModel):
    id: Optional[str] = None
    carrier_name: str = Field(..., description="STAREX, LIMAK, CAMEX, DYNAMEX")
    customer_id: str = Field(..., description="Customer suite/code, e.g. ST123456, ST-98241, LMX-10294")
    auth_token: Optional[str] = Field(default=None, description="JWT / Bearer / Session cookie JSON")
    email: Optional[str] = None
    phone: Optional[str] = None
    default_branch: str = "28 May"
    is_active: bool = True
    warehouse_suites: Dict[str, str] = Field(default_factory=dict)
    last_sync_at: Optional[datetime] = None


class PreDeclarationRequest(BaseModel):
    order_ref: str = Field(..., description="Order Ref, e.g. TB-394829104819284712 or TY-98234123")
    platform: str = Field(..., description="Trendyol, Taobao, Temu, Amazon")
    origin_country: str = Field(..., description="TR, CN, US, DE")
    origin_tracking: str = Field(..., description="Domestic tracking code: Aras, Trendyol Express, SF Express, ZTO")
    seller_name: str = Field(..., description="Store / merchant name")
    category_id: Optional[str] = Field(default=None, description="Carrier internal category ID")
    dgk_main_cat: str = Field(..., description="One of 37 official DGK SmartCustoms categories")
    item_title: str = Field(..., description="Aggregated or primary item description")
    quantity: int = Field(default=1, ge=1)
    invoice_amount: float = Field(..., gt=0.0)
    invoice_currency: str = Field(..., description="TRY, CNY, USD, EUR, AZN")
    invoice_pdf_path: Path = Field(..., description="Path to generated Commercial Invoice PDF")
    branch_id: Optional[str] = Field(default="28 May", description="Local pickup branch in Baku")
    notes: Optional[str] = None


class CarrierShipmentDTO(BaseModel):
    carrier: str
    order_ref: str
    origin_tracking: str
    destination_tracking: Optional[str] = None  # e.g. STRAZ98214401, LMX7712390, CAM441209
    smart_customs_no: Optional[str] = None      # e.g. 6261008017984
    status: str = ShipmentStatus.PRE_DECLARED.value
    origin_country: str = "TR"
    seller_name: Optional[str] = None
    declared_amount: Optional[float] = None
    declared_currency: Optional[str] = None
    weight_kg: Optional[float] = None
    delivery_fee_usd: Optional[float] = None
    delivery_fee_azn: Optional[float] = None
    events: List[Dict[str, Any]] = Field(default_factory=list)


class BaseCarrier(ABC):
    """Standard abstract interface for Azerbaijani freight forwarders."""

    COUNTRY_MAP: Dict[str, int] = {"TR": 1, "US": 2, "CN": 3, "DE": 4, "AE": 5}

    def __init__(
        self,
        carrier_name: str,
        account: CarrierAccountDTO,
        min_delay_sec: float = 0.05,
        max_retries: int = 3,
        transport: Optional[httpx.AsyncBaseTransport] = None,
    ) -> None:
        self.carrier_name = carrier_name.upper()
        self.account = account
        self.min_delay_sec = min_delay_sec
        self.max_retries = max_retries
        self._transport = transport
        self._last_request_ts: float = 0.0

    def _build_client(
        self,
        base_url: str,
        extra_headers: Optional[Dict[str, str]] = None,
        verify: bool = True,
    ) -> httpx.AsyncClient:
        headers = {
            "User-Agent": "PCS-Core/3.0 (AlmaLinux 9.8; +https://127.0.0.1:48481)",
            "Accept": "application/json",
        }
        if self.account.auth_token:
            token = urllib.parse.unquote(self.account.auth_token.strip())
            if token.startswith("Cookie:"):
                headers["Cookie"] = token.replace("Cookie:", "", 1).strip()
            elif ("=" in token or token.startswith("PHPSESSID") or token.startswith("_identity")) and not token.lower().startswith("bearer "):
                headers["Cookie"] = token
            elif token.lower().startswith("bearer "):
                headers["Authorization"] = token
            else:
                headers["Authorization"] = f"Bearer {token}"
        if extra_headers:
            headers.update(extra_headers)
        return httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=25.0,
            verify=verify,
            transport=self._transport,
            follow_redirects=True,
        )

    async def _request_with_backoff(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Executes outbound HTTPS request with dynamic pacing and 429/5xx exponential backoff."""
        now_loop = asyncio.get_event_loop().time()
        elapsed = now_loop - self._last_request_ts
        if elapsed < self.min_delay_sec:
            await asyncio.sleep(self.min_delay_sec - elapsed)

        attempt = 0
        while True:
            attempt += 1
            self._last_request_ts = asyncio.get_event_loop().time()
            try:
                response = await client.request(method, url, **kwargs)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt <= self.max_retries:
                        backoff = (2 ** (attempt - 1)) * max(self.min_delay_sec, 0.2)
                        logger.warning(
                            "[%s] HTTP %s on %s, retrying in %.2fs (attempt %d/%d)",
                            self.carrier_name,
                            response.status_code,
                            url,
                            backoff,
                            attempt,
                            self.max_retries,
                        )
                        await asyncio.sleep(backoff)
                        continue
                return response
            except httpx.RequestError as exc:
                if attempt <= self.max_retries:
                    backoff = (2 ** (attempt - 1)) * max(self.min_delay_sec, 0.2)
                    logger.warning("[%s] Network error %s, retrying in %.2fs", self.carrier_name, exc, backoff)
                    await asyncio.sleep(backoff)
                    continue
                raise

    @abstractmethod
    async def authenticate(self) -> bool:
        """Verifies session/token validity against the carrier API or user cabinet."""
        pass

    @abstractmethod
    async def submit_pre_declaration(self, decl: PreDeclarationRequest) -> Dict[str, Any]:
        """Uploads invoice PDF and pre-declaration fields before or upon foreign warehouse arrival."""
        pass

    @abstractmethod
    async def fetch_active_shipments(self) -> List[CarrierShipmentDTO]:
        """Fetches all active parcels and resolves destination AWB codes (STRAZ..., LMX..., CAM...)."""
        pass

    @abstractmethod
    async def track_by_origin(self, origin_tracking: str) -> Optional[CarrierShipmentDTO]:
        """Resolves international customs AWB and parcel status using the domestic origin tracking code."""
        pass
