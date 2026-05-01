"""
Abstract base agent for the United Airlines Network Planning Multi-Agent System.

Provides shared infrastructure for context management, tool invocation,
trace logging, and response building that all specialist agents inherit.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from data.store import DataStore
from llm.mock_llm import MockLLM
from mcp.context_store import MCPContextStore
from mcp.protocol import MCPMessage, MCPResponse
from mcp.tool_registry import MCPToolRegistry

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all agents in the multi-agent system.

    Provides convenience methods for context storage, tool invocation,
    trace logging, and MCPResponse construction.

    Args:
        name: Unique agent name used in MCP message routing.
        context_store: Shared MCP context store for inter-agent state.
        tool_registry: Central tool registry for callable tools.
        llm: Mock (or real) LLM instance for generating insight text.
        data_store: Singleton DataStore holding all operational DataFrames.
    """

    def __init__(
        self,
        name: str,
        context_store: MCPContextStore,
        tool_registry: MCPToolRegistry,
        llm: MockLLM,
        data_store: DataStore,
    ) -> None:
        self.name = name
        self.context_store = context_store
        self.tool_registry = tool_registry
        self.llm = llm
        self.data_store = data_store

    # ------------------------------------------------------------------ #
    # Abstract interface
    # ------------------------------------------------------------------ #

    @abstractmethod
    def handle(self, message: MCPMessage) -> MCPResponse:
        """Process an incoming MCP message and return a response.

        Args:
            message: The inbound MCPMessage to handle.

        Returns:
            An MCPResponse containing structured results and insight text.
        """
        ...

    # ------------------------------------------------------------------ #
    # Context helpers
    # ------------------------------------------------------------------ #

    def _store_result(self, key: str, value: Any) -> None:
        """Write a value into the shared context store.

        Args:
            key: Storage key.
            value: Arbitrary Python object.
        """
        self.context_store.set(key, value)

    def _get_context(self, key: str) -> Any:
        """Read a value from the shared context store.

        Args:
            key: Storage key.

        Returns:
            The stored value, or None if the key is missing or expired.
        """
        return self.context_store.get(key)

    # ------------------------------------------------------------------ #
    # Tool invocation
    # ------------------------------------------------------------------ #

    def _call_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a registered tool and record the call in the message trace.

        Args:
            tool_name: Name of the tool to invoke.
            **kwargs: Arguments forwarded to the tool callable.

        Returns:
            Whatever the tool callable returns.
        """
        logger.info(
            "[%s] Calling tool '%s' with args %s", self.name, tool_name, kwargs
        )
        return self.tool_registry.invoke(tool_name, **kwargs)

    # ------------------------------------------------------------------ #
    # Trace logging
    # ------------------------------------------------------------------ #

    def _log_trace(self, msg: MCPMessage, step: str) -> None:
        """Append a processing step to the message trace.

        Args:
            msg: The MCPMessage being processed.
            step: Description of the processing step.
        """
        msg.add_trace(f"{self.name}:{step}")

    # ------------------------------------------------------------------ #
    # Response builder
    # ------------------------------------------------------------------ #

    def _build_response(
        self,
        msg: MCPMessage,
        result_dict: Dict[str, Any],
        insight_text: str,
        confidence: float,
        tool_calls: Optional[List[str]] = None,
    ) -> MCPResponse:
        """Construct an MCPResponse from processed results.

        Args:
            msg: The originating MCPMessage.
            result_dict: Structured result data.
            insight_text: Human-readable insight or summary.
            confidence: Confidence score (0.0 -- 1.0).
            tool_calls: List of tool names that were invoked.

        Returns:
            A fully populated MCPResponse.
        """
        response = MCPResponse(
            message_id=msg.message_id,
            responder=self.name,
            result=result_dict,
            insight=insight_text,
            confidence=confidence,
            tool_calls=tool_calls or [],
        )
        # Record in conversation history
        self.context_store.push_message(msg, response)
        return response
