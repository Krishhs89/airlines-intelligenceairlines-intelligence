# MCP (Model Context Protocol) Guide

## What is MCP?

MCP is an open standard by Anthropic that lets AI models (like Claude Desktop) discover and call external tools, read resources, and use canned prompts via a JSON-RPC 2.0 protocol over stdio. It is the "USB-C of AI integrations."

The UA Network Intelligence MCP server exposes all 15 airline planning tools, 4 data resources, and 4 analytical prompt templates to any MCP-compatible client.

---

## Architecture

```
Claude Desktop / MCP Client
        │
        │  JSON-RPC 2.0 over stdin/stdout
        │
┌───────▼────────────────────────────────┐
│         mcp/mcp_server.py              │
│                                        │
│  tools/list    — list 15 tools         │
│  tools/call    — invoke any tool       │
│  resources/list — list 4 UA resources  │
│  resources/read — fetch resource data  │
│  prompts/list  — list 4 prompts        │
│  prompts/get   — get prompt template   │
└───────┬────────────────────────────────┘
        │
┌───────▼────────────────────────────────┐
│        OrchestratorAgent.setup()       │
│  (creates all agents + registers tools)│
└────────────────────────────────────────┘
```

---

## Starting the MCP Server

```bash
# From the project root
python mcp/mcp_server.py
```

The server reads from stdin and writes to stdout (no network port needed).

---

## Claude Desktop Integration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ua-network-intelligence": {
      "command": "python",
      "args": ["/path/to/Airlines/mcp/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "USE_MOCK_LLM": "false"
      }
    }
  }
}
```

After restarting Claude Desktop, the tools appear automatically in the Claude interface.

---

## Exposed Tools (15 total)

### Network Planning (5)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `get_route_performance` | Route metrics with demand/revenue/OTP | `airport` (optional filter) |
| `get_underperforming_routes` | Routes below demand threshold | `threshold` (default 0.5) |
| `get_gate_conflicts` | Gate scheduling conflicts by hub | `hub` (optional) |
| `get_fleet_utilization` | Aircraft utilization rates by type | — |
| `find_schedule_gaps` | Connection opportunities and gaps | `hub` (optional) |

### Disruption Analysis (5)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `get_active_disruptions` | All active disruptions with severity | `severity` filter (optional) |
| `get_disruption_impact` | Passenger and revenue impact | `disruption_id` (optional) |
| `get_cancellation_candidates` | Flights ranked for cancellation | `threshold` (load factor) |
| `get_aircraft_swap_options` | Available spare aircraft | `required_type` (optional) |
| `simulate_disruption_scenario` | What-if disruption modeling | `disruption_type`, `severity`, `affected_airports`, `duration_hours` |

### Analytics Insights (5)

| Tool | Description | Key Parameters |
|------|-------------|----------------|
| `get_network_kpis` | Headline KPIs: OTP, load factor, delays | — |
| `get_hub_performance` | Per-hub operational metrics | `hub` (optional) |
| `get_load_factor_trends` | Load factor by route/aircraft | `aircraft_type` (optional) |
| `detect_delay_anomalies` | Statistical outliers in delay data | `threshold_minutes` |
| `get_revenue_insights` | Revenue index and yield by route | `top_n` (default 10) |

---

## Exposed Resources (4)

Resources are read-only data snapshots that MCP clients can inspect:

| URI | Description |
|-----|-------------|
| `ua://flights/summary` | Aggregated flight statistics |
| `ua://routes/all` | Full route table with metrics |
| `ua://disruptions/active` | Active disruptions with severity |
| `ua://network/kpis` | Real-time KPI snapshot |

---

## Canned Prompts (4)

Pre-built analytical prompt templates that Claude can use:

| Name | Description |
|------|-------------|
| `network_health_check` | Full network status assessment |
| `disruption_triage` | Rapid IROPS assessment and prioritization |
| `route_opportunity_scan` | Revenue opportunity identification |
| `fleet_utilization_review` | Fleet efficiency and maintenance analysis |

---

## JSON-RPC 2.0 Protocol Examples

### Initialize
```json
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
```

### List Tools
```json
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
```

### Call a Tool
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "simulate_disruption_scenario",
    "arguments": {
      "disruption_type": "Weather",
      "severity": "Critical",
      "affected_airports": ["ORD"],
      "duration_hours": 8
    }
  }
}
```

### Read a Resource
```json
{"jsonrpc":"2.0","id":4,"method":"resources/read","params":{"uri":"ua://flights/summary"}}
```

### Get a Prompt
```json
{"jsonrpc":"2.0","id":5,"method":"prompts/get","params":{"name":"disruption_triage","arguments":{}}}
```

---

## Testing the MCP Server

```bash
# Send initialize + tools/list via stdin
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python mcp/mcp_server.py

# Or interactively with a pipe
python mcp/mcp_server.py <<EOF
{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}
{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}
EOF
```

---

## Extending the MCP Server

To add a new tool:
1. Implement the tool function in the appropriate agent class
2. Register it with `tool_registry.register(name, fn)` in `register_tools()`
3. Add a JSON Schema entry to `TOOL_SCHEMAS` in `mcp_server.py`
4. The tool is automatically discoverable via `tools/list`

To add a new resource:
1. Add a key-value pair to `RESOURCE_DESCRIPTIONS` in `mcp_server.py`
2. Add a data-fetch case in `_handle_resource_read()`

To add a new prompt:
1. Add an entry to `CANNED_PROMPTS` in `mcp_server.py`
