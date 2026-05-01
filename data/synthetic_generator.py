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
    """Generate *n* realistic United Airlines flights between hub airports.

    Distribution of statuses:
        80 % On Time, 12 % Delayed, 5 % Cancelled, 3 % Diverted

    Args:
        n: Number of flights to generate.
        seed: Random seed for reproducibility.

    Returns:
        List of Flight model instances.
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

    status_choices = [
        FlightStatus.ON_TIME,
        FlightStatus.DELAYED,
        FlightStatus.CANCELLED,
        FlightStatus.DIVERTED,
    ]
    status_weights = [0.80, 0.12, 0.05, 0.03]

    aircraft_types = list(AircraftType)
    type_weights = [0.40, 0.25, 0.15, 0.20]  # B737 most common

    # Base date for schedule
    base_date = datetime(2026, 5, 1)

    flights: List[Flight] = []
    used_flight_numbers: set[str] = set()

    for i in range(n):
        # Pick origin / destination (prefer hub-to-hub)
        origin = rng.choice(HUBS)
        dest_choices = [h for h in HUBS if h != origin]
        destination = rng.choice(dest_choices)

        # Flight number
        while True:
            fn = f"UA{rng.randint(100, 9999)}"
            if fn not in used_flight_numbers:
                used_flight_numbers.add(fn)
                break

        # Aircraft type
        ac_type = rng.choices(aircraft_types, weights=type_weights, k=1)[0]
        tails = tail_map.get(ac_type, ["N00000"])
        tail = rng.choice(tails)

        # Departure time: spread across 3 days, 05:00-23:00 local
        day_offset = rng.randint(0, 2)
        local_hour = rng.randint(5, 22)
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

        # Gate
        gate_id = None
        if origin in gate_ids_by_airport:
            gate_id = rng.choice(gate_ids_by_airport[origin])

        # Status & delay
        status = rng.choices(status_choices, weights=status_weights, k=1)[0]
        delay_minutes = 0
        if status == FlightStatus.DELAYED:
            delay_minutes = int(np_rng.exponential(scale=45)) + 15
            delay_minutes = min(delay_minutes, 360)
        elif status == FlightStatus.DIVERTED:
            delay_minutes = rng.randint(60, 240)

        # Load factor
        load_factor = round(
            float(np_rng.beta(a=5, b=2) * 0.43 + 0.55), 2
        )
        load_factor = min(load_factor, 0.98)

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
    """Generate all meaningful hub-pair route combinations (~28 routes).

    Each route receives realistic demand scores, revenue indices, competition
    levels, and seasonal peaks.

    Args:
        seed: Random seed for reproducibility.

    Returns:
        List of Route model instances.
    """
    rng = random.Random(seed)
    np_rng = np.random.default_rng(seed)

    competition_options = ["Low", "Medium", "High"]
    season_options = [None, "Summer", "Winter", "Holiday", "Spring Break"]

    routes: List[Route] = []
    for origin, destination in combinations(HUBS, 2):
        route_id = f"{origin}-{destination}"
        frequency = rng.choice([7, 14, 21, 28, 35, 42])
        demand = round(float(np_rng.beta(a=3, b=2)), 2)
        revenue = round(float(np_rng.lognormal(mean=0.0, sigma=0.3)), 2)
        competition = rng.choice(competition_options)
        seasonal = rng.choice(season_options)

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
