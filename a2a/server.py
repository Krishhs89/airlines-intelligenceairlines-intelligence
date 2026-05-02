"""
A2A (Agent-to-Agent) FastAPI server for the UA Network Intelligence system.

Exposes:
  GET  /.well-known/agent.json   — Agent Card discovery
  POST /tasks                    — Submit a new task
  GET  /tasks/{id}               — Get task status + messages
  POST /tasks/{id}/cancel        — Cancel a running task
  GET  /tasks/{id}/events        — SSE stream of task events
  GET  /health                   — Health check

Run standalone:
    python -m a2a.server

Or programmatically:
    from a2a.server import create_app
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8765)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sse_starlette.sse import EventSourceResponse

import config
from a2a.protocol import (
    A2AEvent,
    A2ATask,
    AgentCapability,
    AgentCard,
    CancelTaskResponse,
    GetTaskResponse,
    SendTaskRequest,
    SendTaskResponse,
    TaskState,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task store (in-memory; replace with Redis/DB for production)
# ---------------------------------------------------------------------------

class TaskStore:
    def __init__(self) -> None:
        self._tasks: Dict[str, A2ATask] = {}
        self._event_queues: Dict[str, asyncio.Queue] = {}

    def create(self, task_id: Optional[str] = None) -> A2ATask:
        task = A2ATask(id=task_id or str(uuid.uuid4()))
        self._tasks[task.id] = task
        self._event_queues[task.id] = asyncio.Queue()
        return task

    def get(self, task_id: str) -> Optional[A2ATask]:
        return self._tasks.get(task_id)

    def get_queue(self, task_id: str) -> Optional[asyncio.Queue]:
        return self._event_queues.get(task_id)

    async def emit(self, task_id: str, event: A2AEvent) -> None:
        q = self._event_queues.get(task_id)
        if q:
            await q.put(event)


# ---------------------------------------------------------------------------
# A2A Server
# ---------------------------------------------------------------------------

class A2AServer:
    """Wraps the orchestrator and exposes it via A2A protocol over HTTP/SSE."""

    def __init__(self) -> None:
        self.task_store = TaskStore()
        self._orchestrator: Any = None

    def _get_orchestrator(self) -> Any:
        if self._orchestrator is None:
            from agents.orchestrator import OrchestratorAgent
            self._orchestrator = OrchestratorAgent.setup()
            logger.info("A2A: OrchestratorAgent initialised")
        return self._orchestrator

    def agent_card(self) -> AgentCard:
        return AgentCard(
            name=config.A2A_AGENT_NAME,
            description=config.MCP_SERVER_DESCRIPTION,
            version=config.A2A_AGENT_VERSION,
            url=config.A2A_BASE_URL,
            tags=["airline", "operations", "network-planning", "disruption", "analytics"],
            capabilities=[
                AgentCapability(
                    name="network_planning",
                    description="Route analysis, fleet assignment, schedule gap detection",
                    input_modes=["text"],
                    output_modes=["text", "data"],
                ),
                AgentCapability(
                    name="disruption_analysis",
                    description="IROPS assessment, cascade impact, mitigation recommendations",
                    input_modes=["text"],
                    output_modes=["text", "data"],
                ),
                AgentCapability(
                    name="analytics_insights",
                    description="KPI dashboards, anomaly detection, OTP and load-factor trends",
                    input_modes=["text"],
                    output_modes=["text", "data"],
                ),
            ],
            skills=[
                {"id": "analyze_route", "name": "Analyze Route Performance"},
                {"id": "assess_disruption", "name": "Assess Disruption Impact"},
                {"id": "executive_summary", "name": "Generate Executive Summary"},
                {"id": "detect_anomalies", "name": "Detect Network Anomalies"},
                {"id": "optimize_schedule", "name": "Optimize Flight Schedule"},
            ],
        )

    async def process_task(self, task: A2ATask, query: str) -> None:
        """Run the orchestrator in the background and push SSE events."""
        store = self.task_store

        try:
            task.set_state(TaskState.WORKING, "Routing to specialist agent…")
            await store.emit(
                task.id,
                A2AEvent(
                    event="status",
                    data=task.status.model_dump(),
                    task_id=task.id,
                ),
            )

            # Run orchestrator (blocking call — offloaded to thread pool)
            orchestrator = self._get_orchestrator()
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, orchestrator.route, query)

            # Add agent reply to task messages
            task.add_message(
                "agent",
                response.insight,
                {"result": response.result, "confidence": response.confidence},
            )
            task.artifacts.append(
                {
                    "type": "analysis",
                    "data": response.result,
                    "tool_calls": response.tool_calls,
                }
            )
            task.set_state(TaskState.COMPLETED)

            # Emit artifact + final status
            await store.emit(
                task.id,
                A2AEvent(
                    event="artifact",
                    data=task.artifacts[-1],
                    task_id=task.id,
                ),
            )
            await store.emit(
                task.id,
                A2AEvent(
                    event="status",
                    data=task.status.model_dump(),
                    task_id=task.id,
                ),
            )

        except Exception as exc:
            logger.exception("Task %s failed: %s", task.id, exc)
            task.add_message("agent", f"Error processing request: {exc}")
            task.set_state(TaskState.FAILED, str(exc))
            await store.emit(
                task.id,
                A2AEvent(
                    event="error",
                    data={"message": str(exc)},
                    task_id=task.id,
                ),
            )
        finally:
            await store.emit(
                task.id,
                A2AEvent(event="done", data={}, task_id=task.id),
            )


# ---------------------------------------------------------------------------
# FastAPI app factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    server = A2AServer()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("A2A server starting on %s:%s", config.A2A_HOST, config.A2A_PORT)
        yield
        logger.info("A2A server shutting down")

    app = FastAPI(
        title=config.A2A_AGENT_NAME,
        description=config.MCP_SERVER_DESCRIPTION,
        version=config.A2A_AGENT_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------ #
    # Agent Card
    # ------------------------------------------------------------------ #

    @app.get("/.well-known/agent.json", tags=["Discovery"])
    async def get_agent_card():
        """Return the A2A Agent Card for discovery."""
        return server.agent_card().model_dump()

    # ------------------------------------------------------------------ #
    # Health
    # ------------------------------------------------------------------ #

    @app.get("/health", tags=["Operations"])
    async def health():
        return {"status": "ok", "agent": config.A2A_AGENT_NAME}

    # ------------------------------------------------------------------ #
    # Tasks
    # ------------------------------------------------------------------ #

    @app.post("/tasks", response_model=SendTaskResponse, tags=["Tasks"])
    async def send_task(request: SendTaskRequest):
        """Submit a new analytical task to the UA Network Intelligence agent."""
        task = server.task_store.create(request.id)
        task.session_id = request.session_id
        task.metadata = request.metadata

        # Extract text from message parts
        msg_parts = request.message.get("parts", [])
        query = ""
        for part in msg_parts:
            if part.get("type") == "text":
                query = part.get("content", "")
                break
        if not query:
            query = str(request.message.get("content", ""))

        task.add_message("user", query)

        # Background processing
        asyncio.create_task(server.process_task(task, query))

        return SendTaskResponse(
            id=task.id,
            status=task.status,
            messages=task.messages,
        )

    @app.get("/tasks/{task_id}", response_model=GetTaskResponse, tags=["Tasks"])
    async def get_task(task_id: str):
        """Retrieve current state, messages, and artifacts for a task."""
        task = server.task_store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return GetTaskResponse(
            id=task.id,
            status=task.status,
            messages=task.messages,
            artifacts=task.artifacts,
            metadata=task.metadata,
        )

    @app.post("/tasks/{task_id}/cancel", response_model=CancelTaskResponse, tags=["Tasks"])
    async def cancel_task(task_id: str):
        """Cancel a running task."""
        task = server.task_store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        task.set_state(TaskState.CANCELLED)
        return CancelTaskResponse(id=task.id, status=task.status)

    # ------------------------------------------------------------------ #
    # SSE Streaming
    # ------------------------------------------------------------------ #

    @app.get("/tasks/{task_id}/events", tags=["Streaming"])
    async def stream_task_events(task_id: str):
        """Stream task events as Server-Sent Events (SSE)."""
        task = server.task_store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        queue = server.task_store.get_queue(task_id)

        async def event_generator() -> AsyncGenerator[Dict, None]:
            while True:
                try:
                    event: A2AEvent = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {
                        "event": event.event,
                        "data": json.dumps(event.data),
                        "id": event.task_id,
                    }
                    if event.event in ("done", "error"):
                        break
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": "{}"}

        return EventSourceResponse(event_generator())

    # ------------------------------------------------------------------ #
    # List tasks (convenience)
    # ------------------------------------------------------------------ #

    @app.get("/tasks", tags=["Tasks"])
    async def list_tasks():
        """List all tasks (id, state, created_at)."""
        tasks = server.task_store._tasks
        return [
            {
                "id": t.id,
                "state": t.status.state,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
            }
            for t in tasks.values()
        ]

    return app


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
        stream=sys.stderr,
    )
    app = create_app()
    uvicorn.run(
        app,
        host=config.A2A_HOST,
        port=config.A2A_PORT,
        log_level="info",
    )


if __name__ == "__main__":
    main()
