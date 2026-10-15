"""Azerbaijani freight forwarders and carrier integration package for PCS v3.0."""

from __future__ import annotations

from typing import Any, Dict, Optional, Type
import httpx

from .base_carrier import (
    BaseCarrier,
    CarrierAccountDTO,
    CarrierShipmentDTO,
    PreDeclarationRequest,
    ShipmentStatus,
)
from .camex import CamexCarrierAdapter
from .dynamex import DynamexCarrierAdapter
from .limak import LimakCarrierAdapter
from .starex import StarexCarrierAdapter
from .tariff_calculator import calculate_delivery_fee


class CarrierRegistry:
    """Factory and registry for Azerbaijani carrier adapters."""

    _registry: Dict[str, Type[BaseCarrier]] = {
        "STAREX": StarexCarrierAdapter,
        "LIMAK": LimakCarrierAdapter,
        "CAMEX": CamexCarrierAdapter,
        "DYNAMEX": DynamexCarrierAdapter,
    }

    @classmethod
    def register(cls, carrier_name: str, adapter_cls: Type[BaseCarrier]) -> None:
        cls._registry[carrier_name.upper()] = adapter_cls

    @classmethod
    def get_adapter_cls(cls, carrier_name: str) -> Optional[Type[BaseCarrier]]:
        return cls._registry.get(carrier_name.upper())

    @classmethod
    def create(
        cls,
        account: CarrierAccountDTO,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        min_delay_sec: float = 0.05,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> BaseCarrier:
        key = account.carrier_name.upper()
        if key not in cls._registry:
            raise ValueError(f"Unsupported carrier: {account.carrier_name}")
        adapter_cls = cls._registry[key]
        return adapter_cls(
            account=account,
            transport=transport,
            min_delay_sec=min_delay_sec,
            **kwargs,
        )


__all__ = [
    "BaseCarrier",
    "CarrierAccountDTO",
    "CarrierShipmentDTO",
    "PreDeclarationRequest",
    "ShipmentStatus",
    "StarexCarrierAdapter",
    "LimakCarrierAdapter",
    "CamexCarrierAdapter",
    "DynamexCarrierAdapter",
    "CarrierRegistry",
    "calculate_delivery_fee",
]
