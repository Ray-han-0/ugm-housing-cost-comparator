"""
cost_calculator.py - True Housing Cost Calculation & Livability Scoring Index
Computes true monthly cost by uncovering hidden electricity, utility fees,
and amortized deposits, eliminating superficial rent advertising deception.
"""

from typing import Dict, Tuple

try:
    from .models import KosListing, TrueCostBreakdown
except ImportError:
    from models import KosListing, TrueCostBreakdown

# PLN Non-Subsidized Household Tariff R-1/TR 1300 VA (Tarif Dasar Listrik)
PLN_TARIFF_PER_KWH = 1444.70


def estimate_monthly_electricity_kwh(listing: KosListing) -> float:
    """
    Computes estimated monthly kWh based on in-room electrical appliances:
    - Base Student Load (LED lights, laptop charging, smartphone): ~24 kWh
    - Air Conditioner (0.5 PK 360W, 7 hours/day * 30 days): ~75.6 kWh
    - Water Heater (350W, 20 mins/day * 30 days): ~3.5 kWh
    - Mini Refrigerator (45W continuous compressor cycle): ~32.4 kWh
    """
    if listing.electricity_system.lower() == "gratis":
        return 0.0

    kwh_total = 24.0  # Base lighting & gadgets

    if listing.has_ac:
        kwh_total += 75.6
    if listing.has_water_heater:
        kwh_total += 3.5
    if listing.has_refrigerator:
        kwh_total += 32.4

    return kwh_total


def calculate_true_monthly_cost(listing: KosListing) -> TrueCostBreakdown:
    """
    True Housing Cost Formula:
    TrueCost = BaseRent + ElectricityCost + UtilityFees + AmortizedDeposit
    """
    kwh = estimate_monthly_electricity_kwh(listing)
    estimated_electricity = round(kwh * PLN_TARIFF_PER_KWH, 2)

    utility_fees = round(
        listing.water_fee_monthly + listing.trash_security_fee_monthly + listing.wifi_fee_monthly,
        2
    )

    contract_months = max(1, listing.min_contract_months)
    amortized_deposit = round(listing.deposit_amount / contract_months, 2)

    true_monthly = round(
        listing.base_rent_monthly + estimated_electricity + utility_fees + amortized_deposit,
        2
    )

    hidden_cost = round(true_monthly - listing.base_rent_monthly, 2)
    hidden_pct = round((hidden_cost / listing.base_rent_monthly) * 100.0, 1) if listing.base_rent_monthly > 0 else 0.0

    return TrueCostBreakdown(
        base_rent_monthly=listing.base_rent_monthly,
        estimated_electricity=estimated_electricity,
        utility_fees=utility_fees,
        amortized_deposit=amortized_deposit,
        true_monthly_cost=true_monthly,
        hidden_cost_monthly=hidden_cost,
        hidden_cost_percentage=hidden_pct
    )


def evaluate_livability_index(listing: KosListing,
                              cost: TrueCostBreakdown,
                              distance_km: float) -> Tuple[float, Dict[str, float]]:
    """
    Computes holistic 0-100% Livability Score across 4 dimensions:
    1. Affordability (35%): lower true cost = higher score
    2. Proximity (25%): closer distance to UGM campus cluster = higher score
    3. Facilities (25%): AC, private bathroom, wifi, furnished, water heater
    4. Curfew / Freedom (15%): 24-hour access vs strict gate locks
    """
    # 1. Affordability subscore (Target baseline: Rp 1.500.000)
    # Rp 800k -> 100, Rp 1.5M -> 85, Rp 2.5M -> 60, Rp 3.5M -> 40
    affordability = max(20.0, min(100.0, 120.0 - (cost.true_monthly_cost / 25000.0)))

    # 2. Proximity subscore (Target: <= 1.0 km)
    # 0.5 km -> 100, 1.5 km -> 85, 3.0 km -> 65, 5.0 km -> 45
    proximity = max(20.0, min(100.0, 105.0 - (distance_km * 12.0)))

    # 3. Facilities subscore (Max 100)
    facility_points = 0.0
    if listing.has_ac:
        facility_points += 25.0
    if listing.has_private_bathroom:
        facility_points += 25.0
    if listing.has_wifi:
        facility_points += 20.0
    if listing.has_furnished:
        facility_points += 15.0
    if listing.has_water_heater:
        facility_points += 15.0
    facilities = min(100.0, facility_points)

    # 4. Curfew subscore
    if "24" in listing.curfew or "bebas" in listing.curfew.lower():
        freedom = 100.0
    elif "23" in listing.curfew:
        freedom = 75.0
    else:
        freedom = 55.0

    weights = {
        "affordability": 0.35,
        "proximity": 0.25,
        "facilities": 0.25,
        "freedom": 0.15
    }

    total_score = (
        affordability * weights["affordability"] +
        proximity * weights["proximity"] +
        facilities * weights["facilities"] +
        freedom * weights["freedom"]
    )

    breakdown = {
        "affordability_score": round(affordability, 1),
        "proximity_score": round(proximity, 1),
        "facilities_score": round(facilities, 1),
        "freedom_score": round(freedom, 1)
    }

    return round(total_score, 1), breakdown
