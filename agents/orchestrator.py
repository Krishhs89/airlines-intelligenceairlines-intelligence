"""
Orchestrator Agent for the United Airlines Multi-Agent System.

Routes user queries to the appropriate specialist agent based on intent
classification, manages shared MCP components, and coordinates multi-agent
workflows.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from agents.analytics_insights import AnalyticsInsightsAgent
from agents.disruption_analysis import DisruptionAnalysisAgent
from agents.network_planning import NetworkPlanningAgent
from data.store import DataStore
from llm.mock_llm import MockLLM
from mcp.context_store import MCPContextStore
from mcp.protocol import MCPMessage, MCPResponse
from mcp.tool_registry import MCPToolRegistry

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """Top-level orchestrator that classifies intent and dispatches to
    specialist agents.

    Holds references to all three specialist agents and uses keyword-based
    intent classification (with MockLLM fallback) to route queries.

    Attributes:
        network_planning: NetworkPlanningAgent instance.
        disruption_analysis: DisruptionAnalysisAgent instance.
        analytics_insights: AnalyticsInsightsAgent instance.
    """

    # Keyword -> agent name mapping
    INTENT_MAP: Dict[str, str] = {
        # Network planning keywords
        "route": "network_planning",
        "schedule": "network_planning",
        "frequency": "network_planning",
        "fleet": "network_planning",
        "aircraft assignment": "network_planning",
        "underperform": "network_planning",
        "gate conflict": "network_planning",
        "overlap": "network_planning",
        "network": "network_planning",
        # Disruption analysis keywords
        "disruption": "disruption_analysis",
        "gate closure": "disruption_analysis",
        "weather": "disruption_analysis",
        "storm": "disruption_analysis",
        "swap": "disruption_analysis",
        "mechanical": "disruption_analysis",
        "cancel": "disruption_analysis",
        "delay impact": "disruption_analysis",
        "irops": "disruption_analysis",
        "grounding": "disruption_analysis",
        "passenger impact": "disruption_analysis",
        # Analytics keywords
        "trend": "analytics_insights",
        "summary": "analytics_insights",
        "insight": "analytics_insights",
        "anomaly": "analytics_insights",
        "compare": "analytics_insights",
        "performance": "analytics_insights",
        "on-time": "analytics_insights",
        "load factor": "analytics_insights",
        "executive": "analytics_insights",
        "dashboard": "analytics_insights",
        "report": "analytics_insights",
        "kpi": "analytics_insights",
        "otp": "analytics_insights",
    }

    # Map MockLLM intents to agent names
    _LLM_INTENT_TO_AGENT: Dict[str, str] = {
        "route_analysis": "network_planning",
        "schedule_gap": "network_planning",
        "disruption_impact": "disruption_analysis",
        "executive_summary": "analytics_insights",
        "anomaly_report": "analytics_insights",
    }

    def __init__(
        self,
        context_store: MCPContextStore,
        tool_registry: MCPToolRegistry,
        llm: MockLLM,
        data_store: DataStore,
        network_planning: NetworkPlanningAgent,
        disruption_analysis: DisruptionAnalysisAgent,
        analytics_insights: AnalyticsInsightsAgent,
    ) -> None:
        super().__init__(
            name="orchestrator",
            context_store=context_store,
            tool_registry=tool_registry,
            llm=llm,
            data_store=data_store,
        )
        self.network_planning = network_planning
        self.disruption_analysis = disruption_analysis
        self.analytics_insights = analytics_insights

        self._agents: Dict[str, BaseAgent] = {
            "network_planning": self.network_planning,
            "disruption_analysis": self.disruption_analysis,
            "analytics_insights": self.analytics_insights,
        }

    # ------------------------------------------------------------------ #
    # Intent classification
    # ------------------------------------------------------------------ #

    def _classify_intent(self, query: str) -> str:
        """Classify a user query into an agent name.

        Uses keyword matching first, then falls back to MockLLM classification.

        Args:
            query: The raw user query string.

        Returns:
            Agent name string (network_planning, disruption_analysis, or
            analytics_insights).
        """
        query_lower = query.lower()

        # Multi-word keywords first (more specific)
        for keyword in sorted(self.INTENT_MAP.keys(), key=len, reverse=True):
            if keyword in query_lower:
                agent_name = self.INTENT_MAP[keyword]
                logger.info(
                    "Intent classified via keyword '%s' -> %s", keyword, agent_name
                )
                return agent_name

        # Fallback to MockLLM
        llm_intent = self.llm.classify_intent(query)
        agent_name = self._LLM_INTENT_TO_AGENT.get(llm_intent, "analytics_insights")
        logger.info(
            "Intent classified via LLM '%s' -> %s", llm_intent, agent_name
        )
        return agent_name

    # ------------------------------------------------------------------ #
    # Routing
    # ------------------------------------------------------------------ #

    def route(self, user_query: str) -> MCPResponse:
        """Classify intent, build MCPMessage, dispatch to the correct agent,
        store result, and return MCPResponse.

        This is the primary entry point for user queries.

        Args:
            user_query: Natural-language query from the user.

        Returns:
            MCPResponse from the specialist agent.
        """
        # Classify
        agent_name = self._classify_intent(user_query)
        target_agent = self._agents[agent_name]

        # Build MCPMessage
        message = MCPMessage(
            sender="user",
            recipient=agent_name,
            intent=agent_name,
            payload={"query": user_query},
        )

        self._log_trace(message, f"routing_to:{agent_name}")
        logger.info(
            "Orchestrator routing query to '%s': %s",
            agent_name, user_query[:80],
        )

        # Dispatch
        response = target_agent.handle(message)

        # Store result for future context
        self._store_result(f"last_query", user_query)
        self._store_result(f"last_agent", agent_name)
        self._store_result(f"last_response:{response.message_id}", response.to_dict())

        return response

    # ------------------------------------------------------------------ #
    # Handle (for MCP compatibility)
    # ------------------------------------------------------------------ #

    def handle(self, message: MCPMessage) -> MCPResponse:
        """Process an MCPMessage by routing to the appropriate specialist.

        Args:
            message: Inbound MCPMessage.

        Returns:
            MCPResponse from the dispatched specialist agent.
        """
        query = message.payload.get("query", "")
        return self.route(query)

    # ------------------------------------------------------------------ #
    # Factory
    # ------------------------------------------------------------------ #

    @classmethod
    def setup(cls) -> "OrchestratorAgent":
        """Create all agents with shared MCP components and register all tools.

        This is the recommended way to initialise the entire agent system.

        Returns:
            A fully configured OrchestratorAgent with all specialist agents
            and their tools registered.
        """
        # Shared components
        context_store = MCPContextStore()
        tool_registry = MCPToolRegistry()
        llm = MockLLM()
        data_store = DataStore.get()

        # Specialist agents
        network_planning = NetworkPlanningAgent(
            context_store=context_store,
            tool_registry=tool_registry,
            llm=llm,
            data_store=data_store,
        )
        disruption_analysis = DisruptionAnalysisAgent(
            context_store=context_store,
            tool_registry=tool_registry,
            llm=llm,
            data_store=data_store,
        )
        analytics_insights = AnalyticsInsightsAgent(
            context_store=context_store,
            tool_registry=tool_registry,
            llm=llm,
            data_store=data_store,
        )

        # Register all tools
        network_planning.register_tools()
        disruption_analysis.register_tools()
        analytics_insights.register_tools()

        # Orchestrator
        orchestrator = cls(
            context_store=context_store,
            tool_registry=tool_registry,
            llm=llm,
            data_store=data_store,
            network_planning=network_planning,
            disruption_analysis=disruption_analysis,
            analytics_insights=analytics_insights,
        )

        logger.info(
            "Orchestrator setup complete: %d tools registered",
            len(tool_registry),
        )

        return orchestrator
