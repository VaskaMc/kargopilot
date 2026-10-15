"""SmartCustoms Duty & Tax Prediction Engine for Personal Customs System (PCS).

Compliant with:
1. Azerbaijan Republic Cabinet of Ministers Resolution No. 305
   (300 USD duty-free personal allowance per physical person / calendar month).
2. Tax Code of the Republic of Azerbaijan (Article 162.1 - Import VAT Tax Base).
3. Cabinet of Ministers Resolution No. 91 (Electronic customs processing fee - 15 AZN).
4. Central Bank of the Republic of Azerbaijan (CBAR) official exchange rates.
5. State Customs Committee of Azerbaijan (DGK / e.customs.gov.az) 37 Official Categories.
"""

from __future__ import annotations

import enum
import hashlib
import json
import logging
import re
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ==============================================================================
# 1. LEGAL CONSTANTS & STATUTORY THRESHOLDS
# ==============================================================================

# Statutory Duty-Free Allowance (Resolution No. 305)
MONTHLY_ALLOWANCE_USD: float = 300.00

# Customs Tariff (İdxal gömrük rüsumu) on excess value
CUSTOMS_TARIFF_RATE: float = 0.15  # 15.0%

# Value Added Tax (ƏDV) applied on (Excess Customs Value + Customs Tariff)
# Tax Code of Azerbaijan Republic, Art. 162.1: Tax Base = CIF Value + Duty + Excise
VAT_RATE: float = 0.18  # 18.0%

# Flat Electronic Customs Processing Fee (Resolution No. 91)
ELECTRONIC_PROCESSING_FEE_AZN: float = 15.00  # 15.00 AZN (~8.82 USD)

# Official CBAR Pegged Rate for USD/AZN
PEG_USD_AZN_RATE: float = 1.7000

# Legal Quota Warning Percentage Thresholds
THRESHOLD_SAFE_LIMIT: float = 0.80      # < 80% ($240.00)
THRESHOLD_WARNING_LIMIT: float = 0.90   # 80% - 90% ($240.00 - $270.00)
THRESHOLD_CRITICAL_LIMIT: float = 1.00  # 90% - 100% ($270.00 - $300.00)

# ==============================================================================
# 2. STATE CUSTOMS COMMITTEE (DGK) 37 OFFICIAL CATEGORIES
# ==============================================================================

DGK_37_CATEGORIES: List[str] = [
    "Ampüllər/lampalar",
    "Ayaqqabı",
    "Bağ ləvazimatları",
    "Bitki və bitki toxumları",
    "Elektronika",
    "Ev aksesuarları (mebel, dekor)",
    "Ərzaq",
    "Geyim aksesuarları",
    "Heyvanlar",
    "Heyvan ləvazimatları",
    "Hobbi və əl işi",
    "İdman alətləri",
    "Kimyəvi təmizləyici vasitələr",
    "Kitablar",
    "Kompüter və aksesuarları",
    "Kosmetik vasitələr",
    "Maşın ehtiyat hissələri",
    "Media avadanlıqları",
    "Məişət avadanlıqları (böyük)",
    "Məişət avadanlıqları (kiçik)",
    "Mülki dövriyyəsi məhdudlaşdırılmış mallar",
    "Musiqi alətləri",
    "Ofis ləvazimatları",
    "Optik cihazlar",
    "Ovçuluq ləvazimatları",
    "Oyun konsolları",
    "Paltar",
    "Qida əlavələri/dərman",
    "Spirtli içkilər",
    "Süfrə və mətbəx əşyaları",
    "Suvenir və oyuncaqlar",
    "Tekstil",
    "Telefon və aksesuarları",
    "Təmir-tikinti alətləri",
    "Tibbi ləvazimatlar",
    "Tütün məmulatları",
    "Zinət əşyaları",
]

# Restricted / Regulated category metadata & statutory limitations
CATEGORY_REGULATORY_RULES: Dict[str, Dict[str, Any]] = {
    "Spirtli içkilər": {
        "is_restricted": True,
        "max_personal_quota": "3 litr",
        "warning_az": "Şəxsi istifadə üçün fiziki şəxslərə 1 ay ərzində maksimum 3 litr spirtli içki gətirməyə icazə verilir. Artıq miqdar qadağandır.",
        "requires_license": False,
    },
    "Tütün məmulatları": {
        "is_restricted": True,
        "max_personal_quota": "600 ədəd siqaret (3 blok) / 200 siqarilla / 50 siqar / 300 qram tütün",
        "warning_az": "Fiziki şəxslər tərəfindən ayda maksimum 3 blok (600 ədəd) siqaret idxal edilə bilər. Həddi aşan bağlamalar saxlanılır.",
        "requires_license": False,
    },
    "Mülki dövriyyəsi məhdudlaşdırılmış mallar": {
        "is_restricted": True,
        "max_personal_quota": "0 (Xüsusi icazə tələb olunur)",
        "warning_az": "Dronlar, gizli kameralar, güclü lazerlər, hərbi ləvazimatlar və radio skanerlər üçün DTX/DİN xüsusi icazəsi tələb olunur. İcazəsiz idxal cinayət məsuliyyəti yaradır.",
        "requires_license": True,
    },
    "Qida əlavələri/dərman": {
        "is_restricted": True,
        "max_personal_quota": "Maksimum 10 qutu (şəxsi resept ilə)",
        "warning_az": "Dərman vasitələri və qida əlavələri Səhiyyə Nazirliyinin Analitik Ekspertiza Mərkəzi tərəfindən yoxlanıla bilər. Kommersiya miqdarında idxal qadağandır.",
        "requires_license": False,
    },
    "Bitki və bitki toxumları": {
        "is_restricted": True,
        "max_personal_quota": "AQTA Fitosanitar sertifikatı tələb olunur",
        "warning_az": "Bitki və toxumların idxalı üçün Azərbaycan Qida Təhlükəsizliyi Agentliyinin (AQTA) rəyi zəruridir.",
        "requires_license": True,
    },
    "Heyvanlar": {
        "is_restricted": True,
        "max_personal_quota": "Baytarlıq pasportu və sertifikatı",
        "warning_az": "Canlı heyvanlar üçün beynəlxalq baytarlıq sertifikatı və mikroçip tələb olunur.",
        "requires_license": True,
    },
}

# ==============================================================================
# 3. ENUMS & DATA STRUCTURES
# ==============================================================================

class ThresholdLevel(str, enum.Enum):
    SAFE = "safe"                    # < 80% (< $240)
    WARNING_80 = "warning_80"        # 80% - 90% ($240 - $270)
    CRITICAL_90 = "critical_90"      # 90% - 100% ($270 - $300)
    BREACHED_100 = "breached_100"    # >= 100% (>= $300)


@dataclass
class ExchangeRate:
    currency: str
    rate_to_azn: float
    nominal: int = 1
    as_of_date: str = ""
    source: str = "CBAR"

    @property
    def unit_rate_azn(self) -> float:
        return self.rate_to_azn / self.nominal


@dataclass
class BasketItem:
    title: str
    price: float
    currency: str = "AZN"
    quantity: int = 1
    main_cat: Optional[str] = None
    sub_cat: Optional[str] = "Digər"
    country_of_origin: str = "CN"

    @property
    def line_total(self) -> float:
        return round(self.price * max(1, self.quantity), 2)


@dataclass
class CategorySuggestion:
    main_cat: str
    sub_cat: str = "Digər"
    confidence: float = 1.0
    matched_keyword: str = ""
    match_source: str = "deterministic"
    is_restricted: bool = False
    restriction_warning: Optional[str] = None
    requires_license: bool = False
    alternative_suggestions: List[str] = field(default_factory=list)


@dataclass
class DutyBreakdown:
    """Mathematical breakdown of customs debt on excess value under Res. No. 305."""
    excess_usd: float
    excess_azn: float
    tariff_duty_azn: float       # 15% customs tariff
    vat_azn: float               # 18% VAT on (excess + tariff)
    clearance_fee_azn: float     # 15.00 AZN flat electronic processing fee
    total_payable_azn: float     # Tariff + VAT + Fee
    total_payable_usd: float     # Total in USD at CBAR rate
    effective_tax_rate_pct: float # (Tariff + VAT) / Excess = 35.7%
    effective_burden_with_fee_pct: float # Total payable / Excess
    legal_basis: str = (
        "AR Nazirlər Kabinetinin 305 və 91 saylı Qərarları, "
        "AR Vergi Məcəlləsinin 162.1-ci maddəsi"
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QuotaStatus:
    """Monthly 300 USD customs quota utilization and risk status."""
    limit_usd: float
    limit_azn: float
    used_usd: float
    used_azn: float
    remaining_usd: float
    remaining_azn: float
    utilization_pct: float
    threshold_level: ThresholdLevel
    alert_badge: str
    alert_color: str
    warning_title: str
    warning_message: str
    actionable_recommendations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["threshold_level"] = self.threshold_level.value
        return d


@dataclass
class OptimizationStrategy:
    strategy_name: str
    description: str
    estimated_duty_savings_azn: float
    action_type: str  # "hold_in_warehouse", "fin_splitting", "cart_split"
    is_recommended: bool = False


@dataclass
class PredictionResult:
    """Complete prediction report for incoming order or simulated shopping basket."""
    current_quota: QuotaStatus
    basket_total_usd: float
    basket_total_azn: float
    currency_breakdown: Dict[str, float]
    projected_total_usd: float
    projected_quota: QuotaStatus
    spillover_excess_usd: float
    marginal_duty: DutyBreakdown
    threshold_transition: str
    items_categorized: List[Dict[str, Any]]
    optimization_strategies: List[OptimizationStrategy]
    has_restricted_items: bool
    regulatory_alerts: List[str]

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        res["current_quota"] = self.current_quota.to_dict()
        res["projected_quota"] = self.projected_quota.to_dict()
        res["marginal_duty"] = self.marginal_duty.to_dict()
        res["optimization_strategies"] = [asdict(s) for s in self.optimization_strategies]
        return res


# ==============================================================================
# 4. MULTI-CURRENCY CONVERTER & CBAR REAL-TIME ENGINE
# ==============================================================================

# Static legal fallback rates when CBAR is unreachable or offline
DEFAULT_FALLBACK_RATES: Dict[str, float] = {
    "AZN": 1.0000,
    "USD": 1.7000,   # Pegged
    "EUR": 1.8480,   # Nominal Euro
    "TRY": 0.0485,   # Turkish Lira
    "CNY": 0.2380,   # Chinese Yuan Renminbi
    "GBP": 2.1850,   # British Pound
    "RUB": 0.0175,   # Russian Ruble
}


class CBARCurrencyConverter:
    """Real-time CBAR XML FX rate manager with multi-tier caching and fallback."""

    def __init__(self, cache_ttl_seconds: int = 43200) -> None:
        self.cache_ttl = cache_ttl_seconds
        self._rates: Dict[str, ExchangeRate] = {}
        self._last_fetched: Optional[datetime] = None
        self._initialize_baseline_rates()

    def _initialize_baseline_rates(self) -> None:
        today_str = datetime.now(timezone.utc).strftime("%d.%m.%Y")
        for ccy, rate in DEFAULT_FALLBACK_RATES.items():
            self._rates[ccy] = ExchangeRate(
                currency=ccy,
                rate_to_azn=rate,
                nominal=1,
                as_of_date=today_str,
                source="BASELINE_PEGGED" if ccy in ("AZN", "USD") else "STATUTORY_FALLBACK",
            )

    def fetch_live_cbar_rates(self, target_date: Optional[str] = None) -> bool:
        """Fetches official rates from CBAR XML API (https://www.cbar.az/currencies/{DD.MM.YYYY}.xml)."""
        date_str = target_date or datetime.now(timezone.utc).strftime("%d.%m.%Y")
        url = f"https://www.cbar.az/currencies/{date_str}.xml"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "PCS-SmartCustoms-DutyEngine/3.0 (+https://customs.gov.az)"},
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                xml_data = resp.read()
                root = ET.fromstring(xml_data)

                for valute in root.findall(".//Valute"):
                    code = valute.attrib.get("Code", "").upper()
                    nominal_elem = valute.find("Nominal")
                    value_elem = valute.find("Value")

                    if code and value_elem is not None and value_elem.text:
                        nominal = int(nominal_elem.text) if nominal_elem is not None and nominal_elem.text else 1
                        val_str = value_elem.text.strip().replace(",", ".")
                        rate_val = float(val_str)
                        self._rates[code] = ExchangeRate(
                            currency=code,
                            rate_to_azn=rate_val,
                            nominal=nominal,
                            as_of_date=date_str,
                            source="CBAR_LIVE_XML",
                        )

                self._rates["AZN"] = ExchangeRate("AZN", 1.0, 1, date_str, "NATIONAL_CURRENCY")
                self._rates["USD"] = ExchangeRate("USD", PEG_USD_AZN_RATE, 1, date_str, "CBAR_PEGGED")
                self._last_fetched = datetime.now(timezone.utc)
                logger.info("Successfully refreshed live CBAR exchange rates for date: %s", date_str)
                return True
        except Exception as exc:
            logger.warning("CBAR live rate fetch warning (%s): using resilient cached/fallback rates.", exc)
            return False

    def get_rate(self, currency: str) -> ExchangeRate:
        ccy = currency.upper().strip()
        # Refresh if cache expired
        if self._last_fetched:
            elapsed = (datetime.now(timezone.utc) - self._last_fetched).total_seconds()
            if elapsed > self.cache_ttl:
                self.fetch_live_cbar_rates()

        if ccy in self._rates:
            return self._rates[ccy]

        # Unknown currency fallback to 1.0
        return ExchangeRate(currency=ccy, rate_to_azn=1.0, nominal=1, source="DEFAULT_FALLBACK")

    def convert_to_azn(self, amount: float, currency: str) -> float:
        rate = self.get_rate(currency)
        return round(float(amount) * rate.unit_rate_azn, 4)

    def convert_to_usd(self, amount: float, currency: str) -> float:
        amount_azn = self.convert_to_azn(amount, currency)
        usd_rate = self.get_rate("USD").unit_rate_azn or PEG_USD_AZN_RATE
        return round(amount_azn / usd_rate, 2)

    def convert_between(self, amount: float, from_ccy: str, to_ccy: str) -> float:
        amt_azn = self.convert_to_azn(amount, from_ccy)
        to_rate = self.get_rate(to_ccy).unit_rate_azn
        return round(amt_azn / to_rate, 4)

    def evaluate_mixed_basket(self, items: List[BasketItem]) -> Tuple[float, float, Dict[str, float]]:
        """Calculates total value of a multi-currency mixed shopping basket in AZN and USD."""
        total_azn = 0.0
        ccy_breakdown: Dict[str, float] = {}

        for item in items:
            ccy = item.currency.upper()
            line_val = item.line_total
            ccy_breakdown[ccy] = round(ccy_breakdown.get(ccy, 0.0) + line_val, 2)
            total_azn += self.convert_to_azn(line_val, ccy)

        usd_rate = self.get_rate("USD").unit_rate_azn or PEG_USD_AZN_RATE
        total_usd = round(total_azn / usd_rate, 2)
        total_azn_rounded = round(total_azn, 2)
        return total_azn_rounded, total_usd, ccy_breakdown


# Global Singleton Converter Instance
cbar_converter = CBARCurrencyConverter()


# ==============================================================================
# 5. MATHEMATICAL FORMULAS FOR CUSTOMS DUTY ON EXCESS
# ==============================================================================

def calculate_duty_on_excess(
    excess_usd: float,
    usd_azn_rate: Optional[float] = None,
) -> DutyBreakdown:
    """Computes exact customs tariff, VAT, and electronic processing fee on excess over $300.

    Mathematical Formulation:
    -------------------------
    1. Excess Customs Value in AZN:
       Excess_AZN = Excess_USD * Rate_USD_to_AZN

    2. Customs Import Tariff (15%):
       Tariff_AZN = round(Excess_AZN * 0.15, 2)

    3. Import VAT (18% applied to taxable base pursuant to Tax Code Art. 162.1):
       TaxBase_VAT = Excess_AZN + Tariff_AZN
       VAT_AZN = round(TaxBase_VAT * 0.18, 2)
               = round((Excess_AZN * 1.15) * 0.18, 2)
               = round(Excess_AZN * 0.207, 2)   # 20.7% effective on excess

    4. Combined Statutory Tax Rate:
       Tariff + VAT = 15% + 20.7% = 35.70% of Excess Customs Value!

    5. Electronic Customs Clearance Fee (Res. No. 91):
       ProcessingFee_AZN = 15.00 AZN (if Excess_USD > 0, else 0.00 AZN)

    6. Total Payable Customs Debt:
       Total_AZN = Tariff_AZN + VAT_AZN + ProcessingFee_AZN
       Total_USD = round(Total_AZN / Rate_USD_to_AZN, 2)
    """
    rate = usd_azn_rate or cbar_converter.get_rate("USD").unit_rate_azn or PEG_USD_AZN_RATE
    clean_excess_usd = max(0.0, round(float(excess_usd), 2))

    if clean_excess_usd <= 0.0:
        return DutyBreakdown(
            excess_usd=0.0,
            excess_azn=0.0,
            tariff_duty_azn=0.0,
            vat_azn=0.0,
            clearance_fee_azn=0.0,
            total_payable_azn=0.0,
            total_payable_usd=0.0,
            effective_tax_rate_pct=0.0,
            effective_burden_with_fee_pct=0.0,
        )

    excess_azn = round(clean_excess_usd * rate, 2)
    tariff_duty_azn = round(excess_azn * CUSTOMS_TARIFF_RATE, 2)
    vat_tax_base_azn = excess_azn + tariff_duty_azn
    vat_azn = round(vat_tax_base_azn * VAT_RATE, 2)
    clearance_fee_azn = ELECTRONIC_PROCESSING_FEE_AZN

    total_payable_azn = round(tariff_duty_azn + vat_azn + clearance_fee_azn, 2)
    total_payable_usd = round(total_payable_azn / rate, 2)

    pure_tax_sum = tariff_duty_azn + vat_azn
    effective_tax_rate_pct = round((pure_tax_sum / excess_azn) * 100, 2) if excess_azn > 0 else 0.0
    effective_burden_with_fee_pct = round((total_payable_azn / excess_azn) * 100, 2) if excess_azn > 0 else 0.0

    return DutyBreakdown(
        excess_usd=clean_excess_usd,
        excess_azn=excess_azn,
        tariff_duty_azn=tariff_duty_azn,
        vat_azn=vat_azn,
        clearance_fee_azn=clearance_fee_azn,
        total_payable_azn=total_payable_azn,
        total_payable_usd=total_payable_usd,
        effective_tax_rate_pct=effective_tax_rate_pct,
        effective_burden_with_fee_pct=effective_burden_with_fee_pct,
    )


# ==============================================================================
# 6. AUTO-WARNING GENERATOR (80%, 90%, 100%+ QUOTA THRESHOLDS)
# ==============================================================================

def get_quota_status(
    used_usd: float,
    limit_usd: float = MONTHLY_ALLOWANCE_USD,
    usd_azn_rate: Optional[float] = None,
) -> QuotaStatus:
    """Generates localized risk gauge warnings and threshold logic for customs quota."""
    rate = usd_azn_rate or cbar_converter.get_rate("USD").unit_rate_azn or PEG_USD_AZN_RATE
    clean_used_usd = round(max(0.0, float(used_usd)), 2)
    clean_limit_usd = round(max(1.0, float(limit_usd)), 2)

    used_azn = round(clean_used_usd * rate, 2)
    limit_azn = round(clean_limit_usd * rate, 2)

    remaining_usd = max(0.0, round(clean_limit_usd - clean_used_usd, 2))
    remaining_azn = round(remaining_usd * rate, 2)
    pct = round((clean_used_usd / clean_limit_usd) * 100, 1)

    # 1. BREACHED (100%+)
    if clean_used_usd >= clean_limit_usd:
        excess_usd = round(clean_used_usd - clean_limit_usd, 2)
        excess_azn = round(excess_usd * rate, 2)
        duty = calculate_duty_on_excess(excess_usd, rate)

        return QuotaStatus(
            limit_usd=clean_limit_usd,
            limit_azn=limit_azn,
            used_usd=clean_used_usd,
            used_azn=used_azn,
            remaining_usd=0.0,
            remaining_azn=0.0,
            utilization_pct=pct,
            threshold_level=ThresholdLevel.BREACHED_100,
            alert_badge="LİMİT AŞILDI (100%+)",
            alert_color="rose-500",
            warning_title="Gömrük Limiti Aşıldı - Vergi və Rüsum Hesablanır",
            warning_message=(
                f"300$ aylıq güzəşt limiti ${excess_usd:.2f} USD ({excess_azn:.2f} AZN) məbləğində aşılmışdır. "
                f"Gözlənilən gömrük borcu: {duty.total_payable_azn:.2f} AZN ({duty.tariff_duty_azn:.2f} AZN rüsum + "
                f"{duty.vat_azn:.2f} AZN ƏDV + 15 AZN elektron yığım)."
            ),
            actionable_recommendations=[
                "SmartCustoms portalında bəyannamə 'Gömrük ödənişi ilə' statusuna keçəcəkdir.",
                f"Ödənişi Hökumət Ödəniş Portalı (gpp.az) və ya SmartCustoms mobil tətbiqi vasitəsilə edin ({duty.total_payable_azn:.2f} AZN).",
                "Əgər bağlama hələ xarici karqo anbarındadırsa, bağlamanı ailə üzvünün FİN koduna yönləndirərək rüsumu 0 AZN-ə endirə bilərsiniz.",
            ],
        )

    # 2. CRITICAL (90% - 99.9%)
    if pct >= 90.0:
        return QuotaStatus(
            limit_usd=clean_limit_usd,
            limit_azn=limit_azn,
            used_usd=clean_used_usd,
            used_azn=used_azn,
            remaining_usd=remaining_usd,
            remaining_azn=remaining_azn,
            utilization_pct=pct,
            threshold_level=ThresholdLevel.CRITICAL_90,
            alert_badge="KRİTİK ZOLAĞ (90%+)",
            alert_color="orange-500",
            warning_title="Kritik Hədd - 90% Limiti Tükəndi",
            warning_message=(
                f"Aylıq limitin {pct:.1f}%-i istifadə edilib. Qalan rüsumsuz limit cəmi ${remaining_usd:.2f} "
                f"({remaining_azn:.2f} AZN)-dir. Yeni bağlama əlavə edildikdə gömrük rüsumuna (35.7% + 15 AZN) düşmə ehtimalı yüksəkdir."
            ),
            actionable_recommendations=[
                f"Növbəti sifarişinizin ümumi məbləğinin ${remaining_usd:.2f}-dan az olmasına diqqət edin.",
                "Bağlamanı növbəti təqvim ayının 1-dək karqo xarici anbarında saxlamaq (Hold) tövsiyə olunur.",
                "Sifarişləri ailə üzvünün FİN profilinə keçirərək 300$ təzə limitdən yararlanın.",
            ],
        )

    # 3. WARNING (80% - 89.9%)
    if pct >= 80.0:
        return QuotaStatus(
            limit_usd=clean_limit_usd,
            limit_azn=limit_azn,
            used_usd=clean_used_usd,
            used_azn=used_azn,
            remaining_usd=remaining_usd,
            remaining_azn=remaining_azn,
            utilization_pct=pct,
            threshold_level=ThresholdLevel.WARNING_80,
            alert_badge="XƏBƏRDARLIQ (80%+)",
            alert_color="amber-500",
            warning_title="Xəbərdarlıq - 80% Həddinə Çatıldı",
            warning_message=(
                f"300$ limitinin {pct:.1f}%-i dolmuşdur. Qalan rüsumsuz məbləğ: ${remaining_usd:.2f} "
                f"({remaining_azn:.2f} AZN). Yüksək qiymətli bağlamaları planlaşdırarkən ehtiyatlı olun."
            ),
            actionable_recommendations=[
                "Yeni bağlamalar əlavə etməzdən əvvəl səbət dəyərini SmartCustoms proqnozlayıcısı ilə yoxlayın.",
                "Sifarişi 2 müxtəlif göndərişə bölərək limitin aşılmasının qarşısını alın.",
            ],
        )

    # 4. SAFE (< 80%)
    return QuotaStatus(
        limit_usd=clean_limit_usd,
        limit_azn=limit_azn,
        used_usd=clean_used_usd,
        used_azn=used_azn,
        remaining_usd=remaining_usd,
        remaining_azn=remaining_azn,
        utilization_pct=pct,
        threshold_level=ThresholdLevel.SAFE,
        alert_badge="TƏHLÜKƏSİZ (RÜSUMSUZ)",
        alert_color="emerald-500",
        warning_title="Təhlükəsiz Zolaq - Rüsumsuz İdxal",
        warning_message=(
            f"Aylıq limitin {pct:.1f}%-i istifadə olunub. Qalan rüsumsuz limit: ${remaining_usd:.2f} "
            f"({remaining_azn:.2f} AZN). Mallarınız rüsumsuz zolaqdadır."
        ),
        actionable_recommendations=[
            "Alış-verişi təhlükəsiz şəkildə davam etdirə bilərsiniz.",
            "Bütün bağlamalarınızı vaxtında SmartCustoms-da bəyan etməyi unutmayın.",
        ],
    )


# ==============================================================================
# 7. AUTO-CATEGORY MAPPING ENGINE (37 DGK CATEGORIES)
# ==============================================================================

# Multilingual keywords dictionary (AZ, TR, EN)
MULTILINGUAL_RULES: List[Tuple[str, str, str]] = [
    # Geyim aksesuarları
    (r"kəmər|kemer|şərf|atkı|papaq|şapka|bere|corab|çorap|corablar|çoraplar|əlcək|eldiven|qalstuk|kravat|çanta|canta|sırt çantası|pulqabı|cüzdan|çətir|şemsiye|belt|sock|socks|wallet|bag|backpack|umbrella|gloves|scarf|tie", "Geyim aksesuarları", "Digər"),
    # Ayaqqabı
    (r"ayaqqabı|ayakkabı|krossovka|spor ayakkabı|çəkmə|çizme|bot|səndəl|sandalet|başmaq|tərlik|terlik|lofer|sneaker|sneakers|shoes|boots|sandals|slippers", "Ayaqqabı", "Digər"),
    # Paltar
    (r"köynək|t-shirt|tişört|şalvar|don|kurtka|sviter|kazak|hoodie|şort|pencək|ceket|kofta|palto|geyim|mayka|ətək|etek|hırka|eşofman|pijama|sweatshirt|clothes|dress|pants|jacket|jeans|coat|sweater|shorts|skirt", "Paltar", "Digər"),
    # Telefon və aksesuarları
    (r"telefon|smartfon|cep telefonu|keys|kılıf|kilif|kabura|qulaqlıq|kulaklık|şarj|kabel|ekran qoruyucu|ekran koruyucu|powerbank|charger|cable|phone|smartphone|earphones|headphones|screen protector|case", "Telefon və aksesuarları", "Digər"),
    # Kompüter və aksesuarları
    (r"noutbuk|laptop|kompüter|bilgisayar|siçan|mouse|fare|klaviatura|klavye|usb|fleşka|flash|monitor|ssd|hdd|mousepad|graphics card|cpu|motherboard", "Kompüter və aksesuarları", "Digər"),
    # Media avadanlıqları
    (r"proyektor|projektor|mikrofon|spiker|kolonka|hoparlör|kamera|veb kamera|projector|microphone|speaker|webcam", "Media avadanlıqları", "Digər"),
    # Oyun konsolları
    (r"playstation|xbox|nintendo|gamepad|coystik|joystick|oyun pultu|gaming console|ps5|ps4", "Oyun konsolları", "Digər"),
    # Süfrə və mətbəx əşyaları
    (r"qab|qaşıq|kaşık|çəngəl|çatal|bıçaq|bicak|tava|qazan|tencere|fincan|kupa|bardak|boşqab|tabak|süzgəc|mətbəx|mutfak|termos|çaydan|çaydanlık|mug|spoon|fork|knife|pan|pot|kitchenware|cup|plate", "Süfrə və mətbəx əşyaları", "Digər"),
    # Tekstil
    (r"paspas|yastıq|yastık|yorğan|yorgan|dəsmal|havlu|pərdə|perde|xalça|halı|kilim|mələfə|çarşaf|örtük|örtü|towel|blanket|pillow|curtain|carpet|rug|bedsheet", "Tekstil", "Digər"),
    # Kosmetik vasitələr
    (r"krem|pomada|tuş|maskara|parfüm|parfum|ətir|şampun|şampuan|sabun|kosmetika|dodaq|dudak|üz təmizləyici|cilt bakımı|saç|serum|losyon|shampoo|cream|perfume|lipstick|cosmetics|skincare|soap", "Kosmetik vasitələr", "Digər"),
    # Ampüllər/lampalar
    (r"lampa|lamba|işıq|ışık|led|bra|lyustr|avize|lampoçka|ampul|gecə lambası|lamp|light|bulb|chandelier|led strip", "Ampüllər/lampalar", "Digər"),
    # Suvenir və oyuncaqlar
    (r"oyuncaq|oyuncak|fiqur|figür|pazl|puzzle|kukla|bebek|lego|suvenir|hediye|süs|maket|peluş|toy|doll|action figure|souvenir", "Suvenir və oyuncaqlar", "Digər"),
    # Ofis ləvazimatları
    (r"qələm|kalem|kalemlik|dəftər|defter|bloknot|marker|qovluq|dosya|xətkeş|cetvel|yapışqan|zımba|stiker|etiket|pen|notebook|stationery|pencil|folder", "Ofis ləvazimatları", "Digər"),
    # Ev aksesuarları (mebel, dekor)
    (r"dekor|dekorasyon|çərçivə|çerçeve|vaza|vazo|şam|mum|saat|güzgü|ayna|orqanayzer|düzenleyici|rəf|raf|mebel|mobilya|qutu|kutu|askı|tutucu|clock|mirror|frame|furniture|vase|shelf", "Ev aksesuarları (mebel, dekor)", "Digər"),
    # Təmir-tikinti alətləri
    (r"drel|matkap|vint|vida|tornavida|kəlbətin|pense|çəkic|çekiç|yapışdırıcı|ölçü|alət|alet|tools|screwdriver|hammer|drill|wrench|pliers", "Təmir-tikinti alətləri", "Digər"),
    # Kimyəvi təmizləyici vasitələr
    (r"təmizləyici|temizleyici|yuyucu|fırça|fırçası|sprey|detergent|süngər|sünger|cleaner|brush|sponge|detergent", "Kimyəvi təmizləyici vasitələr", "Digər"),
    # Zinət əşyaları
    (r"üzük|yüzük|sırğa|küpe|boyunbağı|kolye|qolbaq|bileklik|kulon|bijuteriya|takı|jewelry|ring|necklace|earrings|bracelet", "Zinət əşyaları", "Digər"),
    # İdman alətləri
    (r"fitness|idman|spor|trenajor|rezin|yoqa|yoga|top|sport|dumbbell|barbell|jump rope", "İdman alətləri", "Digər"),
    # Elektronika
    (r"adaptor|adapter|rozetka|priz|uzadıcı|timer|tərəzi|terazi|ölçən|elektron|power strip|socket|smart plug", "Elektronika", "Digər"),
    # Məişət avadanlıqları (kiçik)
    (r"fen|ütü|ütüsü|ütü|çaydan elektirk|toster|blender|mikser|tozsoran|kofe maşını|hair dryer|iron|toaster|blender|vacuum cleaner", "Məişət avadanlıqları (kiçik)", "Digər"),
    # Məişət avadanlıqları (böyük)
    (r"paltaryuyan|soyuducu|qabyuyan|kondisioner|soba|washing machine|refrigerator|dishwasher|air conditioner", "Məişət avadanlıqları (böyük)", "Digər"),
    # Maşın ehtiyat hissələri
    (r"avtomobil|maşın|araba|ehtiyat hissə|filtir|filtr|təkər|lastik|fara|silecek|şüşəsilən|car parts|wiper|filter", "Maşın ehtiyat hissələri", "Digər"),
    # Kitablar
    (r"kitab|kitap|roman|dərslik|albom|ensiklopediya|book|novel|textbook", "Kitablar", "Digər"),
    # Musiqi alətləri
    (r"gitara|piano|skripka|kamança|tar|sintezator|guitar|violin|musical instrument", "Musiqi alətləri", "Digər"),
    # Optik cihazlar
    (r"eynək|gözlük|gün eynəyi|linza|teleskop|mikroskop|glasses|sunglasses|contact lenses|binoculars", "Optik cihazlar", "Digər"),
    # Heyvan ləvazimatları
    (r"it üçün|pişik üçün|köpek|kedi|tasma|heyvan yemi|qum|pet food|cat litter|dog collar", "Heyvan ləvazimatları", "Digər"),
    # Qida əlavələri/dərman (Restricted)
    (r"vitamin|dərman|ilaç|supplement|probiotik|kollagen|protein|balıq yağı|omega 3|creatine", "Qida əlavələri/dərman", "Digər"),
    # Tibbi ləvazimatlar
    (r"tonometr|qlyukometr|termometr|maska|bint|tibbi|blood pressure|thermometer|medical mask", "Tibbi ləvazimatlar", "Digər"),
    # Bağ ləvazimatları
    (r"bağ|budama|qayçı|suvarma|şlanq|torpaq|garden tools|hose|pruning shears", "Bağ ləvazimatları", "Digər"),
    # Bitki və bitki toxumları (Restricted)
    (r"toxum|tohum|ting|bitki|çiçək toxumu|seeds|plant seeds", "Bitki və bitki toxumları", "Digər"),
    # Hobbi və əl işi
    (r"boya|fırça dəsti|kətan|toxuma|yun|boncuk|crafts|embroidery|knitting|painting canvas", "Hobbi və əl işi", "Digər"),
    # Ovçuluq ləvazimatları
    (r"tilov|tilov qarmağı|balıq ovu|olta|hunting|fishing rod|fishing lure", "Ovçuluq ləvazimatları", "Digər"),
    # Ərzaq
    (r"şirniyyat|çay|qəhvə|şokolad|zeytun yağı|qida|food|tea|coffee|chocolate", "Ərzaq", "Digər"),
    # Spirtli içkilər (Restricted)
    (r"şərab|şampan|viski|araq|pivə|konyak|vodka|wine|whiskey|beer|alcohol", "Spirtli içkilər", "Digər"),
    # Tütün məmulatları (Restricted)
    (r"siqaret|siqar|veyp|elektron siqaret|tütün|iqos|tobacco|cigarette|vape", "Tütün məmulatları", "Digər"),
    # Mülki dövriyyəsi məhdudlaşdırılmış mallar (Restricted/Prohibited)
    (r"dron|kvadrokopter|gizli kamera|casus|lazer göstərici|pnevmatik|silah|drone|quadcopter|hidden camera|jammer", "Mülki dövriyyəsi məhdudlaşdırılmış mallar", "Digər"),
    # Heyvanlar (Restricted)
    (r"canlı balıq|canlı heyvan|live animal", "Heyvanlar", "Digər"),
]

# Chinese Keywords Dictionary for Taobao / 1688 / Tmall
CHINESE_RULES: List[Tuple[str, List[str]]] = [
    ("Paltar", ["短袖", "长袖", "T恤", "纯棉衣服", "衬衫", "卫衣", "连帽", "毛衣", "针织衫", "大衣", "羽绒服", "棉衣", "夹克", "牛仔裤", "裤子", "短裤", "裙子", "连衣裙", "睡衣", "衣服", "女装", "男装", "童装"]),
    ("Ayaqqabı", ["运动鞋", "跑步鞋", "休闲鞋", "板鞋", "帆布鞋", "皮鞋", "高跟鞋", "凉鞋", "拖鞋", "棉拖鞋", "马丁靴", "短靴", "雪地靴", "女鞋", "男鞋", "鞋子", "鞋"]),
    ("Geyim aksesuarları", ["单肩包", "斜挎包", "手提包", "双肩包", "背包", "书包", "钱包", "皮带", "腰带", "帽子", "鸭舌帽", "棒球帽", "渔夫帽", "围巾", "手套", "袜子", "短袜", "丝袜", "领带", "雨伞", "发夹", "发圈", "包包"]),
    ("Telefon və aksesuarları", ["手机壳", "保护套", "钢化膜", "手机膜", "蓝牙耳机", "有线耳机", "耳机", "充电器", "快充", "数据线", "Type-C", "充电宝", "移动电源", "手机支架", "自拍杆", "智能手机", "手机"]),
    ("Kompüter və aksesuarları", ["笔记本电脑", "台式电脑", "显示器", "鼠标", "机械键盘", "蓝牙键盘", "键盘", "鼠标垫", "固态硬盘", "SSD", "移动硬盘", "U盘", "内存条", "散热器", "扩展坞", "集线器", "网线", "电脑"]),
    ("Süfrə və mətbəx əşyaları", ["保温杯", "水杯", "马克杯", "餐具", "筷子", "勺子", "叉子", "碗", "陶瓷盘", "盘子", "炒锅", "平底锅", "汤锅", "菜刀", "菜板", "砧板", "开瓶器", "茶壶", "茶具", "餐具", "锅具"]),
    ("Ev aksesuarları (mebel, dekor)", ["收纳盒", "收纳箱", "整理盒", "置物架", "衣架", "挂钩", "相框", "花瓶", "摆件", "装饰画", "壁画", "化妆镜", "梳妆镜", "全身镜", "挂钟", "香薰", "垃圾桶", "鞋架", "椅子", "收纳", "家具"]),
    ("Tekstil", ["四件套", "床单", "被套", "枕头", "抱枕", "毛毯", "毯子", "冬被", "窗帘", "桌布", "毛巾", "浴巾", "地毯", "地垫", "坐垫", "床上用品", "纺织品"]),
    ("Kosmetik vasitələr", ["面膜", "洗面奶", "爽肤水", "乳液", "面霜", "精华液", "眼霜", "防晒霜", "卸妆水", "口红", "唇膏", "粉底液", "散粉", "眼影", "眼线笔", "睫毛膏", "腮红", "香水", "洗发水", "沐浴露", "化妆品", "护肤品"]),
    ("Ampüllər/lampalar", ["台灯", "吊灯", "吸顶灯", "落地灯", "壁灯", "小夜灯", "LED灯泡", "灯泡", "LED灯带", "灯条", "手电筒", "射灯", "筒灯", "灯具", "灯饰", "灯"]),
    ("Suvenir və oyuncaqlar", ["公仔", "玩偶", "手办", "模型", "车模", "盲盒", "拼图", "积木", "遥控车", "玩具"]),
    ("Ofis ləvazimatları", ["中性笔", "签字笔", "圆珠笔", "钢笔", "记号笔", "铅笔", "笔记本", "记事本", "便签", "文件夹", "订书机", "剪刀", "美工刀", "胶带", "文具", "办公用品"]),
    ("Təmir-tikinti alətləri", ["螺丝刀", "扳手", "电钻", "冲击钻", "钳子", "铁锤", "卷尺", "水平仪", "热熔胶枪", "电烙铁", "万用表", "螺丝钉", "工具箱", "五金工具"]),
    ("Kimyəvi təmizləyici vasitələr", ["清洁剂", "油污净", "洗衣液", "洗衣粉", "洗衣凝珠", "消毒液", "除垢剂", "马桶刷", "抹布", "百洁布", "海绵擦", "拖把", "扫把", "洗涤剂"]),
    ("İdman alətləri", ["瑜伽垫", "瑜伽球", "拉力器", "阻力带", "哑铃", "跳绳", "握力器", "健腹轮", "护膝", "羽毛球拍", "乒乓球拍", "篮球", "足球", "泳镜", "健身器材"]),
    ("Elektronika", ["插座", "插排", "转换插头", "定时器", "电子秤", "体脂秤", "温湿度计", "电池", "充电电池", "电子元件"]),
    ("Məişət avadanlıqları (kiçik)", ["吹风机", "卷发棒", "直发板", "电动牙刷", "剃须刀", "刮胡刀", "电水壶", "加湿器", "挂烫机", "电熨斗", "吸尘器", "榨汁机", "空气炸锅", "电饭煲", "小家电"]),
    ("Zinət əşyaları", ["戒指", "项链", "吊坠", "耳钉", "耳环", "手链", "手镯", "脚链", "胸针", "首饰", "珠宝", "饰品"]),
    ("Optik cihazlar", ["近视眼镜", "老花镜", "防蓝光眼镜", "太阳镜", "墨镜", "隐形眼镜", "镜架", "放大镜", "望远镜", "眼镜"]),
    ("Heyvan ləvazimatları", ["猫粮", "狗粮", "猫砂", "猫罐头", "狗罐头", "猫抓板", "猫窝", "狗窝", "牵引绳", "狗链", "逗猫棒", "宠物用品"]),
    ("Media avadanlıqları", ["投影仪", "麦克风", "话筒", "蓝牙音箱", "音响", "摄像头"]),
    ("Oyun konsolları", ["Switch", "PS5", "PS4", "Xbox", "游戏机", "游戏手柄", "游戏卡带"]),
    ("Maşın ehtiyat hissələri", ["车载支架", "车载充电器", "汽车坐垫", "汽车脚垫", "行车记录仪", "胎压监测", "充气泵", "车载香薰", "雨刮器", "汽车用品"]),
    ("Kitablar", ["正版图书", "小说", "书籍", "画册", "绘本", "字典", "图书"]),
    ("Musiqi alətləri", ["吉他", "尤克里里", "电子琴", "电钢琴", "口琴", "笛子", "古筝", "小提琴", "乐器"]),
    ("Spirtli içkilər", ["白酒", "红酒", "葡萄酒", "啤酒", "威士忌", "洋酒", "伏特加"]),
    ("Tütün məmulatları", ["电子烟", "雾化器", "烟油", "烟斗", "雪茄", "香烟"]),
    ("Ərzaq", ["零食", "坚果", "糖果", "巧克力", "饼干", "茶叶", "咖啡豆", "食品"]),
    ("Mülki dövriyyəsi məhdudlaşdırılmış mallar", ["无人机", "航拍器", "针孔摄像", "隐形摄像", "监听器", "激光笔", "电击器"]),
]


def classify_product_category(title: str | None) -> CategorySuggestion:
    """Classifies an item title into the official DGK 37 Category system with regulatory checks."""
    if not title or not title.strip():
        return CategorySuggestion(
            main_cat="Ev aksesuarları (mebel, dekor)",
            sub_cat="Digər",
            confidence=0.50,
            matched_keyword="",
            match_source="fallback_empty",
        )

    raw_title = title.strip()
    low_title = raw_title.lower()

    # 1. Chinese Character Sequence Matching (Taobao / 1688 / Tmall)
    has_chinese = bool(re.search(r"[\u4e00-\u9fff]", raw_title))
    if has_chinese:
        best_zh_cat: Optional[str] = None
        best_zh_kw = ""
        max_score = 0

        for cat, kws in CHINESE_RULES:
            for kw in kws:
                if kw in raw_title:
                    score = len(kw)
                    if score > max_score:
                        max_score = score
                        best_zh_cat = cat
                        best_zh_kw = kw

        if best_zh_cat and best_zh_cat in DGK_37_CATEGORIES:
            reg_info = CATEGORY_REGULATORY_RULES.get(best_zh_cat, {})
            return CategorySuggestion(
                main_cat=best_zh_cat,
                sub_cat="Digər",
                confidence=min(0.98, round(0.70 + (max_score * 0.08), 2)),
                matched_keyword=best_zh_kw,
                match_source="chinese_exact_keyword",
                is_restricted=reg_info.get("is_restricted", False),
                restriction_warning=reg_info.get("warning_az"),
                requires_license=reg_info.get("requires_license", False),
            )

    # 2. Strict Multilingual Regex & Word-Boundary Matching (AZ / TR / EN)
    best_latin_cat: Optional[str] = None
    best_latin_sub = "Digər"
    best_latin_kw = ""
    max_len = 0

    for pattern, main_c, sub_c in MULTILINGUAL_RULES:
        match = re.search(pattern, low_title)
        if match:
            matched_str = match.group(0)
            if len(matched_str) > max_len:
                max_len = len(matched_str)
                best_latin_cat = main_c
                best_latin_sub = sub_c
                best_latin_kw = matched_str

    if best_latin_cat and best_latin_cat in DGK_37_CATEGORIES:
        reg_info = CATEGORY_REGULATORY_RULES.get(best_latin_cat, {})
        confidence = min(0.95, round(0.75 + (max_len * 0.03), 2))
        return CategorySuggestion(
            main_cat=best_latin_cat,
            sub_cat=best_latin_sub,
            confidence=confidence,
            matched_keyword=best_latin_kw,
            match_source="multilingual_regex",
            is_restricted=reg_info.get("is_restricted", False),
            restriction_warning=reg_info.get("warning_az"),
            requires_license=reg_info.get("requires_license", False),
        )

    # 3. Fallback to default safe household/decor category
    return CategorySuggestion(
        main_cat="Ev aksesuarları (mebel, dekor)",
        sub_cat="Digər",
        confidence=0.40,
        matched_keyword="",
        match_source="default_fallback",
        alternative_suggestions=["Geyim aksesuarları", "Elektronika", "Ofis ləvazimatları"],
    )


# ==============================================================================
# 8. PREDICTION & WHAT-IF BASKET OPTIMIZER
# ==============================================================================

def predict_basket_duty(
    current_month_spent_usd: float,
    basket_items: List[BasketItem],
    target_fin: Optional[str] = None,
    available_fins: Optional[List[Dict[str, Any]]] = None,
    usd_azn_rate: Optional[float] = None,
) -> PredictionResult:
    """Simulates quota impact, calculates marginal duty, and provides optimization advice.

    Mathematical Workflow:
    ----------------------
    1. Evaluate mixed currency basket -> convert each item to AZN and USD.
    2. Assess Current Quota Status (before purchase).
    3. Calculate Projected Monthly Spending:
       Projected_USD = Current_Spent_USD + Basket_Total_USD
    4. Calculate Marginal Excess attributable to this basket:
       If Current_Spent_USD >= 300:
           Spillover_USD = Basket_Total_USD (Entire basket taxable)
       Else if Projected_USD > 300:
           Spillover_USD = Projected_USD - 300 (Only excess taxable)
       Else:
           Spillover_USD = 0.0 (Duty-free)
    5. Compute Duty on Spillover Amount:
       15% Tariff + 18% VAT + 15 AZN fee.
    6. Formulate Optimization Strategies (e.g. FIN splitting, Warehouse hold).
    """
    rate = usd_azn_rate or cbar_converter.get_rate("USD").unit_rate_azn or PEG_USD_AZN_RATE
    clean_current_usd = max(0.0, round(float(current_month_spent_usd), 2))

    # 1. Evaluate basket items & multi-currency conversion
    basket_azn, basket_usd, ccy_breakdown = cbar_converter.evaluate_mixed_basket(basket_items)

    # 2. Categorize all items & check for statutory restrictions
    items_categorized = []
    has_restricted = False
    reg_alerts = []

    for it in basket_items:
        sugg = classify_product_category(it.title)
        it_azn = cbar_converter.convert_to_azn(it.line_total, it.currency)
        it_usd = cbar_converter.convert_to_usd(it.line_total, it.currency)

        if sugg.is_restricted:
            has_restricted = True
            if sugg.restriction_warning and sugg.restriction_warning not in reg_alerts:
                reg_alerts.append(f"[{sugg.main_cat}]: {sugg.restriction_warning}")

        items_categorized.append({
            "title": it.title,
            "currency": it.currency,
            "price": it.price,
            "quantity": it.quantity,
            "line_total": it.line_total,
            "line_total_azn": it_azn,
            "line_total_usd": it_usd,
            "suggested_main_cat": sugg.main_cat,
            "suggested_sub_cat": sugg.sub_cat,
            "confidence": sugg.confidence,
            "matched_keyword": sugg.matched_keyword,
            "is_restricted": sugg.is_restricted,
            "requires_license": sugg.requires_license,
        })

    # 3. Current & Projected Quota Status
    current_status = get_quota_status(clean_current_usd, MONTHLY_ALLOWANCE_USD, rate)
    projected_usd = round(clean_current_usd + basket_usd, 2)
    projected_status = get_quota_status(projected_usd, MONTHLY_ALLOWANCE_USD, rate)

    # 4. Marginal Excess & Duty Calculation
    if clean_current_usd >= MONTHLY_ALLOWANCE_USD:
        spillover_excess_usd = basket_usd
    elif projected_usd > MONTHLY_ALLOWANCE_USD:
        spillover_excess_usd = round(projected_usd - MONTHLY_ALLOWANCE_USD, 2)
    else:
        spillover_excess_usd = 0.0

    marginal_duty = calculate_duty_on_excess(spillover_excess_usd, rate)

    # 5. Threshold Transition Label
    transition_str = f"{current_status.threshold_level.value.upper()} -> {projected_status.threshold_level.value.upper()}"

    # 6. Formulate Smart Optimization Strategies
    strategies: List[OptimizationStrategy] = []

    if marginal_duty.total_payable_azn > 0:
        # Strategy A: Hold in Carrier Warehouse until 1st of next month
        strategies.append(OptimizationStrategy(
            strategy_name="Karqo Xarici Anbarında Saxlama (Hold in Warehouse)",
            description=(
                f"Bağlamanı xarici karqo anbarında (Türkiyə/Çin/ABŞ) növbəti təqvim ayının 1-dək saxlayın. "
                f"Yeni ayda 300$ limitiniz sıfırlanacaq və bu bağlama üçün gömrük rüsumu 0 AZN olacaqdır."
            ),
            estimated_duty_savings_azn=marginal_duty.total_payable_azn,
            action_type="hold_in_warehouse",
            is_recommended=True,
        ))

        # Strategy B: FIN Splitting (Use Secondary Family FIN Profile)
        other_fins = [f for f in (available_fins or []) if f.get("fin") != target_fin]
        if other_fins:
            secondary_fin = other_fins[0].get("fin", "Digər FİN")
            sec_name = other_fins[0].get("full_name", "Ailə üzvü")
            strategies.append(OptimizationStrategy(
                strategy_name=f"FİN Bölünməsi ({sec_name} - {secondary_fin})",
                description=(
                    f"Bu sifarişi digər aktiv ailə üzvünün FİN profilinə ({secondary_fin}) yönləndirin. "
                    f"Onun aylıq 300$ limitindən istifadə edilərək gömrük rüsumundan tam azad olunacaqsınız."
                ),
                estimated_duty_savings_azn=marginal_duty.total_payable_azn,
                action_type="fin_splitting",
                is_recommended=True,
            ))

        # Strategy C: Cart Split (if basket has multiple items)
        if len(basket_items) > 1 and current_status.remaining_usd > 0:
            strategies.append(OptimizationStrategy(
                strategy_name="Səbəti İki Hissəyə Bölmək (Cart Split)",
                description=(
                    f"Səbətdəki məhsulları ayırın: birinci partiyanı ${current_status.remaining_usd:.2f} limitinə "
                    f"uyğunlaşdırıb bu ay gətirin, qalan məhsulları isə növbəti aya saxlayın."
                ),
                estimated_duty_savings_azn=round(marginal_duty.tariff_duty_azn + marginal_duty.vat_azn, 2),
                action_type="cart_split",
                is_recommended=False,
            ))

    return PredictionResult(
        current_quota=current_status,
        basket_total_usd=basket_usd,
        basket_total_azn=basket_azn,
        currency_breakdown=ccy_breakdown,
        projected_total_usd=projected_usd,
        projected_quota=projected_status,
        spillover_excess_usd=spillover_excess_usd,
        marginal_duty=marginal_duty,
        threshold_transition=transition_str,
        items_categorized=items_categorized,
        optimization_strategies=strategies,
        has_restricted_items=has_restricted,
        regulatory_alerts=reg_alerts,
    )


# ==============================================================================
# 9. INTEGRATED SMARTCUSTOMS ENGINE FACADE
# ==============================================================================

class SmartCustomsEngine:
    """Unified High-Level Interface for Duty Calculation, Category Intelligence & Threshold Warnings."""

    def __init__(self, cbar_client: Optional[CBARCurrencyConverter] = None) -> None:
        self.cbar = cbar_client or cbar_converter

    def calculate_duty(self, excess_usd: float, usd_azn_rate: Optional[float] = None) -> DutyBreakdown:
        return calculate_duty_on_excess(excess_usd, usd_azn_rate)

    def check_quota(
        self,
        used_usd: float,
        limit_usd: float = MONTHLY_ALLOWANCE_USD,
        usd_azn_rate: Optional[float] = None,
    ) -> QuotaStatus:
        return get_quota_status(used_usd, limit_usd, usd_azn_rate)

    def classify_title(self, title: str | None) -> CategorySuggestion:
        return classify_product_category(title)

    def convert_currency(self, amount: float, from_ccy: str, to_ccy: str = "AZN") -> float:
        return self.cbar.convert_between(amount, from_ccy, to_ccy)

    def predict(
        self,
        current_month_spent_usd: float,
        basket_items: List[BasketItem],
        target_fin: Optional[str] = None,
        available_fins: Optional[List[Dict[str, Any]]] = None,
        usd_azn_rate: Optional[float] = None,
    ) -> PredictionResult:
        return predict_basket_duty(
            current_month_spent_usd=current_month_spent_usd,
            basket_items=basket_items,
            target_fin=target_fin,
            available_fins=available_fins,
            usd_azn_rate=usd_azn_rate,
        )


# Global Engine Instance
smart_customs_engine = SmartCustomsEngine()


# Convenient module-level aliases
convert_currency = cbar_converter.convert_between
