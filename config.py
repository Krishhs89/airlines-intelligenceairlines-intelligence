"""
Global configuration constants for the United Airlines Network Planning System.

Contains hub definitions, airport coordinates, scenario presets, and LLM settings.
"""

from typing import Dict, List, Tuple

# --------------------------------------------------------------------------- #
# Hub airports
# --------------------------------------------------------------------------- #
HUBS: List[str] = ["ORD", "IAH", "DEN", "EWR", "LAX", "SFO", "DCA", "LAS"]

# --------------------------------------------------------------------------- #
# Airport coordinates (lat, lon) for map plotting
# --------------------------------------------------------------------------- #
AIRPORT_COORDS: Dict[str, Tuple[float, float]] = {
    "ORD": (41.9742, -87.9073),   # Chicago O'Hare
    "IAH": (29.9902, -95.3368),   # Houston Intercontinental
    "DEN": (39.8561, -104.6737),  # Denver International
    "EWR": (40.6895, -74.1745),   # Newark Liberty
    "LAX": (33.9416, -118.4085),  # Los Angeles International
    "SFO": (37.6213, -122.3790),  # San Francisco International
    "DCA": (38.8512, -77.0402),   # Ronald Reagan Washington
    "LAS": (36.0840, -115.1537),  # Las Vegas Harry Reid
    # Supplementary spoke airports used in synthetic routes
    "ATL": (33.6407, -84.4277),
    "DFW": (32.8998, -97.0403),
    "JFK": (40.6413, -73.7781),
    "SEA": (47.4502, -122.3088),
    "MIA": (25.7959, -80.2870),
    "BOS": (42.3656, -71.0096),
    "PHX": (33.4373, -112.0078),
    "MSP": (44.8848, -93.2223),
    "DTW": (42.2124, -83.3534),
    "FLL": (26.0742, -80.1506),
    "MCO": (28.4312, -81.3081),
    "CLE": (41.4058, -81.8539),
    "HNL": (21.3187, -157.9225),
    "ANC": (61.1743, -149.9982),
}

# --------------------------------------------------------------------------- #
# UTC offsets (approximate, standard time) for departure / arrival realism
# --------------------------------------------------------------------------- #
AIRPORT_UTC_OFFSETS: Dict[str, int] = {
    "ORD": -6, "IAH": -6, "DEN": -7, "EWR": -5, "LAX": -8,
    "SFO": -8, "DCA": -5, "LAS": -8, "ATL": -5, "DFW": -6,
    "JFK": -5, "SEA": -8, "MIA": -5, "BOS": -5, "PHX": -7,
    "MSP": -6, "DTW": -5, "FLL": -5, "MCO": -5, "CLE": -5,
    "HNL": -10, "ANC": -9,
}

# --------------------------------------------------------------------------- #
# Scenario presets for disruption simulations
# --------------------------------------------------------------------------- #
SCENARIO_PRESETS: Dict[str, Dict] = {
    "ORD Winter Storm": {
        "disruption_type": "Weather",
        "severity": "Critical",
        "affected_airports": ["ORD"],
        "duration_hours": 8,
        "description": (
            "Major winter storm impacting Chicago O'Hare with heavy snowfall, "
            "freezing rain, and 40-knot crosswinds. Runway operations reduced to "
            "single-runway configuration. Ground stop in effect."
        ),
        "estimated_pax_impact": 12000,
    },
    "Gate C Closure": {
        "disruption_type": "Gate Closure",
        "severity": "High",
        "affected_airports": ["EWR"],
        "duration_hours": 6,
        "description": (
            "Emergency closure of Terminal C gates C70-C90 at Newark Liberty due "
            "to water main break. Twenty gates unavailable; flights must be "
            "reassigned to remaining gates or delayed."
        ),
        "estimated_pax_impact": 4500,
    },
    "Fleet Grounding B737": {
        "disruption_type": "Mechanical",
        "severity": "Critical",
        "affected_airports": HUBS,
        "duration_hours": 48,
        "description": (
            "FAA Emergency Airworthiness Directive requires immediate inspection "
            "of all B737-MAX9 aircraft following cabin pressure incident. Fleet "
            "grounded until inspections are complete."
        ),
        "estimated_pax_impact": 28000,
    },
}

# --------------------------------------------------------------------------- #
# LLM configuration
# --------------------------------------------------------------------------- #
USE_MOCK_LLM: bool = True
BEDROCK_MODEL_ID: str = "anthropic.claude-3-sonnet-20240229-v1:0"
BEDROCK_REGION: str = "us-east-1"

# --------------------------------------------------------------------------- #
# Application defaults
# --------------------------------------------------------------------------- #
RANDOM_SEED: int = 42
DEFAULT_FLIGHT_COUNT: int = 200
DEFAULT_AIRCRAFT_COUNT: int = 80
DEFAULT_DISRUPTION_COUNT: int = 10
