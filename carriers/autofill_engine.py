"""PCS v3.5 Zero-Friction 1-Click Address Autofill Engine & Bookmarklet.

Specialized for Trendyol Turkey, Taobao / 1688 China, and Azerbaijani Freight Forwarders:
Starex, Limak, Camex, and Dynamex.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

try:
    from carriers.address_formatter import CARRIER_WAREHOUSES, AddressFormatterEngine
except (ImportError, ModuleNotFoundError):
    try:
        from carriers.address_formatter import CARRIER_WAREHOUSES, AddressFormatterEngine
    except (ImportError, ModuleNotFoundError):
        from address_formatter import CARRIER_WAREHOUSES, AddressFormatterEngine


# ============================================================================
# 1. DATA MODELS & CONFIGURATION SCHEMAS
# ============================================================================

class AutofillFieldSelector(BaseModel):
    """Field mapping rule containing multi-layer CSS selectors and fallbacks."""
    field_key: str = Field(..., description="Canonical key (e.g. first_name, last_name, phone, city, etc.)")
    label: str = Field(..., description="Human-readable field label")
    css_selectors: List[str] = Field(..., description="Priority-ordered CSS selectors")
    fallback_placeholders: List[str] = Field(default_factory=list, description="Fallback placeholder/aria-label keywords")
    input_type: str = Field(default="text", description="text, textarea, select, custom_dropdown, cascader, checkbox")
    transform_rule: Optional[str] = Field(default=None, description="Optional transformation, e.g. TR_PHONE_10_DIGIT, SUITE_IN_SOYAD")


class AntiBotTimingConfig(BaseModel):
    """Timing and behavioral heuristics to safeguard against anti-bot heuristics (DataDome, AliSec, Cloudflare)."""
    min_field_delay_ms: int = Field(default=35, description="Minimum delay between filling individual form fields")
    max_field_delay_ms: int = Field(default=85, description="Maximum jitter delay between filling individual form fields")
    simulate_keystrokes: bool = Field(default=False, description="Simulate keystroke jitter on sensitive inputs")
    keystroke_min_delay_ms: int = Field(default=12, description="Min keystroke delay")
    keystroke_max_delay_ms: int = Field(default=30, description="Max keystroke delay")
    dispatch_full_lifecycle: bool = Field(default=True, description="Fire focus -> keydown -> input -> keyup -> change -> blur")
    highlight_fields: bool = Field(default=True, description="Visually highlight filled fields in emerald green")
    highlight_color: str = Field(default="#10b981", description="Glow color for successful field population")
    human_in_the_loop_only: bool = Field(default=True, description="Strict rule: Never auto-submit payment or checkout button")


class PlatformAutofillProfile(BaseModel):
    """Comprehensive autofill profile and reverse-mapping for an e-commerce platform."""
    platform_id: str = Field(..., description="trendyol, taobao, 1688, temu, amazon")
    origin_country: str = Field(..., description="TR, CN, US, DE")
    display_name: str = Field(..., description="Display title with country flag")
    url_patterns: List[str] = Field(..., description="Regex patterns to auto-detect platform from window.location.href")
    smart_parse_supported: bool = Field(default=False, description="Whether platform supports 1-click smart address parsing textarea")
    smart_parse_selectors: List[str] = Field(default_factory=list, description="Selectors for smart parsing input")
    smart_parse_btn_selectors: List[str] = Field(default_factory=list, description="Selectors for smart parsing button")
    fields: List[AutofillFieldSelector] = Field(default_factory=list, description="Ordered form field reverse-mappings")
    timing: AntiBotTimingConfig = Field(default_factory=AntiBotTimingConfig)


class AutofillPayloadResponse(BaseModel):
    """Complete address payload and mapped field dictionary for a specific carrier and checkout."""
    carrier: str
    platform: str
    origin_country: str
    customer_code: str
    branch: str
    values: Dict[str, str] = Field(default_factory=dict)
    smart_address_block: str
    summary_text: str


# ============================================================================
# 2. PLATFORM REVERSE-MAPPING DEFINITIONS
# ============================================================================

TRENDYOL_PROFILE = PlatformAutofillProfile(
    platform_id="trendyol",
    origin_country="TR",
    display_name="🇹🇷 Trendyol Turkey",
    url_patterns=[
        r"trendyol\.com/.*",
        r"checkout\.trendyol\.com/.*",
        r".*trendyol\.com/sepetim/odeme.*",
        r".*trendyol\.com/uyelik/adreslerim.*",
    ],
    smart_parse_supported=False,
    timing=AntiBotTimingConfig(
        min_field_delay_ms=35,
        max_field_delay_ms=85,
        dispatch_full_lifecycle=True,
        highlight_fields=True,
    ),
    fields=[
        AutofillFieldSelector(
            field_key="first_name",
            label="Ad (First Name)",
            css_selectors=[
                "input[name='firstName']",
                "input[data-testid='firstName-input']",
                "#firstName",
                "input[placeholder*='Adınız']",
                "input[placeholder='Ad']",
                "input[name='name']",
            ],
            fallback_placeholders=["Adınız", "Ad"],
            input_type="text",
        ),
        AutofillFieldSelector(
            field_key="last_name",
            label="Soyad (Last Name with Suite)",
            css_selectors=[
                "input[name='lastName']",
                "input[data-testid='lastName-input']",
                "#lastName",
                "input[placeholder*='Soyadınız']",
                "input[placeholder='Soyad']",
                "input[name='surname']",
            ],
            fallback_placeholders=["Soyadınız", "Soyad"],
            input_type="text",
            transform_rule="SUITE_IN_SOYAD",
        ),
        AutofillFieldSelector(
            field_key="phone",
            label="Telefon (10-digit Phone)",
            css_selectors=[
                "input[name='phoneNumber']",
                "input[data-testid='phone-input']",
                "#phoneNumber",
                "input[type='tel']",
                "input[name='phone']",
                "input[placeholder*='Telefon']",
            ],
            fallback_placeholders=["Telefon", "Cep Telefonu"],
            input_type="text",
            transform_rule="TR_PHONE_10_DIGIT",
        ),
        AutofillFieldSelector(
            field_key="city",
            label="İl (City)",
            css_selectors=[
                "select[name='cityId']",
                "select[data-testid='city-select']",
                "select[name='city']",
                "div[data-testid='city-select']",
                ".ty-city-select",
                "input[placeholder*='İl seçiniz']",
                "input[placeholder*='İl Seçiniz']",
            ],
            fallback_placeholders=["İl", "Şehir", "İl seçiniz"],
            input_type="custom_dropdown",
        ),
        AutofillFieldSelector(
            field_key="district",
            label="İlçe (District)",
            css_selectors=[
                "select[name='districtId']",
                "select[data-testid='district-select']",
                "select[name='district']",
                "div[data-testid='district-select']",
                ".ty-district-select",
                "input[placeholder*='İlçe seçiniz']",
                "input[placeholder*='İlçe Seçiniz']",
            ],
            fallback_placeholders=["İlçe", "İlçe seçiniz"],
            input_type="custom_dropdown",
        ),
        AutofillFieldSelector(
            field_key="neighborhood",
            label="Mahalle (Quarter)",
            css_selectors=[
                "select[name='neighborhoodId']",
                "select[data-testid='neighborhood-select']",
                "select[name='neighborhood']",
                "div[data-testid='neighborhood-select']",
                ".ty-neighborhood-select",
                "input[placeholder*='Mahalle seçiniz']",
                "input[placeholder*='Mahalle Seçiniz']",
            ],
            fallback_placeholders=["Mahalle", "Mahalle seçiniz"],
            input_type="custom_dropdown",
        ),
        AutofillFieldSelector(
            field_key="address_line1",
            label="Açık Adres (Street Address & Suite)",
            css_selectors=[
                "textarea[name='addressLine1']",
                "textarea[data-testid='address-input']",
                "textarea[name='address']",
                "textarea[name='line']",
                "#addressLine1",
                "textarea[placeholder*='Adres']",
                "input[name='addressLine1']",
            ],
            fallback_placeholders=["Adres", "Açık Adres", "Sokak, Mahalle, Kapı No"],
            input_type="textarea",
        ),
        AutofillFieldSelector(
            field_key="zip_code",
            label="Posta Kodu (ZIP)",
            css_selectors=[
                "input[name='postalCode']",
                "input[name='postCode']",
                "input[name='zipCode']",
                "input[placeholder*='Posta Kodu']",
                "input[placeholder*='Posta kodu']",
                "#postalCode",
            ],
            fallback_placeholders=["Posta Kodu", "PK"],
            input_type="text",
        ),
        AutofillFieldSelector(
            field_key="tax_no",
            label="TC / Vergi Kimlik No",
            css_selectors=[
                "input[name='identityNumber']",
                "input[name='taxNumber']",
                "input[name='tcKimlikNo']",
                "input[data-testid='tc-input']",
                "input[placeholder*='T.C.']",
                "input[placeholder*='Vergi']",
                "#identityNumber",
            ],
            fallback_placeholders=["T.C. Kimlik No", "Vergi Kimlik Numarası"],
            input_type="text",
        ),
        AutofillFieldSelector(
            field_key="address_title",
            label="Adres Başlığı (Address Title)",
            css_selectors=[
                "input[name='addressTitle']",
                "input[data-testid='title-input']",
                "#addressTitle",
                "input[placeholder*='Adres Başlığı']",
                "input[name='title']",
            ],
            fallback_placeholders=["Adres Başlığı", "Örn: Evim, İşim"],
            input_type="text",
        ),
    ]
)

TAOBAO_PROFILE = PlatformAutofillProfile(
    platform_id="taobao",
    origin_country="CN",
    display_name="🇨🇳 Taobao / 1688 China",
    url_patterns=[
        r".*taobao\.com/.*",
        r".*buyertrade\.taobao\.com/.*",
        r".*cart\.taobao\.com/.*",
        r".*1688\.com/.*",
        r".*order\.1688\.com/.*",
    ],
    smart_parse_supported=True,
    smart_parse_selectors=[
        "textarea.smart-address-textarea",
        "textarea[placeholder*='粘贴整段地址']",
        "textarea[placeholder*='自动识别']",
        "textarea[placeholder*='识别']",
        ".address-parse-box textarea",
        "textarea[name='smartAddress']",
        ".smart-input textarea",
    ],
    smart_parse_btn_selectors=[
        "button.smart-address-btn",
        "button[data-action='parse']",
        ".smart-parse-btn",
        "button.address-parse-btn",
        ".smart-address-box button",
    ],
    timing=AntiBotTimingConfig(
        min_field_delay_ms=40,
        max_field_delay_ms=90,
        dispatch_full_lifecycle=True,
        highlight_fields=True,
    ),
    fields=[
        AutofillFieldSelector(
            field_key="recipient",
            label="收货人 (Recipient Name & Suite)",
            css_selectors=[
                "input[name='fullName']",
                "input[name='receiverName']",
                "input[placeholder*='收货人']",
                "input[placeholder*='姓名']",
                "#fullName",
                "input[name='deliverName']",
                ".delivery-address input[type='text']",
            ],
            fallback_placeholders=["收货人", "姓名", "请填写收货人姓名"],
            input_type="text",
        ),
        AutofillFieldSelector(
            field_key="phone",
            label="手机号码 (11-digit Chinese Mobile)",
            css_selectors=[
                "input[name='mobile']",
                "input[name='phone']",
                "input[name='mobilePhone']",
                "input[placeholder*='手机号码']",
                "input[placeholder*='11位手机号']",
                "#mobile",
                "input[type='tel']",
            ],
            fallback_placeholders=["手机号码", "电话号码", "11位手机号"],
            input_type="text",
            transform_rule="CLEAN_CN_MOBILE",
        ),
        AutofillFieldSelector(
            field_key="province",
            label="省 (Province)",
            css_selectors=[
                "select[name='prov']",
                "select[name='province']",
                ".cascader-province",
            ],
            fallback_placeholders=["省份", "请选择省"],
            input_type="cascader",
        ),
        AutofillFieldSelector(
            field_key="city",
            label="市 (City)",
            css_selectors=[
                "select[name='city']",
                ".cascader-city",
            ],
            fallback_placeholders=["城市", "请选择市"],
            input_type="cascader",
        ),
        AutofillFieldSelector(
            field_key="district",
            label="区/县 (District)",
            css_selectors=[
                "select[name='area']",
                "select[name='district']",
                ".cascader-district",
            ],
            fallback_placeholders=["区/县", "请选择区"],
            input_type="cascader",
        ),
        AutofillFieldSelector(
            field_key="street",
            label="街道/镇 (Street / Town)",
            css_selectors=[
                "select[name='town']",
                "select[name='street']",
                ".cascader-street",
            ],
            fallback_placeholders=["街道", "镇", "请选择街道"],
            input_type="cascader",
        ),
        AutofillFieldSelector(
            field_key="detail_address",
            label="详细地址 (Detailed Street Address)",
            css_selectors=[
                "textarea[name='addressDetail']",
                "textarea[name='address']",
                "textarea[name='street']",
                "textarea[placeholder*='详细地址']",
                "input[name='detailAddress']",
                "#addressDetail",
                ".address-detail-input",
            ],
            fallback_placeholders=["详细地址", "如道路、门牌号、小区、楼栋号、单元室等"],
            input_type="textarea",
        ),
        AutofillFieldSelector(
            field_key="zip_code",
            label="邮政编码 (ZIP Code)",
            css_selectors=[
                "input[name='postCode']",
                "input[name='zip']",
                "input[placeholder*='邮政编码']",
                "input[placeholder*='邮编']",
                "#postCode",
            ],
            fallback_placeholders=["邮政编码", "邮编", "6位邮政编码"],
            input_type="text",
        ),
    ]
)

PLATFORM_PROFILES: Dict[str, PlatformAutofillProfile] = {
    "trendyol": TRENDYOL_PROFILE,
    "taobao": TAOBAO_PROFILE,
    "1688": TAOBAO_PROFILE,
}


# ============================================================================
# 3. SECURITY POLICY & SPECIFICATIONS
# ============================================================================

class AutofillSecurityPolicy:
    """Security rules, CORS whitelist, JSONP sanitizers, and origin validation."""

    ALLOWED_ORIGIN_PATTERNS = [
        r"^https?://(www\.)?trendyol\.com$",
        r"^https?://checkout\.trendyol\.com$",
        r"^https?://(www\.)?taobao\.com$",
        r"^https?://buyertrade\.taobao\.com$",
        r"^https?://cart\.taobao\.com$",
        r"^https?://(www\.)?1688\.com$",
        r"^https?://order\.1688\.com$",
        r"^http://127\.0\.0\.1(:[0-9]+)?$",
        r"^http://localhost(:[0-9]+)?$",
    ]

    ALLOWED_METHODS = "GET, POST, OPTIONS"
    ALLOWED_HEADERS = "Content-Type, Authorization, X-PCS-Token, X-Requested-With, Accept"
    MAX_AGE_SECONDS = "86400"

    @classmethod
    def is_origin_allowed(cls, origin: Optional[str]) -> bool:
        if not origin:
            return True  # Direct browser bar or local invocation
        for pattern in cls.ALLOWED_ORIGIN_PATTERNS:
            if re.match(pattern, origin, re.IGNORECASE):
                return True
        return False

    @classmethod
    def get_cors_headers(cls, request_origin: Optional[str] = None) -> Dict[str, str]:
        """Produces strict CORS response headers for browser injection and bookmarklets."""
        origin_val = "*"
        if request_origin and cls.is_origin_allowed(request_origin):
            origin_val = request_origin

        headers = {
            "Access-Control-Allow-Origin": origin_val,
            "Access-Control-Allow-Methods": cls.ALLOWED_METHODS,
            "Access-Control-Allow-Headers": cls.ALLOWED_HEADERS,
            "Access-Control-Max-Age": cls.MAX_AGE_SECONDS,
            "X-Content-Type-Options": "nosniff",
        }
        if origin_val != "*":
            headers["Access-Control-Allow-Credentials"] = "true"
        return headers

    @classmethod
    def sanitize_jsonp_callback(cls, callback_name: Optional[str]) -> str:
        """Protects against XSS and injection by strictly validating JSONP callback identifier."""
        if not callback_name:
            return "pcsAutofillCallback"
        # Only allow alphanumeric, underscore, dot, dollar sign up to 64 chars
        cleaned = re.sub(r"[^a-zA-Z0-9_$.]", "", callback_name)[:64]
        return cleaned or "pcsAutofillCallback"


# ============================================================================
# 4. AUTOFILL ENGINE IMPLEMENTATION
# ============================================================================

class AutofillEngine:
    """Core engine generating field payloads, Anti-Bot injection scripts, and browser Bookmarklets."""

    @classmethod
    def clean_turkish_phone_10_digits(cls, raw_phone: str) -> str:
        """Strips country codes (+90, 90, 0) and non-digits to yield a clean 10-digit number (5XX XXX XX XX)."""
        digits = re.sub(r"\D", "", raw_phone)
        if digits.startswith("90") and len(digits) == 12:
            digits = digits[2:]
        elif digits.startswith("0") and len(digits) == 11:
            digits = digits[1:]
        return digits

    @classmethod
    def clean_chinese_phone_11_digits(cls, raw_phone: str) -> str:
        """Strips +86 and symbols to yield an 11-digit Chinese mobile number."""
        digits = re.sub(r"\D", "", raw_phone)
        if digits.startswith("86") and len(digits) == 13:
            digits = digits[2:]
        return digits

    @classmethod
    def build_payload(
        cls,
        carrier: str,
        platform: str,
        customer_code: str,
        branch: str = "28 May",
        full_name: str = "Vasif Məcidli",
        origin_country: Optional[str] = None,
    ) -> AutofillPayloadResponse:
        """Builds exact reverse-mapped field key-value pairs for the requested carrier and platform."""
        carrier = carrier.upper()
        platform = platform.lower().strip()
        if not origin_country:
            origin_country = "TR" if platform == "trendyol" else "CN"
        origin_country = origin_country.upper()

        wh_map = CARRIER_WAREHOUSES.get(carrier, {}).get(origin_country)
        if not wh_map:
            raise ValueError(f"No warehouse found for carrier '{carrier}' in country '{origin_country}'")

        suite = customer_code.strip()
        values: Dict[str, str] = {}
        smart_block = ""
        summary_text = ""

        first_name = "Vasif"
        last_name_base = "Məcidli"
        parts = full_name.split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name_base = " ".join(parts[1:])

        if platform == "trendyol" or origin_country == "TR":
            # 1. Trendyol Turkey Reverse-Mapping
            # CRITICAL RULE: Suite in Soyad for zero-loss Turkish domestic courier labeling
            suite_in_soyad = f"{last_name_base} {suite}"
            raw_phone = wh_map.get("phone", "+90 534 892 10 44")
            phone_10 = cls.clean_turkish_phone_10_digits(raw_phone)
            addr_line1 = f"{wh_map['address_line_1']} {suite}"
            city_name = wh_map["city"]
            district_name = wh_map["district"]
            neighborhood_name = f"{district_name} Mah."
            tax_no = wh_map.get("tax_no", "11111111111")
            zip_code = wh_map.get("zip_code", "34310")
            title = f"{carrier.title()} Istanbul ({branch})"

            values = {
                "first_name": first_name,
                "last_name": suite_in_soyad,
                "phone": phone_10,
                "city": city_name,
                "district": district_name,
                "neighborhood": neighborhood_name,
                "address_line1": addr_line1,
                "zip_code": zip_code,
                "tax_no": tax_no,
                "address_title": title,
            }
            smart_block = f"{addr_line1}, {neighborhood_name}, {district_name}/{city_name}, {zip_code}, {first_name} {suite_in_soyad}, {phone_10}"
            summary_text = f"Trendyol [{carrier}]: {first_name} {suite_in_soyad} | Tel: {phone_10} | {city_name}/{district_name} | {addr_line1}"

        elif platform in ("taobao", "1688") or origin_country == "CN":
            # 2. Taobao / 1688 China Reverse-Mapping
            recipient = f"{full_name} ({suite})"
            raw_phone = wh_map.get("phone", "+86 138 2841 9920")
            phone_11 = cls.clean_chinese_phone_11_digits(raw_phone)
            prov = wh_map.get("province", "广东省")
            city = wh_map.get("city", "广州市")
            dist = wh_map.get("district", "白云区")
            street = wh_map.get("street", "嘉禾街道")
            zip_code = wh_map.get("zip_code", "510440")
            detail_addr = f"{wh_map['address_line_1']} {suite}"

            # Chinese Smart Address Block for Taobao 1-Click Parsing Textarea
            # Format: 所在地区 详细地址 (Suite)，收货人，手机号，邮编
            smart_block = f"{prov}{city}{dist}{street}{wh_map['address_line_1']} ({suite})，{full_name}，{phone_11}，{zip_code}"

            values = {
                "recipient": recipient,
                "phone": phone_11,
                "province": prov,
                "city": city,
                "district": dist,
                "street": street,
                "detail_address": detail_addr,
                "zip_code": zip_code,
                "smart_address": smart_block,
            }
            summary_text = f"Taobao [{carrier}]: {recipient} | 手机: {phone_11} | 地区: {prov} {city} {dist} {street} | {detail_addr}"

        else:
            # Global fallback (US / DE)
            full_name_suite = f"{full_name} {suite}"
            values = {
                "full_name": full_name_suite,
                "address_line1": wh_map.get("address_line_1", ""),
                "address_line2": suite,
                "city": wh_map.get("city", ""),
                "state": wh_map.get("state", wh_map.get("state_code", "")),
                "zip_code": wh_map.get("zip_code", ""),
                "phone": wh_map.get("phone", ""),
            }
            smart_block = f"{full_name_suite}, {values['address_line1']}, {suite}, {values['city']}, {values['state']} {values['zip_code']}, {values['phone']}"
            summary_text = f"Global [{carrier}]: {full_name_suite} | {values['address_line1']} | {values['city']} {values['zip_code']}"

        return AutofillPayloadResponse(
            carrier=carrier,
            platform=platform,
            origin_country=origin_country,
            customer_code=suite,
            branch=branch,
            values=values,
            smart_address_block=smart_block,
            summary_text=summary_text,
        )

    @classmethod
    def generate_injection_javascript(
        cls,
        server_url: str = "http://127.0.0.1:48481",
        default_carrier: str = "STAREX",
        default_branch: str = "28 May",
        customer_code: str = "ST123456",
        minified: bool = False,
    ) -> str:
        """Generates zero-dependency vanilla JS with a Floating HUD, React/Vue synthetic event triggers, and anti-bot jitter."""
        # Pre-package emergency fallback dictionary so script works even if server is offline
        fallback_data = {
            "STAREX": {
                "TR": cls.build_payload("STAREX", "trendyol", customer_code, default_branch).model_dump(mode="json"),
                "CN": cls.build_payload("STAREX", "taobao", customer_code, default_branch).model_dump(mode="json"),
            },
            "LIMAK": {
                "TR": cls.build_payload("LIMAK", "trendyol", "LMX-10294", default_branch).model_dump(mode="json"),
                "CN": cls.build_payload("LIMAK", "taobao", "LMX-10294", default_branch).model_dump(mode="json"),
            },
            "CAMEX": {
                "TR": cls.build_payload("CAMEX", "trendyol", "CAM-11111", default_branch).model_dump(mode="json"),
                "CN": cls.build_payload("CAMEX", "taobao", "CAM-11111", default_branch).model_dump(mode="json"),
            },
            "DYNAMEX": {
                "TR": cls.build_payload("DYNAMEX", "trendyol", "DYN-22222", default_branch).model_dump(mode="json"),
                "CN": cls.build_payload("DYNAMEX", "taobao", "DYN-22222", default_branch).model_dump(mode="json"),
            },
        }
        fallback_json = json.dumps(fallback_data, ensure_ascii=False)
        profiles_json = json.dumps({k: v.model_dump(mode="json") for k, v in PLATFORM_PROFILES.items()}, ensure_ascii=False)

        raw_script = f"""(function() {{
    'use strict';
    if (window.__PCS_AUTOFILL_ACTIVE__) {{
        const existing = document.getElementById('pcs-autofill-hud');
        if (existing) {{
            existing.style.animation = 'pcsPulse 0.4s ease';
            return;
        }}
    }}
    window.__PCS_AUTOFILL_ACTIVE__ = true;

    const SERVER_URL = '{server_url}';
    let currentCarrier = '{default_carrier}';
    let currentBranch = '{default_branch}';
    let currentSuite = '{customer_code}';

    const PROFILES = {profiles_json};
    const EMERGENCY_CACHE = {fallback_json};

    // 1. Detect active platform
    function detectPlatform() {{
        const url = window.location.href.toLowerCase();
        if (url.includes('trendyol.com')) return 'trendyol';
        if (url.includes('taobao.com')) return 'taobao';
        if (url.includes('1688.com')) return '1688';
        return 'trendyol';
    }}
    const activePlatform = detectPlatform();
    const profile = PROFILES[activePlatform] || PROFILES['trendyol'];

    // 2. Anti-Bot Async Jitter Sleep
    function sleep(ms) {{
        return new Promise(resolve => setTimeout(resolve, ms));
    }}
    function randomJitter(min, max) {{
        return Math.floor(Math.random() * (max - min + 1)) + min;
    }}

    // 3. React 16/17/18 & Vue Synthetic Input Event Dispatcher
    function setNativeValue(element, value) {{
        if (!element) return false;
        try {{
            element.focus();
            element.dispatchEvent(new FocusEvent('focus', {{ bubbles: true, cancelable: true }}));

            const proto = element.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
            if (nativeSetter) {{
                nativeSetter.call(element, value);
            }} else {{
                element.value = value;
            }}

            element.dispatchEvent(new Event('input', {{ bubbles: true, cancelable: true }}));
            element.dispatchEvent(new KeyboardEvent('keydown', {{ bubbles: true, cancelable: true, key: 'Process' }}));
            element.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true, cancelable: true, key: 'Process' }}));
            element.dispatchEvent(new Event('change', {{ bubbles: true, cancelable: true }}));
            element.dispatchEvent(new FocusEvent('blur', {{ bubbles: true, cancelable: true }}));

            // Visual feedback
            element.style.transition = 'all 0.3s ease';
            element.style.outline = '2px solid #10b981';
            element.style.backgroundColor = 'rgba(16, 185, 129, 0.08)';
            setTimeout(() => {{
                element.style.outline = '';
                element.style.backgroundColor = '';
            }}, 3000);
            return true;
        }} catch (err) {{
            console.warn('[PCS Autofill] Error setting native value:', err);
            return false;
        }}
    }}

    // 4. Custom Dropdown & Cascader Solver (for Trendyol & Taobao)
    async function selectDropdownOption(selectElem, targetValue) {{
        if (!selectElem) return false;
        targetValue = targetValue.trim().toLowerCase();

        // Native <select>
        if (selectElem.tagName === 'SELECT') {{
            for (let i = 0; i < selectElem.options.length; i++) {{
                const opt = selectElem.options[i];
                if (opt.text.toLowerCase().includes(targetValue) || opt.value.toLowerCase() === targetValue) {{
                    selectElem.selectedIndex = i;
                    selectElem.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return true;
                }}
            }}
            return false;
        }}

        // Custom div combobox / searchable dropdown (e.g. Trendyol ty-select)
        selectElem.click();
        await sleep(randomJitter(60, 120));
        const options = document.querySelectorAll('.ty-select-option, .dropdown-item, .ant-select-item-option, li[role="option"]');
        for (const opt of options) {{
            if (opt.textContent.toLowerCase().includes(targetValue)) {{
                opt.click();
                await sleep(50);
                return true;
            }}
        }}
        return false;
    }}

    // 5. Fetch Address Configuration from PCS (with fallback)
    async function fetchAddressData(carrier, platform) {{
        const country = platform === 'trendyol' ? 'TR' : 'CN';
        try {{
            const url = `${{SERVER_URL}}/carriers/api/address?carrier=${{carrier}}&country=${{country}}&platform=${{platform}}&branch=${{encodeURIComponent(currentBranch)}}`;
            const resp = await fetch(url, {{ mode: 'cors' }});
            if (resp.ok) {{
                const data = await resp.json();
                if (data.customer_code) currentSuite = data.customer_code;
                return data;
            }}
        }} catch (e) {{
            console.info('[PCS Autofill] Localhost API unreachable, engaging emergency warehouse cache.');
        }}
        // Emergency Cache fallback
        const carrierCache = EMERGENCY_CACHE[carrier] || EMERGENCY_CACHE['STAREX'];
        return carrierCache[country] || carrierCache['TR'];
    }}

    // 6. Core 1-Click Execution Logic
    async function executeAutofill(hudStatus) {{
        hudStatus.textContent = 'Doldurulur...';
        hudStatus.className = 'pcs-status pcs-status-working';

        const addrData = await fetchAddressData(currentCarrier, activePlatform);
        if (!addrData || !addrData.values) {{
            hudStatus.textContent = 'Xəta: Məlumat tapılmadı';
            hudStatus.className = 'pcs-status pcs-status-err';
            return;
        }}

        let filledCount = 0;

        // Check for Taobao / 1688 Smart Address Parser First (100% Reliable!)
        if (profile.smart_parse_supported && addrData.smart_address_block) {{
            for (const sel of profile.smart_parse_selectors) {{
                const smartInput = document.querySelector(sel);
                if (smartInput && smartInput.offsetParent !== null) {{
                    setNativeValue(smartInput, addrData.smart_address_block);
                    await sleep(randomJitter(50, 100));

                    // Click smart recognize button
                    for (const btnSel of profile.smart_parse_btn_selectors) {{
                        const btn = document.querySelector(btnSel);
                        if (btn) {{
                            btn.click();
                            hudStatus.textContent = '⚡ 智能识别 Aktivləşdirildi!';
                            hudStatus.className = 'pcs-status pcs-status-ok';
                            return;
                        }}
                    }}
                }}
            }}
        }}

        // Standard sequential field-by-field reverse mapping
        for (const field of profile.fields) {{
            const val = addrData.values[field.field_key];
            if (!val) continue;

            let targetElem = null;
            for (const selector of field.css_selectors) {{
                const el = document.querySelector(selector);
                if (el && el.offsetParent !== null) {{ // Visible in DOM
                    targetElem = el;
                    break;
                }}
            }}

            if (!targetElem && field.fallback_placeholders.length > 0) {{
                // Search by placeholder or label
                const inputs = document.querySelectorAll('input, textarea, select');
                for (const input of inputs) {{
                    const ph = (input.placeholder || '').toLowerCase();
                    const aria = (input.getAttribute('aria-label') || '').toLowerCase();
                    for (const term of field.fallback_placeholders) {{
                        if (ph.includes(term.toLowerCase()) || aria.includes(term.toLowerCase())) {{
                            targetElem = input;
                            break;
                        }}
                    }}
                    if (targetElem) break;
                }}
            }}

            if (targetElem) {{
                if (field.input_type === 'custom_dropdown' || field.input_type === 'select') {{
                    await selectDropdownOption(targetElem, val);
                }} else {{
                    setNativeValue(targetElem, val);
                }}
                filledCount++;
                // Anti-Bot Jitter Delay
                await sleep(randomJitter(profile.timing.min_field_delay_ms, profile.timing.max_field_delay_ms));
            }}
        }}

        if (filledCount > 0) {{
            hudStatus.textContent = `Tamamlandı (${{filledCount}} sahə)`;
            hudStatus.className = 'pcs-status pcs-status-ok';
        }} else {{
            hudStatus.textContent = 'Form aşkar edilmədi';
            hudStatus.className = 'pcs-status pcs-status-warn';
        }}
    }}

    // 7. Render Floating HUD (Zero CSS Dependencies)
    function renderHUD() {{
        const hud = document.createElement('div');
        hud.id = 'pcs-autofill-hud';
        hud.innerHTML = `
            <style>
                #pcs-autofill-hud {{
                    position: fixed;
                    top: 24px;
                    right: 24px;
                    z-index: 2147483647;
                    background: rgba(15, 23, 42, 0.95);
                    backdrop-filter: blur(12px);
                    border: 1px solid rgba(51, 65, 85, 0.8);
                    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(255, 255, 255, 0.05);
                    border-radius: 16px;
                    padding: 16px;
                    width: 320px;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    color: #f8fafc;
                    font-size: 13px;
                    transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
                }}
                #pcs-autofill-hud * {{ box-sizing: border-box; }}
                .pcs-hdr {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }}
                .pcs-badge {{ background: #0284c7; color: #fff; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 9999px; text-transform: uppercase; letter-spacing: 0.5px; }}
                .pcs-close {{ background: transparent; border: none; color: #94a3b8; font-size: 16px; cursor: pointer; padding: 0 4px; }}
                .pcs-close:hover {{ color: #f8fafc; }}
                .pcs-pills {{ display: flex; gap: 6px; margin-bottom: 12px; }}
                .pcs-pill {{ flex: 1; text-align: center; padding: 6px 0; background: #1e293b; border: 1px solid #334155; border-radius: 8px; cursor: pointer; font-size: 11px; font-weight: 600; color: #cbd5e1; transition: all 0.2s; }}
                .pcs-pill:hover {{ background: #334155; color: #fff; }}
                .pcs-pill.active {{ background: #10b981; border-color: #059669; color: #fff; box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3); }}
                .pcs-suite-box {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 8px 10px; margin-bottom: 12px; font-size: 11px; display: flex; justify-content: space-between; }}
                .pcs-suite-val {{ font-family: monospace; font-weight: 700; color: #34d399; }}
                .pcs-btn-primary {{ width: 100%; background: linear-gradient(135deg, #10b981, #059669); color: #fff; border: none; border-radius: 10px; padding: 10px; font-weight: 700; font-size: 13px; cursor: pointer; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.35); transition: all 0.2s; display: flex; align-items: center; justify-content: center; gap: 6px; }}
                .pcs-btn-primary:hover {{ filter: brightness(1.1); transform: translateY(-1px); }}
                .pcs-btn-sec {{ width: 100%; background: #1e293b; color: #cbd5e1; border: 1px solid #334155; border-radius: 8px; padding: 7px; font-size: 11px; font-weight: 600; cursor: pointer; margin-top: 8px; }}
                .pcs-btn-sec:hover {{ background: #334155; color: #fff; }}
                .pcs-status {{ margin-top: 10px; font-size: 11px; text-align: center; color: #94a3b8; font-weight: 500; min-height: 16px; }}
                .pcs-status-ok {{ color: #34d399 !important; font-weight: 700; }}
                .pcs-status-warn {{ color: #fbbf24 !important; }}
                .pcs-status-err {{ color: #f87171 !important; }}
                @keyframes pcsPulse {{ 0% {{ transform: scale(1); }} 50% {{ transform: scale(1.05); }} 100% {{ transform: scale(1); }} }}
            </style>
            <div class="pcs-hdr">
                <div style="font-weight: 700; font-size: 14px;">⚡ PCS 1-Click Autofill</div>
                <div style="display: flex; align-items: center; gap: 6px;">
                    <span class="pcs-badge">${{profile.display_name.split(' ')[0]}} ${{profile.platform_id}}</span>
                    <button class="pcs-close" id="pcs-close-btn">&times;</button>
                </div>
            </div>
            <div class="pcs-pills" id="pcs-carrier-pills">
                <div class="pcs-pill ${{currentCarrier === 'STAREX' ? 'active' : ''}}" data-carrier="STAREX">STAREX</div>
                <div class="pcs-pill ${{currentCarrier === 'LIMAK' ? 'active' : ''}}" data-carrier="LIMAK">LIMAK</div>
                <div class="pcs-pill ${{currentCarrier === 'CAMEX' ? 'active' : ''}}" data-carrier="CAMEX">CAMEX</div>
                <div class="pcs-pill ${{currentCarrier === 'DYNAMEX' ? 'active' : ''}}" data-carrier="DYNAMEX">DYNAMEX</div>
            </div>
            <div class="pcs-suite-box">
                <span style="color: #94a3b8;">Müştəri Suite:</span>
                <span class="pcs-suite-val" id="pcs-suite-display">${{currentSuite}}</span>
            </div>
            <button class="pcs-btn-primary" id="pcs-autofill-btn">
                <span>⚡ Ünvanı Avtomatik Doldur</span>
            </button>
            <button class="pcs-btn-sec" id="pcs-copy-btn">📋 Tam Ünvanı Kopyala</button>
            <div class="pcs-status" id="pcs-status-msg">Hazırdır (127.0.0.1:48481)</div>
        `;
        document.body.appendChild(hud);

        // Event Listeners
        document.getElementById('pcs-close-btn').onclick = () => {{
            hud.remove();
            window.__PCS_AUTOFILL_ACTIVE__ = false;
        }};

        const statusMsg = document.getElementById('pcs-status-msg');
        const suiteDisplay = document.getElementById('pcs-suite-display');

        // Pill clicks
        document.querySelectorAll('#pcs-carrier-pills .pcs-pill').forEach(pill => {{
            pill.onclick = async () => {{
                document.querySelectorAll('#pcs-carrier-pills .pcs-pill').forEach(p => p.classList.remove('active'));
                pill.classList.add('active');
                currentCarrier = pill.getAttribute('data-carrier');
                const data = await fetchAddressData(currentCarrier, activePlatform);
                if (data && data.customer_code) {{
                    currentSuite = data.customer_code;
                    suiteDisplay.textContent = currentSuite;
                }}
                statusMsg.textContent = `${{currentCarrier}} seçildi`;
                statusMsg.className = 'pcs-status';
            }};
        }});

        // Main Autofill Button
        document.getElementById('pcs-autofill-btn').onclick = () => {{
            executeAutofill(statusMsg);
        }};

        // Copy Button
        document.getElementById('pcs-copy-btn').onclick = async () => {{
            const data = await fetchAddressData(currentCarrier, activePlatform);
            if (data && (data.smart_address_block || data.summary_text)) {{
                const textToCopy = data.smart_address_block || data.summary_text;
                navigator.clipboard.writeText(textToCopy);
                statusMsg.textContent = '📋 Buferə kopyalandı!';
                statusMsg.className = 'pcs-status pcs-status-ok';
            }}
        }};

        // Immediate Initial Fill execution
        executeAutofill(statusMsg);
    }}

    renderHUD();
}})();"""

        if minified:
            # Safe basic minification
            lines = [l.strip() for l in raw_script.splitlines() if l.strip() and not l.strip().startswith("//")]
            return " ".join(lines)
        return raw_script

    @classmethod
    def generate_bookmarklet_href(
        cls,
        server_url: str = "http://127.0.0.1:48481",
        default_carrier: str = "STAREX",
        default_branch: str = "28 May",
        customer_code: str = "ST123456",
    ) -> str:
        """Returns the URI-encoded bookmarklet string ready for an <a href='javascript:...'> anchor tag."""
        js_code = cls.generate_injection_javascript(
            server_url=server_url,
            default_carrier=default_carrier,
            default_branch=default_branch,
            customer_code=customer_code,
            minified=True,
        )
        return "javascript:" + urllib.parse.quote(js_code)

    @classmethod
    def generate_bookmarklet_card_html(
        cls,
        server_url: str = "http://127.0.0.1:48481",
        default_carrier: str = "STAREX",
    ) -> str:
        """Produces a ready-to-render HTML card for the PCS Web Panel with 1-click drag-to-bar and copy-snippet features."""
        href = cls.generate_bookmarklet_href(server_url=server_url, default_carrier=default_carrier)
        js_raw = cls.generate_injection_javascript(server_url=server_url, default_carrier=default_carrier, minified=False)
        escaped_js = json.dumps(js_raw)

        return f"""
        <div class="bg-gradient-to-br from-slate-900 to-indigo-950/40 border border-indigo-500/30 rounded-2xl p-6 shadow-xl space-y-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center font-bold text-lg border border-indigo-500/30">
                        ⚡
                    </div>
                    <div>
                        <h3 class="text-base font-bold text-white">Zero-Friction 1-Click Autofill Bookmarklet</h3>
                        <p class="text-xs text-slate-400">Trendyol və Taobao/1688 səbətlərində xarici anbar ünvanını 1 saniyədə doldurun.</p>
                    </div>
                </div>
                <span class="px-2.5 py-1 text-xs font-mono font-semibold rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                    Active (v3.5)
                </span>
            </div>

            <div class="p-4 rounded-xl bg-slate-950/70 border border-slate-800 text-xs text-slate-300 space-y-2">
                <div class="flex items-center gap-2 text-indigo-300 font-semibold">
                    <span>💡 Necə istifadə edilir?</span>
                </div>
                <ol class="list-decimal list-inside space-y-1 text-slate-400">
                    <li>Aşağıdakı yaşıl <strong class="text-emerald-400">⚡ PCS 1-Click Autofill</strong> düyməsini siçanla tutub brauzerinizin <strong>Əlfəcinlər (Bookmarks)</strong> panelinə sürükləyin (Drag & Drop).</li>
                    <li>Trendyol və ya Taobao səhifəsində yeni ünvan əlavə edərkən həmin əlfəcinə klikləyin.</li>
                    <li>Sistem süni intellekt və anti-bot qorunması ilə bütün xanaları (İl, İlçe, Mahalle, Suite in Soyad, 智能地址) avtomatik dolduracaqdır.</li>
                </ol>
            </div>

            <div class="flex flex-wrap items-center gap-3 pt-2">
                <a href="{href}"
                   class="px-5 py-2.5 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold text-sm shadow-lg shadow-emerald-500/25 transition flex items-center gap-2 cursor-grab active:cursor-grabbing border border-emerald-400"
                   onclick="event.preventDefault(); alert('Bu düyməni siçanla tutub yuxarıdakı Əlfəcinlər (Bookmarks) panelinə sürükləyin!');">
                    <span>⚡ PCS 1-Click Autofill</span>
                    <span class="text-[11px] bg-slate-950/20 px-2 py-0.5 rounded font-mono font-normal">Sürükləyin</span>
                </a>

                <button onclick="navigator.clipboard.writeText({escaped_js}); alert('Tam JavaScript kodu buferə kopyalandı! F12 Console-a yapışdıra bilərsiniz.');"
                        class="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition flex items-center gap-2 border border-slate-700">
                    <span>📋 Console Kodunu Kopyala</span>
                </button>
            </div>
        </div>
        """
