"""Baku Branch Proximity & Delivery Routing Engine for PCS v3.5.

Comprehensive branch directory, geo-proximity matching, service capability matrix,
and reverse logistics repatriation engine for Azerbaijani cargo carriers:
Starex (22 branches), Camex (18 branches), Dynamex (20 branches), Limak (16 branches).
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# 1. ENUMS & CONSTANTS
# -----------------------------------------------------------------------------

class CarrierName(str, Enum):
    STAREX = "STAREX"
    CAMEX = "CAMEX"
    DYNAMEX = "DYNAMEX"
    LIMAK = "LIMAK"


class RegionType(str, Enum):
    BAKU = "Baku"
    ABSHERON = "Absheron"
    REGIONS = "Regions"


class ReturnReasonEnum(str, Enum):
    DEFECTIVE = "DEFECTIVE"
    WRONG_ITEM = "WRONG_ITEM"
    SIZE_MISMATCH = "SIZE_MISMATCH"
    DAMAGED_IN_TRANSIT = "DAMAGED_IN_TRANSIT"
    NOT_AS_DESCRIBED = "NOT_AS_DESCRIBED"
    CUSTOMS_REJECTED = "CUSTOMS_REJECTED"


class ReturnStatusEnum(str, Enum):
    REQUESTED = "REQUESTED"
    WAYBILL_ISSUED = "WAYBILL_ISSUED"
    DROPPED_OFF = "DROPPED_OFF"
    CUSTOMS_EXPORT_APPROVED = "CUSTOMS_EXPORT_APPROVED"
    IN_FLIGHT = "IN_FLIGHT"
    DELIVERED_TO_ORIGIN_WAREHOUSE = "DELIVERED_TO_ORIGIN_WAREHOUSE"
    FORWARDED_TO_SELLER = "FORWARDED_TO_SELLER"
    REFUND_CONFIRMED = "REFUND_CONFIRMED"


# -----------------------------------------------------------------------------
# 2. KEY BAKU TRANSIT HUBS & METRO NETWORK
# -----------------------------------------------------------------------------

METRO_STATIONS: Dict[str, Tuple[float, float]] = {
    "28 May": (40.3798, 49.8489),
    "Gənclik": (40.4011, 49.8519),
    "Nəriman Nərimanov": (40.4027, 49.8715),
    "Elmlər Akademiyası": (40.3744, 49.8153),
    "İnşaatçılar": (40.3892, 49.8028),
    "20 Yanvar": (40.4022, 49.8105),
    "Memar Əcəmi": (40.4109, 49.8159),
    "Nəsimi": (40.4243, 49.8166),
    "Azadlıq Prospekti": (40.4258, 49.8431),
    "Dərnəgül": (40.4267, 49.8578),
    "Koroğlu": (40.4203, 49.9184),
    "Qara Qarayev": (40.4178, 49.9328),
    "Neftçilər": (40.4111, 49.9427),
    "Xalqlar Dostluğu": (40.3976, 49.9531),
    "Əhmədli": (40.3857, 49.9542),
    "Həzi Aslanov": (40.3736, 49.9536),
    "Sahil": (40.3705, 49.8432),
    "İçərişəhər": (40.3660, 49.8317),
    "Nizami": (40.3794, 49.8300),
    "Cəfər Cabbarlı": (40.3804, 49.8497),
    "Xətai": (40.3831, 49.8732),
    "Bakmil": (40.4093, 49.8872),
    "8 Noyabr": (40.3986, 49.8248),
    "Avtovağzal": (40.4208, 49.7997),
    "Xocəsən": (40.4150, 49.7620),
}

TRANSIT_HUBS: Dict[str, Dict[str, Any]] = {
    "28 May": {
        "name": "28 May Dəmiryol & Metro Qovşağı",
        "coords": (40.3798, 49.8489),
        "district": "Nəsimi",
        "type": "Primary Rail/Metro Junction",
    },
    "Gənclik": {
        "name": "Gənclik Mall & Atatürk Prospekti Qovşağı",
        "coords": (40.4011, 49.8519),
        "district": "Nərimanov",
        "type": "Commercial & Transit Corridor",
    },
    "Əhmədli": {
        "name": "Əhmədli Şərq Yaşayış və Ticarət Qovşağı",
        "coords": (40.3857, 49.9542),
        "district": "Xətai",
        "type": "East Baku Residential Hub",
    },
    "Xalqlar Dostluğu": {
        "name": "Xalqlar Dostluğu & Laçın Ticarət Qovşağı",
        "coords": (40.3976, 49.9531),
        "district": "Nizami",
        "type": "East Baku Trade Center",
    },
    "Elmlər Akademiyası": {
        "name": "Elmlər Akademiyası & BDU Universitet Qovşağı",
        "coords": (40.3744, 49.8153),
        "district": "Yasamal",
        "type": "Academic & Tech Corridor",
    },
    "Yasamal": {
        "name": "Yasamal Şərifzadə & İnşaatçılar Qovşağı",
        "coords": (40.3814, 49.8080),
        "district": "Yasamal",
        "type": "Dense Residential Arterial",
    },
    "Nərimanov": {
        "name": "Nərimanov Metropark & Ağa Nemətulla Koridoru",
        "coords": (40.4027, 49.8715),
        "district": "Nərimanov",
        "type": "North Central Business Hub",
    },
    "Sumqayıt": {
        "name": "Sumqayıt Sülh Küçəsi & Mərkəzi Qovşaq",
        "coords": (40.5897, 49.6686),
        "district": "Sumqayıt",
        "type": "Satellite Industrial Hub",
    },
    "Xırdalan": {
        "name": "Xırdalan Heydər Əliyev Prospekti & AAAF Park",
        "coords": (40.4481, 49.7550),
        "district": "Abşeron",
        "type": "Absheron Gateway Hub",
    },
}


# -----------------------------------------------------------------------------
# 3. METADATA MODELS & DTOS
# -----------------------------------------------------------------------------

class BranchCapabilities(BaseModel):
    liquid_accepted: bool = Field(True, description="Accepts liquid cosmetics/perfumes subject to safety rules")
    bulky_items_accepted: bool = Field(True, description="Accepts oversized packages > 20kg or volume > 0.15 m3")
    weekend_open: bool = Field(True, description="Open on Saturdays")
    sunday_open: bool = Field(False, description="Open on Sundays")
    courier_door_delivery: bool = Field(True, description="Acts as dispatch point for local door delivery")
    smart_locker_available: bool = Field(False, description="Equipped with 24/7 automated parcel lockers")
    card_payment: bool = Field(True, description="Equipped with POS terminal for cashless card payments")
    fitting_room: bool = Field(False, description="Has changing cabin for trying on apparel/footwear")
    reverse_logistics_dropoff: bool = Field(True, description="Dropoff point for defective item returns to TR/CN")


class BranchDTO(BaseModel):
    branch_id: str
    carrier: str
    name: str
    city: str
    region: str = "Baku"
    district: Optional[str] = None
    address: str
    latitude: float
    longitude: float
    metro_station: Optional[str] = None
    distance_to_metro_m: Optional[int] = None
    transit_hub: Optional[str] = None
    working_hours: Dict[str, str] = Field(default_factory=dict)
    phone: str
    capabilities: BranchCapabilities
    is_active: bool = True


class BranchProximityResult(BaseModel):
    branch: BranchDTO
    distance_km: float
    distance_m: int
    walking_minutes: int
    driving_minutes: int
    metro_station: Optional[str] = None
    suitability_score: float
    capability_matches: List[str] = Field(default_factory=list)
    missing_capabilities: List[str] = Field(default_factory=list)


class MultiCarrierProximityResponse(BaseModel):
    origin_point: Dict[str, Any]
    carrier_recommendations: Dict[str, BranchProximityResult]
    overall_closest: BranchProximityResult
    summary_az: str


class RoutingDecision(BaseModel):
    carrier: str
    recommended_branch: BranchDTO
    is_original_preferred: bool
    reroute_reason: Optional[str] = None
    distance_from_user_km: float
    requires_special_handling: bool
    handling_notes: List[str] = Field(default_factory=list)


# Reverse Logistics Models
class ReverseLogisticsRequest(BaseModel):
    order_ref: str = Field(..., description="Order Ref e.g. TY-98234123 or TB-394829104819284712")
    carrier_name: str = Field(..., description="STAREX, CAMEX, DYNAMEX, LIMAK")
    origin_country: str = Field(..., description="TR or CN")
    return_reason: ReturnReasonEnum = Field(..., description="Reason for repatriation")
    item_description: str = Field(..., description="Item details, defect description")
    weight_kg: float = Field(default=0.5, ge=0.05, le=50.0)
    merchant_return_code: str = Field(..., description="Trendyol iade kodu or Taobao merchant return code")
    seller_return_address: str = Field(..., description="Merchant return address in Istanbul or Guangzhou")
    user_preferred_branch_id: Optional[str] = None
    doorstep_pickup_required: bool = False
    customer_notes: Optional[str] = None


class ReverseLogisticsQuote(BaseModel):
    return_id: str
    carrier_name: str
    destination_country: str
    weight_kg: float
    return_fee_azn: float
    return_fee_usd: float
    estimated_transit_days: str
    repatriation_warehouse: str
    origin_carrier: str
    customs_quota_refund_eligible: bool
    recommended_dropoff_branch: BranchDTO
    required_documents: List[str]
    step_by_step_workflow: List[str]


class ReverseLogisticsWaybill(BaseModel):
    return_id: str
    order_ref: str
    carrier: str
    tracking_number: str
    barcode: str
    qr_payload: str
    dropoff_branch_name: str
    merchant_return_code: str
    created_at: str
    status: ReturnStatusEnum


# -----------------------------------------------------------------------------
# 4. HAVERSINE & PROXIMITY UTILITIES
# -----------------------------------------------------------------------------

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two GPS coordinates in kilometers."""
    r = 6371.0  # Earth radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(r * c, 3)


def estimate_travel_time(distance_km: float) -> Dict[str, int]:
    """Estimates urban walking (4.8 km/h) and driving (28 km/h in Baku traffic) time in minutes."""
    walk_min = max(1, int(round((distance_km / 4.8) * 60)))
    drive_min = max(2, int(round((distance_km / 28.0) * 60)))
    return {
        "walking_minutes": walk_min,
        "driving_minutes": drive_min,
    }


# -----------------------------------------------------------------------------
# 5. COMPLETE BRANCH DIRECTORY (76 BRANCHES ACROSS AZERBAIJAN)
# Starex: 22 branches
# Camex: 18 branches
# Dynamex: 20 branches
# Limak: 16 branches
# -----------------------------------------------------------------------------

_STAREX_BRANCHES: List[Dict[str, Any]] = [
    {
        "branch_id": "starex-28-may",
        "carrier": "STAREX",
        "name": "Starex 28 May (Baş ofis)",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nəsimi",
        "address": "Nizami küç. 142 (28 May m. və Dəmiryol Vağzalı yanı)",
        "latitude": 40.3792,
        "longitude": 40.3792 and 49.8498,
        "metro_station": "28 May",
        "distance_to_metro_m": 120,
        "transit_hub": "28 May",
        "working_hours": {"weekdays": "10:00 - 21:00", "saturday": "10:00 - 20:00", "sunday": "11:00 - 18:00"},
        "phone": "*3334 / +994 12 310 33 34",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-genclik",
        "carrier": "STAREX",
        "name": "Starex Gənclik",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nərimanov",
        "address": "Atatürk pr. 4 (Gənclik Mall yaxınlığı)",
        "latitude": 40.4005,
        "longitude": 49.8530,
        "metro_station": "Gənclik",
        "distance_to_metro_m": 180,
        "transit_hub": "Gənclik",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-ehmedli",
        "carrier": "STAREX",
        "name": "Starex Əhmədli",
        "city": "Bakı",
        "region": "Baku",
        "district": "Xətai",
        "address": "Məzahir Rüstəmov küç. 8 (Əhmədli m. çıxışı)",
        "latitude": 40.3860,
        "longitude": 49.9535,
        "metro_station": "Əhmədli",
        "distance_to_metro_m": 90,
        "transit_hub": "Əhmədli",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-xalqlar",
        "carrier": "STAREX",
        "name": "Starex Xalqlar Dostluğu",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nizami",
        "address": "Qara Qarayev pr. 74 (Laçın ticarət mərkəzi yanı)",
        "latitude": 40.3980,
        "longitude": 49.9525,
        "metro_station": "Xalqlar Dostluğu",
        "distance_to_metro_m": 150,
        "transit_hub": "Xalqlar Dostluğu",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-elmler",
        "carrier": "STAREX",
        "name": "Starex Elmlər Akademiyası",
        "city": "Bakı",
        "region": "Baku",
        "district": "Yasamal",
        "address": "Bəxtiyar Vahabzadə küç. 55 (BDU və Texniki Universitet yanı)",
        "latitude": 40.3750,
        "longitude": 49.8162,
        "metro_station": "Elmlər Akademiyası",
        "distance_to_metro_m": 110,
        "transit_hub": "Elmlər Akademiyası",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-yasamal",
        "carrier": "STAREX",
        "name": "Starex Yasamal",
        "city": "Bakı",
        "region": "Baku",
        "district": "Yasamal",
        "address": "A.M. Şərifzadə küç. 148 (İnşaatçılar m. yaxınlığı)",
        "latitude": 40.3885,
        "longitude": 49.8035,
        "metro_station": "İnşaatçılar",
        "distance_to_metro_m": 160,
        "transit_hub": "Yasamal",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-nerimanov",
        "carrier": "STAREX",
        "name": "Starex Nərimanov",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nərimanov",
        "address": "Təbriz küç. 98 (Metropark yaxınlığı)",
        "latitude": 40.4030,
        "longitude": 49.8708,
        "metro_station": "Nəriman Nərimanov",
        "distance_to_metro_m": 140,
        "transit_hub": "Nərimanov",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-sahil",
        "carrier": "STAREX",
        "name": "Starex Sahil Ekspres",
        "city": "Bakı",
        "region": "Baku",
        "district": "Səbail",
        "address": "Xəqani küç. 18 (Sahil bağı qarşısı)",
        "latitude": 40.3712,
        "longitude": 49.8445,
        "metro_station": "Sahil",
        "distance_to_metro_m": 130,
        "transit_hub": "28 May",
        "working_hours": {"weekdays": "10:00 - 19:30", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": False,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": False,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": False,
        },
    },
    {
        "branch_id": "starex-nizami",
        "carrier": "STAREX",
        "name": "Starex Nizami",
        "city": "Bakı",
        "region": "Baku",
        "district": "Yasamal",
        "address": "Zivərbəy Əhmədbəyov küç. 42 (Nizami m. çıxışı)",
        "latitude": 40.3800,
        "longitude": 49.8310,
        "metro_station": "Nizami",
        "distance_to_metro_m": 80,
        "transit_hub": "28 May",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-icherisheher",
        "carrier": "STAREX",
        "name": "Starex İçərişəhər",
        "city": "Bakı",
        "region": "Baku",
        "district": "Səbail",
        "address": "Lermontov küç. 68 (İçərişəhər m. və Axundov bağı yanı)",
        "latitude": 40.3665,
        "longitude": 49.8325,
        "metro_station": "İçərişəhər",
        "distance_to_metro_m": 120,
        "transit_hub": "28 May",
        "working_hours": {"weekdays": "10:00 - 19:30", "saturday": "10:00 - 17:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": False,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": False,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": False,
        },
    },
    {
        "branch_id": "starex-neftciler",
        "carrier": "STAREX",
        "name": "Starex Neftçilər",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nizami",
        "address": "Rüstəm Rüstəmov küç. 24 (Neftçilər m.)",
        "latitude": 40.4118,
        "longitude": 49.9435,
        "metro_station": "Neftçilər",
        "distance_to_metro_m": 100,
        "transit_hub": "Xalqlar Dostluğu",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-qara-qarayev",
        "carrier": "STAREX",
        "name": "Starex Qara Qarayev",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nizami",
        "address": "Qara Qarayev pr. 38 (Qara Qarayev m.)",
        "latitude": 40.4182,
        "longitude": 49.9332,
        "metro_station": "Qara Qarayev",
        "distance_to_metro_m": 80,
        "transit_hub": "Xalqlar Dostluğu",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-hezi-aslanov",
        "carrier": "STAREX",
        "name": "Starex Həzi Aslanov",
        "city": "Bakı",
        "region": "Baku",
        "district": "Xətai",
        "address": "Xudu Məmmədov küç. 29 (Həzi Aslanov m. çıxışı)",
        "latitude": 40.3742,
        "longitude": 49.9540,
        "metro_station": "Həzi Aslanov",
        "distance_to_metro_m": 90,
        "transit_hub": "Əhmədli",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-koroglu",
        "carrier": "STAREX",
        "name": "Starex Koroğlu",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nizami",
        "address": "Heydər Əliyev pr. 105 (Koroğlu Nəqliyyat Mübadilə Mərkəzi)",
        "latitude": 40.4210,
        "longitude": 49.9190,
        "metro_station": "Koroğlu",
        "distance_to_metro_m": 120,
        "transit_hub": "Nərimanov",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 16:00"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-bakixanov",
        "carrier": "STAREX",
        "name": "Starex Bakıxanov",
        "city": "Bakı",
        "region": "Baku",
        "district": "Sabunçu",
        "address": "Sakit Qocayev küç. 27 (Bakıxanov Mall yanı)",
        "latitude": 40.4248,
        "longitude": 49.9615,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Xalqlar Dostluğu",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-badamdar",
        "carrier": "STAREX",
        "name": "Starex Badamdar",
        "city": "Bakı",
        "region": "Baku",
        "district": "Səbail",
        "address": "Badamdar şosesi 12 (1-ci massiv)",
        "latitude": 40.3540,
        "longitude": 49.8085,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Elmlər Akademiyası",
        "working_hours": {"weekdays": "10:00 - 19:30", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-merdekan",
        "carrier": "STAREX",
        "name": "Starex Mərdəkan",
        "city": "Bakı",
        "region": "Baku",
        "district": "Xəzər",
        "address": "Sergey Yesenin küç. 92",
        "latitude": 40.4912,
        "longitude": 50.1430,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Əhmədli",
        "working_hours": {"weekdays": "10:00 - 19:00", "saturday": "10:00 - 17:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": False,
        },
    },
    {
        "branch_id": "starex-xirdalan",
        "carrier": "STAREX",
        "name": "Starex Xırdalan",
        "city": "Xırdalan",
        "region": "Absheron",
        "district": "Abşeron",
        "address": "Heydər Əliyev pr. 120 (AAAF Park yaxınlığı)",
        "latitude": 40.4485,
        "longitude": 49.7545,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Xırdalan",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-sumqayit-1",
        "carrier": "STAREX",
        "name": "Starex Sumqayıt 1 (Mərkəz)",
        "city": "Sumqayıt",
        "region": "Absheron",
        "district": "Sumqayıt",
        "address": "Sülh küçəsi, 3-cü mkr (Heydər Əliyev Mərkəzi yaxınlığı)",
        "latitude": 40.5902,
        "longitude": 49.6690,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Sumqayıt",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-sumqayit-2",
        "carrier": "STAREX",
        "name": "Starex Sumqayıt 2 (13-cü mkr)",
        "city": "Sumqayıt",
        "region": "Absheron",
        "district": "Sumqayıt",
        "address": "Heydər Əliyev pr. 45, 13-cü mkr",
        "latitude": 40.5820,
        "longitude": 49.6540,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Sumqayıt",
        "working_hours": {"weekdays": "10:00 - 19:30", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-gence",
        "carrier": "STAREX",
        "name": "Starex Gəncə",
        "city": "Gəncə",
        "region": "Regions",
        "district": "Gəncə",
        "address": "Heydər Əliyev pr. 153",
        "latitude": 40.6828,
        "longitude": 46.3606,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": None,
        "working_hours": {"weekdays": "10:00 - 19:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "starex-lenkeran",
        "carrier": "STAREX",
        "name": "Starex Lənkəran",
        "city": "Lənkəran",
        "region": "Regions",
        "district": "Lənkəran",
        "address": "Zərifə Əliyeva küç. 24",
        "latitude": 38.7540,
        "longitude": 48.8505,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": None,
        "working_hours": {"weekdays": "10:00 - 19:00", "saturday": "10:00 - 17:00", "sunday": "Bağlı"},
        "phone": "*3334",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
]

_CAMEX_BRANCHES: List[Dict[str, Any]] = [
    {
        "branch_id": "camex-28-may",
        "carrier": "CAMEX",
        "name": "Camex 28 May",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nəsimi",
        "address": "28 May küç. 54 (Səməd Vurğun bağı yanı)",
        "latitude": 40.3802,
        "longitude": 49.8475,
        "metro_station": "28 May",
        "distance_to_metro_m": 150,
        "transit_hub": "28 May",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-genclik",
        "carrier": "CAMEX",
        "name": "Camex Gənclik",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nərimanov",
        "address": "Fətəli Xan Xoyski pr. 83 (Gənclik m. yanı)",
        "latitude": 40.4015,
        "longitude": 49.8510,
        "metro_station": "Gənclik",
        "distance_to_metro_m": 100,
        "transit_hub": "Gənclik",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-ehmedli",
        "carrier": "CAMEX",
        "name": "Camex Əhmədli",
        "city": "Bakı",
        "region": "Baku",
        "district": "Xətai",
        "address": "Sarayevo küç. 11 (Əhmədli m. arxası)",
        "latitude": 40.3852,
        "longitude": 49.9548,
        "metro_station": "Əhmədli",
        "distance_to_metro_m": 110,
        "transit_hub": "Əhmədli",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-xalqlar",
        "carrier": "CAMEX",
        "name": "Camex Xalqlar Dostluğu",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nizami",
        "address": "Məhəmməd Hadi küç. 41",
        "latitude": 40.3970,
        "longitude": 49.9538,
        "metro_station": "Xalqlar Dostluğu",
        "distance_to_metro_m": 130,
        "transit_hub": "Xalqlar Dostluğu",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-elmler",
        "carrier": "CAMEX",
        "name": "Camex Elmlər Akademiyası",
        "city": "Bakı",
        "region": "Baku",
        "district": "Yasamal",
        "address": "Zahid Xəlilov küç. 33",
        "latitude": 40.3738,
        "longitude": 49.8145,
        "metro_station": "Elmlər Akademiyası",
        "distance_to_metro_m": 120,
        "transit_hub": "Elmlər Akademiyası",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-yasamal",
        "carrier": "CAMEX",
        "name": "Camex Yasamal",
        "city": "Bakı",
        "region": "Baku",
        "district": "Yasamal",
        "address": "Həsən bəy Zərdabi pr. 78",
        "latitude": 40.3920,
        "longitude": 49.8090,
        "metro_station": "20 Yanvar",
        "distance_to_metro_m": 250,
        "transit_hub": "Yasamal",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-nerimanov",
        "carrier": "CAMEX",
        "name": "Camex Nərimanov",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nərimanov",
        "address": "Ağa Nemətulla küç. 34 (Nərimanov parkı yanı)",
        "latitude": 40.4035,
        "longitude": 49.8722,
        "metro_station": "Nəriman Nərimanov",
        "distance_to_metro_m": 120,
        "transit_hub": "Nərimanov",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-sahil",
        "carrier": "CAMEX",
        "name": "Camex Sahil",
        "city": "Bakı",
        "region": "Baku",
        "district": "Səbail",
        "address": "Üzeyir Hacıbəyov küç. 26",
        "latitude": 40.3725,
        "longitude": 49.8480,
        "metro_station": "Sahil",
        "distance_to_metro_m": 190,
        "transit_hub": "28 May",
        "working_hours": {"weekdays": "10:00 - 19:00", "saturday": "10:00 - 17:00", "sunday": "Bağlı"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": False,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": False,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": False,
        },
    },
    {
        "branch_id": "camex-azadliq",
        "carrier": "CAMEX",
        "name": "Camex Azadlıq",
        "city": "Bakı",
        "region": "Baku",
        "district": "Binəqədi",
        "address": "Süleyman Sani Axundov küç. 3 (Azadlıq pr. m.)",
        "latitude": 40.4262,
        "longitude": 49.8425,
        "metro_station": "Azadlıq Prospekti",
        "distance_to_metro_m": 90,
        "transit_hub": "Gənclik",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-memar-ecemi",
        "carrier": "CAMEX",
        "name": "Camex Memar Əcəmi",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nəsimi",
        "address": "Cavadxan küç. 19 (Memar Əcəmi m.)",
        "latitude": 40.4115,
        "longitude": 49.8152,
        "metro_station": "Memar Əcəmi",
        "distance_to_metro_m": 80,
        "transit_hub": "Yasamal",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-20-yanvar",
        "carrier": "CAMEX",
        "name": "Camex 20 Yanvar",
        "city": "Bakı",
        "region": "Baku",
        "district": "Yasamal",
        "address": "Moskva pr. 62 (20 Yanvar m. dairəsi)",
        "latitude": 40.4030,
        "longitude": 49.8115,
        "metro_station": "20 Yanvar",
        "distance_to_metro_m": 110,
        "transit_hub": "Yasamal",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-xetai",
        "carrier": "CAMEX",
        "name": "Camex Xətai",
        "city": "Bakı",
        "region": "Baku",
        "district": "Xətai",
        "address": "Nəcəfqulu Rəfiyev küç. 14 (Xətai m.)",
        "latitude": 40.3838,
        "longitude": 49.8740,
        "metro_station": "Xətai",
        "distance_to_metro_m": 120,
        "transit_hub": "28 May",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-hovsan",
        "carrier": "CAMEX",
        "name": "Camex Hövsan",
        "city": "Bakı",
        "region": "Baku",
        "district": "Suraxanı",
        "address": "İlqar Əhmədov küç. 5",
        "latitude": 40.3702,
        "longitude": 50.0880,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Əhmədli",
        "working_hours": {"weekdays": "10:00 - 19:00", "saturday": "10:00 - 17:00", "sunday": "Bağlı"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": False,
        },
    },
    {
        "branch_id": "camex-xirdalan",
        "carrier": "CAMEX",
        "name": "Camex Xırdalan",
        "city": "Xırdalan",
        "region": "Absheron",
        "district": "Abşeron",
        "address": "Mehdi Hüseynzadə küç. 18",
        "latitude": 40.4475,
        "longitude": 49.7560,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Xırdalan",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-sumqayit",
        "carrier": "CAMEX",
        "name": "Camex Sumqayıt",
        "city": "Sumqayıt",
        "region": "Absheron",
        "district": "Sumqayıt",
        "address": "Nəriman Nərimanov küç. 14 (Sülh pr. kəsişməsi)",
        "latitude": 40.5890,
        "longitude": 49.6675,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Sumqayıt",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-gence",
        "carrier": "CAMEX",
        "name": "Camex Gəncə",
        "city": "Gəncə",
        "region": "Regions",
        "district": "Gəncə",
        "address": "Atatürk pr. 72",
        "latitude": 40.6850,
        "longitude": 46.3580,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": None,
        "working_hours": {"weekdays": "10:00 - 19:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-mingecevir",
        "carrier": "CAMEX",
        "name": "Camex Mingəçevir",
        "city": "Mingəçevir",
        "region": "Regions",
        "district": "Mingəçevir",
        "address": "Heydər Əliyev pr. 38",
        "latitude": 40.7702,
        "longitude": 47.0495,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": None,
        "working_hours": {"weekdays": "10:00 - 19:00", "saturday": "10:00 - 17:00", "sunday": "Bağlı"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "camex-seki",
        "carrier": "CAMEX",
        "name": "Camex Şəki",
        "city": "Şəki",
        "region": "Regions",
        "district": "Şəki",
        "address": "M.Ə. Rəsulzadə pr. 112",
        "latitude": 41.1915,
        "longitude": 47.1680,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": None,
        "working_hours": {"weekdays": "10:00 - 19:00", "saturday": "10:00 - 17:00", "sunday": "Bağlı"},
        "phone": "+994 12 441 55 55",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
]

_DYNAMEX_BRANCHES: List[Dict[str, Any]] = [
    {
        "branch_id": "dynamex-28-may",
        "carrier": "DYNAMEX",
        "name": "Dynamex 28 May",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nəsimi",
        "address": "Dilarə Əliyeva küç. 235 (28 May m. 2-ci çıxış)",
        "latitude": 40.3808,
        "longitude": 49.8492,
        "metro_station": "28 May",
        "distance_to_metro_m": 110,
        "transit_hub": "28 May",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-genclik",
        "carrier": "DYNAMEX",
        "name": "Dynamex Gənclik",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nərimanov",
        "address": "Əhməd Rəcəbli küç. 1 (Gənclik m. çıxışı)",
        "latitude": 40.4020,
        "longitude": 49.8525,
        "metro_station": "Gənclik",
        "distance_to_metro_m": 120,
        "transit_hub": "Gənclik",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-ehmedli",
        "carrier": "DYNAMEX",
        "name": "Dynamex Əhmədli",
        "city": "Bakı",
        "region": "Baku",
        "district": "Xətai",
        "address": "Məhəmməd Hadi küç. 130 (Bakı k/t yanı)",
        "latitude": 40.3865,
        "longitude": 49.9530,
        "metro_station": "Əhmədli",
        "distance_to_metro_m": 100,
        "transit_hub": "Əhmədli",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-xalqlar",
        "carrier": "DYNAMEX",
        "name": "Dynamex Xalqlar Dostluğu",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nizami",
        "address": "Bəhruz Nuriyev küç. 21",
        "latitude": 40.3985,
        "longitude": 49.9540,
        "metro_station": "Xalqlar Dostluğu",
        "distance_to_metro_m": 140,
        "transit_hub": "Xalqlar Dostluğu",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-elmler",
        "carrier": "DYNAMEX",
        "name": "Dynamex Elmlər Akademiyası",
        "city": "Bakı",
        "region": "Baku",
        "district": "Yasamal",
        "address": "Hüseyn Cavid pr. 52 (Hüseyn Cavid parkı qarşısı)",
        "latitude": 40.3748,
        "longitude": 49.8158,
        "metro_station": "Elmlər Akademiyası",
        "distance_to_metro_m": 90,
        "transit_hub": "Elmlər Akademiyası",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-yasamal",
        "carrier": "DYNAMEX",
        "name": "Dynamex Yasamal",
        "city": "Bakı",
        "region": "Baku",
        "district": "Yasamal",
        "address": "İnşaatçılar pr. 12 (İnşaatçılar m.)",
        "latitude": 40.3878,
        "longitude": 49.8042,
        "metro_station": "İnşaatçılar",
        "distance_to_metro_m": 120,
        "transit_hub": "Yasamal",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-nerimanov",
        "carrier": "DYNAMEX",
        "name": "Dynamex Nərimanov",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nərimanov",
        "address": "Faiq Yusifov küç. 45",
        "latitude": 40.4020,
        "longitude": 49.8700,
        "metro_station": "Nəriman Nərimanov",
        "distance_to_metro_m": 130,
        "transit_hub": "Nərimanov",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-sahil",
        "carrier": "DYNAMEX",
        "name": "Dynamex Sahil",
        "city": "Bakı",
        "region": "Baku",
        "district": "Səbail",
        "address": "Bülbül pr. 30",
        "latitude": 40.3718,
        "longitude": 49.8438,
        "metro_station": "Sahil",
        "distance_to_metro_m": 140,
        "transit_hub": "28 May",
        "working_hours": {"weekdays": "10:00 - 19:00", "saturday": "10:00 - 17:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": False,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": False,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": False,
        },
    },
    {
        "branch_id": "dynamex-nizami",
        "carrier": "DYNAMEX",
        "name": "Dynamex Nizami",
        "city": "Bakı",
        "region": "Baku",
        "district": "Yasamal",
        "address": "Salatın Əsgərova küç. 85 (Nizami m. yaxınlığı)",
        "latitude": 40.3790,
        "longitude": 49.8295,
        "metro_station": "Nizami",
        "distance_to_metro_m": 110,
        "transit_hub": "28 May",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-memar-ecemi",
        "carrier": "DYNAMEX",
        "name": "Dynamex Memar Əcəmi",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nəsimi",
        "address": "Asif Məhərrəmov küç. 32",
        "latitude": 40.4105,
        "longitude": 49.8165,
        "metro_station": "Memar Əcəmi",
        "distance_to_metro_m": 130,
        "transit_hub": "Yasamal",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-nesimi",
        "carrier": "DYNAMEX",
        "name": "Dynamex Nəsimi",
        "city": "Bakı",
        "region": "Baku",
        "district": "Binəqədi",
        "address": "Svetlana Məmmədova küç. 14 (Nəsimi m.)",
        "latitude": 40.4238,
        "longitude": 49.8172,
        "metro_station": "Nəsimi",
        "distance_to_metro_m": 80,
        "transit_hub": "Gənclik",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-neftciler",
        "carrier": "DYNAMEX",
        "name": "Dynamex Neftçilər",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nizami",
        "address": "Əlif Hacıyev küç. 18",
        "latitude": 40.4108,
        "longitude": 49.9420,
        "metro_station": "Neftçilər",
        "distance_to_metro_m": 120,
        "transit_hub": "Xalqlar Dostluğu",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-hezi-aslanov",
        "carrier": "DYNAMEX",
        "name": "Dynamex Həzi Aslanov",
        "city": "Bakı",
        "region": "Baku",
        "district": "Xətai",
        "address": "Məhəmməd Hadi küç. 94",
        "latitude": 40.3740,
        "longitude": 49.9530,
        "metro_station": "Həzi Aslanov",
        "distance_to_metro_m": 110,
        "transit_hub": "Əhmədli",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-bayil",
        "carrier": "DYNAMEX",
        "name": "Dynamex Bayıl",
        "city": "Bakı",
        "region": "Baku",
        "district": "Səbail",
        "address": "Qurban Abbasov küç. 28",
        "latitude": 40.3475,
        "longitude": 49.8310,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "28 May",
        "working_hours": {"weekdays": "10:00 - 19:00", "saturday": "10:00 - 17:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": False,
        },
    },
    {
        "branch_id": "dynamex-zabrat",
        "carrier": "DYNAMEX",
        "name": "Dynamex Zabrat",
        "city": "Bakı",
        "region": "Baku",
        "district": "Sabunçu",
        "address": "Zabrat 1 qəsəbəsi, Babək küç. 12",
        "latitude": 40.4635,
        "longitude": 49.9690,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Xalqlar Dostluğu",
        "working_hours": {"weekdays": "10:00 - 19:30", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-xirdalan",
        "carrier": "DYNAMEX",
        "name": "Dynamex Xırdalan",
        "city": "Xırdalan",
        "region": "Absheron",
        "district": "Abşeron",
        "address": "Qalubiyyə küç. 5",
        "latitude": 40.4478,
        "longitude": 49.7540,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Xırdalan",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-sumqayit-1",
        "carrier": "DYNAMEX",
        "name": "Dynamex Sumqayıt 1",
        "city": "Sumqayıt",
        "region": "Absheron",
        "district": "Sumqayıt",
        "address": "Bakı küçəsi, 2-ci mkr",
        "latitude": 40.5910,
        "longitude": 49.6702,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Sumqayıt",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-sumqayit-2",
        "carrier": "DYNAMEX",
        "name": "Dynamex Sumqayıt 2",
        "city": "Sumqayıt",
        "region": "Absheron",
        "district": "Sumqayıt",
        "address": "Zülfü Hacıyev küç. 64",
        "latitude": 40.5840,
        "longitude": 49.6580,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Sumqayıt",
        "working_hours": {"weekdays": "10:00 - 19:30", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-gence",
        "carrier": "DYNAMEX",
        "name": "Dynamex Gəncə",
        "city": "Gəncə",
        "region": "Regions",
        "district": "Gəncə",
        "address": "Nizami Gəncəvi pr. 88",
        "latitude": 40.6865,
        "longitude": 46.3620,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": None,
        "working_hours": {"weekdays": "10:00 - 19:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "dynamex-berde",
        "carrier": "DYNAMEX",
        "name": "Dynamex Bərdə",
        "city": "Bərdə",
        "region": "Regions",
        "district": "Bərdə",
        "address": "İsmət Qayıbov küç. 10",
        "latitude": 40.3755,
        "longitude": 47.1265,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": None,
        "working_hours": {"weekdays": "10:00 - 18:30", "saturday": "10:00 - 17:00", "sunday": "Bağlı"},
        "phone": "+994 12 310 03 33",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
]

_LIMAK_BRANCHES: List[Dict[str, Any]] = [
    {
        "branch_id": "limak-28-may",
        "carrier": "LIMAK",
        "name": "Limak 28 May",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nəsimi",
        "address": "Rəşid Behbudov küç. 53 (Azərbaycan Dillər Universiteti yanı)",
        "latitude": 40.3800,
        "longitude": 49.8485,
        "metro_station": "28 May",
        "distance_to_metro_m": 130,
        "transit_hub": "28 May",
        "working_hours": {"weekdays": "10:00 - 21:00", "saturday": "10:00 - 20:00", "sunday": "11:00 - 18:00"},
        "phone": "*9595 / +994 12 310 95 95",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-genclik",
        "carrier": "LIMAK",
        "name": "Limak Gənclik",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nərimanov",
        "address": "Koroğlu Rəhimov küç. 13 (Abu Arena yaxınlığı)",
        "latitude": 40.4018,
        "longitude": 49.8538,
        "metro_station": "Gənclik",
        "distance_to_metro_m": 170,
        "transit_hub": "Gənclik",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-ehmedli",
        "carrier": "LIMAK",
        "name": "Limak Əhmədli",
        "city": "Bakı",
        "region": "Baku",
        "district": "Xətai",
        "address": "Sarayevo küç. 24 (Əhmədli m. qarşısı)",
        "latitude": 40.3855,
        "longitude": 49.9545,
        "metro_station": "Əhmədli",
        "distance_to_metro_m": 80,
        "transit_hub": "Əhmədli",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-xalqlar",
        "carrier": "LIMAK",
        "name": "Limak Xalqlar Dostluğu",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nizami",
        "address": "Qara Qarayev pr. 118",
        "latitude": 40.3972,
        "longitude": 49.9528,
        "metro_station": "Xalqlar Dostluğu",
        "distance_to_metro_m": 120,
        "transit_hub": "Xalqlar Dostluğu",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-elmler",
        "carrier": "LIMAK",
        "name": "Limak Elmlər Akademiyası",
        "city": "Bakı",
        "region": "Baku",
        "district": "Yasamal",
        "address": "Şəfayət Mehdiyev küç. 136",
        "latitude": 40.3742,
        "longitude": 49.8150,
        "metro_station": "Elmlər Akademiyası",
        "distance_to_metro_m": 100,
        "transit_hub": "Elmlər Akademiyası",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-yasamal",
        "carrier": "LIMAK",
        "name": "Limak Yasamal",
        "city": "Bakı",
        "region": "Baku",
        "district": "Yasamal",
        "address": "A.M. Şərifzadə küç. 75",
        "latitude": 40.3890,
        "longitude": 49.8025,
        "metro_station": "İnşaatçılar",
        "distance_to_metro_m": 140,
        "transit_hub": "Yasamal",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-nerimanov",
        "carrier": "LIMAK",
        "name": "Limak Nərimanov",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nərimanov",
        "address": "Əliəşrəf Əlizadə küç. 9",
        "latitude": 40.4025,
        "longitude": 49.8710,
        "metro_station": "Nəriman Nərimanov",
        "distance_to_metro_m": 110,
        "transit_hub": "Nərimanov",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-nizami",
        "carrier": "LIMAK",
        "name": "Limak Nizami",
        "city": "Bakı",
        "region": "Baku",
        "district": "Yasamal",
        "address": "Bəşir Səfəroğlu küç. 172 (Nizami m. yaxınlığı)",
        "latitude": 40.3788,
        "longitude": 49.8305,
        "metro_station": "Nizami",
        "distance_to_metro_m": 120,
        "transit_hub": "28 May",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": False,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-memar-ecemi",
        "carrier": "LIMAK",
        "name": "Limak Memar Əcəmi",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nəsimi",
        "address": "Hüseynbala Əliyev küç. 15",
        "latitude": 40.4110,
        "longitude": 49.8160,
        "metro_station": "Memar Əcəmi",
        "distance_to_metro_m": 90,
        "transit_hub": "Yasamal",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-dernegul",
        "carrier": "LIMAK",
        "name": "Limak Dərnəgül (Mərkəzi Karqo Anbarı)",
        "city": "Bakı",
        "region": "Baku",
        "district": "Binəqədi",
        "address": "Ziya Bünyadov pr. 1965 (Dərnəgül m. yaxınlığı)",
        "latitude": 40.4270,
        "longitude": 49.8585,
        "metro_station": "Dərnəgül",
        "distance_to_metro_m": 180,
        "transit_hub": "Gənclik",
        "working_hours": {"weekdays": "09:00 - 21:00", "saturday": "09:00 - 20:00", "sunday": "10:00 - 18:00"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-koroglu",
        "carrier": "LIMAK",
        "name": "Limak Koroğlu",
        "city": "Bakı",
        "region": "Baku",
        "district": "Nizami",
        "address": "Ziya Bünyadov pr. 38 (Koroğlu m. çıxışı)",
        "latitude": 40.4200,
        "longitude": 49.9180,
        "metro_station": "Koroğlu",
        "distance_to_metro_m": 110,
        "transit_hub": "Nərimanov",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-bakixanov",
        "carrier": "LIMAK",
        "name": "Limak Bakıxanov",
        "city": "Bakı",
        "region": "Baku",
        "district": "Sabunçu",
        "address": "Ramiz Qəmbərov küç. 14",
        "latitude": 40.4240,
        "longitude": 49.9605,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Xalqlar Dostluğu",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-xirdalan",
        "carrier": "LIMAK",
        "name": "Limak Xırdalan",
        "city": "Xırdalan",
        "region": "Absheron",
        "district": "Abşeron",
        "address": "Heydər Əliyev pr. 18",
        "latitude": 40.4480,
        "longitude": 49.7552,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Xırdalan",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-sumqayit",
        "carrier": "LIMAK",
        "name": "Limak Sumqayıt",
        "city": "Sumqayıt",
        "region": "Absheron",
        "district": "Sumqayıt",
        "address": "Sülh pr. 34 (Sumqayıt Plaza yanı)",
        "latitude": 40.5895,
        "longitude": 49.6682,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": "Sumqayıt",
        "working_hours": {"weekdays": "10:00 - 20:00", "saturday": "10:00 - 19:00", "sunday": "11:00 - 17:00"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": True,
            "courier_door_delivery": True,
            "smart_locker_available": True,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-gence",
        "carrier": "LIMAK",
        "name": "Limak Gəncə",
        "city": "Gəncə",
        "region": "Regions",
        "district": "Gəncə",
        "address": "Həsən Əliyev pr. 42",
        "latitude": 40.6835,
        "longitude": 46.3615,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": None,
        "working_hours": {"weekdays": "10:00 - 19:00", "saturday": "10:00 - 18:00", "sunday": "Bağlı"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": True,
            "reverse_logistics_dropoff": True,
        },
    },
    {
        "branch_id": "limak-zaqatala",
        "carrier": "LIMAK",
        "name": "Limak Zaqatala",
        "city": "Zaqatala",
        "region": "Regions",
        "district": "Zaqatala",
        "address": "Car küç. 16",
        "latitude": 41.6335,
        "longitude": 46.6430,
        "metro_station": None,
        "distance_to_metro_m": None,
        "transit_hub": None,
        "working_hours": {"weekdays": "10:00 - 18:30", "saturday": "10:00 - 17:00", "sunday": "Bağlı"},
        "phone": "*9595",
        "capabilities": {
            "liquid_accepted": True,
            "bulky_items_accepted": True,
            "weekend_open": True,
            "sunday_open": False,
            "courier_door_delivery": True,
            "smart_locker_available": False,
            "card_payment": True,
            "fitting_room": False,
            "reverse_logistics_dropoff": True,
        },
    },
]


# Build typed BranchDTO catalog
def _load_branch_registry() -> Dict[str, BranchDTO]:
    raw_list = _STAREX_BRANCHES + _CAMEX_BRANCHES + _DYNAMEX_BRANCHES + _LIMAK_BRANCHES
    catalog: Dict[str, BranchDTO] = {}
    for item in raw_list:
        caps = BranchCapabilities(**item["capabilities"])
        dto = BranchDTO(
            branch_id=item["branch_id"],
            carrier=item["carrier"],
            name=item["name"],
            city=item["city"],
            region=item.get("region", "Baku"),
            district=item.get("district"),
            address=item["address"],
            latitude=item["latitude"],
            longitude=item["longitude"],
            metro_station=item.get("metro_station"),
            distance_to_metro_m=item.get("distance_to_metro_m"),
            transit_hub=item.get("transit_hub"),
            working_hours=item.get("working_hours", {}),
            phone=item["phone"],
            capabilities=caps,
            is_active=True,
        )
        catalog[dto.branch_id] = dto
    return catalog


BRANCH_CATALOG: Dict[str, BranchDTO] = _load_branch_registry()


# -----------------------------------------------------------------------------
# 6. MATCHING & PROXIMITY ENGINE
# -----------------------------------------------------------------------------

class BranchDirectoryEngine:
    """Intelligent Geo-Proximity & Delivery Routing Engine for PCS."""

    @staticmethod
    def get_all_branches(carrier: Optional[str] = None) -> List[BranchDTO]:
        """Returns all branches, optionally filtered by carrier."""
        branches = list(BRANCH_CATALOG.values())
        if carrier:
            carrier_upper = carrier.upper()
            branches = [b for b in branches if b.carrier == carrier_upper]
        return branches

    @staticmethod
    def get_branch_by_id(branch_id: str) -> Optional[BranchDTO]:
        """Retrieves a specific branch by unique identifier."""
        return BRANCH_CATALOG.get(branch_id.lower().strip())

    @staticmethod
    def get_branch_counts_by_carrier() -> Dict[str, int]:
        """Returns verified branch count per carrier."""
        counts = {"STAREX": 0, "CAMEX": 0, "DYNAMEX": 0, "LIMAK": 0}
        for b in BRANCH_CATALOG.values():
            if b.carrier in counts:
                counts[b.carrier] += 1
        return counts

    @classmethod
    def filter_branches(
        cls,
        carrier: Optional[str] = None,
        region: Optional[str] = None,
        city: Optional[str] = None,
        metro_station: Optional[str] = None,
        transit_hub: Optional[str] = None,
        requires_liquid: bool = False,
        requires_bulky: bool = False,
        requires_sunday: bool = False,
        requires_door_delivery: bool = False,
        requires_locker: bool = False,
        requires_fitting_room: bool = False,
        requires_reverse_logistics: bool = False,
    ) -> List[BranchDTO]:
        """Filters branches based on carrier, location, and capability flags."""
        res = cls.get_all_branches(carrier=carrier)
        if region:
            res = [b for b in res if b.region.lower() == region.lower()]
        if city:
            res = [b for b in res if b.city.lower() == city.lower()]
        if metro_station:
            res = [b for b in res if b.metro_station and b.metro_station.lower() == metro_station.lower()]
        if transit_hub:
            res = [b for b in res if b.transit_hub and b.transit_hub.lower() == transit_hub.lower()]

        if requires_liquid:
            res = [b for b in res if b.capabilities.liquid_accepted]
        if requires_bulky:
            res = [b for b in res if b.capabilities.bulky_items_accepted]
        if requires_sunday:
            res = [b for b in res if b.capabilities.sunday_open]
        if requires_door_delivery:
            res = [b for b in res if b.capabilities.courier_door_delivery]
        if requires_locker:
            res = [b for b in res if b.capabilities.smart_locker_available]
        if requires_fitting_room:
            res = [b for b in res if b.capabilities.fitting_room]
        if requires_reverse_logistics:
            res = [b for b in res if b.capabilities.reverse_logistics_dropoff]

        return res

    @classmethod
    def find_nearest_branch(
        cls,
        user_lat: float,
        user_lon: float,
        carrier: Optional[str] = None,
        required_capabilities: Optional[Set[str]] = None,
    ) -> Optional[BranchProximityResult]:
        """Finds the single nearest branch matching criteria to the given coordinates."""
        candidates = cls.get_all_branches(carrier=carrier)
        if not candidates:
            return None

        req_caps = required_capabilities or set()
        best_result: Optional[BranchProximityResult] = None
        min_dist = float("inf")

        for branch in candidates:
            # Check mandatory capabilities
            has_all_caps = True
            matched: List[str] = []
            missing: List[str] = []
            for cap in req_caps:
                if getattr(branch.capabilities, cap, False):
                    matched.append(cap)
                else:
                    has_all_caps = False
                    missing.append(cap)

            if not has_all_caps:
                continue

            dist = haversine_distance(user_lat, user_lon, branch.latitude, branch.longitude)
            if dist < min_dist:
                min_dist = dist
                times = estimate_travel_time(dist)
                # Compute suitability score
                score = max(10.0, 100.0 - (dist * 7.5))
                if branch.capabilities.sunday_open:
                    score = min(100.0, score + 5.0)
                if branch.capabilities.smart_locker_available:
                    score = min(100.0, score + 3.0)

                best_result = BranchProximityResult(
                    branch=branch,
                    distance_km=dist,
                    distance_m=int(dist * 1000),
                    walking_minutes=times["walking_minutes"],
                    driving_minutes=times["driving_minutes"],
                    metro_station=branch.metro_station,
                    suitability_score=round(score, 1),
                    capability_matches=matched,
                    missing_capabilities=missing,
                )

        return best_result

    @classmethod
    def find_nearest_branches_for_all_carriers(
        cls,
        user_lat: float,
        user_lon: float,
        required_capabilities: Optional[Set[str]] = None,
    ) -> MultiCarrierProximityResponse:
        """Finds and compares the nearest branch for EACH of the 4 major carriers."""
        results: Dict[str, BranchProximityResult] = {}
        for c in [CarrierName.STAREX.value, CarrierName.CAMEX.value, CarrierName.DYNAMEX.value, CarrierName.LIMAK.value]:
            res = cls.find_nearest_branch(
                user_lat=user_lat,
                user_lon=user_lon,
                carrier=c,
                required_capabilities=required_capabilities,
            )
            if res:
                results[c] = res

        if not results:
            raise ValueError("No matching branches found for given criteria.")

        overall = min(results.values(), key=lambda r: r.distance_km)
        summary = (
            f"Sizə ən yaxın karqo filialı: {overall.branch.carrier} ({overall.branch.name}) - "
            f"{overall.distance_km} km ({overall.walking_minutes} dəq piyada)."
        )

        return MultiCarrierProximityResponse(
            origin_point={"latitude": user_lat, "longitude": user_lon, "required_capabilities": list(required_capabilities or [])},
            carrier_recommendations=results,
            overall_closest=overall,
            summary_az=summary,
        )

    @classmethod
    def find_branches_by_metro(
        cls,
        metro_name: str,
        carrier: Optional[str] = None,
        max_distance_km: float = 2.5,
        required_capabilities: Optional[Set[str]] = None,
    ) -> List[BranchProximityResult]:
        """Finds all branches within walkable or transit distance of a Baku metro station."""
        if metro_name not in METRO_STATIONS:
            # Fuzzy / case-insensitive search
            found_key = None
            for key in METRO_STATIONS:
                if key.lower() == metro_name.lower():
                    found_key = key
                    break
            if not found_key:
                raise ValueError(f"Unknown Baku metro station: '{metro_name}'")
            metro_name = found_key

        lat, lon = METRO_STATIONS[metro_name]
        candidates = cls.get_all_branches(carrier=carrier)
        req_caps = required_capabilities or set()
        matched_results: List[BranchProximityResult] = []

        for b in candidates:
            has_all_caps = True
            matched: List[str] = []
            missing: List[str] = []
            for cap in req_caps:
                if getattr(b.capabilities, cap, False):
                    matched.append(cap)
                else:
                    has_all_caps = False
                    missing.append(cap)

            if not has_all_caps:
                continue

            dist = haversine_distance(lat, lon, b.latitude, b.longitude)
            if dist <= max_distance_km:
                times = estimate_travel_time(dist)
                score = max(10.0, 100.0 - (dist * 8.0))
                matched_results.append(
                    BranchProximityResult(
                        branch=b,
                        distance_km=dist,
                        distance_m=int(dist * 1000),
                        walking_minutes=times["walking_minutes"],
                        driving_minutes=times["driving_minutes"],
                        metro_station=b.metro_station,
                        suitability_score=round(score, 1),
                        capability_matches=matched,
                        missing_capabilities=missing,
                    )
                )

        matched_results.sort(key=lambda r: r.distance_km)
        return matched_results

    @classmethod
    def find_branches_by_transit_hub(
        cls,
        hub_name: str,
        carrier: Optional[str] = None,
        max_distance_km: float = 3.5,
        required_capabilities: Optional[Set[str]] = None,
    ) -> List[BranchProximityResult]:
        """Finds all branches serving a major Baku transit hub."""
        hub = None
        for k, v in TRANSIT_HUBS.items():
            if k.lower() == hub_name.lower():
                hub = v
                break

        if not hub:
            raise ValueError(f"Unknown Baku transit hub: '{hub_name}'. Valid hubs: {list(TRANSIT_HUBS.keys())}")

        lat, lon = hub["coords"]
        candidates = cls.get_all_branches(carrier=carrier)
        req_caps = required_capabilities or set()
        matched_results: List[BranchProximityResult] = []

        for b in candidates:
            # Check capabilities
            has_all_caps = True
            matched: List[str] = []
            missing: List[str] = []
            for cap in req_caps:
                if getattr(b.capabilities, cap, False):
                    matched.append(cap)
                else:
                    has_all_caps = False
                    missing.append(cap)

            if not has_all_caps:
                continue

            dist = haversine_distance(lat, lon, b.latitude, b.longitude)
            if dist <= max_distance_km or b.transit_hub == hub_name:
                times = estimate_travel_time(dist)
                score = max(10.0, 100.0 - (dist * 7.0))
                matched_results.append(
                    BranchProximityResult(
                        branch=b,
                        distance_km=dist,
                        distance_m=int(dist * 1000),
                        walking_minutes=times["walking_minutes"],
                        driving_minutes=times["driving_minutes"],
                        metro_station=b.metro_station,
                        suitability_score=round(score, 1),
                        capability_matches=matched,
                        missing_capabilities=missing,
                    )
                )

        matched_results.sort(key=lambda r: r.distance_km)
        return matched_results

    @classmethod
    def smart_route_shipment(
        cls,
        carrier: str,
        user_preferred_branch_id: str,
        is_liquid: bool = False,
        is_bulky: bool = False,
        requires_sunday: bool = False,
    ) -> RoutingDecision:
        """Evaluates whether the user's preferred branch satisfies item constraints.
        If not, automatically reroutes to the nearest capable branch of the same carrier.
        """
        carrier_upper = carrier.upper()
        pref_branch = cls.get_branch_by_id(user_preferred_branch_id)

        if not pref_branch:
            # Fallback to carrier's 28 May primary hub
            fallback_id = f"{carrier.lower()}-28-may"
            pref_branch = cls.get_branch_by_id(fallback_id) or cls.get_all_branches(carrier=carrier_upper)[0]

        notes: List[str] = []
        needs_reroute = False
        reroute_reasons: List[str] = []

        if is_liquid:
            notes.append("Maye/ətir/kosmetika məhsulu (ADR təhlükəsizlik qaydaları)")
            if not pref_branch.capabilities.liquid_accepted:
                needs_reroute = True
                reroute_reasons.append("seçilmiş filial maye/ətir qəbul etmir")

        if is_bulky:
            notes.append("İriqabaritli / ağır bağlama (>20 kq və ya həcmli)")
            if not pref_branch.capabilities.bulky_items_accepted:
                needs_reroute = True
                reroute_reasons.append("seçilmiş filial iriqabaritli yükləri qəbul etmir")

        if requires_sunday:
            notes.append("Bazar günü təhvil tələb olunur")
            if not pref_branch.capabilities.sunday_open:
                needs_reroute = True
                reroute_reasons.append("seçilmiş filial Bazar günləri fəaliyyət göstərmir")

        if not needs_reroute:
            return RoutingDecision(
                carrier=carrier_upper,
                recommended_branch=pref_branch,
                is_original_preferred=True,
                reroute_reason=None,
                distance_from_user_km=0.0,
                requires_special_handling=bool(is_liquid or is_bulky),
                handling_notes=notes,
            )

        # Reroute to closest branch of SAME carrier with required capabilities
        req_caps: Set[str] = set()
        if is_liquid:
            req_caps.add("liquid_accepted")
        if is_bulky:
            req_caps.add("bulky_items_accepted")
        if requires_sunday:
            req_caps.add("sunday_open")

        rerouted = cls.find_nearest_branch(
            user_lat=pref_branch.latitude,
            user_lon=pref_branch.longitude,
            carrier=carrier_upper,
            required_capabilities=req_caps,
        )

        if not rerouted:
            # Fallback to main central branch
            central_id = f"{carrier.lower()}-28-may"
            chosen_branch = cls.get_branch_by_id(central_id) or pref_branch
            dist = haversine_distance(pref_branch.latitude, pref_branch.longitude, chosen_branch.latitude, chosen_branch.longitude)
        else:
            chosen_branch = rerouted.branch
            dist = rerouted.distance_km

        reason_str = (
            f"Avtomatik yönləndirmə: {', '.join(reroute_reasons)}. "
            f"Bağlama eyni daşıyıcının tələblərə cavab verən ən yaxın filialına ('{chosen_branch.name}') yönləndirildi."
        )

        return RoutingDecision(
            carrier=carrier_upper,
            recommended_branch=chosen_branch,
            is_original_preferred=False,
            reroute_reason=reason_str,
            distance_from_user_km=dist,
            requires_special_handling=True,
            handling_notes=notes,
        )


# -----------------------------------------------------------------------------
# 7. REVERSE LOGISTICS REPATRIATION ENGINE
# Return workflow for defective/rejected items back to Istanbul/Guangzhou.
# -----------------------------------------------------------------------------

REPATRIATION_HUBS: Dict[Tuple[str, str], Dict[str, Any]] = {
    ("STAREX", "TR"): {
        "hub_name": "Starex İstanbul İade & Təhvil Mərkəzi (Avcılar)",
        "address": "Cihangir Mah. Şehit Jandarma Komando Er Hakan Öner Sk. No: 14, Avcılar, İstanbul",
        "domestic_carrier": "Trendyol Express / Yurtiçi Kargo",
        "base_rate_usd": 3.50,
        "per_kg_usd": 4.50,
        "transit_days": "4 - 7 iş günü",
    },
    ("STAREX", "CN"): {
        "hub_name": "Starex Guangzhou Repatriation Depot",
        "address": "广东省广州市白云区嘉禾望岗工业区14号仓库",
        "domestic_carrier": "SF Express (顺丰速运)",
        "base_rate_usd": 9.50,
        "per_kg_usd": 12.00,
        "transit_days": "8 - 12 iş günü",
    },
    ("CAMEX", "TR"): {
        "hub_name": "Camex Güngören İade Şöbəsi",
        "address": "Güngören Mah. Mareşal Fevzi Çakmak Cad. No: 38, Güngören, İstanbul",
        "domestic_carrier": "Aras Kargo / Yurtiçi Kargo",
        "base_rate_usd": 3.80,
        "per_kg_usd": 4.60,
        "transit_days": "4 - 7 iş günü",
    },
    ("CAMEX", "CN"): {
        "hub_name": "Camex Guangzhou Return Terminal",
        "address": "广东省广州市越秀区站西路58号仓库",
        "domestic_carrier": "ZTO Express (中通快递)",
        "base_rate_usd": 9.00,
        "per_kg_usd": 11.50,
        "transit_days": "8 - 12 iş günü",
    },
    ("DYNAMEX", "TR"): {
        "hub_name": "Dynamex İstanbul İade Bölümü",
        "address": "Yenibosna Merkez Mah. Değirmenbahçe Cad. No: 11, Bahçelievler, İstanbul",
        "domestic_carrier": "MNG Kargo / Trendyol Express",
        "base_rate_usd": 3.50,
        "per_kg_usd": 4.40,
        "transit_days": "4 - 6 iş günü",
    },
    ("DYNAMEX", "CN"): {
        "hub_name": "Dynamex Yiwu / Guangzhou Hub",
        "address": "Zhejiang Province, Yiwu Cargo Logistics City, Warehouse 6",
        "domestic_carrier": "SF Express (顺丰速运)",
        "base_rate_usd": 9.20,
        "per_kg_usd": 11.80,
        "transit_days": "8 - 12 iş günü",
    },
    ("LIMAK", "TR"): {
        "hub_name": "Limak Halkalı İade və Çeşidləmə Mərkəzi",
        "address": "Halkalı Merkez Mah. Basın Ekspres Yolu No: 22, Küçükçekmece, İstanbul",
        "domestic_carrier": "Trendyol Express / Yurtiçi Kargo",
        "base_rate_usd": 3.50,
        "per_kg_usd": 4.50,
        "transit_days": "4 - 7 iş günü",
    },
    ("LIMAK", "CN"): {
        "hub_name": "Limak Guangzhou Return Center",
        "address": "Guangdong Province, Guangzhou, Baiyun District, Warehouse B-8",
        "domestic_carrier": "SF Express / STO Express",
        "base_rate_usd": 9.50,
        "per_kg_usd": 12.00,
        "transit_days": "8 - 12 iş günü",
    },
}


class ReverseLogisticsEngine:
    """Manages cross-border return workflows for defective/wrong items back to foreign sellers."""

    USD_TO_AZN_RATE: float = 1.70

    @classmethod
    def calculate_return_fee(
        cls,
        carrier_name: str,
        origin_country: str,
        weight_kg: float,
    ) -> Dict[str, float]:
        """Calculates return freight fee based on carrier tariff schedule."""
        key = (carrier_name.upper(), origin_country.upper())
        hub_data = REPATRIATION_HUBS.get(key)
        if not hub_data:
            # Default rate
            base_usd = 4.0 if origin_country.upper() == "TR" else 10.0
            per_kg = 5.0 if origin_country.upper() == "TR" else 12.0
        else:
            base_usd = hub_data["base_rate_usd"]
            per_kg = hub_data["per_kg_usd"]

        if weight_kg <= 0.5:
            cost_usd = base_usd
        else:
            cost_usd = base_usd + ((weight_kg - 0.5) * per_kg)

        cost_usd = round(cost_usd, 2)
        cost_azn = round(cost_usd * cls.USD_TO_AZN_RATE, 2)
        return {"cost_usd": cost_usd, "cost_azn": cost_azn}

    @classmethod
    def generate_return_quote(cls, request: ReverseLogisticsRequest) -> ReverseLogisticsQuote:
        """Generates a complete reverse logistics return quote, workflow, and dropoff branch recommendation."""
        fees = cls.calculate_return_fee(
            carrier_name=request.carrier_name,
            origin_country=request.origin_country,
            weight_kg=request.weight_kg,
        )

        key = (request.carrier_name.upper(), request.origin_country.upper())
        hub_data = REPATRIATION_HUBS.get(key, {
            "hub_name": f"{request.carrier_name.upper()} Xarici İade Mərkəzi",
            "domestic_carrier": "Yerli Kuryer",
            "transit_days": "5 - 10 iş günü",
        })

        # Identify suitable dropoff branch
        if request.user_preferred_branch_id:
            chosen = BranchDirectoryEngine.get_branch_by_id(request.user_preferred_branch_id)
            if not chosen or not chosen.capabilities.reverse_logistics_dropoff:
                # Find closest capable branch of same carrier
                chosen = BranchDirectoryEngine.filter_branches(
                    carrier=request.carrier_name,
                    requires_reverse_logistics=True,
                )[0]
        else:
            chosen = BranchDirectoryEngine.filter_branches(
                carrier=request.carrier_name,
                requires_reverse_logistics=True,
            )[0]

        return_id = f"RET-{request.carrier_name[:3]}-{uuid.uuid4().hex[:6].upper()}"

        docs = [
            f"Satıcı İade Kodu / RMA: {request.merchant_return_code}",
            "Ticarət Qaiməsi / Commercial Invoice (PDF surəti)",
            "Məhsulun qüsurunu əks etdirən foto/video aktı",
            "Şəxsiyyət vəsiqəsinin FİN kodu",
        ]

        workflow = [
            f"1. Məhsulu qutusu və aksesuarları ilə birlikdə paketləyin və üzərinə '{return_id}' barkodunu yapışdırın.",
            f"2. Bağlamanı seçilmiş filialımıza ('{chosen.name}', {chosen.address}) təhvil verin (və ya kuryer çağırın).",
            f"3. Filial əməkdaşı bağlamanı skan edərək 'Geri Qaytarılma Qəbzi' təqdim edəcək.",
            "4. DGK 'SmartCustoms' sistemində bəyannaməyə 'İxrac/Geri Qaytarma' qeydi edilir və 300 USD aylıq limitiniz bərpa olunur.",
            f"5. Bağlama hava yolu ilə {hub_data['hub_name']} anbarına çatdırılır.",
            f"6. Xarici anbar məhsulu {hub_data['domestic_carrier']} vasitəsilə satıcıya təhvil verir və pulunuz karta geri qaytarılır.",
        ]

        return ReverseLogisticsQuote(
            return_id=return_id,
            carrier_name=request.carrier_name.upper(),
            destination_country=request.origin_country.upper(),
            weight_kg=request.weight_kg,
            return_fee_azn=fees["cost_azn"],
            return_fee_usd=fees["cost_usd"],
            estimated_transit_days=hub_data["transit_days"],
            repatriation_warehouse=hub_data["hub_name"],
            origin_carrier=hub_data["domestic_carrier"],
            customs_quota_refund_eligible=True,
            recommended_dropoff_branch=chosen,
            required_documents=docs,
            step_by_step_workflow=workflow,
        )

    @classmethod
    def issue_return_waybill(
        cls,
        quote: ReverseLogisticsQuote,
        order_ref: str,
        merchant_return_code: str,
    ) -> ReverseLogisticsWaybill:
        """Issues an official repatriation return waybill with barcode payload."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        tracking_num = f"AZRET{quote.carrier_name[:2]}{quote.return_id.split('-')[-1]}"
        barcode = f"*{tracking_num}*"
        qr_payload = f"PCS-RETURN|{quote.return_id}|{order_ref}|{quote.carrier_name}|{merchant_return_code}"

        return ReverseLogisticsWaybill(
            return_id=quote.return_id,
            order_ref=order_ref,
            carrier=quote.carrier_name,
            tracking_number=tracking_num,
            barcode=barcode,
            qr_payload=qr_payload,
            dropoff_branch_name=quote.recommended_dropoff_branch.name,
            merchant_return_code=merchant_return_code,
            created_at=now_str,
            status=ReturnStatusEnum.WAYBILL_ISSUED,
        )

    @classmethod
    def get_customs_quota_advice(cls, order_ref: str, invoice_usd: float) -> Dict[str, Any]:
        """Provides guidance for restoring DGK 300 USD monthly personal customs allowance."""
        return {
            "order_ref": order_ref,
            "refunded_quota_usd": invoice_usd,
            "dgk_action_required": True,
            "portal": "SmartCustoms (e-gov.az / smartcustoms.gov.az)",
            "legal_basis": "AR Nazirlər Kabinetinin 305 nömrəli Qərarı (Fiziki şəxslər tərəfindən güzəştli qaydada malların idxalı)",
            "instructions_az": (
                f"Sifariş '{order_ref}' xaricə geri göndərildikdən sonra, PCS sisteminin təqdim etdiyi "
                f"'Geri İxrac Təsdiq Sənədi' (Reverse Export Declaration) ilə SmartCustoms tətbiqində "
                f"'Düzəliş / İmtina' sorğusu göndərin. {invoice_usd} ABŞ dolları məbləğində idxal dəyəri "
                f"cari təqvim ayının 300 USD güzəştli limitindən dərhal silinərək bərpa olunacaqdır."
            ),
        }


__all__ = [
    "CarrierName",
    "RegionType",
    "ReturnReasonEnum",
    "ReturnStatusEnum",
    "METRO_STATIONS",
    "TRANSIT_HUBS",
    "BranchCapabilities",
    "BranchDTO",
    "BranchProximityResult",
    "MultiCarrierProximityResponse",
    "RoutingDecision",
    "ReverseLogisticsRequest",
    "ReverseLogisticsQuote",
    "ReverseLogisticsWaybill",
    "haversine_distance",
    "estimate_travel_time",
    "BRANCH_CATALOG",
    "BranchDirectoryEngine",
    "ReverseLogisticsEngine",
]
