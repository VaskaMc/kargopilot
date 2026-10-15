"""Tariff calculator for Azerbaijani cargo carriers (Starex, Limak, Camex, Dynamex)."""

from __future__ import annotations

from typing import Optional, Tuple


def calculate_delivery_fee(
    carrier: str,
    country: str,
    weight_kg: Optional[float],
) -> Tuple[Optional[float], Optional[float]]:
    """
    Calculates estimated international delivery fee in USD and AZN.
    Returns: (fee_usd, fee_azn)
    """
    if weight_kg is None or weight_kg <= 0:
        return None, None

    c = country.upper().strip()
    w = float(weight_kg)
    carrier_up = carrier.upper().strip()

    fee_usd: float = 0.0

    if c == "TR":
        # Turkey rates (Istanbul -> Baku)
        if w <= 0.25:
            fee_usd = 1.20
        elif w <= 0.5:
            fee_usd = 1.90
        elif w <= 0.7:
            fee_usd = 2.50
        elif w <= 1.0:
            fee_usd = 3.20
        else:
            fee_usd = 3.20 + (w - 1.0) * 3.00
    elif c == "CN":
        # China rates (Guangzhou / Yiwu -> Baku): $7.50 USD / kg
        fee_usd = round(w * 7.50, 2)
    elif c == "US":
        # USA rates (Delaware -> Baku): $6.50 USD / kg
        fee_usd = round(w * 6.50, 2)
    elif c == "DE":
        # Germany rates (Frankfurt -> Baku): $5.00 USD / kg
        fee_usd = round(w * 5.00, 2)
    else:
        # Default international rate
        fee_usd = round(w * 5.00, 2)

    fee_usd = round(fee_usd, 2)
    fee_azn = round(fee_usd * 1.70, 2)
    return fee_usd, fee_azn
