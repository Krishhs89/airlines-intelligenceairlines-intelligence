# UA Network Intelligence — System Architecture

## Overview

The UA Network Intelligence system is a production-grade, multi-agent AI platform for United Airlines network operations. It combines Anthropic Claude (claude-opus-4-7) with a structured multi-agent architecture, MCP (Model Context Protocol), A2A (Agent-to-Agent), guardrails, and a Streamlit real-time operations dashboard.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        User Interfaces                                  │
│  Streamlit UI (app.py)   │  Claude Desktop (MCP)   │  External Agents   │
│                          │                         │  (A2A Protocol)    │
└──────────────────────────┼─────────────────────────┼────────────────────┘
                           │                         │
                    ┌──────▼──────────────────────────▼──────┐
                    │         OrchestratorAgent              │
                    │   Intent Classification + Routing      │
                    │   Guardrail Validation (in/out)        │
                    └──────┬──────────┬──────────────┬───────┘
                           │          │              │
               ┌───────────▼──┐  ┌───▼──────────┐  ┌▼──────────────────┐
               │  Network      │  │  Disruption   │  │  Analytics        │
               │  Planning     │  │  Analysis     │  │  Insights         │
               │  Agent        │  │  Agent        │  │  Agent            │
               └──────┬────────┘  └───┬───────────┘  └──────┬────────────┘
                      │               │                      │
               ┌──────▼───────────────▼──────────────────────▼────────────┐
               │                MCP Layer (Shared)                         │
               │   MCPContextStore │ MCPToolRegistry │ MCPMessage/Response │
               └──────────────────────────┬────────────────────────────────┘
                                          │
                              ┌───────────▼────────────┐
                              │   DataStore (Singleton) │
                              │   200 flights           │
                              │   28 routes             │
                              │   80 aircraft           │
                              │   40 gates              │
                              │   10 disruptions        │
                              └────────────────────────┘
```

---

## Component Breakdown

### 1. Orchestrator Agent (`agents/orchestrator.py`)

- **Role**: Top-level router and guardrail enforcer
- **Intent Classification**: Keyword matching (priority) → LLM classify_intent fallback
- **Routing**: Maps intents to one of 3 specialist agents
- **Guardrails**: Validates input before dispatch; sanitizes PII; blocks unsafe content
- **LLM**: Uses `get_llm()` factory — ClaudeLLM if `ANTHROPIC_API_KEY` is set, else MockLLM

### 2. Specialist Agents

| Agent | File | Tools | Domain |
|-------|------|-------|--------|
| NetworkPlanningAgent | `agents/network_planning.py` | 5 | Route performance, fleet, schedule gaps |
| DisruptionAnalysisAgent | `agents/disruption_analysis.py` | 5 | IROPS, cancellations, aircraft swaps |
| AnalyticsInsightsAgent | `agents/analytics_insights.py` | 5 | KPIs, anomalies, load factors, revenue |

All agents inherit from `BaseAgent` which provides:
- `_call_tool()` — invokes registered MCP tools
- `_build_response()` — constructs standard MCPResponse
- `_store_result()` / `_get_context()` — shared context management
- `_log_trace()` — step-by-step trace recording

### 3. MCP Layer (`mcp/`)

| Component | Purpose |
|-----------|---------|
| `MCPContextStore` | Thread-safe TTL-based key-value context store |
| `MCPToolRegistry` | Tool registration, invocation, and listing |
| `MCPMessage` | Typed message with sender/recipient/intent/payload/trace |
| `MCPResponse` | Typed response with result/insight/confidence/tool_calls |
| `mcp_server.py` | Standalone JSON-RPC 2.0 stdio server for Claude Desktop |

### 4. LLM Integration (`llm/`)

| Class | Model | Use Case |
|-------|-------|----------|
| `ClaudeLLM` | claude-opus-4-7 | Real API (adaptive thinking, prompt caching, streaming) |
| `MockLLM` | — | Offline / testing (deterministic, no API calls) |

**ClaudeLLM features:**
- `thinking={"type": "adaptive"}` — Claude decides when/how much to think
- System prompt cached with `cache_control: {"type": "ephemeral"}` — up to 90% cost savings
- `classify_intent()` uses a fast single call with thinking disabled (max_tokens=15)
- `stream_from_query()` yields token-by-token for real-time Streamlit updates

### 5. A2A Protocol (`a2a/`)

Google's Agent-to-Agent protocol over HTTP+SSE:
- `GET /.well-known/agent.json` — Agent Card (capabilities, skills, auth)
- `POST /tasks` — Submit query, returns task ID
- `GET /tasks/{id}` — Poll task status and messages
- `GET /tasks/{id}/events` — SSE stream of task events
- `POST /tasks/{id}/cancel` — Cancel in-flight task

### 6. Guardrails (`guardrails/`)

Layered safety applied to every query:
1. Rate limiting (sliding 60-second window)
2. Input length enforcement (2000 char default)
3. Content safety (blocked terms for security, competitor info, off-topic)
4. PII detection & redaction (email, phone, SSN, credit card, passport)
5. Output validation (length truncation, low-confidence warning)

### 7. Evaluation Framework (`evaluation/`)

- 10 built-in test cases spanning all 3 agent domains
- Metrics: agent routing accuracy, tool call coverage, keyword coverage, confidence, latency
- Weighted composite score (threshold: 0.6 = pass)
- `EvaluationSuite.report()` produces category breakdown and per-test detail

---

## Data Layer (`data/`)

All data is synthetically generated with a fixed seed (`RANDOM_SEED=42`) for reproducibility.

| Dataset | Count | Key Fields |
|---------|-------|------------|
| Flights | 200 | flight_id, origin, destination, status, load_factor, delay_minutes, aircraft_type |
| Routes | 28 | route_id, origin, destination, demand_score, revenue_index, competition_level |
| Aircraft | 80 | aircraft_id, type, status, hub, maintenance_due |
| Gates | 40 | gate_id, airport, terminal, conflicts |
| Disruptions | 10 | disruption_id, type, severity, affected_airports, passenger_impact |

---

## Configuration (`config.py`)

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_MOCK_LLM` | `true` | Set `false` + API key to use ClaudeLLM |
| `ANTHROPIC_API_KEY` | env | Real Claude API key |
| `A2A_PORT` | `8765` | A2A FastAPI server port |
| `GUARDRAIL_MAX_QUERY_LENGTH` | `2000` | Max input chars |
| `GUARDRAIL_RATE_LIMIT_PER_MINUTE` | `60` | API call rate limit |

---

## Directory Structure

```
Airlines/
├── agents/
│   ├── base_agent.py          # Abstract base with MCP helpers
│   ├── orchestrator.py        # Top-level router + guardrails
│   ├── network_planning.py    # 5 network planning tools
│   ├── disruption_analysis.py # 5 disruption tools
│   └── analytics_insights.py  # 5 analytics tools
├── a2a/
│   ├── protocol.py            # A2A data models (AgentCard, Task, Message)
│   └── server.py              # FastAPI A2A server
├── data/
│   ├── models.py              # Pydantic data models
│   ├── store.py               # DataStore singleton
│   └── synthetic_generator.py # Deterministic synthetic data
├── evaluation/
│   └── evaluator.py           # Metrics, test cases, scoring
├── guardrails/
│   └── validators.py          # Input/output guardrail validators
├── llm/
│   ├── claude_llm.py          # Real Claude API integration
│   └── mock_llm.py            # Offline mock LLM
├── mcp/
│   ├── context_store.py       # TTL key-value store
│   ├── mcp_server.py          # Stdio JSON-RPC 2.0 MCP server
│   ├── protocol.py            # MCPMessage / MCPResponse types
│   └── tool_registry.py       # Tool registration and invocation
├── tests/
│   ├── test_agents.py         # Agent routing and response tests
│   ├── test_tools.py          # All 15 tool invocation tests
│   ├── test_guardrails.py     # Guardrail validation tests
│   └── test_evaluation.py     # Evaluation framework tests
├── ui/
│   ├── components/            # Reusable UI components
│   └── pages/                 # 5 Streamlit pages
├── docs/
│   ├── ARCHITECTURE.md        # This document
│   ├── REAL_WORLD_AIRLINE_OPS.md
│   ├── MCP_GUIDE.md
│   ├── A2A_GUIDE.md
│   └── GUARDRAILS.md
├── app.py                     # Streamlit entry point
└── config.py                  # Global configuration
```

---

## Running the System

### Streamlit UI
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export USE_MOCK_LLM=false
streamlit run app.py
```

### MCP Server (Claude Desktop)
```bash
python mcp/mcp_server.py
```

### A2A Server
```bash
python -m a2a.server
# or
uvicorn a2a.server:create_app --factory --port 8765
```

### Tests
```bash
pytest tests/ -v --cov=. --cov-report=html
# Integration tests (require full agent stack):
pytest tests/ -v -m integration
```

### Evaluation
```python
from agents.orchestrator import OrchestratorAgent
from evaluation.evaluator import EvaluationSuite

orc = OrchestratorAgent.setup()
suite = EvaluationSuite(orc)
results = suite.run()
report = suite.report(results)
print(report["summary"])
```
