# Agent Skills Reference

Complete catalogue of every agent, its tools, inputs, and outputs in the UA Network Intelligence system.

---

## OrchestratorAgent

**File:** [agents/orchestrator.py](agents/orchestrator.py)  
**Role:** Entry point for all user queries. Classifies intent, routes to the right specialist, applies guardrails, and returns a unified response.

| Method | Description |
|--------|-------------|
| `route(user_query)` | Full pipeline: guardrail → intent classify → delegate → guardrail output → return |
| `_classify_intent(query)` | Returns one of: `network_planning`, `disruption_analysis`, `analytics_insights`, `general` |
| `handle(message)` | MCP message handler (wraps `route`) |
| `setup()` | Class-method factory — wires up all sub-agents |

**Intent keywords:**
- `network_planning` — route, schedule, frequency, demand, aircraft assignment, underperforming
- `disruption_analysis` — gate closure, weather, swap, passenger impact, mitigation
- `analytics_insights` — OTD, load factor, anomaly, executive summary, compare routes

---

## NetworkPlanningAgent

**File:** [agents/network_planning.py](agents/network_planning.py)  
**Role:** Analyses route demand, schedule health, and fleet assignment for network optimisation.

| Tool | Signature | What it returns |
|------|-----------|-----------------|
| `get_route_demand` | `(origin: str, dest: str)` | Demand score, revenue index, competition level, great-circle distance, weekly frequency |
| `get_schedule_conflicts` | `()` | Flights sharing a gate within 30 min; lists conflict pairs with overlap minutes |
| `suggest_frequency_change` | `(route_id: str)` | Recommended ±frequency delta based on demand score thresholds |
| `get_underperforming_routes` | `()` | Routes with demand < 0.4 and revenue < 0.5; sorted by composite score |
| `optimize_aircraft_assignment` | `(route_id: str)` | Best-fit aircraft type by range and capacity vs. demand; lists candidates |

**Helper:** `_great_circle_nm(origin, dest)` — haversine distance using IATA coords lookup.

---

## DisruptionAnalysisAgent

**File:** [agents/disruption_analysis.py](agents/disruption_analysis.py)  
**Role:** Simulates operational disruptions and recommends mitigations.

| Tool | Signature | What it returns |
|------|-----------|-----------------|
| `simulate_gate_closure` | `(gate_id: str)` | Affected flights, suggested alternate gates, impact severity |
| `simulate_weather_event` | `(airport: str, severity: str, duration_hours: int)` | Delay cascade, ground-stop candidates, estimated delay minutes per flight |
| `simulate_aircraft_swap` | `(flight_number: str, new_aircraft_type: str)` | Capacity delta, range compatibility check, swap feasibility |
| `calculate_pax_impact` | `(affected_flights: List[str])` | Total passengers affected, connection risk count, rebooking estimate |
| `suggest_mitigation` | `(disruption_type: str, severity: str, affected_flights: List[str])` | Ranked mitigation actions with confidence scores |

**Severity levels:** `low`, `moderate`, `high`, `severe`  
**Disruption types:** `weather`, `gate_closure`, `aircraft_swap`, `mechanical`

---

## AnalyticsInsightsAgent

**File:** [agents/analytics_insights.py](agents/analytics_insights.py)  
**Role:** Computes KPIs, detects anomalies, and generates executive-ready summaries.

| Tool | Signature | What it returns |
|------|-----------|-----------------|
| `compute_otd_summary` | `()` | On-time departure rate, avg delay by route/aircraft/airport, delay distribution |
| `compute_load_factor_trends` | `()` | Mean/median load factor by route, top/bottom 5 routes, trend direction |
| `flag_anomalies` | `()` | Flights/routes outside 2σ on delay or load factor; anomaly type + magnitude |
| `generate_executive_summary` | `()` | Full narrative: OTD, load factor, top issues, recommended actions |
| `compare_routes` | `(route1: str, route2: str)` | Side-by-side: frequency, demand, revenue, load factor, OTD, competition |

---

## Cross-Cutting Infrastructure

### LLM — [llm/claude_llm.py](llm/claude_llm.py)
- `ClaudeLLM`: uses `claude-opus-4-7`, adaptive thinking, prompt caching, streaming
- `MockLLM`: deterministic responses for tests (activated when `USE_MOCK_LLM=true` or no API key)
- `get_llm()` factory selects the right implementation automatically

### MCP Server — [mcp/mcp_server.py](mcp/mcp_server.py)
- JSON-RPC 2.0 over stdio
- Exposes all 15 tools, 4 `ua://` resources, 4 canned prompts
- Run: `python mcp/mcp_server.py`

### A2A Server — [a2a/server.py](a2a/server.py)
- FastAPI at port 8765
- Agent Card at `GET /.well-known/agent.json`
- SSE streaming for long-running tasks
- Run: `python -m a2a.server`

### Guardrails — [guardrails/validators.py](guardrails/validators.py)
- Rate limiting (per user/IP)
- Input length cap
- Content safety (blocked-term list)
- PII redaction (email, phone, SSN patterns)
- Output validation (schema + length)
- Auto-applied in `OrchestratorAgent.route()`

### Evaluation — [evaluation/evaluator.py](evaluation/evaluator.py)
- 9 built-in test cases covering all three agents
- 5 metrics: routing accuracy, tool coverage, keyword coverage, confidence, latency
- `EvaluationSuite.run()` + `.report()` for a full benchmark pass

---

## Tool Quick-Reference (all 15)

| # | Tool | Agent |
|---|------|-------|
| 1 | `get_route_demand(origin, dest)` | NetworkPlanning |
| 2 | `get_schedule_conflicts()` | NetworkPlanning |
| 3 | `suggest_frequency_change(route_id)` | NetworkPlanning |
| 4 | `get_underperforming_routes()` | NetworkPlanning |
| 5 | `optimize_aircraft_assignment(route_id)` | NetworkPlanning |
| 6 | `simulate_gate_closure(gate_id)` | DisruptionAnalysis |
| 7 | `simulate_weather_event(airport, severity, duration_hours)` | DisruptionAnalysis |
| 8 | `simulate_aircraft_swap(flight_number, new_aircraft_type)` | DisruptionAnalysis |
| 9 | `calculate_pax_impact(affected_flights=[])` | DisruptionAnalysis |
| 10 | `suggest_mitigation(disruption_type, severity, affected_flights)` | DisruptionAnalysis |
| 11 | `compute_otd_summary()` | AnalyticsInsights |
| 12 | `compute_load_factor_trends()` | AnalyticsInsights |
| 13 | `flag_anomalies()` | AnalyticsInsights |
| 14 | `generate_executive_summary()` | AnalyticsInsights |
| 15 | `compare_routes(route1, route2)` | AnalyticsInsights |
