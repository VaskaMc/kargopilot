"""PCS v3.5 Address Formatter & 1-Click Clipboard Engine for Azerbaijani Carriers and E-Commerce Platforms."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FormattedAddressField(BaseModel):
    label: str
    value: str
    description: Optional[str] = None
    copyable: bool = True


class FormattedAddressBlock(BaseModel):
    carrier: str
    platform: str
    origin_country: str
    branch: str
    customer_code: str
    full_text_block: str
    fields: List[FormattedAddressField] = Field(default_factory=list)


# Verified warehouse database for Azerbaijani forwarders
CARRIER_WAREHOUSES: Dict[str, Dict[str, Dict[str, str]]] = {
    "STAREX": {
        "TR": {
            "name": "Starex",
            "address_line_1": "Cihangir Mah. Şehit Jandarma Komando Er Hakan Öner Sk. No: 14",
            "address_line_2": "{suite_code}",
            "district": "Avcılar",
            "city": "İstanbul",
            "state": "İstanbul",
            "zip_code": "34310",
            "phone": "+90 534 892 10 44",
            "tax_no": "7810564920",
        },
        "CN": {
            "name": "Starex",
            "recipient": "Vasif Mecidli ({suite_code})",
            "address_line_1": "广东省广州市白云区嘉禾望岗工业区14号仓库",
            "address_line_2": "{suite_code}",
            "province": "广东省",
            "city": "广州市",
            "district": "白云区",
            "street": "嘉禾望岗工业区14号",
            "zip_code": "510440",
            "phone": "+86 138 2841 9920",
        },
        "US": {
            "name": "Starex Logistics",
            "address_line_1": "2401 Ogletown Rd",
            "address_line_2": "Suite {suite_code}",
            "city": "Newark",
            "state": "Delaware",
            "state_code": "DE",
            "zip_code": "19711",
            "phone": "+1 (302) 273-0500",
        },
        "DE": {
            "name": "Starex Frankfurt",
            "address_line_1": "Cargo City Süd, Gebäude 537",
            "address_line_2": "{suite_code}",
            "city": "Frankfurt am Main",
            "state": "Hessen",
            "zip_code": "60549",
            "phone": "+49 69 690 70000",
        },
    },
    "CAMEX": {
        "TR": {
            "name": "Camex Kargo",
            "address_line_1": "Güngören Mah. Mareşal Fevzi Çakmak Cad. No: 38",
            "address_line_2": "{suite_code}",
            "district": "Güngören",
            "city": "İstanbul",
            "state": "İstanbul",
            "zip_code": "34164",
            "phone": "+90 212 555 12 34",
            "tax_no": "1940381029",
        },
        "CN": {
            "name": "Camex Guangzhou",
            "recipient": "Vasif Mecidli ({suite_code})",
            "address_line_1": "广东省广州市越秀区站西路58号仓库",
            "address_line_2": "{suite_code}",
            "province": "广东省",
            "city": "广州市",
            "district": "越秀区",
            "street": "站西路58号",
            "zip_code": "510010",
            "phone": "+86 139 1029 4810",
        },
        "US": {
            "name": "Camex International",
            "address_line_1": "1100 Interchange Blvd",
            "address_line_2": "STE {suite_code}",
            "city": "Newark",
            "state": "Delaware",
            "state_code": "DE",
            "zip_code": "19711",
            "phone": "+1 (302) 453-8800",
        },
    },
    "DYNAMEX": {
        "TR": {
            "name": "Dynamex Lojistik",
            "address_line_1": "İkitelli OSB Mah. Bedrettin Dalan Cad. No: 23",
            "address_line_2": "{suite_code}",
            "district": "Başakşehir",
            "city": "İstanbul",
            "state": "İstanbul",
            "zip_code": "34490",
            "phone": "+90 212 485 99 00",
            "tax_no": "3194018291",
        },
        "US": {
            "name": "Dynamex USA",
            "address_line_1": "700 Prides Crossing",
            "address_line_2": "Suite {suite_code}",
            "city": "Newark",
            "state": "Delaware",
            "state_code": "DE",
            "zip_code": "19713",
            "phone": "+1 (302) 731-9800",
        },
    },
    "LIMAK": {
        "TR": {
            "name": "Limak Express",
            "address_line_1": "Halkalı Merkez Mah. Basın Ekspres Yolu No: 12",
            "address_line_2": "{suite_code}",
            "district": "Küçükçekmece",
            "city": "İstanbul",
            "state": "İstanbul",
            "zip_code": "34303",
            "phone": "+90 212 698 10 20",
            "tax_no": "6080491820",
        },
        "US": {
            "name": "Limak USA LLC",
            "address_line_1": "201 Prides Crossing",
            "address_line_2": "Unit {suite_code}",
            "city": "Newark",
            "state": "Delaware",
            "state_code": "DE",
            "zip_code": "19713",
            "phone": "+1 (302) 292-1200",
        },
    },
}


class AddressFormatterEngine:
    """Formats carrier warehouse addresses specifically for Trendyol, Taobao, Temu, and Amazon."""

    @classmethod
    def get_supported_carriers(cls) -> List[str]:
        return list(CARRIER_WAREHOUSES.keys())

    @classmethod
    def get_supported_countries(cls, carrier: str) -> List[str]:
        carrier = carrier.upper()
        return list(CARRIER_WAREHOUSES.get(carrier, {}).keys())

    @classmethod
    def format_address(
        cls,
        carrier: str,
        origin_country: str,
        platform: str,
        customer_code: str,
        full_name: str = "Vasif Məcidli",
        branch: str = "28 May",
    ) -> FormattedAddressBlock:
        carrier = carrier.upper()
        origin_country = origin_country.upper()
        platform = platform.lower().strip()

        wh_map = CARRIER_WAREHOUSES.get(carrier, {}).get(origin_country)
        if not wh_map:
            raise ValueError(f"No warehouse found for carrier '{carrier}' in country '{origin_country}'")

        suite = customer_code.strip()
        fields: List[FormattedAddressField] = []
        full_text_lines: List[str] = []

        if platform == "trendyol" or origin_country == "TR":
            # Trendyol Turkish Address Book Format
            sur_with_suite = f"Məcidli {suite}"
            addr_line = f"{wh_map['address_line_1']} {suite}"
            fields = [
                FormattedAddressField(label="Ad (First Name)", value="Vasif", description="Trendyol Ad sahəsi"),
                FormattedAddressField(label="Soyad (Last Name)", value=sur_with_suite, description="Trendyol Soyad sahəsi (Müştəri kodu ilə)"),
                FormattedAddressField(label="İl (City)", value=wh_map["city"], description="Türkiyə Şəhəri"),
                FormattedAddressField(label="İlçe (District)", value=wh_map["district"], description="Bələdiyyə / Rayon"),
                FormattedAddressField(label="Mahalle (Quarter)", value=wh_map.get("district", "") + " Mah.", description="Məhəllə sahəsi"),
                FormattedAddressField(label="Açıq Ünvan (Address)", value=addr_line, description="Küçə, Bina və Suite"),
                FormattedAddressField(label="Posta Kodu (ZIP)", value=wh_map["zip_code"], description="Poçt indeksi"),
                FormattedAddressField(label="Telefon (Phone)", value=wh_map["phone"], description="Türkiyə daxili anbar əlaqə telefonu"),
                FormattedAddressField(label="TC / Vergi No", value=wh_map.get("tax_no", "11111111111"), description="Vergi və ya şəxsiyyət nömrəsi"),
            ]
            full_text_lines = [
                f"Ad Soyad: Vasif {sur_with_suite}",
                f"Telefon: {wh_map['phone']}",
                f"İl/İlçe: {wh_map['city']} / {wh_map['district']}",
                f"Adres: {addr_line}",
                f"Posta Kodu: {wh_map['zip_code']}",
                f"TC/Vergi No: {wh_map.get('tax_no', '11111111111')}",
                f"Təhvil Filialı: {branch}",
            ]

        elif platform in ("taobao", "1688") or origin_country == "CN":
            # Taobao / 1688 Chinese Address Book Format
            recipient = f"{full_name} ({suite})"
            full_detailed_addr = f"{wh_map['address_line_1']} {suite}"
            region_str = f"{wh_map.get('province', '广东省')} {wh_map.get('city', '广州市')} {wh_map.get('district', '白云区')} 嘉禾街道"
            fields = [
                FormattedAddressField(label="收货人 (Recipient)", value=recipient, description="Taobao alıcı adı və müştəri kodu"),
                FormattedAddressField(label="所在地区 (Region)", value=region_str, description="Vilayət / Şəhər / Rayon / Küçə"),
                FormattedAddressField(label="详细地址 (Detailed Address)", value=full_detailed_addr, description="Tam anbar ünvanı"),
                FormattedAddressField(label="邮政编码 (ZIP Code)", value=wh_map["zip_code"], description="Poçt indeksi"),
                FormattedAddressField(label="手机号码 (Phone Number)", value=wh_map["phone"], description="Çin mobil nömrəsi"),
            ]
            full_text_lines = [
                f"收货人: {recipient}",
                f"手机号码: {wh_map['phone']}",
                f"所在地区: {region_str}",
                f"详细地址: {full_detailed_addr}",
                f"邮政编码: {wh_map['zip_code']}",
                f"Baku Branch: {branch}",
            ]

        else:
            # Temu / Amazon US & DE Global Address Format
            full_name_suite = f"{full_name} {suite}"
            addr1 = wh_map["address_line_1"]
            addr2 = wh_map.get("address_line_2", "{suite_code}").format(suite_code=suite)
            state_val = wh_map.get("state_code") or wh_map.get("state", "")
            fields = [
                FormattedAddressField(label="Full Name", value=full_name_suite, description="Ad və Soyad müştəri kodu ilə"),
                FormattedAddressField(label="Address Line 1", value=addr1, description="Küçə və bina"),
                FormattedAddressField(label="Address Line 2 (Apt / Ste)", value=addr2, description="Suite / Müştəri nömrəsi"),
                FormattedAddressField(label="City", value=wh_map["city"], description="Şəhər"),
                FormattedAddressField(label="State / Province", value=state_val, description="Ştat / Vilayət"),
                FormattedAddressField(label="ZIP / Postal Code", value=wh_map["zip_code"], description="Poçt indeksi"),
                FormattedAddressField(label="Phone Number", value=wh_map["phone"], description="Əlaqə telefonu"),
            ]
            full_text_lines = [
                f"Name: {full_name_suite}",
                f"Address 1: {addr1}",
                f"Address 2: {addr2}",
                f"City, State, ZIP: {wh_map['city']}, {state_val} {wh_map['zip_code']}",
                f"Phone: {wh_map['phone']}",
                f"Destination Branch: {branch}",
            ]

        return FormattedAddressBlock(
            carrier=carrier,
            platform=platform,
            origin_country=origin_country,
            branch=branch,
            customer_code=suite,
            full_text_block="\n".join(full_text_lines),
            fields=fields,
        )
