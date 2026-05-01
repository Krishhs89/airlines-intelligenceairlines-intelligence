"""
Pydantic v2 domain models for the United Airlines Network Planning System.

Defines enumerations and validated data models for flights, routes, aircraft,
gates, and disruptions.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #

class AircraftType(str, Enum):
    """Aircraft types in the United Airlines fleet."""
    B737_MAX9 = "B737-MAX9"
    B787_9 = "B787-9"
    B777_200 = "B777-200"
    A319 = "A319"


class FlightStatus(str, Enum):
    """Possible statuses for a scheduled flight."""
    ON_TIME = "On Time"
    DELAYED = "Delayed"
    CANCELLED = "Cancelled"
    DIVERTED = "Diverted"


class DisruptionType(str, Enum):
    """Categories of operational disruptions."""
    WEATHER = "Weather"
    MECHANICAL = "Mechanical"
    ATC = "ATC"
    GATE_CLOSURE = "Gate Closure"


class SeverityLevel(str, Enum):
    """Disruption severity levels."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


# --------------------------------------------------------------------------- #
# Domain models
# --------------------------------------------------------------------------- #

class Flight(BaseModel):
    """Represents a single scheduled flight."""

    flight_number: str = Field(
        ..., description="IATA flight number, e.g. UA1234"
    )
    origin: str = Field(
        ..., min_length=3, max_length=3, description="Origin IATA airport code"
    )
    destination: str = Field(
        ..., min_length=3, max_length=3, description="Destination IATA airport code"
    )
    departure: datetime = Field(
        ..., description="Scheduled departure time (UTC)"
    )
    arrival: datetime = Field(
        ..., description="Scheduled arrival time (UTC)"
    )
    aircraft_type: AircraftType = Field(
        ..., description="Aircraft type operating this flight"
    )
    tail_number: str = Field(
        ..., description="Aircraft tail number, e.g. N12345"
    )
    gate_id: Optional[str] = Field(
        default=None, description="Assigned gate identifier"
    )
    status: FlightStatus = Field(
        default=FlightStatus.ON_TIME, description="Current flight status"
    )
    delay_minutes: int = Field(
        default=0, ge=0, description="Delay in minutes (0 if on time)"
    )
    load_factor: float = Field(
        default=0.85, ge=0.0, le=1.0,
        description="Passenger load factor (0.0 – 1.0)"
    )

    model_config = {"use_enum_values": True}


class Route(BaseModel):
    """Represents a city-pair route in the network."""

    route_id: str = Field(
        ..., description="Unique route identifier, e.g. ORD-LAX"
    )
    origin: str = Field(
        ..., min_length=3, max_length=3, description="Origin hub code"
    )
    destination: str = Field(
        ..., min_length=3, max_length=3, description="Destination hub code"
    )
    frequency_weekly: int = Field(
        ..., ge=1, description="Number of weekly frequencies"
    )
    demand_score: float = Field(
        ..., ge=0.0, le=1.0, description="Normalised demand score"
    )
    revenue_index: float = Field(
        ..., ge=0.0, description="Revenue performance index (1.0 = average)"
    )
    competition_level: str = Field(
        ..., description="Competition intensity: Low / Medium / High"
    )
    seasonal_peak: Optional[str] = Field(
        default=None,
        description="Peak travel season, e.g. Summer, Winter, Holiday"
    )

    model_config = {"use_enum_values": True}


class Aircraft(BaseModel):
    """Represents an aircraft in the fleet."""

    tail_number: str = Field(
        ..., description="FAA registration / tail number"
    )
    aircraft_type: AircraftType = Field(
        ..., description="Aircraft type designation"
    )
    capacity: int = Field(
        ..., gt=0, description="Maximum passenger capacity"
    )
    range_nm: int = Field(
        ..., gt=0, description="Maximum range in nautical miles"
    )
    status: str = Field(
        default="Active",
        description="Operational status: Active / Maintenance / Grounded"
    )
    hub: str = Field(
        ..., min_length=3, max_length=3, description="Home hub airport code"
    )
    next_maintenance: Optional[datetime] = Field(
        default=None, description="Next scheduled maintenance date"
    )

    model_config = {"use_enum_values": True}


class Gate(BaseModel):
    """Represents an airport gate."""

    gate_id: str = Field(
        ..., description="Gate identifier, e.g. C12"
    )
    terminal: str = Field(
        ..., description="Terminal letter or number"
    )
    airport: str = Field(
        ..., min_length=3, max_length=3, description="Airport IATA code"
    )
    size_category: str = Field(
        ..., description="Gate size: Narrow-body / Wide-body / Regional"
    )
    status: str = Field(
        default="Available",
        description="Gate status: Available / Occupied / Maintenance / Closed"
    )
    current_flight: Optional[str] = Field(
        default=None, description="Flight number currently at this gate"
    )

    model_config = {"use_enum_values": True}


class Disruption(BaseModel):
    """Represents an operational disruption event."""

    disruption_id: str = Field(
        ..., description="Unique disruption identifier"
    )
    disruption_type: DisruptionType = Field(
        ..., description="Category of disruption"
    )
    severity: SeverityLevel = Field(
        ..., description="Severity level"
    )
    affected_flights: List[str] = Field(
        default_factory=list,
        description="List of affected flight numbers"
    )
    affected_airports: List[str] = Field(
        default_factory=list,
        description="List of affected airport codes"
    )
    timestamp: datetime = Field(
        ..., description="Disruption start time (UTC)"
    )
    duration_hours: float = Field(
        ..., gt=0, description="Expected duration in hours"
    )
    description: str = Field(
        ..., description="Human-readable description of the disruption"
    )
    estimated_pax_impact: int = Field(
        default=0, ge=0,
        description="Estimated number of passengers affected"
    )

    model_config = {"use_enum_values": True}
