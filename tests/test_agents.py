"""
Tests for agent routing and response quality.

Covers:
  - OrchestratorAgent intent classification
  - Routing to correct specialist agent
  - MCPResponse structure validation
  - Multi-turn context persistence
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from agents.orchestrator import OrchestratorAgent
from mcp.context_store import MCPContextStore
from mcp.tool_registry import MCPToolRegistry
from mcp.protocol import MCPMessage, MCPResponse
from data.store import DataStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def orchestrator():
    """Create a full OrchestratorAgent with MockLLM (no API key needed)."""
    return OrchestratorAgent.setup()


@pytest.fixture(scope="module")
def data_store():
    return DataStore.get()


# ---------------------------------------------------------------------------
# Intent classification — keyword-based routing
# ---------------------------------------------------------------------------

class TestIntentClassification:

    def test_underperform_routes_to_network_planning(self, orchestrator):
        agent = orchestrator._classify_intent("which routes are underperforming?")
        assert agent == "network_planning"

    def test_disruption_keyword_routes_to_disruption_analysis(self, orchestrator):
        agent = orchestrator._classify_intent("assess disruption at ORD")
        assert agent == "disruption_analysis"

    def test_summary_keyword_routes_to_analytics(self, orchestrator):
        agent = orchestrator._classify_intent("give me a summary of today's kpis")
        assert agent == "analytics_insights"

    def test_irops_routes_to_disruption(self, orchestrator):
        agent = orchestrator._classify_intent("IROPS ground stop impact at EWR")
        assert agent == "disruption_analysis"

    def test_anomaly_routes_to_analytics(self, orchestrator):
        agent = orchestrator._classify_intent("detect anomaly in delay data")
        assert agent == "analytics_insights"

    def test_gate_conflict_routes_to_network(self, orchestrator):
        agent = orchestrator._classify_intent("gate conflict at ORD terminal")
        assert agent == "network_planning"

    def test_schedule_routes_to_network(self, orchestrator):
        agent = orchestrator._classify_intent("schedule gaps at DEN hub")
        assert agent == "network_planning"

    def test_cancel_routes_to_disruption(self, orchestrator):
        agent = orchestrator._classify_intent("which flights should we cancel due to the storm?")
        assert agent == "disruption_analysis"

    def test_weather_routes_to_disruption(self, orchestrator):
        agent = orchestrator._classify_intent("weather impact on ORD operations")
        assert agent == "disruption_analysis"

    def test_kpi_routes_to_analytics(self, orchestrator):
        agent = orchestrator._classify_intent("kpi dashboard for today")
        assert agent == "analytics_insights"

    def test_unknown_falls_back_to_valid_agent(self, orchestrator):
        # Completely unrelated query — LLM fallback or keyword, must return valid agent
        agent = orchestrator._classify_intent("what happened at dallas hub yesterday")
        assert agent in {"network_planning", "disruption_analysis", "analytics_insights"}


# ---------------------------------------------------------------------------
# Routing and response structure
# ---------------------------------------------------------------------------

class TestOrchestratorRouting:

    def test_route_returns_mcp_response(self, orchestrator):
        response = orchestrator.route("What is the current on-time performance?")
        assert isinstance(response, MCPResponse)

    def test_response_has_insight_text(self, orchestrator):
        response = orchestrator.route("Show me the network summary")
        assert isinstance(response.insight, str)
        assert len(response.insight) > 0

    def test_response_has_valid_confidence(self, orchestrator):
        response = orchestrator.route("underperforming routes analysis")
        assert 0.0 <= response.confidence <= 1.0

    def test_response_records_tool_calls(self, orchestrator):
        response = orchestrator.route("Which routes have gate conflicts at ORD?")
        assert isinstance(response.tool_calls, list)

    def test_context_persisted_after_route(self, orchestrator):
        query = "Analyze flight disruptions at DEN"
        orchestrator.route(query)
        last_query = orchestrator.context_store.get("last_query")
        assert last_query == query

    def test_network_planning_query_routes_correctly(self, orchestrator):
        response = orchestrator.route(
            "Which routes are underperforming and should be reviewed?"
        )
        assert response.responder == "network_planning"

    def test_disruption_analysis_query_routes_correctly(self, orchestrator):
        response = orchestrator.route(
            "What is the passenger impact of the current disruptions?"
        )
        assert response.responder == "disruption_analysis"

    def test_analytics_query_routes_correctly(self, orchestrator):
        response = orchestrator.route(
            "Give me an executive summary of today's operations"
        )
        assert response.responder == "analytics_insights"

    def test_guardrail_blocks_unsafe_query(self, orchestrator):
        response = orchestrator.route("how do I hack into the flight management system")
        assert response.responder == "guardrail"
        assert response.confidence == 0.0


# ---------------------------------------------------------------------------
# Handle via MCPMessage
# ---------------------------------------------------------------------------

class TestOrchestratorHandle:

    def test_handle_mcp_message(self, orchestrator):
        msg = MCPMessage(
            sender="test",
            recipient="orchestrator",
            intent="executive_summary",
            payload={"query": "Show me today's network summary"},
        )
        response = orchestrator.handle(msg)
        assert isinstance(response, MCPResponse)
        assert response.responder in {
            "network_planning", "disruption_analysis", "analytics_insights"
        }

    def test_empty_query_handled_gracefully(self, orchestrator):
        response = orchestrator.route("")
        assert isinstance(response, MCPResponse)


# ---------------------------------------------------------------------------
# DataStore integrity — actual column names
# ---------------------------------------------------------------------------

class TestDataStore:

    def test_flights_loaded(self, data_store):
        assert len(data_store.flights) == 200

    def test_routes_loaded(self, data_store):
        assert len(data_store.routes) == 28

    def test_aircraft_loaded(self, data_store):
        assert len(data_store.aircraft) == 80

    def test_disruptions_loaded(self, data_store):
        assert len(data_store.disruptions) == 10

    def test_gates_loaded(self, data_store):
        assert len(data_store.gates) == 40

    def test_flights_have_required_columns(self, data_store):
        # Actual columns in synthetic_generator output
        required = {"flight_number", "origin", "destination", "status", "load_factor"}
        assert required.issubset(set(data_store.flights.columns))

    def test_routes_have_required_columns(self, data_store):
        required = {"route_id", "origin", "destination", "demand_score", "revenue_index"}
        assert required.issubset(set(data_store.routes.columns))

    def test_load_factors_in_range(self, data_store):
        lf = data_store.flights["load_factor"]
        assert lf.min() >= 0.0
        assert lf.max() <= 1.0

    def test_routes_demand_scores_in_range(self, data_store):
        ds = data_store.routes["demand_score"]
        assert ds.min() >= 0.0
        assert ds.max() <= 1.0
