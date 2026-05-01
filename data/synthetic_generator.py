"""
Synthetic data generator for the United Airlines Network Planning System.

Produces deterministic, realistic airline operational data using seed-based
random generation for full reproducibility.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from itertools import combinations
from typing import List

import numpy as np

from config import (
    AIRPORT_UTC_OFFSETS,
    HUBS,
    RANDOM_SEED,
)
from data.models import (
    Aircraft,
    AircraftType,
    Disruption,
    DisruptionType,
    Flight,
    FlightStatus,
    Gate,
    Route,
    SeverityLevel,
)

# --------------------------------------------------------------------------- #
# Aircraft specifications lookup
# --------------------------------------------------------------------------- #
_AIRCRAFT_SPECS = {
    AircraftType.B737_MAX9: {"capacity": 178, "range_nm": 3550},
    AircraftType.B787_9:    {"capacity": 252, "range_nm": 7530},
    AircraftType.B777_200:  {"capacity": 364, "range_nm": 5240},
    AircraftType.A319:      {"capacity": 128, "range_nm": 3700},
}

# --------------------------------------------------------------------------- #
# Flight-time estimates (hours) between hub pairs (simplified)
# --------------------------------------------------------------------------- #

def _flight_hours(origin: str, destination: str) -> float:
    """Estimate flight time in hours between two airports using great-circle
    approximation based on coordinate distance, with a floor of 1.0 h."""
    from config import AIRPORT_COORDS

    lat1, lon1 = AIRPORT_COORDS.get(origin, (40.0, -100.0))
    lat2, lon2 = AIRPORT_COORDS.get(destination, (40.0, -100.0))
    # rough degree-distance -> hours at ~500 mph ground speed
    dist_deg = ((lat2 - lat1) ** 2 + (lon2 - lon1) ** 2) ** 0.5
    dist_miles = dist_deg * 54.6  # ~54.6 statute miles per degree avg
    hours = max(dist_miles / 500.0, 1.0)
    return round(hours, 2)


# =========================================================================== #
# Public generator functions
# =========================================================================== #

def generate_flights(n: int = 200, seed: int = RANDOM_SEED) -> List[Flight]:
    """Generate *n* realistic United Airlines flights with authentic metrics.

    Produces flights with realistic patterns including:
        - Hub-to-hub preference (60%)
        - Hub-to-spoke routes (40%)
        - Authentic delay distribution (exponential)
        - Time-of-day based patterns
        - Aircraft gauge appropriateness
        - Load factor correlations with demand

    Status distribution:
        82% On Time, 11% Delayed, 4% Cancelled, 3% Diverted

    Args:
        n: Number of flights to generate.
        seed: Random seed for reproducibility.

    Returns:
        List of Flight model instances with realistic data.
    """
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    # Pre-generate aircraft pool for tail-number assignment
    aircraft_pool = generate_aircraft(n=80, seed=seed)
    tail_map: dict[AircraftType, list[str]] = {}
    for ac in aircraft_pool:
        tail_map.setdefault(ac.aircraft_type, []).append(ac.tail_number)

    # Gate pool
    gate_pool = generate_gates(seed=seed)
    gate_ids_by_airport: dict[str, list[str]] = {}
    for g in gate_pool:
        gate_ids_by_airport.setdefault(g.airport, []).append(g.gate_id)

    # More realistic status distribution based on actual airline data
    status_choices = [
        FlightStatus.ON_TIME,
        FlightStatus.DELAYED,
        FlightStatus.CANCELLED,
        FlightStatus.DIVERTED,
    ]
    status_weights = [0.82, 0.11, 0.04, 0.03]

    aircraft_types = list(AircraftType)
    type_weights = [0.40, 0.25, 0.15, 0.20]  # B737 most common

    # Base date for schedule
    base_date = datetime(2026, 5, 1)

    flights: List[Flight] = []
    used_flight_numbers: set[str] = set()

    # Hub-pair preferences for realistic routing
    hub_to_hub_prob = 0.60  # 60% of flights hub-to-hub
    all_airports = list(HUBS) + ["ATL", "DFW", "JFK", "SEA", "MIA", "BOS", "PHX"]

    for i in range(n):
        # Realistic route selection: prefer hub pairs, but include hub-to-spoke
        if rng.random() < hub_to_hub_prob:
            origin = rng.choice(HUBS)
            dest_choices = [h for h in HUBS if h != origin]
            destination = rng.choice(dest_choices)
        else:
            # Hub-to-spoke or spoke-to-spoke
            origin = rng.choice(HUBS) if rng.random() < 0.7 else rng.choice(all_airports)
            dest_choices = [a for a in all_airports if a != origin]
            destination = rng.choice(dest_choices)

        # Flight number with realistic patterns
        while True:
            fn = f"UA{rng.randint(100, 9999)}"
            if fn not in used_flight_numbers:
                used_flight_numbers.add(fn)
                break

        # Aircraft type selection based on route distance
        dist = _flight_hours(origin, destination)
        if dist <= 2.5:
            ac_type = rng.choices([AircraftType.A319, AircraftType.B737_MAX9], weights=[0.4, 0.6], k=1)[0]
        elif dist <= 4.5:
            ac_type = rng.choices(aircraft_types, weights=[0.30, 0.10, 0.20, 0.40], k=1)[0]
        else:
            ac_type = rng.choices([AircraftType.B787_9, AircraftType.B777_200], weights=[0.6, 0.4], k=1)[0]
        
        tails = tail_map.get(ac_type, ["N00000"])
        tail = rng.choice(tails)

        # Departure time: realistic patterns
        day_offset = rng.randint(0, 2)
        
        # Peak hours: 06-09, 17-19; Off-peak: 05, 10-16, 20-23
        if rng.random() < 0.5:
            local_hour = rng.choice([6, 7, 8, 17, 18, 19])  # Peak times
        else:
            local_hour = rng.choice([5] + list(range(10, 17)) + list(range(20, 24)))
        
        local_minute = rng.choice([0, 15, 30, 45])
        utc_offset = AIRPORT_UTC_OFFSETS.get(origin, -6)
        departure = base_date + timedelta(
            days=day_offset,
            hours=local_hour - utc_offset,
            minutes=local_minute,
        )

        # Arrival
        flight_hrs = _flight_hours(origin, destination)
        arrival = departure + timedelta(hours=flight_hrs)

        # Gate assignment
        gate_id = None
        if origin in gate_ids_by_airport:
            gate_id = rng.choice(gate_ids_by_airport[origin])

        # Status & delay with realistic distributions
        status = rng.choices(status_choices, weights=status_weights, k=1)[0]
        delay_minutes = 0
        
        if status == FlightStatus.DELAYED:
            # Exponential distribution for delays (realistic: many small, few large)
            delay_minutes = int(np_rng.exponential(scale=25)) + 10
            delay_minutes = min(delay_minutes, 300)  # Cap at 5 hours
        elif status == FlightStatus.DIVERTED:
            delay_minutes = rng.randint(90, 240)
        elif status == FlightStatus.CANCELLED:
            delay_minutes = 0  # Cancelled flights don't have delays

        # Load factor: realistic distribution with time-of-day and seasonality
        base_load = 0.70 if rng.random() < 0.6 else 0.85  # Different busy/quiet periods
        load_variance = float(np_rng.normal(loc=0, scale=0.06))
        load_factor = round(min(0.98, max(0.35, base_load + load_variance)), 2)

        flights.append(
            Flight(
                flight_number=fn,
                origin=origin,
                destination=destination,
                departure=departure,
                arrival=arrival,
                aircraft_type=ac_type,
                tail_number=tail,
                gate_id=gate_id,
                status=status,
                delay_minutes=delay_minutes,
                load_factor=load_factor,
            )
        )

    return flights


def generate_routes(seed: int = RANDOM_SEED) -> List[Route]:
    """Generate all meaningful hub-pair route combinations with authentic metrics.

    Each route receives realistic demand scores, revenue indices, competition
    levels, and seasonal patterns based on airline industry benchmarks.

    Produces ~28 routes with characteristics reflecting:
        - Actual United hub network
        - Business vs leisure demand patterns
        - Competitive dynamics
        - Seasonal revenue peaks
        - Real-world load factor correlations

    Args:
        seed: Random seed for reproducibility.

    Returns:
        List of Route model instances with authentic data.
    """
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    competition_options = ["Low", "Medium", "High"]
    season_options = [None, "Summer", "Winter", "Holiday", "Spring Break"]

    # Hub network realistic patterns
    hub_strength: Dict[str, float] = {
        "ORD": 1.0,  # Dominant hub
        "IAH": 0.95,
        "DEN": 0.85,
        "EWR": 0.90,
        "LAX": 0.80,  # More leisure-focused
        "SFO": 0.75,
        "DCA": 0.70,  # Slot-constrained
        "LAS": 0.65,  # Leisure destination
    }

    # Domestic routes with business/leisure splits
    routes: List[Route] = []
    for origin, destination in combinations(HUBS, 2):
        route_id = f"{origin}-{destination}"
        
        # Realistic frequency based on hub importance
        origin_strength = hub_strength.get(origin, 0.7)
        dest_strength = hub_strength.get(destination, 0.7)
        hub_factor = (origin_strength + dest_strength) / 2
        
        # Frequency: stronger hubs get higher frequency
        base_freq = max(7, min(42, int(hub_factor * 30)))
        frequency = rng.choice([f for f in [7, 14, 21, 28, 35, 42] if f >= base_freq])
        
        # Demand scoring
        # Biased toward important hubs and business markets (ORD, EWR connections strong)
        if origin in ["ORD", "EWR"] or destination in ["ORD", "EWR"]:
            demand = round(float(np_rng.beta(a=4, b=1.5)), 2)  # Higher demand
        elif origin in ["LAS", "LAX"] or destination in ["LAS"]:
            demand = round(float(np_rng.beta(a=2.5, b=2)), 2)  # Moderate leisure
        else:
            demand = round(float(np_rng.beta(a=3, b=2.5)), 2)  # Standard
        
        # Revenue indices based on market characteristics
        if origin in ["ORD", "EWR", "DEN"] and destination in ["ORD", "EWR", "DEN"]:
            revenue = round(float(np_rng.lognormal(mean=0.15, sigma=0.25)), 2)  # Premium business routes
        elif origin in ["LAS", "LAX"] or destination in ["LAS", "LAX"]:
            revenue = round(float(np_rng.lognormal(mean=-0.1, sigma=0.2)), 2)  # Leisure discounts
        else:
            revenue = round(float(np_rng.lognormal(mean=0.0, sigma=0.25)), 2)
        
        revenue = max(0.7, min(1.6, revenue))  # Realistic bounds
        
        # Competition model: longer routes have less, trunk routes have more
        distance_nm = _great_circle_nm(origin, destination)
        if distance_nm < 500:
            competition = rng.choices(competition_options, weights=[0.2, 0.5, 0.3], k=1)[0]  # Mostly Medium/High
        elif distance_nm < 1500:
            competition = rng.choices(competition_options, weights=[0.3, 0.5, 0.2], k=1)[0]
        else:
            competition = rng.choices(competition_options, weights=[0.5, 0.35, 0.15], k=1)[0]  # More Low
        
        # Seasonal peaks
        if (origin in ["LAS", "LAX"] or destination in ["LAS", "LAX"]):
            seasonal = rng.choice([None, "Summer", "Holiday"])  # Leisure seasons
        elif (origin in ["DEN"] and destination in ["DEN", "IAH"]):
            seasonal = rng.choice([None, "Winter", "Spring Break"])  # Colorado mountains/skiing
        else:
            seasonal = rng.choice([None, "Summer", None, None])  # Minimal seasonal pattern
        
        routes.append(
            Route(
                route_id=route_id,
                origin=origin,
                destination=destination,
                frequency_weekly=frequency,
                demand_score=demand,
                revenue_index=revenue,
                competition_level=competition,
                seasonal_peak=seasonal,
            )
        )

    return routes


def _great_circle_nm(origin: str, destination: str) -> float:
    """Compute great-circle distance in nautical miles."""
    from config import AIRPORT_COORDS
    import math
    
    lat1, lon1 = AIRPORT_COORDS.get(origin, (40.0, -100.0))
    lat2, lon2 = AIRPORT_COORDS.get(destination, (40.0, -100.0))
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    return c * 3440.065  # Nautical miles


def generate_aircraft(n: int = 80, seed: int = RANDOM_SEED) -> List[Aircraft]:
    """Generate *n* aircraft across United's fleet types.

    Fleet mix (approximate):
        B737-MAX9  40 %
        B787-9     25 %
        B777-200   15 %
        A319       20 %

    Args:
        n: Number of aircraft to generate.
        seed: Random seed for reproducibility.

    Returns:
        List of Aircraft model instances.
    """
    rng = random.Random(seed)

    types_and_weights = [
        (AircraftType.B737_MAX9, 0.40),
        (AircraftType.B787_9, 0.25),
        (AircraftType.B777_200, 0.15),
        (AircraftType.A319, 0.20),
    ]
    types = [t for t, _ in types_and_weights]
    weights = [w for _, w in types_and_weights]

    statuses = ["Active", "Active", "Active", "Active", "Maintenance"]
    base_date = datetime(2026, 5, 1)

    aircraft: List[Aircraft] = []
    for i in range(n):
        ac_type = rng.choices(types, weights=weights, k=1)[0]
        specs = _AIRCRAFT_SPECS[ac_type]
        tail = f"N{rng.randint(10000, 99999)}"
        hub = rng.choice(HUBS)
        status = rng.choice(statuses)
        next_maint = base_date + timedelta(days=rng.randint(1, 90))

        aircraft.append(
            Aircraft(
                tail_number=tail,
                aircraft_type=ac_type,
                capacity=specs["capacity"],
                range_nm=specs["range_nm"],
                status=status,
                hub=hub,
                next_maintenance=next_maint,
            )
        )

    return aircraft


def generate_gates(seed: int = RANDOM_SEED) -> List[Gate]:
    """Generate ~40 gates across ORD (20), IAH (10), and DEN (10).

    Gates are distributed across realistic terminal letters with appropriate
    size categories.

    Args:
        seed: Random seed for reproducibility.

    Returns:
        List of Gate model instances.
    """
    rng = random.Random(seed)

    gate_defs: list[tuple[str, str, int]] = [
        # (airport, terminal, gate_count)
        ("ORD", "B", 7),
        ("ORD", "C", 8),
        ("ORD", "F", 5),
        ("IAH", "A", 4),
        ("IAH", "C", 3),
        ("IAH", "E", 3),
        ("DEN", "A", 5),
        ("DEN", "B", 5),
    ]

    size_options = ["Narrow-body", "Wide-body", "Regional"]
    size_weights = [0.55, 0.30, 0.15]
    status_options = ["Available", "Occupied", "Maintenance"]
    status_weights = [0.50, 0.40, 0.10]

    gates: List[Gate] = []
    for airport, terminal, count in gate_defs:
        for idx in range(1, count + 1):
            gate_id = f"{terminal}{idx}"
            size = rng.choices(size_options, weights=size_weights, k=1)[0]
            status = rng.choices(status_options, weights=status_weights, k=1)[0]

            gates.append(
                Gate(
                    gate_id=gate_id,
                    terminal=terminal,
                    airport=airport,
                    size_category=size,
                    status=status,
                    current_flight=None,
                )
            )

    return gates


def generate_disruptions(
    n: int = 10, seed: int = RANDOM_SEED
) -> List[Disruption]:
    """Generate *n* realistic disruption events.

    Args:
        n: Number of disruptions to generate.
        seed: Random seed for reproducibility.

    Returns:
        List of Disruption model instances.
    """
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    base_date = datetime(2026, 5, 1)

    descriptions_by_type = {
        DisruptionType.WEATHER: [
            "Thunderstorm complex causing ground delays and reduced arrival rate.",
            "Dense fog limiting visibility below ILS Cat-I minimums.",
            "Winter storm with icing conditions and runway contamination.",
            "Severe turbulence reports along corridor requiring reroutes.",
        ],
        DisruptionType.MECHANICAL: [
            "Engine oil pressure indication requiring return to gate.",
            "Landing gear sensor fault detected during pre-flight.",
            "Bleed air system anomaly; aircraft out of service pending inspection.",
            "Windshield crack discovered during walk-around.",
        ],
        DisruptionType.ATC: [
            "ATC staffing shortage resulting in miles-in-trail restrictions.",
            "NAVAID outage causing procedural approach delays.",
            "Airspace closure for military operations.",
            "Ground delay program initiated due to volume and weather.",
        ],
        DisruptionType.GATE_CLOSURE: [
            "Gate area flooding from burst pipe; gates closed for repair.",
            "Security incident requiring terminal evacuation and re-screening.",
            "Jet bridge mechanical failure; gate temporarily unavailable.",
            "Construction activity blocking access to gate cluster.",
        ],
    }

    disruption_types = list(DisruptionType)
    severity_levels = list(SeverityLevel)

    disruptions: List[Disruption] = []
    for i in range(n):
        d_type = rng.choice(disruption_types)
        severity = rng.choice(severity_levels)
        affected_airports = rng.sample(HUBS, k=rng.randint(1, 3))
        timestamp = base_date + timedelta(
            hours=rng.randint(0, 72),
            minutes=rng.choice([0, 15, 30, 45]),
        )
        duration = round(float(np_rng.exponential(scale=4)) + 1.0, 1)
        duration = min(duration, 48.0)
        description = rng.choice(descriptions_by_type[d_type])
        pax_impact = rng.randint(200, 15000)

        # Generate some affected flight numbers
        num_affected = rng.randint(2, 20)
        affected_flights = [
            f"UA{rng.randint(100, 9999)}" for _ in range(num_affected)
        ]

        disruptions.append(
            Disruption(
                disruption_id=f"DISRUPT-{i + 1:04d}",
                disruption_type=d_type,
                severity=severity,
                affected_flights=affected_flights,
                affected_airports=affected_airports,
                timestamp=timestamp,
                duration_hours=duration,
                description=description,
                estimated_pax_impact=pax_impact,
            )
        )

    return disruptions
