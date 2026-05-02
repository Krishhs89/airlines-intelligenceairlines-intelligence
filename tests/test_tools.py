"""
Tests for all 15 registered MCP tools across the three specialist agents.

Each tool is exercised directly via the tool registry to verify:
  - Correct return type
  - Expected keys in response dict
  - No exceptions on valid input

Actual registered tool names (from agent register_tools() calls):
  Network Planning:  get_route_demand, get_schedule_conflicts,
                     suggest_frequency_change, get_underperforming_routes,
                     optimize_aircraft_assignment
  Disruption:        simulate_gate_closure, simulate_weather_event,
                     simulate_aircraft_swap, calculate_pax_impact,
                     suggest_mitigation
  Analytics:         compute_otd_summary, compute_load_factor_trends,
                     flag_anomalies, generate_executive_summary, compare_routes
"""

from __future__ import annotations

import pytest
from agents.orchestrator import OrchestratorAgent
from data.store import DataStore


@pytest.fixture(scope="module")
def orchestrator():
    return OrchestratorAgent.setup()


@pytest.fixture(scope="module")
def registry(orchestrator):
    return orchestrator.tool_registry


@pytest.fixture(scope="module")
def data_store():
    return DataStore.get()


# ---------------------------------------------------------------------------
# Network Planning tools
# ---------------------------------------------------------------------------

class TestNetworkPlanningTools:

    def test_get_route_demand(self, registry, data_store):
        # Use the first route's origin/destination from the DataStore
        route = data_store.routes.iloc[0]
        result = registry.invoke(
            "get_route_demand",
            origin=route["origin"],
            dest=route["destination"],
        )
        assert isinstance(result, dict)

    def test_get_schedule_conflicts(self, registry):
        result = registry.invoke("get_schedule_conflicts")
        assert isinstance(result, dict)
        assert "conflict_count" in result

    def test_suggest_frequency_change(self, registry, data_store):
        route_id = data_store.routes.iloc[0]["route_id"]
        result = registry.invoke("suggest_frequency_change", route_id=route_id)
        assert isinstance(result, dict)
        assert "recommendation" in result or "error" in result

    def test_get_underperforming_routes(self, registry):
        result = registry.invoke("get_underperforming_routes")
        assert isinstance(result, dict)
        assert "total_underperforming" in result

    def test_optimize_aircraft_assignment(self, registry, data_store):
        route_id = data_store.routes.iloc[0]["route_id"]
        result = registry.invoke("optimize_aircraft_assignment", route_id=route_id)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Disruption Analysis tools
# ---------------------------------------------------------------------------

class TestDisruptionAnalysisTools:

    def test_simulate_gate_closure(self, registry, data_store):
        gate_id = data_store.gates.iloc[0]["gate_id"]
        result = registry.invoke("simulate_gate_closure", gate_id=gate_id)
        assert isinstance(result, dict)

    def test_simulate_weather_event(self, registry):
        result = registry.invoke(
            "simulate_weather_event",
            airport="ORD",
            severity="High",
            duration_hours=4.0,
        )
        assert isinstance(result, dict)
        assert "total_flights_affected" in result

    def test_simulate_aircraft_swap(self, registry, data_store):
        flight_num = data_store.flights.iloc[0]["flight_number"]
        result = registry.invoke(
            "simulate_aircraft_swap",
            flight_number=flight_num,
            new_aircraft_type="B787-9",
        )
        assert isinstance(result, dict)
        assert "feasible" in result

    def test_calculate_pax_impact(self, registry, data_store):
        flights = data_store.flights["flight_number"].head(5).tolist()
        result = registry.invoke("calculate_pax_impact", affected_flights=flights)
        assert isinstance(result, dict)
        assert "total_pax_impact" in result

    def test_suggest_mitigation(self, registry):
        result = registry.invoke(
            "suggest_mitigation",
            disruption_type="Weather",
            severity="High",
            affected_flights=["UA101", "UA202"],
        )
        assert isinstance(result, dict)
        assert "strategies" in result


# ---------------------------------------------------------------------------
# Analytics Insights tools
# ---------------------------------------------------------------------------

class TestAnalyticsInsightsTools:

    def test_compute_otd_summary(self, registry):
        result = registry.invoke("compute_otd_summary")
        assert isinstance(result, dict)
        assert "overall_otp_pct" in result

    def test_compute_load_factor_trends(self, registry):
        result = registry.invoke("compute_load_factor_trends")
        assert isinstance(result, dict)

    def test_flag_anomalies(self, registry):
        result = registry.invoke("flag_anomalies")
        assert isinstance(result, dict)

    def test_generate_executive_summary(self, registry):
        result = registry.invoke("generate_executive_summary")
        assert isinstance(result, dict)

    def test_compare_routes(self, registry, data_store):
        r1 = data_store.routes.iloc[0]["route_id"]
        r2 = data_store.routes.iloc[1]["route_id"]
        result = registry.invoke("compare_routes", route1=r1, route2=r2)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Tool registry meta
# ---------------------------------------------------------------------------

class TestToolRegistry:

    def test_fifteen_tools_registered(self, registry):
        assert len(registry) == 15

    def test_list_tools_returns_dicts(self, registry):
        tools = registry.list_tools()
        assert len(tools) == 15
        for t in tools:
            assert "name" in t
            assert "agent" in t

    def test_unknown_tool_raises(self, registry):
        with pytest.raises(KeyError):
            registry.invoke("nonexistent_tool_xyz")

    def test_tool_names_are_strings(self, registry):
        for t in registry.list_tools():
            assert isinstance(t["name"], str)
