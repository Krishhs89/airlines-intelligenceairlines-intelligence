"""
MCP Tool Registry -- central catalogue of callable tools for agents.

Each tool is a plain Python callable registered with metadata (owning agent,
description).  The registry supports intent-based tool look-up so the
orchestrator can auto-select tools for a given query intent.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class _ToolEntry:
    """Internal descriptor for a registered tool."""

    name: str
    fn: Callable[..., Any]
    agent: str
    description: str
    intents: List[str] = field(default_factory=list)


class MCPToolRegistry:
    """Registry that maps tool names to callables with agent ownership.

    Example::

        registry = MCPToolRegistry()
        registry.register(
            name="analyse_route",
            fn=route_agent.analyse,
            agent="RouteAgent",
            description="Analyse a specific route pair.",
        )
        result = registry.invoke("analyse_route", origin="ORD", dest="LAX")
    """

    def __init__(self) -> None:
        self._tools: Dict[str, _ToolEntry] = {}

    # ------------------------------------------------------------------ #
    # Registration
    # ------------------------------------------------------------------ #

    def register(
        self,
        name: str,
        fn: Callable[..., Any],
        agent: str,
        description: str = "",
        intents: Optional[List[str]] = None,
    ) -> None:
        """Register a tool in the catalogue.

        Args:
            name: Unique tool name.
            fn: Callable implementing the tool logic.
            agent: Name of the owning agent.
            description: Human-readable description.
            intents: List of intent strings this tool can service.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if name in self._tools:
            raise ValueError(
                f"Tool '{name}' is already registered by agent "
                f"'{self._tools[name].agent}'."
            )
        self._tools[name] = _ToolEntry(
            name=name,
            fn=fn,
            agent=agent,
            description=description,
            intents=intents or [],
        )
        logger.info("Registered tool '%s' (agent=%s)", name, agent)

    def unregister(self, name: str) -> bool:
        """Remove a tool from the registry.

        Args:
            name: Tool name to remove.

        Returns:
            True if the tool existed and was removed, False otherwise.
        """
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    # ------------------------------------------------------------------ #
    # Invocation
    # ------------------------------------------------------------------ #

    def invoke(self, tool_name: str, **kwargs: Any) -> Any:
        """Invoke a registered tool by name.

        Args:
            tool_name: Name of the tool to call.
            **kwargs: Arguments forwarded to the tool callable.

        Returns:
            Whatever the tool callable returns.

        Raises:
            KeyError: If the tool is not registered.
            RuntimeError: If the tool raises an exception.
        """
        if tool_name not in self._tools:
            raise KeyError(f"Tool '{tool_name}' is not registered.")

        entry = self._tools[tool_name]
        logger.debug("Invoking tool '%s' with kwargs=%s", tool_name, kwargs)
        try:
            return entry.fn(**kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"Tool '{tool_name}' raised an error: {exc}"
            ) from exc

    # ------------------------------------------------------------------ #
    # Discovery
    # ------------------------------------------------------------------ #

    def list_tools(self, agent: Optional[str] = None) -> List[Dict[str, str]]:
        """List registered tools, optionally filtered by owning agent.

        Args:
            agent: If provided, only tools belonging to this agent are listed.

        Returns:
            List of dicts with ``name``, ``agent``, and ``description`` keys.
        """
        results: List[Dict[str, str]] = []
        for entry in self._tools.values():
            if agent is not None and entry.agent != agent:
                continue
            results.append({
                "name": entry.name,
                "agent": entry.agent,
                "description": entry.description,
            })
        return results

    def get_tools_for_intent(self, intent: str) -> List[Dict[str, str]]:
        """Find tools that can service a given intent.

        Args:
            intent: The intent string to match against.

        Returns:
            List of matching tool descriptors.
        """
        results: List[Dict[str, str]] = []
        intent_lower = intent.lower()
        for entry in self._tools.values():
            if any(intent_lower in i.lower() for i in entry.intents):
                results.append({
                    "name": entry.name,
                    "agent": entry.agent,
                    "description": entry.description,
                })
        return results

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
