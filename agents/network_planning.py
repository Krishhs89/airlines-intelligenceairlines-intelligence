"""
Network Planning Agent for the United Airlines Multi-Agent System.

Handles route analysis, schedule conflict detection, frequency recommendations,
underperforming route identification, and aircraft assignment optimization.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any, Dict, List, Optional

import pandas as pd

from agents.base_agent import BaseAgent
from config import AIRPORT_COORDS
from data.store import DataStore
from llm.mock_llm import MockLLM
from mcp.context_store import MCPContextStore
from mcp.protocol import MCPMessage, MCPResponse
from mcp.tool_registry import MCPToolRegistry

logger = logging.getLogger(__name__)


def _great_circle_nm(origin: str, destination: str) -> float:
    """Compute approximate great-circle distance in nautical miles."""
    lat1, lon1 = AIRPORT_COORDS.get(origin, (40.0, -100.0))
    lat2, lon2 = AIRPORT_COORDS.get(destination, (40.0, -100.0))
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    nm = c * 3440.065  # Earth radius in NM
    return round(nm, 1)


class NetworkPlanningAgent(BaseAgent):
    """Specialist agent for network planning, route analysis, and fleet decisions.

    Registered tools:
        - get_route_demand
        - get_schedule_conflicts
        - suggest_frequency_change
        - get_underperforming_routes
        - optimize_aircraft_assignment
    """

    def __init__(
        self,
        context_store: MCPContextStore,
        tool_registry: MCPToolRegistry,
        llm: MockLLM,
        data_store: DataStore,
    ) -> None:
        super().__init__(
            name="network_planning",
            context_store=context_store,
            tool_registry=tool_registry,
            llm=llm,
            data_store=data_store,
        )

    # ------------------------------------------------------------------ #
    # Tool implementations
    # ------------------------------------------------------------------ #

    def get_route_demand(self, origin: str, dest: str) -> Dict[str, Any]:
        """Look up route demand, revenue, and competition from DataStore.

        Args:
            origin: Origin IATA code.
            dest: Destination IATA code.

        Returns:
            Dict with route metrics or an error message.
        """
        routes_df = self.data_store.routes
        flights_df = self.data_store.flights

        # Try both directions
        mask = (
            ((routes_df["origin"] == origin) & (routes_df["destination"] == dest))
            | ((routes_df["origin"] == dest) & (routes_df["destination"] == origin))
        )
        route_rows = routes_df.loc[mask]

        if route_rows.empty:
            return {"error": f"No route found for {origin}-{dest}"}

        route = route_rows.iloc[0]

        # Compute actual flight stats for this route pair
        flight_mask = (
            ((flights_df["origin"] == origin) & (flights_df["destination"] == dest))
            | ((flights_df["origin"] == dest) & (flights_df["destination"] == origin))
        )
        route_flights = flights_df.loc[flight_mask]
        avg_load = round(float(route_flights["load_factor"].mean()), 3) if not route_flights.empty else 0.0
        flight_count = len(route_flights)
        on_time_count = int((route_flights["status"] == "On Time").sum()) if not route_flights.empty else 0
        otp = round(on_time_count / flight_count, 3) if flight_count > 0 else 0.0

        return {
            "route_id": route["route_id"],
            "origin": route["origin"],
            "destination": route["destination"],
            "demand_score": float(route["demand_score"]),
            "revenue_index": float(route["revenue_index"]),
            "competition_level": route["competition_level"],
            "frequency_weekly": int(route["frequency_weekly"]),
            "seasonal_peak": route["seasonal_peak"],
            "avg_load_factor": avg_load,
            "flight_count": flight_count,
            "on_time_performance": otp,
            "distance_nm": _great_circle_nm(origin, dest),
        }

    def get_schedule_conflicts(self) -> Dict[str, Any]:
        """Find flights with overlapping gates at the same airport and time.

        Returns:
            Dict with list of conflicts and count.
        """
        flights_df = self.data_store.flights.copy()
        # Only consider flights with assigned gates
        gated = flights_df.dropna(subset=["gate_id"]).copy()
        if gated.empty:
            return {"conflicts": [], "conflict_count": 0}

        # Need to match on origin airport + gate_id + overlapping time
        # A conflict: two flights share same origin + gate_id and their
        # departure windows overlap (within 45 minutes of each other)
        gated = gated.sort_values(["origin", "gate_id", "departure"])
        conflicts: List[Dict[str, Any]] = []

        for (airport, gate), group in gated.groupby(["origin", "gate_id"]):
            if len(group) < 2:
                continue
            departures = group["departure"].values
            flight_nums = group["flight_number"].values
            for i in range(len(departures) - 1):
                diff_minutes = (departures[i + 1] - departures[i]) / pd.Timedelta(minutes=1)
                if diff_minutes < 45:
                    conflicts.append({
                        "airport": airport,
                        "gate_id": gate,
                        "flight_1": flight_nums[i],
                        "flight_2": flight_nums[i + 1],
                        "time_gap_minutes": round(float(diff_minutes), 1),
                    })

        return {
            "conflicts": conflicts[:20],  # cap output
            "conflict_count": len(conflicts),
        }

    def suggest_frequency_change(self, route_id: str) -> Dict[str, Any]:
        """Rule-based frequency recommendation for a route.

        Rules:
            - demand > 0.75 and avg load > 0.85 -> increase frequency
            - avg load < 0.5 -> decrease frequency
            - otherwise -> maintain

        Args:
            route_id: Route identifier (e.g. ORD-LAX).

        Returns:
            Dict with recommendation and supporting metrics.
        """
        routes_df = self.data_store.routes
        flights_df = self.data_store.flights

        mask = routes_df["route_id"] == route_id
        if not mask.any():
            return {"error": f"Route '{route_id}' not found"}

        route = routes_df.loc[mask].iloc[0]
        origin, dest = route["origin"], route["destination"]

        flight_mask = (
            ((flights_df["origin"] == origin) & (flights_df["destination"] == dest))
            | ((flights_df["origin"] == dest) & (flights_df["destination"] == origin))
        )
        route_flights = flights_df.loc[flight_mask]
        avg_load = float(route_flights["load_factor"].mean()) if not route_flights.empty else 0.0
        demand = float(route["demand_score"])
        current_freq = int(route["frequency_weekly"])

        if demand > 0.75 and avg_load > 0.85:
            recommendation = "INCREASE"
            suggested_freq = min(current_freq + 7, 63)
            rationale = (
                f"High demand ({demand:.2f}) and high load factor ({avg_load:.2f}) "
                f"indicate unmet passenger demand. Adding frequencies will capture "
                f"additional revenue."
            )
        elif avg_load < 0.5:
            recommendation = "DECREASE"
            suggested_freq = max(current_freq - 7, 7)
            rationale = (
                f"Low load factor ({avg_load:.2f}) suggests overcapacity on this "
                f"route. Reducing frequency will improve unit economics."
            )
        else:
            recommendation = "MAINTAIN"
            suggested_freq = current_freq
            rationale = (
                f"Demand ({demand:.2f}) and load factor ({avg_load:.2f}) are within "
                f"acceptable ranges. Current frequency is appropriate."
            )

        return {
            "route_id": route_id,
            "current_frequency": current_freq,
            "recommendation": recommendation,
            "suggested_frequency": suggested_freq,
            "demand_score": round(demand, 2),
            "avg_load_factor": round(avg_load, 3),
            "competition_level": route["competition_level"],
            "rationale": rationale,
        }

    def get_underperforming_routes(self) -> Dict[str, Any]:
        """Identify routes with demand < 0.30 or average load factor < 0.6.

        Returns:
            Dict with list of underperforming routes and count.
        """
        routes_df = self.data_store.routes
        flights_df = self.data_store.flights

        underperforming: List[Dict[str, Any]] = []

        for _, route in routes_df.iterrows():
            origin, dest = route["origin"], route["destination"]
            flight_mask = (
                ((flights_df["origin"] == origin) & (flights_df["destination"] == dest))
                | ((flights_df["origin"] == dest) & (flights_df["destination"] == origin))
            )
            route_flights = flights_df.loc[flight_mask]
            avg_load = float(route_flights["load_factor"].mean()) if not route_flights.empty else 0.0
            demand = float(route["demand_score"])

            reasons: List[str] = []
            if demand < 0.30:
                reasons.append(f"low demand ({demand:.2f})")
            if avg_load < 0.6:
                reasons.append(f"low load factor ({avg_load:.2f})")

            if reasons:
                underperforming.append({
                    "route_id": route["route_id"],
                    "origin": origin,
                    "destination": dest,
                    "demand_score": round(demand, 2),
                    "avg_load_factor": round(avg_load, 3),
                    "revenue_index": float(route["revenue_index"]),
                    "frequency_weekly": int(route["frequency_weekly"]),
                    "reasons": reasons,
                })

        return {
            "underperforming_routes": underperforming,
            "total_underperforming": len(underperforming),
            "total_routes": len(routes_df),
        }

    def optimize_aircraft_assignment(self, route_id: str) -> Dict[str, Any]:
        """Match aircraft range and capacity to route distance and demand.

        Args:
            route_id: Route identifier (e.g. ORD-LAX).

        Returns:
            Dict with current and recommended aircraft assignment.
        """
        routes_df = self.data_store.routes
        flights_df = self.data_store.flights
        aircraft_df = self.data_store.aircraft

        mask = routes_df["route_id"] == route_id
        if not mask.any():
            return {"error": f"Route '{route_id}' not found"}

        route = routes_df.loc[mask].iloc[0]
        origin, dest = route["origin"], route["destination"]
        distance_nm = _great_circle_nm(origin, dest)
        demand = float(route["demand_score"])

        # Estimate required capacity from demand
        # Higher demand -> need more seats
        if demand >= 0.7:
            min_capacity = 200
        elif demand >= 0.4:
            min_capacity = 150
        else:
            min_capacity = 100

        # Current assignment: what aircraft types fly this route?
        flight_mask = (
            ((flights_df["origin"] == origin) & (flights_df["destination"] == dest))
            | ((flights_df["origin"] == dest) & (flights_df["destination"] == origin))
        )
        route_flights = flights_df.loc[flight_mask]
        current_types = route_flights["aircraft_type"].value_counts().to_dict() if not route_flights.empty else {}

        # Find best-fit aircraft type
        # Must have range > distance (with 10% buffer) and capacity >= min_capacity
        required_range = distance_nm * 1.1
        candidates: List[Dict[str, Any]] = []
        for ac_type in aircraft_df["aircraft_type"].unique():
            ac_info = aircraft_df.loc[aircraft_df["aircraft_type"] == ac_type].iloc[0]
            capacity = int(ac_info["capacity"])
            range_nm = int(ac_info["range_nm"])
            if range_nm >= required_range:
                score = 0.0
                # Prefer aircraft whose capacity closely matches need (not too big, not too small)
                if capacity >= min_capacity:
                    score = 1.0 / (1.0 + abs(capacity - min_capacity) / 100.0)
                candidates.append({
                    "aircraft_type": ac_type,
                    "capacity": capacity,
                    "range_nm": range_nm,
                    "fit_score": round(score, 3),
                })

        candidates.sort(key=lambda c: c["fit_score"], reverse=True)
        recommended = candidates[0]["aircraft_type"] if candidates else "No suitable aircraft"

        # Count available aircraft of recommended type
        available_count = 0
        if candidates:
            available_count = int(
                (aircraft_df["aircraft_type"] == recommended)
                & (aircraft_df["status"] == "Active")
            ).sum() if isinstance(recommended, str) else 0
            available_mask = (
                (aircraft_df["aircraft_type"] == recommended)
                & (aircraft_df["status"] == "Active")
            )
            available_count = int(available_mask.sum())

        return {
            "route_id": route_id,
            "distance_nm": distance_nm,
            "demand_score": round(demand, 2),
            "min_capacity_needed": min_capacity,
            "current_aircraft_mix": current_types,
            "recommended_type": recommended,
            "candidates": candidates[:4],
            "available_aircraft": available_count,
        }

    # ------------------------------------------------------------------ #
    # Tool registration
    # ------------------------------------------------------------------ #

    def register_tools(self) -> None:
        """Register all network planning tools with the tool registry."""
        tools = [
            ("get_route_demand", self.get_route_demand,
             "Look up route demand, revenue, and competition metrics.",
             ["route_analysis"]),
            ("get_schedule_conflicts", self.get_schedule_conflicts,
             "Find flights with overlapping gates at the same time.",
             ["schedule_gap"]),
            ("suggest_frequency_change", self.suggest_frequency_change,
             "Rule-based frequency change recommendation for a route.",
             ["route_analysis"]),
            ("get_underperforming_routes", self.get_underperforming_routes,
             "Identify routes with low demand or low load factors.",
             ["route_analysis"]),
            ("optimize_aircraft_assignment", self.optimize_aircraft_assignment,
             "Match aircraft range/capacity to route distance/demand.",
             ["route_analysis"]),
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
        """Process a network planning query.

        Parses the query for route pairs or general schedule questions,
        calls appropriate tools, uses MockLLM to generate insight text,
        and returns an MCPResponse.

        Args:
            message: Inbound MCPMessage.

        Returns:
            MCPResponse with structured results and insight.
        """
        self._log_trace(message, "received")
        query = message.payload.get("query", "").lower()
        tool_calls: List[str] = []
        result: Dict[str, Any] = {}

        # Extract route pair from query (e.g. "ORD-LAX", "ORD to LAX")
        route_match = re.search(
            r"\b([A-Z]{3})\s*[-to]+\s*([A-Z]{3})\b", message.payload.get("query", "")
        )

        if "underperform" in query or "weak" in query or "poor" in query:
            self._log_trace(message, "tool:get_underperforming_routes")
            result = self._call_tool("get_underperforming_routes")
            tool_calls.append("get_underperforming_routes")

        elif "conflict" in query or "overlap" in query or "gate conflict" in query:
            self._log_trace(message, "tool:get_schedule_conflicts")
            result = self._call_tool("get_schedule_conflicts")
            tool_calls.append("get_schedule_conflicts")

        elif ("frequency" in query or "increase" in query or "reduce" in query) and route_match:
            route_id = f"{route_match.group(1)}-{route_match.group(2)}"
            self._log_trace(message, f"tool:suggest_frequency_change({route_id})")
            result = self._call_tool("suggest_frequency_change", route_id=route_id)
            tool_calls.append("suggest_frequency_change")

        elif ("aircraft" in query or "fleet" in query or "assign" in query) and route_match:
            route_id = f"{route_match.group(1)}-{route_match.group(2)}"
            self._log_trace(message, f"tool:optimize_aircraft_assignment({route_id})")
            result = self._call_tool("optimize_aircraft_assignment", route_id=route_id)
            tool_calls.append("optimize_aircraft_assignment")

        elif route_match:
            origin, dest = route_match.group(1), route_match.group(2)
            self._log_trace(message, f"tool:get_route_demand({origin},{dest})")
            result = self._call_tool("get_route_demand", origin=origin, dest=dest)
            tool_calls.append("get_route_demand")

        else:
            # Default: run underperforming routes + schedule conflicts
            self._log_trace(message, "tool:get_underperforming_routes")
            underperf = self._call_tool("get_underperforming_routes")
            tool_calls.append("get_underperforming_routes")

            self._log_trace(message, "tool:get_schedule_conflicts")
            conflicts = self._call_tool("get_schedule_conflicts")
            tool_calls.append("get_schedule_conflicts")

            result = {
                "underperforming": underperf,
                "schedule_conflicts": conflicts,
            }

        # Generate insight text via LLM
        if "error" not in result:
            try:
                if route_match and "route_id" in result:
                    insight = self.llm.generate("route_analysis", {
                        "origin": result.get("origin", route_match.group(1)),
                        "destination": result.get("destination", route_match.group(2)),
                        "demand_score": result.get("demand_score", 0.5),
                        "revenue_index": result.get("revenue_index", 1.0),
                        "competition_level": result.get("competition_level", "Medium"),
                    })
                else:
                    # Build a simple summary for non-route queries
                    insight = self._build_network_summary(result)
            except Exception as exc:
                logger.warning("LLM generation failed: %s", exc)
                insight = f"Network planning analysis complete. {len(tool_calls)} tool(s) invoked."
        else:
            insight = f"Analysis could not be completed: {result.get('error', 'unknown error')}"

        confidence = 0.85 if "error" not in result else 0.3
        self._store_result(f"network_planning:{message.message_id}", result)
        self._log_trace(message, "complete")

        return self._build_response(message, result, insight, confidence, tool_calls)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _build_network_summary(self, result: Dict[str, Any]) -> str:
        """Build a plain-text summary for non-route-specific queries."""
        lines: List[str] = ["Network Planning Analysis", "=" * 40]

        if "underperforming_routes" in result:
            routes_list = result["underperforming_routes"]
            lines.append(
                f"\nUnderperforming Routes: {len(routes_list)} of "
                f"{result.get('total_routes', '?')} total"
            )
            for r in routes_list[:5]:
                lines.append(
                    f"  - {r['route_id']}: demand={r['demand_score']}, "
                    f"load={r['avg_load_factor']}, reasons={', '.join(r['reasons'])}"
                )

        if "underperforming" in result and isinstance(result["underperforming"], dict):
            up = result["underperforming"]
            lines.append(
                f"\nUnderperforming Routes: {up.get('total_underperforming', 0)}"
            )

        if "schedule_conflicts" in result and isinstance(result["schedule_conflicts"], dict):
            sc = result["schedule_conflicts"]
            lines.append(f"Schedule Conflicts: {sc.get('conflict_count', 0)}")

        if "recommendation" in result:
            lines.append(f"\nRecommendation: {result['recommendation']}")
            lines.append(f"Rationale: {result.get('rationale', '')}")

        if "recommended_type" in result:
            lines.append(f"\nRecommended Aircraft: {result['recommended_type']}")
            lines.append(f"Route Distance: {result.get('distance_nm', 0)} NM")

        if "conflicts" in result:
            lines.append(f"\nGate Conflicts Found: {result.get('conflict_count', 0)}")
            for c in result.get("conflicts", [])[:5]:
                lines.append(
                    f"  - {c['airport']} gate {c['gate_id']}: "
                    f"{c['flight_1']} vs {c['flight_2']} "
                    f"({c['time_gap_minutes']} min gap)"
                )

        return "\n".join(lines)
