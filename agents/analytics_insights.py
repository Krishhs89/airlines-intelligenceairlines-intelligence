"""
Analytics & Insights Agent for the United Airlines Multi-Agent System.

Computes on-time performance summaries, load factor trends, anomaly detection,
executive summaries, and route comparisons from the operational DataFrames.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from agents.base_agent import BaseAgent
from data.store import DataStore
from llm.mock_llm import MockLLM
from mcp.context_store import MCPContextStore
from mcp.protocol import MCPMessage, MCPResponse
from mcp.tool_registry import MCPToolRegistry

logger = logging.getLogger(__name__)


class AnalyticsInsightsAgent(BaseAgent):
    """Specialist agent for analytics, trend analysis, and executive reporting.

    Registered tools:
        - compute_otd_summary
        - compute_load_factor_trends
        - flag_anomalies
        - generate_executive_summary
        - compare_routes
    """

    def __init__(
        self,
        context_store: MCPContextStore,
        tool_registry: MCPToolRegistry,
        llm: MockLLM,
        data_store: DataStore,
    ) -> None:
        super().__init__(
            name="analytics_insights",
            context_store=context_store,
            tool_registry=tool_registry,
            llm=llm,
            data_store=data_store,
        )

    # ------------------------------------------------------------------ #
    # Tool implementations
    # ------------------------------------------------------------------ #

    def compute_otd_summary(self) -> Dict[str, Any]:
        """Compute on-time performance percentage by hub and overall.

        Returns:
            Dict with overall OTP and per-hub breakdown.
        """
        flights_df = self.data_store.flights

        total = len(flights_df)
        on_time = int((flights_df["status"] == "On Time").sum())
        overall_otp = round(on_time / total * 100, 1) if total > 0 else 0.0

        # Per-hub OTP (by origin)
        hub_otp: List[Dict[str, Any]] = []
        for hub, group in flights_df.groupby("origin"):
            hub_total = len(group)
            hub_on_time = int((group["status"] == "On Time").sum())
            pct = round(hub_on_time / hub_total * 100, 1) if hub_total > 0 else 0.0
            hub_otp.append({
                "hub": hub,
                "total_flights": hub_total,
                "on_time": hub_on_time,
                "otp_pct": pct,
            })

        hub_otp.sort(key=lambda h: h["otp_pct"], reverse=True)

        # Delay statistics
        delayed_flights = flights_df.loc[flights_df["delay_minutes"] > 0]
        avg_delay = round(float(delayed_flights["delay_minutes"].mean()), 1) if not delayed_flights.empty else 0.0
        max_delay = int(delayed_flights["delay_minutes"].max()) if not delayed_flights.empty else 0

        return {
            "overall_otp_pct": overall_otp,
            "total_flights": total,
            "on_time_count": on_time,
            "delayed_count": int((flights_df["status"] == "Delayed").sum()),
            "cancelled_count": int((flights_df["status"] == "Cancelled").sum()),
            "diverted_count": int((flights_df["status"] == "Diverted").sum()),
            "avg_delay_minutes": avg_delay,
            "max_delay_minutes": max_delay,
            "hub_breakdown": hub_otp,
        }

    def compute_load_factor_trends(self) -> Dict[str, Any]:
        """Compute average load factor by route with high/low flags.

        Returns:
            Dict with route-level load factor data and flags.
        """
        flights_df = self.data_store.flights
        routes_df = self.data_store.routes

        overall_avg = round(float(flights_df["load_factor"].mean()), 3)

        route_trends: List[Dict[str, Any]] = []
        for _, route in routes_df.iterrows():
            origin, dest = route["origin"], route["destination"]
            mask = (
                ((flights_df["origin"] == origin) & (flights_df["destination"] == dest))
                | ((flights_df["origin"] == dest) & (flights_df["destination"] == origin))
            )
            route_flights = flights_df.loc[mask]
            if route_flights.empty:
                avg_lf = 0.0
                flight_count = 0
            else:
                avg_lf = round(float(route_flights["load_factor"].mean()), 3)
                flight_count = len(route_flights)

            flag = "normal"
            if avg_lf >= 0.90:
                flag = "high"
            elif avg_lf < 0.60:
                flag = "low"

            route_trends.append({
                "route_id": route["route_id"],
                "origin": origin,
                "destination": dest,
                "avg_load_factor": avg_lf,
                "flight_count": flight_count,
                "flag": flag,
                "demand_score": float(route["demand_score"]),
            })

        route_trends.sort(key=lambda r: r["avg_load_factor"], reverse=True)

        high_routes = [r for r in route_trends if r["flag"] == "high"]
        low_routes = [r for r in route_trends if r["flag"] == "low"]

        return {
            "overall_avg_load_factor": overall_avg,
            "total_routes_analysed": len(route_trends),
            "high_load_routes": len(high_routes),
            "low_load_routes": len(low_routes),
            "route_trends": route_trends,
        }

    def flag_anomalies(self) -> Dict[str, Any]:
        """Detect flights with load < 0.4 or delay > 120 min and unusual patterns.

        Returns:
            Dict with anomaly list and severity breakdown.
        """
        flights_df = self.data_store.flights

        anomalies: List[Dict[str, Any]] = []

        # Low load anomalies
        low_load_mask = flights_df["load_factor"] < 0.4
        for _, f in flights_df.loc[low_load_mask].iterrows():
            anomalies.append({
                "flight_number": f["flight_number"],
                "type": "low_load_factor",
                "severity": "Medium",
                "value": float(f["load_factor"]),
                "detail": f"{f['origin']}-{f['destination']}, load={f['load_factor']:.2f}",
            })

        # High delay anomalies
        high_delay_mask = flights_df["delay_minutes"] > 120
        for _, f in flights_df.loc[high_delay_mask].iterrows():
            sev = "Critical" if f["delay_minutes"] > 240 else "High"
            anomalies.append({
                "flight_number": f["flight_number"],
                "type": "excessive_delay",
                "severity": sev,
                "value": int(f["delay_minutes"]),
                "detail": f"{f['origin']}-{f['destination']}, delay={f['delay_minutes']}min",
            })

        # Cancelled flights are also noteworthy
        cancelled_mask = flights_df["status"] == "Cancelled"
        for _, f in flights_df.loc[cancelled_mask].iterrows():
            anomalies.append({
                "flight_number": f["flight_number"],
                "type": "cancellation",
                "severity": "High",
                "value": 0,
                "detail": f"{f['origin']}-{f['destination']} cancelled",
            })

        # Hub concentration anomaly: if a hub has > 30% of all delays
        delayed_df = flights_df.loc[flights_df["status"] == "Delayed"]
        if not delayed_df.empty:
            delay_by_hub = delayed_df["origin"].value_counts()
            total_delayed = len(delayed_df)
            for hub, count in delay_by_hub.items():
                if count / total_delayed > 0.30:
                    anomalies.append({
                        "flight_number": "N/A",
                        "type": "hub_delay_concentration",
                        "severity": "High",
                        "value": round(count / total_delayed * 100, 1),
                        "detail": f"{hub} accounts for {count}/{total_delayed} ({round(count/total_delayed*100,1)}%) of all delays",
                    })

        # Severity breakdown
        severity_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        for a in anomalies:
            severity_counts[a["severity"]] = severity_counts.get(a["severity"], 0) + 1

        return {
            "anomaly_count": len(anomalies),
            "severity_breakdown": severity_counts,
            "anomalies": anomalies[:50],
        }

    def generate_executive_summary(self) -> Dict[str, Any]:
        """Aggregate all metrics into a narrative executive summary.

        Returns:
            Dict with summary data and generated narrative text.
        """
        stats = self.data_store.get_summary_stats()
        flights_df = self.data_store.flights
        aircraft_df = self.data_store.aircraft
        routes_df = self.data_store.routes

        active_aircraft = int((aircraft_df["status"] == "Active").sum())
        total_aircraft = len(aircraft_df)
        active_pct = round(active_aircraft / total_aircraft * 100, 1) if total_aircraft > 0 else 0.0

        otp_pct = round(stats["on_time_rate"] * 100, 1)
        avg_load_pct = round(stats["average_load_factor"] * 100, 1)

        # Top performing route by load factor
        route_loads: List[tuple] = []
        for _, route in routes_df.iterrows():
            origin, dest = route["origin"], route["destination"]
            mask = (
                ((flights_df["origin"] == origin) & (flights_df["destination"] == dest))
                | ((flights_df["origin"] == dest) & (flights_df["destination"] == origin))
            )
            rf = flights_df.loc[mask]
            if not rf.empty:
                route_loads.append((route["route_id"], float(rf["load_factor"].mean())))

        route_loads.sort(key=lambda x: x[1], reverse=True)
        top_route = route_loads[0] if route_loads else ("N/A", 0.0)
        bottom_route = route_loads[-1] if route_loads else ("N/A", 0.0)

        highlight_1 = f"Top route {top_route[0]} with {top_route[1]*100:.1f}% avg load factor"
        highlight_2 = f"Lowest route {bottom_route[0]} at {bottom_route[1]*100:.1f}% avg load factor"
        highlight_3 = f"{stats['delayed_count']} delays, avg {stats['average_delay_minutes']} min"

        action_items = (
            f"Review {bottom_route[0]} for frequency reduction; "
            f"monitor {stats['active_disruptions']} active disruptions."
        )

        # Use LLM template
        try:
            narrative = self.llm.generate("executive_summary", {
                "total_aircraft": total_aircraft,
                "active_pct": active_pct,
                "total_routes": stats["total_routes"],
                "total_flights": stats["total_flights"],
                "otp_pct": otp_pct,
                "avg_load": avg_load_pct,
                "disruption_count": stats["active_disruptions"],
                "highlight_1": highlight_1,
                "highlight_2": highlight_2,
                "highlight_3": highlight_3,
                "action_items": action_items,
            })
        except Exception:
            narrative = "Executive summary generation failed."

        summary_data = {
            "total_flights": stats["total_flights"],
            "on_time_rate": stats["on_time_rate"],
            "otp_pct": otp_pct,
            "avg_load_factor": stats["average_load_factor"],
            "avg_load_pct": avg_load_pct,
            "total_routes": stats["total_routes"],
            "total_aircraft": total_aircraft,
            "active_aircraft": active_aircraft,
            "active_pct": active_pct,
            "delayed_count": stats["delayed_count"],
            "cancelled_count": stats["cancelled_count"],
            "average_delay_minutes": stats["average_delay_minutes"],
            "disruption_count": stats["active_disruptions"],
            "fleet_by_type": stats["fleet_by_type"],
            "top_route": {"route_id": top_route[0], "avg_load": round(top_route[1], 3)},
            "bottom_route": {"route_id": bottom_route[0], "avg_load": round(bottom_route[1], 3)},
            "narrative": narrative,
        }

        return summary_data

    def compare_routes(self, route1: str, route2: str) -> Dict[str, Any]:
        """Side-by-side comparison of two routes.

        Args:
            route1: First route ID (e.g. ORD-LAX).
            route2: Second route ID (e.g. ORD-DEN).

        Returns:
            Dict with metrics for both routes and delta analysis.
        """
        routes_df = self.data_store.routes
        flights_df = self.data_store.flights

        def _route_metrics(route_id: str) -> Optional[Dict[str, Any]]:
            mask = routes_df["route_id"] == route_id
            if not mask.any():
                return None
            route = routes_df.loc[mask].iloc[0]
            origin, dest = route["origin"], route["destination"]
            flight_mask = (
                ((flights_df["origin"] == origin) & (flights_df["destination"] == dest))
                | ((flights_df["origin"] == dest) & (flights_df["destination"] == origin))
            )
            rf = flights_df.loc[flight_mask]
            avg_load = round(float(rf["load_factor"].mean()), 3) if not rf.empty else 0.0
            flight_count = len(rf)
            on_time_count = int((rf["status"] == "On Time").sum()) if not rf.empty else 0
            otp = round(on_time_count / flight_count * 100, 1) if flight_count > 0 else 0.0
            avg_delay = 0.0
            delayed = rf.loc[rf["delay_minutes"] > 0]
            if not delayed.empty:
                avg_delay = round(float(delayed["delay_minutes"].mean()), 1)

            return {
                "route_id": route_id,
                "demand_score": float(route["demand_score"]),
                "revenue_index": float(route["revenue_index"]),
                "competition_level": route["competition_level"],
                "frequency_weekly": int(route["frequency_weekly"]),
                "seasonal_peak": route["seasonal_peak"],
                "avg_load_factor": avg_load,
                "flight_count": flight_count,
                "otp_pct": otp,
                "avg_delay_minutes": avg_delay,
            }

        r1 = _route_metrics(route1)
        r2 = _route_metrics(route2)

        if r1 is None:
            return {"error": f"Route '{route1}' not found"}
        if r2 is None:
            return {"error": f"Route '{route2}' not found"}

        # Compute deltas
        deltas = {}
        for key in ["demand_score", "revenue_index", "avg_load_factor", "otp_pct", "avg_delay_minutes"]:
            deltas[key] = round(r1[key] - r2[key], 3)

        # Determine which route is stronger
        score1 = r1["demand_score"] * 0.3 + r1["avg_load_factor"] * 0.3 + (r1["otp_pct"] / 100) * 0.2 + r1["revenue_index"] * 0.2
        score2 = r2["demand_score"] * 0.3 + r2["avg_load_factor"] * 0.3 + (r2["otp_pct"] / 100) * 0.2 + r2["revenue_index"] * 0.2
        stronger = route1 if score1 >= score2 else route2

        return {
            "route_1": r1,
            "route_2": r2,
            "deltas": deltas,
            "composite_score_1": round(score1, 3),
            "composite_score_2": round(score2, 3),
            "stronger_route": stronger,
        }

    # ------------------------------------------------------------------ #
    # Tool registration
    # ------------------------------------------------------------------ #

    def register_tools(self) -> None:
        """Register all analytics tools with the tool registry."""
        tools = [
            ("compute_otd_summary", self.compute_otd_summary,
             "Compute on-time performance percentage by hub and overall.",
             ["executive_summary", "anomaly_report"]),
            ("compute_load_factor_trends", self.compute_load_factor_trends,
             "Compute average load factor by route with high/low flags.",
             ["executive_summary", "route_analysis"]),
            ("flag_anomalies", self.flag_anomalies,
             "Detect flights with unusual load factors or excessive delays.",
             ["anomaly_report"]),
            ("generate_executive_summary", self.generate_executive_summary,
             "Aggregate all metrics into a narrative executive summary.",
             ["executive_summary"]),
            ("compare_routes", self.compare_routes,
             "Side-by-side comparison of two routes.",
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
        """Process an analytics or insights query.

        Determines the analytics type, computes metrics, and generates
        a summary response.

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

        if "compare" in query:
            # Extract two route IDs
            route_matches = re.findall(r"\b([A-Z]{3}-[A-Z]{3})\b", payload.get("query", ""))
            if len(route_matches) >= 2:
                route1, route2 = route_matches[0], route_matches[1]
            else:
                # Try extracting airport pairs
                airport_matches = re.findall(r"\b([A-Z]{3})\b", payload.get("query", ""))
                if len(airport_matches) >= 4:
                    route1 = f"{airport_matches[0]}-{airport_matches[1]}"
                    route2 = f"{airport_matches[2]}-{airport_matches[3]}"
                elif len(airport_matches) >= 2:
                    # Use first two as a single route, look for more context
                    route1 = payload.get("route1", f"{airport_matches[0]}-{airport_matches[1]}")
                    route2 = payload.get("route2", "")
                else:
                    route1 = payload.get("route1", "")
                    route2 = payload.get("route2", "")

            if route1 and route2:
                self._log_trace(message, f"tool:compare_routes({route1},{route2})")
                result = self._call_tool("compare_routes", route1=route1, route2=route2)
                tool_calls.append("compare_routes")
            else:
                result = {"error": "Could not identify two routes to compare"}

        elif "anomal" in query or "unusual" in query or "outlier" in query or "alert" in query:
            self._log_trace(message, "tool:flag_anomalies")
            result = self._call_tool("flag_anomalies")
            tool_calls.append("flag_anomalies")

        elif "load" in query and ("factor" in query or "trend" in query):
            self._log_trace(message, "tool:compute_load_factor_trends")
            result = self._call_tool("compute_load_factor_trends")
            tool_calls.append("compute_load_factor_trends")

        elif "on-time" in query or "otp" in query or "otd" in query or "punctual" in query:
            self._log_trace(message, "tool:compute_otd_summary")
            result = self._call_tool("compute_otd_summary")
            tool_calls.append("compute_otd_summary")

        elif "summary" in query or "executive" in query or "overview" in query or "dashboard" in query or "report" in query:
            self._log_trace(message, "tool:generate_executive_summary")
            result = self._call_tool("generate_executive_summary")
            tool_calls.append("generate_executive_summary")

        elif "performance" in query or "insight" in query or "trend" in query:
            # Run OTP + load factors for a combined performance view
            self._log_trace(message, "tool:compute_otd_summary")
            otp = self._call_tool("compute_otd_summary")
            tool_calls.append("compute_otd_summary")

            self._log_trace(message, "tool:compute_load_factor_trends")
            lf = self._call_tool("compute_load_factor_trends")
            tool_calls.append("compute_load_factor_trends")

            result = {
                "on_time_performance": otp,
                "load_factor_trends": lf,
            }

        else:
            # Default: executive summary
            self._log_trace(message, "tool:generate_executive_summary")
            result = self._call_tool("generate_executive_summary")
            tool_calls.append("generate_executive_summary")

        # Generate insight text
        if "narrative" in result:
            insight = result["narrative"]
        elif "error" in result:
            insight = f"Analytics could not be completed: {result['error']}"
        else:
            try:
                if "anomaly_count" in result:
                    sb = result.get("severity_breakdown", {})
                    anomaly_details = "\n".join(
                        f"  - [{a['severity']}] {a['flight_number']}: {a['detail']}"
                        for a in result.get("anomalies", [])[:10]
                    )
                    insight = self.llm.generate("anomaly_report", {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "anomaly_count": result["anomaly_count"],
                        "critical": sb.get("Critical", 0),
                        "high": sb.get("High", 0),
                        "medium": sb.get("Medium", 0),
                        "low": sb.get("Low", 0),
                        "anomaly_details": anomaly_details or "No anomalies",
                        "system_health": "DEGRADED" if sb.get("Critical", 0) > 0 else "HEALTHY",
                        "recommendations": "Investigate critical anomalies immediately; review high-severity items within 2 hours.",
                    })
                else:
                    insight = self._build_analytics_summary(result)
            except Exception as exc:
                logger.warning("LLM generation failed: %s", exc)
                insight = f"Analytics analysis complete. {len(tool_calls)} tool(s) invoked."

        confidence = 0.90 if "error" not in result else 0.3
        self._store_result(f"analytics_insights:{message.message_id}", result)
        self._log_trace(message, "complete")

        return self._build_response(message, result, insight, confidence, tool_calls)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _build_analytics_summary(self, result: Dict[str, Any]) -> str:
        """Build a plain-text summary for analytics results."""
        lines: List[str] = ["Analytics Insights Report", "=" * 40]

        if "overall_otp_pct" in result:
            lines.append(f"\nOn-Time Performance: {result['overall_otp_pct']}%")
            lines.append(f"Total Flights: {result['total_flights']}")
            lines.append(f"Avg Delay: {result.get('avg_delay_minutes', 0)} min")
            for hub in result.get("hub_breakdown", [])[:5]:
                lines.append(f"  {hub['hub']}: {hub['otp_pct']}% ({hub['total_flights']} flights)")

        if "overall_avg_load_factor" in result:
            lines.append(f"\nOverall Avg Load Factor: {result['overall_avg_load_factor']}")
            lines.append(f"High-Load Routes: {result.get('high_load_routes', 0)}")
            lines.append(f"Low-Load Routes: {result.get('low_load_routes', 0)}")

        if "route_1" in result and "route_2" in result:
            r1, r2 = result["route_1"], result["route_2"]
            lines.append(f"\nRoute Comparison: {r1['route_id']} vs {r2['route_id']}")
            lines.append(f"  Demand: {r1['demand_score']:.2f} vs {r2['demand_score']:.2f}")
            lines.append(f"  Load Factor: {r1['avg_load_factor']:.3f} vs {r2['avg_load_factor']:.3f}")
            lines.append(f"  OTP: {r1['otp_pct']}% vs {r2['otp_pct']}%")
            lines.append(f"  Stronger Route: {result.get('stronger_route', 'N/A')}")

        if "on_time_performance" in result:
            otp = result["on_time_performance"]
            lines.append(f"\nOTP: {otp.get('overall_otp_pct', 0)}%")
            lf = result.get("load_factor_trends", {})
            lines.append(f"Avg Load Factor: {lf.get('overall_avg_load_factor', 0)}")

        return "\n".join(lines)
