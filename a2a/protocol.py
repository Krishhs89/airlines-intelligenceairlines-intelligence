"""
A2A (Agent-to-Agent) protocol data models for the UA Network Intelligence system.

Implements Google's A2A spec: agent cards, tasks, messages, and streaming events.
Reference: https://google.github.io/A2A
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TaskState(str, Enum):
    SUBMITTED = "submitted"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ContentType(str, Enum):
    TEXT = "text"
    DATA = "data"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Agent Card — describes this agent to discovery clients
# ---------------------------------------------------------------------------

class AgentCapability(BaseModel):
    name: str
    description: str
    input_modes: List[str] = ["text"]
    output_modes: List[str] = ["text", "data"]


class AgentAuthentication(BaseModel):
    schemes: List[str] = ["none"]


class AgentCard(BaseModel):
    """A2A Agent Card published at /.well-known/agent.json."""

    name: str
    description: str
    version: str
    url: str
    capabilities: List[AgentCapability]
    authentication: AgentAuthentication = Field(default_factory=AgentAuthentication)
    tags: List[str] = []
    skills: List[Dict[str, Any]] = []

    class Config:
        json_schema_extra = {
            "example": {
                "name": "UA Network Intelligence Agent",
                "description": "Multi-agent system for United Airlines network operations",
                "version": "1.0.0",
                "url": "http://localhost:8765",
            }
        }


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

class MessagePart(BaseModel):
    type: ContentType
    content: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)


class A2AMessage(BaseModel):
    """A single message in an A2A task conversation."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: str  # "user" | "agent"
    parts: List[MessagePart]
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

class TaskStatus(BaseModel):
    state: TaskState
    message: Optional[str] = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class A2ATask(BaseModel):
    """An A2A task — the primary unit of work."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    status: TaskStatus = Field(
        default_factory=lambda: TaskStatus(state=TaskState.SUBMITTED)
    )
    messages: List[A2AMessage] = Field(default_factory=list)
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def add_message(self, role: str, text: str, data: Optional[Dict] = None) -> A2AMessage:
        parts = [MessagePart(type=ContentType.TEXT, content=text)]
        if data:
            parts.append(MessagePart(type=ContentType.DATA, content=data))
        msg = A2AMessage(role=role, parts=parts)
        self.messages.append(msg)
        self.updated_at = datetime.now(timezone.utc).isoformat()
        return msg

    def set_state(self, state: TaskState, message: Optional[str] = None) -> None:
        self.status = TaskStatus(state=state, message=message)
        self.updated_at = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Request / Response models for REST endpoints
# ---------------------------------------------------------------------------

class SendTaskRequest(BaseModel):
    id: Optional[str] = None
    session_id: Optional[str] = None
    message: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SendTaskResponse(BaseModel):
    id: str
    status: TaskStatus
    messages: List[A2AMessage]
    artifacts: List[Dict[str, Any]] = []


class GetTaskResponse(BaseModel):
    id: str
    status: TaskStatus
    messages: List[A2AMessage]
    artifacts: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}


class CancelTaskResponse(BaseModel):
    id: str
    status: TaskStatus


# ---------------------------------------------------------------------------
# SSE Event
# ---------------------------------------------------------------------------

class A2AEvent(BaseModel):
    """Server-sent event for streaming task updates."""

    event: str  # "status" | "artifact" | "message" | "done" | "error"
    data: Dict[str, Any]
    task_id: str
