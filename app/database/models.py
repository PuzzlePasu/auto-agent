import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

@dataclass
class CarListing:
    id: Optional[int] = None
    provider: str = ""
    external_id: str = ""
    url: str = ""
    make: str = ""
    model: str = ""
    title: str = ""
    price: float = 0.0
    mileage: int = 0
    first_registration_year: int = 2020
    first_registration_month: int = 1
    power_hp: int = 150
    transmission: str = "Automatik"
    fuel_type: str = "Benzin"
    postal_code: str = ""
    city: str = ""
    distance_km: float = 0.0
    dealer_name: str = ""
    features: List[str] = field(default_factory=list)
    image_url: str = ""
    first_seen: str = field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    last_seen: str = field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))
    is_active: bool = True
    consecutive_missing_runs: int = 0
    is_favorite: bool = False
    canonical_id: Optional[int] = None
    duplicate_info: Optional[Dict[str, Any]] = None
    deal_score: float = 0.0
    sub_scores: Dict[str, float] = field(default_factory=dict)
    market_stats: Dict[str, Any] = field(default_factory=dict)
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    image_url: str = ""
    images: List[str] = field(default_factory=list)  # Liste aller verfügbaren Fotos

@dataclass
class PriceRecord:
    id: Optional[int] = None
    car_id: int = 0
    price: float = 0.0
    recorded_at: str = field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

@dataclass
class SearchLog:
    id: Optional[int] = None
    start_time: str = ""
    end_time: str = ""
    provider: str = ""
    total_found: int = 0
    new_found: int = 0
    price_changes: int = 0
    duplicates_detected: int = 0
    deactivated_count: int = 0
    errors: str = ""