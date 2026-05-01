"""
DataStore singleton for the United Airlines Network Planning System.

Provides centralised, lazy-initialised access to all synthetic DataFrames.
Thread-safe via a class-level lock.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

import pandas as pd

from config import (
    DEFAULT_AIRCRAFT_COUNT,
    DEFAULT_DISRUPTION_COUNT,
    DEFAULT_FLIGHT_COUNT,
    RANDOM_SEED,
)


class DataStore:
    """Singleton that holds all operational DataFrames.

    Usage::

        store = DataStore.get()
        flights_df = store.flights
        store.apply_disruption("DISRUPT-0001")
        store.reset()
    """

    _instance: Optional["DataStore"] = None
    _lock: threading.Lock = threading.Lock()

    # DataFrames
    flights: pd.DataFrame
    routes: pd.DataFrame
    aircraft: pd.DataFrame
    gates: pd.DataFrame
    disruptions: pd.DataFrame

    def __init__(self) -> None:
        """Private constructor -- use DataStore.get() instead."""
        self._initialise()

    # ------------------------------------------------------------------ #
    # Singleton access
    # ------------------------------------------------------------------ #

    @classmethod
    def get(cls) -> "DataStore":
        """Return the singleton DataStore instance, creating it on first call.

        Returns:
            The shared DataStore instance.
        """
        if cls._instance is None:
            with cls._lock:
                # Double-checked locking
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------ #
    # Initialisation helpers
    # ------------------------------------------------------------------ #

    def _initialise(self) -> None:
        """Generate all synthetic data and store as DataFrames."""
        from data.synthetic_generator import (
            generate_aircraft,
            generate_disruptions,
            generate_flights,
            generate_gates,
            generate_routes,
        )

        self.flights = pd.DataFrame(
            [f.model_dump() for f in generate_flights(DEFAULT_FLIGHT_COUNT)]
        )
        self.routes = pd.DataFrame(
            [r.model_dump() for r in generate_routes()]
        )
        self.aircraft = pd.DataFrame(
            [a.model_dump() for a in generate_aircraft(DEFAULT_AIRCRAFT_COUNT)]
        )
        self.gates = pd.DataFrame(
            [g.model_dump() for g in generate_gates()]
        )
        self.disruptions = pd.DataFrame(
            [d.model_dump() for d in generate_disruptions(DEFAULT_DISRUPTION_COUNT)]
        )

    # ------------------------------------------------------------------ #
    # Public methods
    # ------------------------------------------------------------------ #

    def apply_disruption(self, disruption_id: str) -> Dict[str, Any]:
        """Apply a disruption's effects to the operational data.

        Marks affected flights as Cancelled or Delayed and updates gate
        statuses where applicable.

        Args:
            disruption_id: The ID of the disruption to apply.

        Returns:
            A summary dict with counts of affected entities.

        Raises:
            ValueError: If the disruption_id is not found.
        """
        mask = self.disruptions["disruption_id"] == disruption_id
        if not mask.any():
            raise ValueError(f"Disruption '{disruption_id}' not found.")

        row = self.disruptions.loc[mask].iloc[0]
        affected_flights = row["affected_flights"]
        affected_airports = row["affected_airports"]
        severity = row["severity"]

        # Determine how to affect flights
        flights_cancelled = 0
        flights_delayed = 0

        flight_mask = self.flights["flight_number"].isin(affected_flights)
        for idx in self.flights.loc[flight_mask].index:
            if severity in ("Critical", "High"):
                self.flights.at[idx, "status"] = "Cancelled"
                flights_cancelled += 1
            else:
                self.flights.at[idx, "status"] = "Delayed"
                self.flights.at[idx, "delay_minutes"] = (
                    int(row["duration_hours"] * 60) if severity == "Medium" else 30
                )
                flights_delayed += 1

        # Also affect flights originating from affected airports
        airport_mask = (
            self.flights["origin"].isin(affected_airports)
            & (self.flights["status"] == "On Time")
        )
        delay_count = min(int(airport_mask.sum() * 0.3), 50)
        if delay_count > 0:
            delay_indices = self.flights.loc[airport_mask].head(delay_count).index
            self.flights.loc[delay_indices, "status"] = "Delayed"
            self.flights.loc[delay_indices, "delay_minutes"] = int(
                row["duration_hours"] * 15
            )
            flights_delayed += delay_count

        # Close gates at affected airports if Gate Closure type
        gates_closed = 0
        if row["disruption_type"] == "Gate Closure":
            gate_mask = (
                self.gates["airport"].isin(affected_airports)
                & (self.gates["status"] != "Closed")
            )
            close_count = min(int(gate_mask.sum()), 5)
            if close_count > 0:
                close_indices = self.gates.loc[gate_mask].head(close_count).index
                self.gates.loc[close_indices, "status"] = "Closed"
                gates_closed = close_count

        return {
            "disruption_id": disruption_id,
            "flights_cancelled": flights_cancelled,
            "flights_delayed": flights_delayed,
            "gates_closed": gates_closed,
            "severity": severity,
        }

    def reset(self) -> None:
        """Re-generate all synthetic data, restoring the original state."""
        self._initialise()

    def get_summary_stats(self) -> Dict[str, Any]:
        """Return high-level summary statistics across all data sets.

        Returns:
            Dictionary with counts, rates, and averages.
        """
        total_flights = len(self.flights)
        on_time = (self.flights["status"] == "On Time").sum()
        delayed = (self.flights["status"] == "Delayed").sum()
        cancelled = (self.flights["status"] == "Cancelled").sum()
        diverted = (self.flights["status"] == "Diverted").sum()

        avg_load = self.flights["load_factor"].mean()
        avg_delay = self.flights.loc[
            self.flights["delay_minutes"] > 0, "delay_minutes"
        ].mean()

        return {
            "total_flights": total_flights,
            "on_time_count": int(on_time),
            "delayed_count": int(delayed),
            "cancelled_count": int(cancelled),
            "diverted_count": int(diverted),
            "on_time_rate": round(on_time / total_flights, 3) if total_flights else 0,
            "average_load_factor": round(float(avg_load), 3),
            "average_delay_minutes": round(float(avg_delay), 1) if not pd.isna(avg_delay) else 0.0,
            "total_routes": len(self.routes),
            "total_aircraft": len(self.aircraft),
            "total_gates": len(self.gates),
            "active_disruptions": len(self.disruptions),
            "fleet_by_type": self.aircraft["aircraft_type"].value_counts().to_dict(),
        }
