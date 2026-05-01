"""
MCP message protocol data classes.

Defines the envelope format for inter-agent communication within the
United Airlines Network Planning Multi-Agent System.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class MCPMessage:
    """Outbound message sent from one agent to another.

    Attributes:
        message_id: Globally unique message identifier.
        sender: Name of the sending agent.
        recipient: Name of the target agent.
        intent: The action or query intent (e.g. ``route_analysis``).
        payload: Arbitrary key-value data relevant to the intent.
        context_ref: Optional reference key into MCPContextStore.
        timestamp: UTC timestamp of message creation.
        trace: Ordered list of agent names this message has traversed.
    """

    sender: str
    recipient: str
    intent: str
    payload: Dict[str, Any] = field(default_factory=dict)
    context_ref: Optional[str] = None
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    trace: List[str] = field(default_factory=list)

    def add_trace(self, agent_name: str) -> None:
        """Append an agent name to the message trace.

        Args:
            agent_name: The agent that processed this message.
        """
        self.trace.append(agent_name)

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the message to a plain dictionary.

        Returns:
            Dictionary representation suitable for JSON serialisation.
        """
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "intent": self.intent,
            "payload": self.payload,
            "context_ref": self.context_ref,
            "timestamp": self.timestamp.isoformat(),
            "trace": self.trace,
        }


@dataclass
class MCPResponse:
    """Response returned by an agent after processing an MCPMessage.

    Attributes:
        message_id: ID of the originating MCPMessage.
        responder: Name of the responding agent.
        result: Structured result data.
        insight: Human-readable insight or summary string.
        confidence: Confidence score for the result (0.0 -- 1.0).
        tool_calls: List of tool names that were invoked.
        timestamp: UTC timestamp of response creation.
    """

    message_id: str
    responder: str
    result: Dict[str, Any] = field(default_factory=dict)
    insight: str = ""
    confidence: float = 0.0
    tool_calls: List[str] = field(default_factory=list)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> Dict[str, Any]:
        """Serialise the response to a plain dictionary.

        Returns:
            Dictionary representation suitable for JSON serialisation.
        """
        return {
            "message_id": self.message_id,
            "responder": self.responder,
            "result": self.result,
            "insight": self.insight,
            "confidence": self.confidence,
            "tool_calls": self.tool_calls,
            "timestamp": self.timestamp.isoformat(),
        }
