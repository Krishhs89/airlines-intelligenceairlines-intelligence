"""A2A (Agent-to-Agent) protocol module for the UA Network Intelligence system."""

from a2a.protocol import (
    AgentCard,
    AgentCapability,
    A2ATask,
    A2AMessage,
    TaskState,
    TaskStatus,
)
from a2a.server import A2AServer, create_app

__all__ = [
    "AgentCard",
    "AgentCapability",
    "A2ATask",
    "A2AMessage",
    "TaskState",
    "TaskStatus",
    "A2AServer",
    "create_app",
]
