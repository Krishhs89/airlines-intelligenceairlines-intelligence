"""
Disruption Analysis Agent for the United Airlines Multi-Agent System.

Simulates gate closures, weather events, aircraft swaps, calculates
passenger impact, and suggests mitigation strategies.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

import pandas as pd

from agents.base_agent import BaseAgent
from data.store import DataStore
from llm.mock_llm import MockLLM
from mcp.context_store import MCPContextStore
from mcp.protocol import MCPMessage, MCPResponse
from mcp.tool_registry import MCPToolRegistry

logger = logging.getLogger(__name__)


class DisruptionAnalysisAgent(BaseAgent):
    """Specialist agent for disruption simulation and impact analysis.

    Registered tools:
        - simulate_gate_closure
        - simulate_weather_event
        - simulate_aircraft_swap
        - calculate_pax_impact
        - suggest_mitigation
    """

    def __init__(
        self,
        context_store: MCPContextStore,
        tool_registry: MCPToolRegistry,
        llm: MockLLM,
        data_store: DataStore,
    ) -> None:
        super().__init__(
            name="disruption_analysis",
            context_store=context_store,
            tool_registry=tool_registry,
            llm=llm,
            data_store=data_store,
        )

    # ------------------------------------------------------------------ #
    # Tool implementations
    # ------------------------------------------------------------------ #

    def simulate_gate_closure(self, gate_id: str) -> Dict[str, Any]:
        """Find flights affected by a gate closure and suggest reassignments.

        Args:
            gate_id: The gate identifier to close (e.g. C3).

        Returns:
            Dict with affected flights and reassignment suggestions.
        """
        flights_df = self.data_store.flights
        gates_df = self.data_store.gates

        # Find the gate
        gate_mask = gates_df["gate_id"] == gate_id
        if not gate_mask.any():
            return {"error": f"Gate '{gate_id}' not found"}

        gate_info = gates_df.loc[gate_mask].iloc[0]
        airport = gate_info["airport"]
        terminal = gate_info["terminal"]

        # Find flights using this gate at this airport
        affected_mask = (
            (flights_df["gate_id"] == gate_id)
            & (flights_df["origin"] == airport)
            & (flights_df["status"].isin(["On Time", "Delayed"]))
        )
        affected_flights = flights_df.loc[affected_mask]

        # Find available gates at the same airport for reassignment
        available_mask = (
            (gates_df["airport"] == airport)
            & (gates_df["status"] == "Available")
            & (gates_df["gate_id"] != gate_id)
        )
        available_gates = gates_df.loc[available_mask]

        reassignments: List[Dict[str, Any]] = []
        available_list = available_gates["gate_id"].tolist()
        for i, (_, flight) in enumerate(affected_flights.iterrows()):
            suggested_gate = available_list[i % len(available_list)] if available_list else "None available"
            reassignments.append({
                "flight_number": flight["flight_number"],
                "destination": flight["destination"],
                "departure": str(flight["departure"]),
                "suggested_gate": suggested_gate,
            })

        return {
            "closed_gate": gate_id,
            "airport": airport,
            "terminal": terminal,
            "affected_flight_count": len(affected_flights),
            "affected_flights": [f["flight_number"] for _, f in affected_flights.iterrows()],
            "reassignments": reassignments[:20],
            "available_gates_count": len(available_gates),
        }

    def simulate_weather_event(
        self, airport: str, severity: str, duration_hours: float
    ) -> Dict[str, Any]:
        """Simulate a weather event and calculate cascading delay impacts.

        Args:
            airport: Affected airport IATA code.
            severity: Severity level (Low, Medium, High, Critical).
            duration_hours: Expected duration in hours.

        Returns:
            Dict with cascade delay estimates and affected flight counts.
        """
        flights_df = self.data_store.flights

        # Flights originating or arriving at the affected airport
        origin_mask = flights_df["origin"] == airport
        dest_mask = flights_df["destination"] == airport
        affected_mask = origin_mask | dest_mask

        affected_flights = flights_df.loc[affected_mask]
        total_affected = len(affected_flights)

        # Severity multipliers
        severity_config = {
            "Low": {"cancel_pct": 0.0, "delay_pct": 0.2, "avg_delay_min": 30},
            "Medium": {"cancel_pct": 0.05, "delay_pct": 0.4, "avg_delay_min": 60},
            "High": {"cancel_pct": 0.15, "delay_pct": 0.6, "avg_delay_min": 120},
            "Critical": {"cancel_pct": 0.40, "delay_pct": 0.8, "avg_delay_min": 240},
        }
        config = severity_config.get(severity, severity_config["Medium"])

        cancelled_count = int(total_affected * config["cancel_pct"])
        delayed_count = int(total_affected * config["delay_pct"])
        avg_delay = config["avg_delay_min"]

        # Cascade: downstream flights from affected aircraft
        affected_tails = affected_flights["tail_number"].unique().tolist()
        downstream_mask = (
            flights_df["tail_number"].isin(affected_tails)
            & ~affected_mask
        )
        downstream_flights = flights_df.loc[downstream_mask]
        cascade_delayed = int(len(downstream_flights) * config["delay_pct"] * 0.5)
        cascade_avg_delay = int(avg_delay * 0.6)

        # Passenger impact estimate
        affected_on_flights = affected_flights.copy()
        aircraft_df = self.data_store.aircraft
        cap_map = aircraft_df.drop_duplicates("aircraft_type").set_index("aircraft_type")["capacity"].to_dict()
        pax_impact = 0
        for _, f in affected_on_flights.iterrows():
            cap = cap_map.get(f["aircraft_type"], 178)
            pax_impact += int(f["load_factor"] * cap)

        return {
            "airport": airport,
            "severity": severity,
            "duration_hours": duration_hours,
            "total_flights_affected": total_affected,
            "flights_cancelled": cancelled_count,
            "flights_delayed": delayed_count,
            "average_delay_minutes": avg_delay,
            "cascade_flights_affected": len(downstream_flights),
            "cascade_delayed": cascade_delayed,
            "cascade_avg_delay_minutes": cascade_avg_delay,
            "estimated_pax_impact": pax_impact,
            "affected_flight_numbers": affected_flights["flight_number"].tolist()[:20],
        }

    def simulate_aircraft_swap(
        self, flight_number: str, new_aircraft_type: str
    ) -> Dict[str, Any]:
        """Check capacity and range feasibility of an aircraft swap.

        Args:
            flight_number: The flight to swap aircraft on.
            new_aircraft_type: The proposed replacement aircraft type.

        Returns:
            Dict with feasibility assessment.
        """
        flights_df = self.data_store.flights
        aircraft_df = self.data_store.aircraft

        flight_mask = flights_df["flight_number"] == flight_number
        if not flight_mask.any():
            return {"error": f"Flight '{flight_number}' not found"}

        flight = flights_df.loc[flight_mask].iloc[0]
        origin = flight["origin"]
        destination = flight["destination"]
        current_type = flight["aircraft_type"]
        load_factor = float(flight["load_factor"])

        # Current aircraft specs
        curr_ac = aircraft_df.loc[aircraft_df["aircraft_type"] == current_type]
        if curr_ac.empty:
            current_capacity = 178
        else:
            current_capacity = int(curr_ac.iloc[0]["capacity"])

        current_pax = int(load_factor * current_capacity)

        # New aircraft specs
        new_ac = aircraft_df.loc[aircraft_df["aircraft_type"] == new_aircraft_type]
        if new_ac.empty:
            return {"error": f"Aircraft type '{new_aircraft_type}' not found in fleet"}

        new_capacity = int(new_ac.iloc[0]["capacity"])
        new_range = int(new_ac.iloc[0]["range_nm"])

        # Route distance
        from agents.network_planning import _great_circle_nm
        distance = _great_circle_nm(origin, destination)

        # Feasibility checks
        range_ok = new_range >= distance * 1.1
        capacity_ok = new_capacity >= current_pax
        new_load_factor = round(current_pax / new_capacity, 3) if new_capacity > 0 else 1.0

        # Available aircraft of new type
        available_mask = (
            (aircraft_df["aircraft_type"] == new_aircraft_type)
            & (aircraft_df["status"] == "Active")
        )
        available_count = int(available_mask.sum())

        feasible = range_ok and capacity_ok and available_count > 0

        issues: List[str] = []
        if not range_ok:
            issues.append(
                f"Insufficient range: {new_range} NM < {round(distance * 1.1)} NM required"
            )
        if not capacity_ok:
            issues.append(
                f"Insufficient capacity: {new_capacity} seats < {current_pax} passengers booked"
            )
        if available_count == 0:
            issues.append("No available aircraft of this type")

        return {
            "flight_number": flight_number,
            "origin": origin,
            "destination": destination,
            "distance_nm": distance,
            "current_aircraft": current_type,
            "current_capacity": current_capacity,
            "current_pax": current_pax,
            "new_aircraft_type": new_aircraft_type,
            "new_capacity": new_capacity,
            "new_range_nm": new_range,
            "new_load_factor": new_load_factor,
            "feasible": feasible,
            "issues": issues,
            "available_count": available_count,
        }

    def calculate_pax_impact(self, affected_flights: List[str]) -> Dict[str, Any]:
        """Sum load_factor * capacity across affected flights.

        Args:
            affected_flights: List of flight numbers to assess.

        Returns:
            Dict with total passenger impact and per-flight breakdown.
        """
        flights_df = self.data_store.flights
        aircraft_df = self.data_store.aircraft

        cap_map = (
            aircraft_df.drop_duplicates("aircraft_type")
            .set_index("aircraft_type")["capacity"]
            .to_dict()
        )

        mask = flights_df["flight_number"].isin(affected_flights)
        matched = flights_df.loc[mask]

        total_pax = 0
        breakdown: List[Dict[str, Any]] = []
        for _, f in matched.iterrows():
            cap = cap_map.get(f["aircraft_type"], 178)
            pax = int(f["load_factor"] * cap)
            total_pax += pax
            breakdown.append({
                "flight_number": f["flight_number"],
                "origin": f["origin"],
                "destination": f["destination"],
                "aircraft_type": f["aircraft_type"],
                "capacity": cap,
                "load_factor": float(f["load_factor"]),
                "estimated_pax": pax,
            })

        return {
            "total_pax_impact": total_pax,
            "flights_matched": len(matched),
            "flights_requested": len(affected_flights),
            "breakdown": breakdown[:30],
        }

    def suggest_mitigation(
        self,
        disruption_type: str,
        severity: str,
        affected_flights: List[str],
    ) -> Dict[str, Any]:
        """Suggest rule-based mitigation strategies for a disruption.

        Args:
            disruption_type: Category (Weather, Mechanical, ATC, Gate Closure).
            severity: Severity level (Low, Medium, High, Critical).
            affected_flights: List of affected flight numbers.

        Returns:
            Dict with prioritised mitigation actions.
        """
        strategies: List[Dict[str, Any]] = []

        # Universal actions
        strategies.append({
            "priority": 1,
            "action": "Activate IROPS protocol and notify operations center",
            "category": "Operations",
        })

        if severity in ("Critical", "High"):
            strategies.append({
                "priority": 1,
                "action": "Open mass rebooking channels for all affected passengers",
                "category": "Passenger Services",
            })
            strategies.append({
                "priority": 2,
                "action": "Coordinate with crew scheduling for reserve crew activation",
                "category": "Crew Management",
            })

        if disruption_type == "Weather":
            strategies.append({
                "priority": 2,
                "action": "Monitor weather progression and adjust ground stop timing",
                "category": "Operations",
            })
            if severity in ("Critical", "High"):
                strategies.append({
                    "priority": 1,
                    "action": "Evaluate diversion airports and fuel requirements",
                    "category": "Flight Operations",
                })
                strategies.append({
                    "priority": 3,
                    "action": "Pre-position de-icing equipment for recovery operations",
                    "category": "Ground Operations",
                })

        elif disruption_type == "Mechanical":
            strategies.append({
                "priority": 1,
                "action": "Source replacement aircraft from active fleet or wet lease",
                "category": "Fleet Management",
            })
            strategies.append({
                "priority": 2,
                "action": "Evaluate maintenance ferry flight if aircraft must relocate",
                "category": "Maintenance",
            })

        elif disruption_type == "Gate Closure":
            strategies.append({
                "priority": 1,
                "action": "Reassign affected flights to available gates in same terminal",
                "category": "Ground Operations",
            })
            strategies.append({
                "priority": 2,
                "action": "Coordinate busing for remote stand operations if needed",
                "category": "Passenger Services",
            })

        elif disruption_type == "ATC":
            strategies.append({
                "priority": 2,
                "action": "File alternate routing flight plans to avoid restricted airspace",
                "category": "Flight Operations",
            })
            strategies.append({
                "priority": 3,
                "action": "Adjust departure sequencing to minimize ground hold times",
                "category": "Operations",
            })

        # Passenger communication is always needed
        strategies.append({
            "priority": 2,
            "action": "Push passenger notifications with rebooking options and meal vouchers",
            "category": "Passenger Services",
        })

        if len(affected_flights) > 10:
            strategies.append({
                "priority": 3,
                "action": "Open dedicated customer service hotline for high-volume disruption",
                "category": "Passenger Services",
            })

        strategies.sort(key=lambda s: s["priority"])

        return {
            "disruption_type": disruption_type,
            "severity": severity,
            "affected_flight_count": len(affected_flights),
            "strategies": strategies,
            "total_strategies": len(strategies),
        }

    # ------------------------------------------------------------------ #
    # Tool registration
    # ------------------------------------------------------------------ #

    def register_tools(self) -> None:
        """Register all disruption analysis tools with the tool registry."""
        tools = [
            ("simulate_gate_closure", self.simulate_gate_closure,
             "Simulate gate closure and find affected flights with reassignments.",
             ["disruption_impact"]),
            ("simulate_weather_event", self.simulate_weather_event,
             "Simulate a weather event with cascade delay calculation.",
             ["disruption_impact"]),
            ("simulate_aircraft_swap", self.simulate_aircraft_swap,
             "Check capacity and range feasibility of an aircraft swap.",
             ["disruption_impact"]),
            ("calculate_pax_impact", self.calculate_pax_impact,
             "Calculate total passenger impact across affected flights.",
             ["disruption_impact"]),
            ("suggest_mitigation", self.suggest_mitigation,
             "Suggest rule-based mitigation strategies for a disruption.",
             ["disruption_impact"]),
        ]
        for name, fn, desc, intents in tools:
            self.tool_registry.register(
                name=name, fn=fn, agent=self.name,
                description=desc, intents=intents,
            )

    # ------------------------------------------------------------------ #
    # Message handling
    # ------------------------------------------------------------------ #

    def handle(self, message: MCPMessage) -> MCPResponse:
        """Process a disruption analysis query.

        Parses scenario parameters, runs simulation tools, calculates
        cascading impacts, and generates insight text.

        Args:
            message: Inbound MCPMessage.

        Returns:
            MCPResponse with structured results and insight.
        """
        self._log_trace(message, "received")
        query = message.payload.get("query", "").lower()
        payload = message.payload
        tool_calls: List[str] = []
        result: Dict[str, Any] = {}

        if "gate" in query and ("clos" in query or "shut" in query):
            # Extract gate_id from payload or query
            gate_id = payload.get("gate_id", "")
            if not gate_id:
                gate_match = re.search(r"\b([A-Z]\d+)\b", payload.get("query", ""))
                gate_id = gate_match.group(1) if gate_match else "C3"

            self._log_trace(message, f"tool:simulate_gate_closure({gate_id})")
            result = self._call_tool("simulate_gate_closure", gate_id=gate_id)
            tool_calls.append("simulate_gate_closure")

            # Also compute pax impact
            if result.get("affected_flights"):
                self._log_trace(message, "tool:calculate_pax_impact")
                pax = self._call_tool(
                    "calculate_pax_impact",
                    affected_flights=result["affected_flights"],
                )
                result["pax_impact"] = pax
                tool_calls.append("calculate_pax_impact")

            # Suggest mitigation
            self._log_trace(message, "tool:suggest_mitigation")
            mitigation = self._call_tool(
                "suggest_mitigation",
                disruption_type="Gate Closure",
                severity=payload.get("severity", "High"),
                affected_flights=result.get("affected_flights", []),
            )
            result["mitigation"] = mitigation
            tool_calls.append("suggest_mitigation")

        elif "weather" in query or "storm" in query or "snow" in query:
            airport = payload.get("airport", "")
            if not airport:
                airport_match = re.search(r"\b([A-Z]{3})\b", payload.get("query", ""))
                airport = airport_match.group(1) if airport_match else "ORD"
            severity = payload.get("severity", "High")
            duration = payload.get("duration_hours", 4.0)

            self._log_trace(message, f"tool:simulate_weather_event({airport})")
            result = self._call_tool(
                "simulate_weather_event",
                airport=airport, severity=severity, duration_hours=duration,
            )
            tool_calls.append("simulate_weather_event")

            # Suggest mitigation
            self._log_trace(message, "tool:suggest_mitigation")
            mitigation = self._call_tool(
                "suggest_mitigation",
                disruption_type="Weather",
                severity=severity,
                affected_flights=result.get("affected_flight_numbers", []),
            )
            result["mitigation"] = mitigation
            tool_calls.append("suggest_mitigation")

        elif "swap" in query or "replace" in query or "substitute" in query:
            flight_number = payload.get("flight_number", "")
            new_type = payload.get("new_aircraft_type", "")
            if not flight_number:
                fn_match = re.search(r"\b(UA\d+)\b", payload.get("query", ""), re.IGNORECASE)
                flight_number = fn_match.group(1).upper() if fn_match else ""
            if not new_type:
                type_match = re.search(
                    r"\b(B737-MAX9|B787-9|B777-200|A319)\b",
                    payload.get("query", ""), re.IGNORECASE,
                )
                new_type = type_match.group(1) if type_match else "B787-9"

            if flight_number:
                self._log_trace(message, f"tool:simulate_aircraft_swap({flight_number})")
                result = self._call_tool(
                    "simulate_aircraft_swap",
                    flight_number=flight_number,
                    new_aircraft_type=new_type,
                )
                tool_calls.append("simulate_aircraft_swap")
            else:
                result = {"error": "Could not identify flight number for swap simulation"}

        elif "impact" in query or "passenger" in query or "pax" in query:
            affected = payload.get("affected_flights", [])
            if not affected:
                # Use disruptions data to find some affected flights
                disrupt_df = self.data_store.disruptions
                if not disrupt_df.empty:
                    affected = disrupt_df.iloc[0]["affected_flights"][:10]

            self._log_trace(message, "tool:calculate_pax_impact")
            result = self._call_tool("calculate_pax_impact", affected_flights=affected)
            tool_calls.append("calculate_pax_impact")

        else:
            # Default: run weather simulation on busiest hub
            hub_counts = self.data_store.flights["origin"].value_counts()
            busiest = hub_counts.index[0] if not hub_counts.empty else "ORD"
            severity = payload.get("severity", "Medium")
            duration = payload.get("duration_hours", 3.0)

            self._log_trace(message, f"tool:simulate_weather_event({busiest})")
            result = self._call_tool(
                "simulate_weather_event",
                airport=busiest, severity=severity, duration_hours=duration,
            )
            tool_calls.append("simulate_weather_event")

            self._log_trace(message, "tool:suggest_mitigation")
            mitigation = self._call_tool(
                "suggest_mitigation",
                disruption_type="Weather",
                severity=severity,
                affected_flights=result.get("affected_flight_numbers", []),
            )
            result["mitigation"] = mitigation
            tool_calls.append("suggest_mitigation")

        # Generate insight via LLM
        try:
            insight = self.llm.generate("disruption_impact", {
                "disruption_type": result.get("disruption_type", payload.get("disruption_type", "Weather")),
                "severity": result.get("severity", payload.get("severity", "Medium")),
                "affected_airports": result.get("airport", "N/A"),
                "duration_hours": result.get("duration_hours", 0),
                "estimated_pax_impact": result.get("estimated_pax_impact", result.get("total_pax_impact", 0)),
            })
        except Exception as exc:
            logger.warning("LLM generation failed: %s", exc)
            insight = f"Disruption analysis complete. {len(tool_calls)} tool(s) invoked."

        confidence = 0.80 if "error" not in result else 0.3
        self._store_result(f"disruption_analysis:{message.message_id}", result)
        self._log_trace(message, "complete")

        return self._build_response(message, result, insight, confidence, tool_calls)
