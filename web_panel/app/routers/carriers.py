"""FastAPI router for /carriers Central Web Management Panel (127.0.0.1:48481)."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.carriers.base_carrier import CarrierAccountDTO, ShipmentStatus
from app.carriers.forwarding_hub import ForwardingHub
from app.carriers.address_formatter import AddressFormatterEngine
from app.carriers.tariff_engine import DynamicTariffEngine
from app.carriers.consolidation_engine import (
    SmartConsolidationEngine,
    PackageItem,
    FINProfile,
)
from app.carriers.branch_directory import (
    BranchDirectoryEngine,
    ReverseLogisticsEngine,
    BranchDTO,
    ReverseLogisticsRequest,
    ReverseLogisticsQuote,
    ReverseLogisticsWaybill,
    ReturnReasonEnum,
    haversine_distance,
)

router = APIRouter(prefix="/carriers", tags=["carriers"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
TEMPLATE_PATH = TEMPLATES_DIR / "carriers.html"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

STATUS_BADGE_STYLES: Dict[str, tuple[str, str]] = {
    ShipmentStatus.PRE_DECLARED.value: ("bg-sky-950 text-sky-400 border-sky-800/60", "Ön bəyan edildi"),
    ShipmentStatus.AT_FOREIGN_HUB.value: ("bg-amber-950 text-amber-400 border-amber-800/60", "Xarici anbarda"),
    ShipmentStatus.ON_THE_WAY.value: ("bg-amber-950 text-amber-400 border-amber-800/60", "Yolda (Uçuşda)"),
    ShipmentStatus.CUSTOMS_INSPECTION.value: ("bg-sky-950 text-sky-300 border-sky-700/60", "Gömrükdə"),
    ShipmentStatus.AT_LOCAL_BRANCH.value: ("bg-emerald-950 text-emerald-400 border-emerald-800/60", "Filialda (Bakı)"),
    ShipmentStatus.DELIVERED.value: ("bg-emerald-950 text-emerald-400 border-emerald-800/60", "Təhvil verildi"),
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
        ("STAREX", "ST026090", {"TR": "İstanbul (Tuzla/Avcılar)", "CN": "Quançjou", "US": "Delaver", "DE": "Frankfurt"}),
        ("LIMAK", "LMX-10294", {"TR": "İstanbul (Halkalı)", "CN": "Quançjou", "US": "Delaver"}),
        ("CAMEX", "CAM-44810", {"TR": "İstanbul (Güngören)", "CN": "Quançjou", "US": "Delaver"}),
        ("DYNAMEX", "DYN-77120", {"TR": "İstanbul (Başakşehir)", "CN": "Quançjou", "US": "Delaver"}),
    ]
    cards: list[str] = []
    for name, def_code, def_suites in default_carriers:
        acc = by_name.get(name)
        cust_id = acc.customer_id if acc else def_code
        branch = acc.default_branch if acc else "28 May"
        has_token = bool(acc and acc.auth_token)
        status_label = "AKTİV" if has_token else "HAZIR"
        badge_cls = (
            "bg-emerald-950 text-emerald-400 border-emerald-800/60"
            if has_token
            else "bg-slate-800 text-indigo-400 border-slate-700"
        )
        suites = (acc.warehouse_suites if acc and acc.warehouse_suites else def_suites)
        suite_lines = "".join(
            f"<div class='text-xs text-slate-400 flex items-center justify-between'><span class='font-mono font-bold text-slate-300'>{escape(k)}:</span> <span class='text-slate-200'>{escape(v)}</span></div>"
            for k, v in suites.items()
        )
        cards.append(
            f"""<div class="bg-slate-900 border border-slate-800 rounded-2xl p-5 flex flex-col justify-between space-y-4">
                <div>
                    <div class="flex items-center justify-between">
                        <div class="flex items-center gap-2">
                            <span class="w-2.5 h-2.5 rounded-full {'bg-emerald-400' if has_token else 'bg-indigo-400'}"></span>
                            <span class="font-extrabold text-white text-base tracking-tight">{escape(name)}</span>
                        </div>
                        <span class="px-2 py-0.5 text-[11px] font-mono font-bold rounded border {badge_cls}">{status_label}</span>
                    </div>
                    <div class="mt-3 p-2.5 rounded-xl bg-slate-950 text-xs text-slate-300 flex items-center justify-between">
                        <span>Suite: <strong class="font-mono text-indigo-400">{escape(cust_id)}</strong></span>
                        <span>Filial: <strong class="text-white">{escape(branch)}</strong></span>
                    </div>
                    <div class="mt-3 space-y-1.5 pt-2 border-t border-slate-800/80">
                        {suite_lines}
                    </div>
                </div>
                <div class="pt-2 flex items-center justify-between gap-2">
                    <button type="button" onclick="openTokenModal('{escape(name)}', '{escape(cust_id)}', '{escape(branch)}')"
                            class="flex-1 min-h-[44px] py-2.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-bold text-slate-200 flex items-center justify-center gap-1.5 transition">
                        <i data-lucide="key" class="w-3.5 h-3.5 text-sky-400"></i>
                        <span>Kuki / Token</span>
                    </button>
                    <button type="button" onclick="selectCarrierForAddress('{escape(name)}', '{escape(cust_id)}', '{escape(branch)}')"
                            class="flex-1 min-h-[44px] py-2.5 px-3 rounded-xl bg-indigo-600 text-xs font-bold flex items-center justify-center gap-1.5 transition">
                        <i data-lucide="map-pin" class="w-3.5 h-3.5"></i>
                        <span>Ünvanı Al</span>
                    </button>
                </div>
            </div>"""
        )
    return "\n".join(cards)


def _render_shipment_rows(shipments: list[Dict[str, Any]]) -> str:
    if not shipments:
        return """<tr>
            <td colspan="7" class="py-12 px-6 text-center">
                <div class="max-w-md mx-auto space-y-3">
                    <div class="w-12 h-12 mx-auto rounded-2xl bg-slate-800/80 border border-slate-700 flex items-center justify-center text-slate-400 shadow-inner">
                        <i data-lucide="package-check" class="w-6 h-6 text-sky-400"></i>
                    </div>
                    <div>
                        <h3 class="text-sm font-bold text-white">Hələ Aktiv Kargo Bağlaması Yoxdur</h3>
                        <p class="text-xs text-slate-400 mt-1">Sifarişlərinizi ön bəyan edərək AWB izləmə nömrələri və avtomatik PDF invoys tərtib edə bilərsiniz.</p>
                    </div>
                    <div class="pt-1">
                        <button type="button" onclick="openPredeclareModal()" class="min-h-[44px] px-4 py-2.5 rounded-xl bg-indigo-600 text-xs font-bold inline-flex items-center justify-center gap-2 transition">
                            <i data-lucide="file-plus-2" class="w-4 h-4"></i>
                            <span>1-Kliklə Ön Bəyan Yarat</span>
                        </button>
                    </div>
                </div>
            </td>
        </tr>"""
    rows: list[str] = []
    for sh in shipments:
        extra = sh.get("extra") or {}
        platform = extra.get("platform") or ("Taobao" if str(sh["order_ref"]).startswith("TB") else "Trendyol")
        origin_code = sh.get("origin_country") or "TR"
        awb = sh.get("destination_tracking") or "Gözlənilir..."
        sc_no = sh.get("smart_customs_no") or "—"
        status_code = sh.get("status") or "PRE_DECLARED"
        badge_cls, badge_text = STATUS_BADGE_STYLES.get(
            status_code, ("bg-slate-800 text-slate-300 border-slate-700", status_code)
        )
        fee_str = (
            f"<div class='text-[11px] text-slate-400 font-mono mt-0.5'>Daşıma: ${sh['delivery_fee_usd']:.2f} ({sh['delivery_fee_azn']:.2f} ₼)</div>"
            if sh.get("delivery_fee_usd")
            else ""
        )
        rows.append(
            f"""<tr class="hover:bg-slate-800/50 transition">
                <td class="py-3.5 px-4">
                    <div class="font-bold text-white flex items-center gap-1.5">
                        <span class="px-1.5 py-0.5 rounded bg-slate-800 text-indigo-400 font-mono text-[10px] font-bold">{escape(origin_code)}</span>
                        <span>{escape(platform)}</span>
                    </div>
                    <div class="text-xs font-mono text-slate-400 mt-0.5">{escape(str(sh['order_ref']))}</div>
                </td>
                <td class="py-3.5 px-4 font-bold text-slate-200">{escape(str(sh['carrier_name']))}</td>
                <td class="py-3.5 px-4 font-mono text-xs">
                    <span class="text-slate-300">{escape(str(sh['origin_tracking']))}</span>
                    <span class="text-slate-500 mx-1">➔</span>
                    <span class="text-indigo-400 font-bold">{escape(str(awb))}</span>
                </td>
                <td class="py-3.5 px-4 font-mono text-xs text-sky-400 font-bold">{escape(str(sc_no))}</td>
                <td class="py-3.5 px-4">
                    <span class="px-2.5 py-1 rounded-md text-xs font-bold border {badge_cls}">
                        {escape(badge_text)}
                    </span>
                </td>
                <td class="py-3.5 px-4 text-right">
                    <div class="font-mono font-bold text-white">${float(sh.get('amount_usd') or 0):.2f} USD ({float(sh.get('amount_azn') or 0):.2f} ₼)</div>
                    {fee_str}
                </td>
                <td class="py-3.5 px-4 text-center">
                    <a href="/carriers/invoices/{escape(str(sh['order_ref']))}" target="_blank"
                       class="inline-flex items-center justify-center min-h-[44px] min-w-[44px] gap-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-indigo-400 font-bold font-mono transition border border-slate-700">
                        <i data-lucide="file-text" class="w-3.5 h-3.5 text-sky-400"></i>
                        <span>PDF</span>
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
    return templates.TemplateResponse(
        request=request,
        name="carriers.html",
        context={
            "page_title": "4-Kargo Daşıyıcıları İdarəetmə Mərkəzi",
            "active_tab": "carriers",
            "carrier_cards_html": _render_carrier_cards(accounts),
            "shipment_rows_html": _render_shipment_rows(shipments),
            "shipments_count": len(shipments),
        },
    )


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
    c_upper = carrier.upper()
    cntry_upper = country.upper()

    # Automatically adapt default platform if country is US or DE and platform was defaulted to trendyol
    if cntry_upper in ("US", "DE") and platform.lower() == "trendyol":
        platform = "amazon"
    elif cntry_upper == "CN" and platform.lower() == "trendyol":
        platform = "taobao"

    if not customer_code:
        # Resolve customer code from DB or carrier-specific defaults
        accs = {a.carrier_name.upper(): a for a in hub.list_accounts()}
        if c_upper in accs and accs[c_upper].customer_id:
            customer_code = accs[c_upper].customer_id
        else:
            defaults = {
                "STAREX": "ST026090",
                "LIMAK": "LMX-10294",
                "CAMEX": "CAM-44810",
                "DYNAMEX": "DYN-77120",
            }
            customer_code = defaults.get(c_upper, "ST026090")

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


class ConsolidationOptimizeRequest(BaseModel):
    packages: list[PackageItem]
    carrier: str = "STAREX"
    current_used_usd: float = 0.0
    primary_fin: str = "6XXXXXX"
    available_fins: Optional[list[FINProfile]] = None


class RepackAssessmentRequest(BaseModel):
    package: PackageItem
    carrier: str = "STAREX"
    repack_fee_usd: float = 1.00


@router.post("/api/consolidation/optimize")
async def optimize_consolidation_endpoint(payload: ConsolidationOptimizeRequest):
    try:
        report = SmartConsolidationEngine.run_full_optimization(
            packages=payload.packages,
            carrier=payload.carrier,
            current_used_usd=payload.current_used_usd,
            primary_fin=payload.primary_fin,
            available_fins=payload.available_fins,
        )
        return report.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/consolidation/repack-assessment")
async def assess_repack_endpoint(payload: RepackAssessmentRequest):
    try:
        assessment = SmartConsolidationEngine.evaluate_volumetric_repack(
            package=payload.package,
            carrier=payload.carrier,
            repack_fee_usd=payload.repack_fee_usd,
        )
        return assessment.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -----------------------------------------------------------------------------
# BRANCH DIRECTORY, PROXIMITY & REVERSE LOGISTICS ENDPOINTS
# -----------------------------------------------------------------------------

@router.get("/api/branches")
async def list_branches_endpoint(
    carrier: Optional[str] = Query(None),
    region: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    metro: Optional[str] = Query(None),
    transit_hub: Optional[str] = Query(None),
    is_liquid: bool = Query(False),
    is_bulky: bool = Query(False),
    is_sunday: bool = Query(False),
    is_door_delivery: bool = Query(False),
):
    try:
        branches = BranchDirectoryEngine.filter_branches(
            carrier=carrier,
            region=region,
            city=city,
            metro_station=metro,
            transit_hub=transit_hub,
            requires_liquid=is_liquid,
            requires_bulky=is_bulky,
            requires_sunday=is_sunday,
            requires_door_delivery=is_door_delivery,
        )
        return {
            "count": len(branches),
            "branches": [b.model_dump(mode="json") for b in branches],
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/branches/proximity")
async def branch_proximity_endpoint(
    lat: float = Query(...),
    lon: float = Query(...),
    carrier: Optional[str] = Query(None),
    is_liquid: bool = Query(False),
    is_bulky: bool = Query(False),
    is_sunday: bool = Query(False),
):
    try:
        caps = set()
        if is_liquid:
            caps.add("liquid_accepted")
        if is_bulky:
            caps.add("bulky_items_accepted")
        if is_sunday:
            caps.add("sunday_open")

        if carrier:
            res = BranchDirectoryEngine.find_nearest_branch(
                user_lat=lat,
                user_lon=lon,
                carrier=carrier,
                required_capabilities=caps,
            )
            if not res:
                raise HTTPException(status_code=404, detail="No matching branch found")
            return res.model_dump(mode="json")
        else:
            multi_res = BranchDirectoryEngine.find_nearest_branches_for_all_carriers(
                user_lat=lat,
                user_lon=lon,
                required_capabilities=caps,
            )
            return multi_res.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class SmartRoutePayload(BaseModel):
    carrier: str
    user_preferred_branch_id: str
    is_liquid: bool = False
    is_bulky: bool = False
    requires_sunday: bool = False


@router.post("/api/branches/smart-route")
async def smart_route_endpoint(payload: SmartRoutePayload):
    try:
        decision = BranchDirectoryEngine.smart_route_shipment(
            carrier=payload.carrier,
            user_preferred_branch_id=payload.user_preferred_branch_id,
            is_liquid=payload.is_liquid,
            is_bulky=payload.is_bulky,
            requires_sunday=payload.requires_sunday,
        )
        return decision.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/reverse-logistics/quote")
async def reverse_logistics_quote_endpoint(payload: ReverseLogisticsRequest):
    try:
        quote = ReverseLogisticsEngine.generate_return_quote(payload)
        return quote.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class IssueWaybillPayload(BaseModel):
    quote: ReverseLogisticsQuote
    order_ref: str
    merchant_return_code: str


@router.post("/api/reverse-logistics/waybill")
async def reverse_logistics_waybill_endpoint(payload: IssueWaybillPayload):
    try:
        waybill = ReverseLogisticsEngine.issue_return_waybill(
            quote=payload.quote,
            order_ref=payload.order_ref,
            merchant_return_code=payload.merchant_return_code,
        )
        return waybill.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/reverse-logistics/quota-advice")
async def reverse_logistics_quota_advice_endpoint(
    order_ref: str = Query(...),
    invoice_usd: float = Query(...),
):
    try:
        advice = ReverseLogisticsEngine.get_customs_quota_advice(
            order_ref=order_ref,
            invoice_usd=invoice_usd,
        )
        return advice
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------------------------------------------------------
# SMART CONSOLIDATION & QUOTA SPLIT OPTIMIZER ENDPOINTS
# -------------------------------------------------------------------------

class ConsolidationOptimizeRequest(BaseModel):
    packages: list[PackageItem]
    carrier: str = "STAREX"
    current_used_usd: float = 0.0
    primary_fin: str = "6XXXXXX"
    available_fins: Optional[list[FINProfile]] = None


class RepackAssessmentRequest(BaseModel):
    package: PackageItem
    carrier: str = "STAREX"
    repack_fee_usd: float = 1.00


@router.post("/api/consolidation/optimize")
async def optimize_consolidation_endpoint(payload: ConsolidationOptimizeRequest):
    try:
        report = SmartConsolidationEngine.run_full_optimization(
            packages=payload.packages,
            carrier=payload.carrier,
            current_used_usd=payload.current_used_usd,
            primary_fin=payload.primary_fin,
            available_fins=payload.available_fins,
        )
        return report.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/consolidation/repack-assessment")
async def assess_repack_endpoint(payload: RepackAssessmentRequest):
    try:
        assessment = SmartConsolidationEngine.evaluate_volumetric_repack(
            package=payload.package,
            carrier=payload.carrier,
            repack_fee_usd=payload.repack_fee_usd,
        )
        return assessment.model_dump(mode="json")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


class DutyPredictBasketItem(BaseModel):
    title: str
    price: float
    currency: str = "USD"
    quantity: int = 1


class DutyPredictRequest(BaseModel):
    basket_items: List[DutyPredictBasketItem] = []
    current_monthly_used_usd: float = 0.0
    monthly_allowance_usd: float = 300.0


DutyPredictRequest.model_rebuild()


@router.post("/api/duty/predict")
async def predict_duty_endpoint(payload: DutyPredictRequest):
    try:
        import dataclasses
        from app.customs.duty_calculator import (
            BasketItem,
            cbar_converter,
            calculate_duty_on_excess,
            get_quota_status,
        )

        def _to_dict(obj: Any) -> Any:
            if hasattr(obj, "model_dump"):
                return obj.model_dump(mode="json")
            if dataclasses.is_dataclass(obj):
                d = dataclasses.asdict(obj)
                for k, v in list(d.items()):
                    if hasattr(v, "value"):
                        d[k] = v.value
                return d
            return obj

        converted_items = [
            BasketItem(title=it.title, price=it.price, currency=it.currency, quantity=it.quantity)
            for it in payload.basket_items
        ]
        tot_azn, tot_usd, breakdown = cbar_converter.evaluate_mixed_basket(converted_items)
        new_total_usd = payload.current_monthly_used_usd + tot_usd
        excess_usd = max(0.0, new_total_usd - payload.monthly_allowance_usd)
        duty_calc = calculate_duty_on_excess(excess_usd)
        status = get_quota_status(new_total_usd, limit_usd=payload.monthly_allowance_usd)

        return {
            "basket_total_usd": tot_usd,
            "basket_total_azn": tot_azn,
            "currency_breakdown": breakdown,
            "projected_monthly_total_usd": new_total_usd,
            "duty_calculation": _to_dict(duty_calc),
            "quota_status": _to_dict(status),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



