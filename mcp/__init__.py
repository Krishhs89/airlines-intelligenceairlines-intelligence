"""
MCP (Model Context Protocol) layer for inter-agent communication.

Provides message passing, shared context storage, and tool registry.
"""

from mcp.protocol import MCPMessage, MCPResponse
from mcp.context_store import MCPContextStore
from mcp.tool_registry import MCPToolRegistry

__all__ = [
    "MCPMessage",
    "MCPResponse",
    "MCPContextStore",
    "MCPToolRegistry",
]
