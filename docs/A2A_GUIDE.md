# A2A (Agent-to-Agent) Protocol Guide

## What is A2A?

A2A (Agent-to-Agent) is Google's open protocol for enabling AI agents to communicate with each other. It defines a standard HTTP API + SSE streaming model for:
- **Discovery**: `/.well-known/agent.json` (Agent Card)
- **Task submission**: POST /tasks
- **Streaming events**: GET /tasks/{id}/events (Server-Sent Events)
- **Status polling**: GET /tasks/{id}

The UA Network Intelligence A2A server exposes the full multi-agent system as a compliant A2A endpoint at `http://localhost:8765`.

---

## Starting the A2A Server

```bash
# Option 1: Direct module
python -m a2a.server

# Option 2: Uvicorn (production)
uvicorn a2a.server:create_app --factory --host 0.0.0.0 --port 8765 --workers 2

# With Claude API
ANTHROPIC_API_KEY=sk-ant-... USE_MOCK_LLM=false python -m a2a.server
```

---

## Agent Card

Discover the agent's capabilities:

```bash
curl http://localhost:8765/.well-known/agent.json
```

Response:
```json
{
  "name": "UA Network Intelligence Agent",
  "description": "Multi-agent system for United Airlines network operations",
  "version": "1.0.0",
  "url": "http://localhost:8765",
  "capabilities": [
    {
      "name": "network_planning",
      "description": "Route analysis, fleet assignment, schedule gap detection",
      "input_modes": ["text"],
      "output_modes": ["text", "data"]
    },
    {
      "name": "disruption_analysis",
      "description": "IROPS assessment, cascade impact, mitigation recommendations"
    },
    {
      "name": "analytics_insights",
      "description": "KPI dashboards, anomaly detection, OTP and load-factor trends"
    }
  ],
  "skills": [
    {"id": "analyze_route", "name": "Analyze Route Performance"},
    {"id": "assess_disruption", "name": "Assess Disruption Impact"},
    {"id": "executive_summary", "name": "Generate Executive Summary"},
    {"id": "detect_anomalies", "name": "Detect Network Anomalies"},
    {"id": "optimize_schedule", "name": "Optimize Flight Schedule"}
  ]
}
```

---

## Submitting a Task

```bash
curl -X POST http://localhost:8765/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "message": {
      "parts": [
        {
          "type": "text",
          "content": "Which routes are underperforming and should be reviewed for frequency reduction?"
        }
      ]
    },
    "metadata": {"source": "external-agent", "priority": "high"}
  }'
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": {
    "state": "submitted",
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "messages": [
    {
      "id": "msg-001",
      "role": "user",
      "parts": [{"type": "text", "content": "Which routes are underperforming..."}],
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

## Polling Task Status

```bash
curl http://localhost:8765/tasks/550e8400-e29b-41d4-a716-446655440000
```

Response (when complete):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": {"state": "completed"},
  "messages": [
    {"role": "user", "parts": [{"type": "text", "content": "..."}]},
    {
      "role": "agent",
      "parts": [
        {"type": "text", "content": "5 routes flagged for review..."},
        {"type": "data", "content": {"routes": [...], "confidence": 0.87}}
      ]
    }
  ],
  "artifacts": [
    {
      "type": "analysis",
      "data": {"underperforming_routes": [...]},
      "tool_calls": ["get_underperforming_routes", "get_route_performance"]
    }
  ]
}
```

---

## Streaming Task Events (SSE)

```bash
curl -N http://localhost:8765/tasks/550e8400-e29b-41d4-a716-446655440000/events
```

Event stream:
```
event: status
data: {"state": "working", "message": "Routing to specialist agent…"}

event: artifact
data: {"type": "analysis", "data": {...}, "tool_calls": [...]}

event: status
data: {"state": "completed"}

event: done
data: {}
```

---

## Python Client Example

```python
import httpx
import json

BASE_URL = "http://localhost:8765"

# Submit task
response = httpx.post(f"{BASE_URL}/tasks", json={
    "message": {
        "parts": [{"type": "text", "content": "Assess the ORD weather disruption impact"}]
    }
})
task_id = response.json()["id"]
print(f"Task submitted: {task_id}")

# Stream events
with httpx.stream("GET", f"{BASE_URL}/tasks/{task_id}/events") as stream:
    for line in stream.iter_lines():
        if line.startswith("data:"):
            data = json.loads(line[5:])
            print("Event:", data)

# Get final result
result = httpx.get(f"{BASE_URL}/tasks/{task_id}").json()
print("Final state:", result["status"]["state"])
print("Agent response:", result["messages"][-1]["parts"][0]["content"])
```

---

## Cancelling a Task

```bash
curl -X POST http://localhost:8765/tasks/550e8400-e29b-41d4-a716-446655440000/cancel
```

---

## Task States

| State | Description |
|-------|-------------|
| `submitted` | Task received, not yet started |
| `working` | Orchestrator routing and agents processing |
| `completed` | Full response available in messages + artifacts |
| `failed` | An error occurred; check messages for details |
| `cancelled` | Cancelled by client request |

---

## A2A vs. MCP — When to Use Which

| Criterion | MCP | A2A |
|-----------|-----|-----|
| Primary consumer | Claude Desktop | Other AI agents or services |
| Transport | stdio (JSON-RPC) | HTTP (REST + SSE) |
| Session model | Stateless per-call | Stateful tasks with history |
| Streaming | Not required | First-class SSE streaming |
| Authentication | None (local) | Extensible schemes |
| Discovery | Prompt injection | /.well-known/agent.json |
| Best for | Claude Desktop integration | Agent-to-agent automation |

Use **MCP** when connecting to Claude Desktop or other MCP clients locally.
Use **A2A** when exposing the system to other agents, orchestrators, or automation pipelines over the network.

---

## Connecting Agent-to-Agent

To connect another AI agent to the UA Network Intelligence agent:

1. Fetch the agent card from `/.well-known/agent.json`
2. Submit tasks via `POST /tasks` with a message in A2A format
3. Poll `GET /tasks/{id}` or stream `GET /tasks/{id}/events`
4. Extract the agent response from `messages[-1].parts[0].content`

This enables multi-agent workflows where, for example, a capacity planning agent calls the UA Network Intelligence agent to get disruption context before making fleet decisions.

---

## Health Check

```bash
curl http://localhost:8765/health
# {"status": "ok", "agent": "UA Network Intelligence Agent"}
```

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/.well-known/agent.json` | Agent Card discovery |
| GET | `/health` | Health check |
| POST | `/tasks` | Submit a new task |
| GET | `/tasks` | List all tasks |
| GET | `/tasks/{id}` | Get task details |
| POST | `/tasks/{id}/cancel` | Cancel a task |
| GET | `/tasks/{id}/events` | SSE event stream |
