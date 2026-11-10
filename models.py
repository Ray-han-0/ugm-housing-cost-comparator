"""
models.py - Data entities for Kos Aggregator & True Cost Comparator
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple


@dataclass
class CampusCluster:
    name: str
    latitude: float
    longitude: float
    description: str


@dataclass
class KosListing:
    kos_id: str
    name: str
    raw_text: str
    base_rent_monthly: float
    rent_period: str = "bulan"                # "bulan", "semester", "tahun"
    electricity_system: str = "token"         # "token" (bayar sendiri) or "gratis" (include)
    water_fee_monthly: float = 0.0
    trash_security_fee_monthly: float = 0.0
    wifi_fee_monthly: float = 0.0
    deposit_amount: float = 0.0
    min_contract_months: int = 12
    curfew: str = "24 Jam"                    # "24 Jam", "22:00", "23:00"
    has_ac: bool = False
    has_private_bathroom: bool = False
    has_water_heater: bool = False
    has_wifi: bool = False
    has_furnished: bool = False
    has_refrigerator: bool = False
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address_hint: str = "Pogung, Sleman"


@dataclass
class TrueCostBreakdown:
    base_rent_monthly: float
    estimated_electricity: float
    utility_fees: float                       # Water + Trash + WiFi
    amortized_deposit: float                  # Deposit / min_contract_months
    true_monthly_cost: float
    hidden_cost_monthly: float                # true_monthly_cost - base_rent_monthly
    hidden_cost_percentage: float             # (hidden / base) * 100%


@dataclass
class KosComparisonResult:
    listing: KosListing
    cost: TrueCostBreakdown
    distance_km: float
    duration_walking_min: float
    duration_motorcycle_min: float
    target_cluster: str
    livability_score: float                   # 0.0 to 100.0%
    score_breakdown: Dict[str, float] = field(default_factory=dict)
