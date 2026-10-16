"""Customs 300 USD Monthly Quota Calculator & Duty Estimation Service.

Compliant with Azerbaijan Republic Cabinet of Ministers Resolution No. 305
governing duty-free limits for physical persons (300 USD / calendar month).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.config import MONTHLY_CUSTOMS_QUOTA_USD, USD_AZN_RATE
from app.database import get_connection

logger = logging.getLogger(__name__)


def calculate_monthly_quota(target_year: int = None, target_month: int = None, target_fin: str = None) -> Dict[str, Any]:
    """Calculates calendar-month 300 USD quota usage, remaining allowance, and risk gauge metrics for active/target FIN."""
    now = datetime.now(timezone.utc)
    year = target_year or now.year
    month = target_month or now.month

    conn = get_connection()
    cur = conn.cursor()

    # Query active FIN or match target_fin
    from app.database import get_fin_profiles, get_active_fin
    all_fins = get_fin_profiles()
    active_fin_data = get_active_fin()
    selected_fin = target_fin or active_fin_data.get("fin", "6N89P92")

    # Query all orders in the targeted calendar month for the selected FIN
    month_str = f"{year}-{month:02d}"
    query = """
    SELECT id, temu_order_ref, platform, fin, tracking_number, carrier, 
           temu_invoice_amount, invoice_amount_azn, status, created_at
    FROM orders
    WHERE strftime('%Y-%m', created_at) = ?
      AND (fin = ? OR (fin IS NULL AND ? = '6N89P92'))
    ORDER BY created_at DESC
    """
    rows = cur.execute(query, (month_str, selected_fin, selected_fin)).fetchall()
    orders = [dict(r) for r in rows]

    total_azn = 0.0
    valid_orders = []
    for o in orders:
        amt = o.get("invoice_amount_azn") or o.get("temu_invoice_amount") or o.get("original_amount") or 0.0
        amt_float = float(amt)
        if amt_float > 0:
            total_azn += amt_float
            valid_orders.append(o)

    # Convert to USD via official CBAR rate
    used_usd = round(total_azn / USD_AZN_RATE, 2)
    limit_usd = MONTHLY_CUSTOMS_QUOTA_USD
    remaining_usd = max(0.0, round(limit_usd - used_usd, 2))
    remaining_azn = round(remaining_usd * USD_AZN_RATE, 2)
    percentage = min(100.0, round((used_usd / limit_usd) * 100, 1))

    # Risk level determination
    if used_usd >= limit_usd:
        risk_level = "danger"
        risk_label = "Limiti Aşıb (Gömrük Rüsümu Tətbiq Olunur)"
        color_class = "text-rose-500"
        bg_bar_class = "bg-rose-500"
    elif used_usd >= 225.0:  # 75%
        risk_level = "warning"
        risk_label = "Xəbərdarlıq (Limitə Yaxınlaşır)"
        color_class = "text-amber-500"
        bg_bar_class = "bg-amber-500"
    else:
        risk_level = "safe"
        risk_label = "Təhlükəsiz (Rüsumsuz Zolaq)"
        color_class = "text-emerald-500"
        bg_bar_class = "bg-emerald-500"

    # Duty & Tax Estimation on Excess (Resolution No. 305)
    excess_usd = max(0.0, round(used_usd - limit_usd, 2))
    excess_azn = round(excess_usd * USD_AZN_RATE, 2)
    
    # 15% customs tariff on excess + 18% VAT on (excess + duty) + 15 AZN electronic customs fee
    if excess_usd > 0:
        tariff_duty_azn = round(excess_azn * 0.15, 2)
        vat_azn = round((excess_azn + tariff_duty_azn) * 0.18, 2)
        clearance_fee_azn = 15.00
        total_duty_estimate_azn = round(tariff_duty_azn + vat_azn + clearance_fee_azn, 2)
    else:
        tariff_duty_azn = 0.0
        vat_azn = 0.0
        clearance_fee_azn = 0.0
        total_duty_estimate_azn = 0.0

    # 6-Month Historical Monthly Trend
    history = []
    history_rows = cur.execute("""
    SELECT strftime('%Y-%m', created_at) AS m, 
           SUM(COALESCE(invoice_amount_azn, temu_invoice_amount, 0)) AS azn_sum,
           COUNT(*) AS order_cnt
    FROM orders
    GROUP BY m
    ORDER BY m DESC
    LIMIT 6
    """).fetchall()

    for hr in reversed(history_rows):
        h_azn = float(hr["azn_sum"] or 0.0)
        h_usd = round(h_azn / USD_AZN_RATE, 2)
        history.append({
            "month_str": hr["m"],
            "orders_count": hr["order_cnt"],
            "total_azn": round(h_azn, 2),
            "total_usd": h_usd,
            "quota_pct": min(100.0, round((h_usd / limit_usd) * 100, 1)),
        })

    conn.close()

    month_names = {
        1: "Yanvar", 2: "Fevral", 3: "Mart", 4: "Aprel",
        5: "May", 6: "İyun", 7: "İyul", 8: "Avqust",
        9: "Sentyabr", 10: "Oktyabr", 11: "Noyabr", 12: "Dekabr"
    }

    return {
        "period_label": f"{month_names.get(month, '')} {year}",
        "year": year,
        "month": month,
        "limit_usd": limit_usd,
        "limit_azn": round(limit_usd * USD_AZN_RATE, 2),
        "used_usd": used_usd,
        "used_azn": round(total_azn, 2),
        "remaining_usd": remaining_usd,
        "remaining_azn": remaining_azn,
        "percentage": percentage,
        "risk_level": risk_level,
        "risk_label": risk_label,
        "color_class": color_class,
        "bg_bar_class": bg_bar_class,
        "orders_count": len(orders),
        "orders": orders,
        "excess_usd": excess_usd,
        "excess_azn": excess_azn,
        "tariff_duty_azn": tariff_duty_azn,
        "vat_azn": vat_azn,
        "clearance_fee_azn": clearance_fee_azn,
        "total_duty_estimate_azn": total_duty_estimate_azn,
        "history": history,
        "selected_fin": selected_fin,
        "active_fin": active_fin_data,
        "fin_profiles": all_fins,
    }
