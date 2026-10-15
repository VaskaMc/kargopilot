"""FastAPI router for /carriers Central Web Management Panel (127.0.0.1:48481)."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.carriers.base_carrier import CarrierAccountDTO, ShipmentStatus
from app.carriers.forwarding_hub import ForwardingHub
from app.carriers.address_formatter import AddressFormatterEngine
from app.carriers.tariff_engine import DynamicTariffEngine

router = APIRouter(prefix="/carriers", tags=["carriers"])

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "carriers.html"

STATUS_BADGE_STYLES: Dict[str, tuple[str, str]] = {
    ShipmentStatus.PRE_DECLARED.value: ("bg-blue-500/20 text-blue-300 border-blue-500/40", "Ön bəyan edildi"),
    ShipmentStatus.AT_FOREIGN_HUB.value: ("bg-amber-500/20 text-amber-300 border-amber-500/40", "Xarici anbarda"),
    ShipmentStatus.ON_THE_WAY.value: ("bg-amber-500/20 text-amber-300 border-amber-500/40", "Yolda (Uçuşda)"),
    ShipmentStatus.CUSTOMS_INSPECTION.value: ("bg-purple-500/20 text-purple-300 border-purple-500/40", "Gömrükdə"),
    ShipmentStatus.AT_LOCAL_BRANCH.value: ("bg-emerald-500/20 text-emerald-300 border-emerald-500/40", "Filialda (Bakı)"),
    ShipmentStatus.DELIVERED.value: ("bg-emerald-500/20 text-emerald-300 border-emerald-500/40", "Təhvil verildi"),
}


class PreDeclarePayload(BaseModel):
    carrier_name: str = "STAREX"
    order_ref: str
    platform: str = "Taobao"
    origin_country: str = "CN"
    origin_tracking: str
    seller_name: str
    item_title: str
    quantity: int = 1
    invoice_amount: float
    invoice_currency: str = "CNY"
    branch_id: str = "28 May"


def _get_hub(request: Request) -> ForwardingHub:
    hub = getattr(request.app.state, "forwarding_hub", None)
    if hub is None:
        db_path = getattr(request.app.state, "db_path", Path("/data/pcs/pcs.db"))
        inv_dir = getattr(request.app.state, "invoice_dir", Path("/data/pcs/invoices"))
        hub = ForwardingHub(db_path=db_path, invoices_dir=inv_dir)
        request.app.state.forwarding_hub = hub
    return hub


def _render_carrier_cards(accounts: list[CarrierAccountDTO]) -> str:
    by_name = {a.carrier_name.upper(): a for a in accounts}
    default_carriers = [
        ("STAREX", "ST123456", {"TR": "İstanbul (Avcılar)", "CN": "Quançjou", "US": "Delaware", "DE": "Frankfurt"}),
        ("LIMAK", "LMX-10294", {"TR": "İstanbul (Halkalı)", "US": "Delaware"}),
        ("CAMEX", "CAM-11111", {"TR": "İstanbul (Güngören)", "CN": "Quançjou", "US": "Delaware"}),
        ("DYNAMEX", "DYN-22222", {"TR": "İstanbul (Başakşehir)", "US": "Delaware"}),
    ]
    cards: list[str] = []
    for name, def_code, def_suites in default_carriers:
        acc = by_name.get(name)
        cust_id = acc.customer_id if acc else def_code
        branch = acc.default_branch if acc else "28 May"
        has_token = bool(acc and acc.auth_token)
        status_label = "ACTIVE" if has_token else "AUTH_REQUIRED"
        badge_cls = (
            "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
            if has_token
            else "bg-amber-500/20 text-amber-400 border-amber-500/30"
        )
        suites = (acc.warehouse_suites if acc and acc.warehouse_suites else def_suites)
        suite_lines = "".join(
            f"<div class='text-xs text-slate-400'><span class='font-mono text-slate-300'>{escape(k)}:</span> {escape(v)}</div>"
            for k, v in suites.items()
        )
        cards.append(
            f"""<div class="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col justify-between space-y-3">
                <div>
                    <div class="flex items-center justify-between">
                        <span class="font-bold text-white text-base">{escape(name)}</span>
                        <span class="px-2 py-0.5 text-[11px] font-mono rounded border {badge_cls}">{status_label}</span>
                    </div>
                    <div class="mt-2 text-xs text-slate-300">
                        Müştəri ID: <span class="font-mono text-emerald-400 font-semibold">{escape(cust_id)}</span> • Filial: <strong>{escape(branch)}</strong>
                    </div>
                    <div class="mt-2 space-y-1 border-t border-slate-800/80 pt-2">
                        {suite_lines}
                    </div>
                </div>
                <div class="pt-2 flex items-center justify-between space-x-2">
                    <button onclick="openTokenModal('{escape(name)}', '{escape(cust_id)}', '{escape(branch)}')"
                            class="flex-1 py-1.5 px-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 transition">
                        🔑 Kuki/Token
                    </button>
                    <button onclick="selectCarrierForAddress('{escape(name)}', '{escape(cust_id)}', '{escape(branch)}')"
                            class="flex-1 py-1.5 px-2 rounded-lg bg-emerald-600/30 hover:bg-emerald-600/50 text-xs font-medium text-emerald-300 border border-emerald-500/40 transition">
                        📍 Ünvanı Al
                    </button>
                </div>
            </div>"""
        )
    return "\n".join(cards)


def _render_shipment_rows(shipments: list[Dict[str, Any]]) -> str:
    if not shipments:
        return """<tr><td colspan="7" class="py-8 text-center text-slate-500">Hələ aktiv kargo bağlaması yoxdur.</td></tr>"""
    rows: list[str] = []
    for sh in shipments:
        extra = sh.get("extra") or {}
        platform = extra.get("platform") or ("Taobao" if str(sh["order_ref"]).startswith("TB") else "Trendyol")
        flag = "🇨🇳" if sh.get("origin_country") == "CN" else ("🇹🇷" if sh.get("origin_country") == "TR" else "🇺🇸")
        awb = sh.get("destination_tracking") or "Gözlənilir..."
        sc_no = sh.get("smart_customs_no") or "—"
        status_code = sh.get("status") or "PRE_DECLARED"
        badge_cls, badge_text = STATUS_BADGE_STYLES.get(
            status_code, ("bg-slate-700 text-slate-300 border-slate-600", status_code)
        )
        fee_str = (
            f"<div class='text-xs text-slate-400'>Kargo: ${sh['delivery_fee_usd']:.2f} ({sh['delivery_fee_azn']:.2f} ₼)</div>"
            if sh.get("delivery_fee_usd")
            else ""
        )
        rows.append(
            f"""<tr class="hover:bg-slate-900/50">
                <td class="py-3 px-4">
                    <div class="font-medium text-white">{flag} {escape(platform)}</div>
                    <div class="text-xs font-mono text-slate-400">{escape(str(sh['order_ref']))}</div>
                </td>
                <td class="py-3 px-4 font-semibold text-slate-200">{escape(str(sh['carrier_name']))}</td>
                <td class="py-3 px-4 font-mono text-xs">
                    <span class="text-slate-300">{escape(str(sh['origin_tracking']))}</span>
                    <span class="text-slate-500 mx-1">➔</span>
                    <span class="text-emerald-400 font-semibold">{escape(str(awb))}</span>
                </td>
                <td class="py-3 px-4 font-mono text-xs text-indigo-300">{escape(str(sc_no))}</td>
                <td class="py-3 px-4">
                    <span class="px-2.5 py-1 rounded-full text-xs font-medium border {badge_cls}">
                        {escape(badge_text)}
                    </span>
                </td>
                <td class="py-3 px-4 text-right">
                    <div class="font-medium text-white">${float(sh.get('amount_usd') or 0):.2f} USD ({float(sh.get('amount_azn') or 0):.2f} ₼)</div>
                    {fee_str}
                </td>
                <td class="py-3 px-4 text-center">
                    <a href="/carriers/invoices/{escape(str(sh['order_ref']))}" target="_blank"
                       class="px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-xs text-emerald-400 font-mono">
                        📄 PDF
                    </a>
                </td>
            </tr>"""
        )
    return "\n".join(rows)


@router.get("", response_class=HTMLResponse)
async def get_carriers_dashboard(request: Request):
    hub = _get_hub(request)
    accounts = hub.list_accounts()
    shipments = hub.list_shipments()
    if "application/json" in (request.headers.get("accept") or ""):
        return JSONResponse(
            {
                "accounts": [a.model_dump(mode="json") for a in accounts],
                "shipments": shipments,
            }
        )
    template_str = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = template_str.replace("{{CARRIER_CARDS_HTML}}", _render_carrier_cards(accounts)).replace(
        "{{SHIPMENT_ROWS_HTML}}", _render_shipment_rows(shipments)
    )
    return HTMLResponse(content=html)


@router.get("/api/address")
async def get_formatted_address_api(
    carrier: str = Query("STAREX"),
    country: str = Query("TR"),
    platform: str = Query("trendyol"),
    customer_code: Optional[str] = Query(None),
    branch: str = Query("28 May"),
    full_name: str = Query("Vasif Məcidli"),
    request: Request = None,
):
    hub = _get_hub(request)
    if not customer_code:
        # Resolve customer code from DB
        accs = {a.carrier_name.upper(): a for a in hub.list_accounts()}
        if carrier.upper() in accs and accs[carrier.upper()].customer_id:
            customer_code = accs[carrier.upper()].customer_id
        else:
            customer_code = "ST123456" if carrier.upper() == "STAREX" else ("CAM-11111" if carrier.upper() == "CAMEX" else "DYN-22222")

    try:
        block = AddressFormatterEngine.format_address(
            carrier=carrier,
            origin_country=country,
            platform=platform,
            customer_code=customer_code,
            full_name=full_name,
            branch=branch,
        )
        return block.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/tariffs")
async def get_tariff_comparison_api(
    country: str = Query("TR"),
    weight: float = Query(0.5),
    is_liquid: bool = Query(False),
):
    try:
        quotes = DynamicTariffEngine.compare_all_carriers(
            country=country,
            weight_kg=weight,
            usd_to_azn=1.70,
            is_liquid=is_liquid,
        )
        return {"quotes": [q.model_dump(mode="json") for q in quotes], "country": country.upper(), "weight_kg": weight}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/accounts")
async def upsert_account_endpoint(payload: CarrierAccountDTO, request: Request):
    hub = _get_hub(request)
    acc_id = hub.upsert_carrier_account(payload)
    return {"status": "ok", "account_id": acc_id, "carrier_name": payload.carrier_name.upper()}


@router.post("/pre-declare")
async def pre_declare_endpoint(payload: PreDeclarePayload, request: Request):
    hub = _get_hub(request)
    result = await hub.auto_pre_declare(
        carrier_name=payload.carrier_name,
        order_ref=payload.order_ref,
        platform=payload.platform,
        origin_country=payload.origin_country,
        origin_tracking=payload.origin_tracking,
        seller_name=payload.seller_name,
        item_title=payload.item_title,
        quantity=payload.quantity,
        invoice_amount=payload.invoice_amount,
        invoice_currency=payload.invoice_currency,
        branch_id=payload.branch_id,
    )
    return result


@router.post("/sync")
async def sync_carriers_endpoint(request: Request):
    hub = _get_hub(request)
    return await hub.sync_all_carriers()


@router.get("/whatsapp-summary")
async def whatsapp_kargo_summary(request: Request):
    hub = _get_hub(request)
    return {"command": "!kargo", "text": hub.format_whatsapp_kargo_report()}


@router.get("/invoices/{order_ref}")
async def download_carrier_invoice(order_ref: str, request: Request):
    hub = _get_hub(request)
    safe_ref = Path(order_ref).name
    pdf_path = hub.invoices_dir / f"{safe_ref}_customs_invoice.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Invoice PDF not found")
    return FileResponse(path=str(pdf_path), media_type="application/pdf", filename=pdf_path.name)
