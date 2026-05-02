"""
United Airlines Network Intelligence — MCP Server

Implements the Model Context Protocol (MCP) over stdio transport so that
Claude Desktop and other MCP clients can directly call all 15 airline
planning tools without going through the Streamlit UI.

Protocol: JSON-RPC 2.0  |  Transport: stdio (line-delimited)

Supported MCP methods:
  initialize          — capability handshake
  tools/list          — enumerate all 15 registered tools
  tools/call          — invoke any tool with validated arguments
  resources/list      — expose live data snapshots as MCP resources
  resources/read      — read a specific resource
  prompts/list        — expose canned analytical prompts
  prompts/get         — retrieve a specific prompt

Run directly:
    python mcp/mcp_server.py

Or integrate with Claude Desktop (claude_desktop_config.json):
    {
      "mcpServers": {
        "ua-network-intelligence": {
          "command": "python",
          "args": ["/path/to/Airlines/mcp/mcp_server.py"]
        }
      }
    }
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, Dict, List, Optional

from config import MCP_SERVER_NAME, MCP_SERVER_VERSION, MCP_SERVER_DESCRIPTION
from data.store import DataStore
from agents.network_planning import NetworkPlanningAgent
from agents.disruption_analysis import DisruptionAnalysisAgent
from agents.analytics_insights import AnalyticsInsightsAgent
from mcp.context_store import MCPContextStore
from mcp.tool_registry import MCPToolRegistry
from llm.mock_llm import MockLLM

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool schemas — JSON Schema for each of the 15 airline tools
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: List[Dict[str, Any]] = [
    # ---- Network Planning -----------------------------------------------
    {
        "name": "get_route_demand",
        "description": (
            "Retrieve route demand score, revenue index, competition level, "
            "load factor, and on-time performance for a city-pair route."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "Origin airport IATA code (e.g. ORD)",
                },
                "dest": {
                    "type": "string",
                    "description": "Destination airport IATA code (e.g. LAX)",
                },
            },
            "required": ["origin", "dest"],
        },
    },
    {
        "name": "get_schedule_conflicts",
        "description": (
            "Find all gate conflicts — flights sharing the same gate and airport "
            "with fewer than 45 minutes between departures."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "suggest_frequency_change",
        "description": (
            "Get a data-driven frequency change recommendation (INCREASE / "
            "MAINTAIN / DECREASE) for a route based on demand and load factor."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "route_id": {
                    "type": "string",
                    "description": "Route identifier in ORIGIN-DEST format (e.g. ORD-LAX)",
                }
            },
            "required": ["route_id"],
        },
    },
    {
        "name": "get_underperforming_routes",
        "description": (
            "Identify routes with demand score < 0.30 or average load factor < 0.60 "
            "that may require strategic review or service changes."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "optimize_aircraft_assignment",
        "description": (
            "Recommend the optimal aircraft type for a route based on distance, "
            "required range, and passenger demand."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "route_id": {
                    "type": "string",
                    "description": "Route identifier (e.g. ORD-LAX)",
                }
            },
            "required": ["route_id"],
        },
    },
    # ---- Disruption Analysis --------------------------------------------
    {
        "name": "simulate_gate_closure",
        "description": (
            "Model the operational impact of closing a specific gate: "
            "find affected flights and suggest reassignments to nearby gates."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "gate_id": {
                    "type": "string",
                    "description": "Gate identifier (e.g. C-12)",
                },
                "airport": {
                    "type": "string",
                    "description": "Airport IATA code (e.g. ORD)",
                },
            },
            "required": ["gate_id", "airport"],
        },
    },
    {
        "name": "simulate_weather_event",
        "description": (
            "Calculate cascading delay impacts of a weather disruption at one or more "
            "airports, including estimated passenger impact and downstream flight delays."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "affected_airports": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of airport IATA codes affected",
                },
                "severity": {
                    "type": "string",
                    "enum": ["Low", "Medium", "High", "Critical"],
                    "description": "Disruption severity level",
                },
                "duration_hours": {
                    "type": "number",
                    "description": "Estimated disruption duration in hours",
                },
            },
            "required": ["affected_airports", "severity", "duration_hours"],
        },
    },
    {
        "name": "simulate_aircraft_swap",
        "description": (
            "Check feasibility of swapping the aircraft on a specific flight "
            "with another tail number, including range and capacity validation."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "flight_number": {
                    "type": "string",
                    "description": "Flight number (e.g. UA1234)",
                },
                "new_tail": {
                    "type": "string",
                    "description": "Replacement tail number (e.g. N12345)",
                },
            },
            "required": ["flight_number", "new_tail"],
        },
    },
    {
        "name": "calculate_pax_impact",
        "description": (
            "Estimate total passenger impact (stranded, delayed, rebooked) "
            "from a disruption scenario."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "disruption_id": {
                    "type": "string",
                    "description": "Disruption identifier",
                }
            },
            "required": ["disruption_id"],
        },
    },
    {
        "name": "suggest_mitigation",
        "description": (
            "Generate prioritized IROPS mitigation actions for an active disruption, "
            "including rebooking strategies, crew actions, and communication steps."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "disruption_id": {
                    "type": "string",
                    "description": "Disruption identifier",
                }
            },
            "required": ["disruption_id"],
        },
    },
    # ---- Analytics & Insights -------------------------------------------
    {
        "name": "compute_otd_summary",
        "description": (
            "Compute on-time departure (OTD) performance metrics by hub airport, "
            "including delay distribution and top delay causes."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "compute_load_factor_trends",
        "description": (
            "Analyse load factor trends across all routes, flagging routes with "
            "high load (>90%) and low load (<65%) for capacity review."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "flag_anomalies",
        "description": (
            "Detect network anomalies: excessive delays, abnormally low load factors, "
            "unusual cancellation rates, and gate conflict clusters."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "generate_executive_summary",
        "description": (
            "Generate a concise executive-level network health summary with KPIs, "
            "operational highlights, active disruptions, and priority actions."
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "compare_routes",
        "description": (
            "Side-by-side comparison of two routes across demand, revenue, "
            "load factor, OTP, and competitive positioning."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "route_a": {
                    "type": "string",
                    "description": "First route ID (e.g. ORD-LAX)",
                },
                "route_b": {
                    "type": "string",
                    "description": "Second route ID (e.g. IAH-JFK)",
                },
            },
            "required": ["route_a", "route_b"],
        },
    },
]

# ---------------------------------------------------------------------------
# Canned prompts — analytical prompts exposed through the MCP prompts API
# ---------------------------------------------------------------------------

CANNED_PROMPTS = [
    {
        "name": "network_health_check",
        "description": "Generate a full network health report with all KPIs",
        "arguments": [],
    },
    {
        "name": "disruption_triage",
        "description": "Triage active disruptions by passenger impact and severity",
        "arguments": [],
    },
    {
        "name": "route_opportunity_scan",
        "description": "Identify the top 5 route optimization opportunities",
        "arguments": [],
    },
    {
        "name": "fleet_utilization_review",
        "description": "Review aircraft utilization and maintenance readiness",
        "arguments": [],
    },
]


class MCPServer:
    """MCP Server implementing JSON-RPC 2.0 over stdio.

    The server initialises the full multi-agent stack once and reuses it
    across all requests, keeping tool execution fast.

    Protocol lifecycle:
        Client → ``initialize``
        Server → capabilities response
        Client → ``tools/list`` | ``tools/call`` | ``resources/list`` | …
        Server → responses
        Client → ``shutdown`` (optional)
    """

    def __init__(self) -> None:
        self._initialized = False
        self._setup_agents()

    def _setup_agents(self) -> None:
        """Initialise the full agent stack (shared with Streamlit UI)."""
        context_store = MCPContextStore()
        tool_registry = MCPToolRegistry()
        llm = MockLLM()  # MCP server uses mock by default; swap to ClaudeLLM if API key present
        data_store = DataStore.get()

        self.network_agent = NetworkPlanningAgent(
            context_store=context_store,
            tool_registry=tool_registry,
            llm=llm,
            data_store=data_store,
        )
        self.disruption_agent = DisruptionAnalysisAgent(
            context_store=context_store,
            tool_registry=tool_registry,
            llm=llm,
            data_store=data_store,
        )
        self.analytics_agent = AnalyticsInsightsAgent(
            context_store=context_store,
            tool_registry=tool_registry,
            llm=llm,
            data_store=data_store,
        )
        self.network_agent.register_tools()
        self.disruption_agent.register_tools()
        self.analytics_agent.register_tools()
        self.tool_registry = tool_registry
        self.data_store = data_store
        logger.info("MCP agent stack ready — %d tools registered", len(tool_registry))

    # ------------------------------------------------------------------ #
    # JSON-RPC dispatch
    # ------------------------------------------------------------------ #

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a JSON-RPC 2.0 request and return a response dict."""
        req_id = request.get("id")
        method = request.get("method", "")
        params = request.get("params", {})

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_tools_list()
            elif method == "tools/call":
                result = self._handle_tools_call(params)
            elif method == "resources/list":
                result = self._handle_resources_list()
            elif method == "resources/read":
                result = self._handle_resources_read(params)
            elif method == "prompts/list":
                result = self._handle_prompts_list()
            elif method == "prompts/get":
                result = self._handle_prompts_get(params)
            elif method == "shutdown":
                result = {}
            else:
                return self._error_response(req_id, -32601, f"Method not found: {method}")

            return {"jsonrpc": "2.0", "id": req_id, "result": result}

        except Exception as exc:
            logger.exception("Error handling method %s", method)
            return self._error_response(req_id, -32603, str(exc))

    # ------------------------------------------------------------------ #
    # Method handlers
    # ------------------------------------------------------------------ #

    def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._initialized = True
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
            "serverInfo": {
                "name": MCP_SERVER_NAME,
                "version": MCP_SERVER_VERSION,
                "description": MCP_SERVER_DESCRIPTION,
            },
        }

    def _handle_tools_list(self) -> Dict[str, Any]:
        return {"tools": TOOL_SCHEMAS}

    def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        tool_name: str = params.get("name", "")
        arguments: Dict[str, Any] = params.get("arguments", {})

        if not self.tool_registry.has(tool_name):
            raise ValueError(f"Unknown tool: {tool_name}")

        result = self.tool_registry.invoke(tool_name, **arguments)
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2, default=str),
                }
            ],
            "isError": False,
        }

    def _handle_resources_list(self) -> Dict[str, Any]:
        return {
            "resources": [
                {
                    "uri": "ua://flights/summary",
                    "name": "Flight Summary",
                    "description": "Live summary of all 200 flights (status, delays, load factors)",
                    "mimeType": "application/json",
                },
                {
                    "uri": "ua://routes/all",
                    "name": "All Routes",
                    "description": "All 28 routes with demand scores and revenue indices",
                    "mimeType": "application/json",
                },
                {
                    "uri": "ua://disruptions/active",
                    "name": "Active Disruptions",
                    "description": "Currently active disruptions with severity and passenger impact",
                    "mimeType": "application/json",
                },
                {
                    "uri": "ua://network/kpis",
                    "name": "Network KPIs",
                    "description": "Key performance indicators: OTP, load factor, completion factor",
                    "mimeType": "application/json",
                },
            ]
        }

    def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        uri: str = params.get("uri", "")

        if uri == "ua://flights/summary":
            df = self.data_store.flights
            summary = {
                "total_flights": len(df),
                "on_time": int((df["status"] == "On Time").sum()),
                "delayed": int((df["status"] == "Delayed").sum()),
                "cancelled": int((df["status"] == "Cancelled").sum()),
                "avg_delay_minutes": round(float(df["delay_minutes"].mean()), 1),
                "avg_load_factor": round(float(df["load_factor"].mean()), 3),
            }
            content = json.dumps(summary, indent=2)

        elif uri == "ua://routes/all":
            routes = self.data_store.routes[
                ["route_id", "origin", "destination", "demand_score",
                 "revenue_index", "competition_level", "frequency_weekly"]
            ].to_dict(orient="records")
            content = json.dumps(routes, indent=2, default=str)

        elif uri == "ua://disruptions/active":
            disruptions = self.data_store.disruptions.to_dict(orient="records")
            content = json.dumps(disruptions, indent=2, default=str)

        elif uri == "ua://network/kpis":
            flights = self.data_store.flights
            kpis = {
                "otp_pct": round(float((flights["status"] == "On Time").mean()) * 100, 1),
                "avg_load_factor_pct": round(float(flights["load_factor"].mean()) * 100, 1),
                "completion_factor_pct": round(
                    float((flights["status"] != "Cancelled").mean()) * 100, 1
                ),
                "avg_delay_minutes": round(float(flights["delay_minutes"].mean()), 1),
                "total_routes": len(self.data_store.routes),
                "active_aircraft": int(
                    (self.data_store.aircraft["status"] == "Active").sum()
                ),
            }
            content = json.dumps(kpis, indent=2)

        else:
            raise ValueError(f"Unknown resource URI: {uri}")

        return {
            "contents": [
                {
                    "uri": uri,
                    "mimeType": "application/json",
                    "text": content,
                }
            ]
        }

    def _handle_prompts_list(self) -> Dict[str, Any]:
        return {"prompts": CANNED_PROMPTS}

    def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name: str = params.get("name", "")

        prompt_messages: Dict[str, List[Dict]] = {
            "network_health_check": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            "Please run a comprehensive network health check using the "
                            "compute_otd_summary, compute_load_factor_trends, flag_anomalies, "
                            "and generate_executive_summary tools. Present a structured report "
                            "with KPIs, highlights, concerns, and priority actions."
                        ),
                    },
                }
            ],
            "disruption_triage": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            "Review all active disruptions and triage them by passenger impact. "
                            "For each disruption: calculate passenger impact, suggest mitigations, "
                            "and assign a response priority (P1/P2/P3). Present a triage table."
                        ),
                    },
                }
            ],
            "route_opportunity_scan": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            "Scan all routes to find the top 5 optimization opportunities. "
                            "Use get_underperforming_routes, compute_load_factor_trends, and "
                            "suggest_frequency_change. Rank opportunities by revenue potential."
                        ),
                    },
                }
            ],
            "fleet_utilization_review": [
                {
                    "role": "user",
                    "content": {
                        "type": "text",
                        "text": (
                            "Review current fleet utilization across all aircraft types. "
                            "Identify under-utilized aircraft, maintenance bottlenecks, "
                            "and mismatched assignments. Recommend rebalancing actions."
                        ),
                    },
                }
            ],
        }

        messages = prompt_messages.get(name)
        if messages is None:
            raise ValueError(f"Unknown prompt: {name}")

        return {
            "description": next(
                (p["description"] for p in CANNED_PROMPTS if p["name"] == name), ""
            ),
            "messages": messages,
        }

    @staticmethod
    def _error_response(
        req_id: Any, code: int, message: str
    ) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }


# ---------------------------------------------------------------------------
# Stdio event loop
# ---------------------------------------------------------------------------

async def _stdio_loop(server: MCPServer) -> None:
    """Read line-delimited JSON-RPC from stdin, write responses to stdout."""
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_event_loop()
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    writer_transport, writer_protocol = await loop.connect_write_pipe(
        asyncio.BaseProtocol, sys.stdout
    )
    writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, loop)

    while True:
        try:
            line = await reader.readline()
        except Exception:
            break
        if not line:
            break

        line = line.decode("utf-8").strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }
        else:
            response = server.handle_request(request)

        out = json.dumps(response) + "\n"
        writer.write(out.encode("utf-8"))
        await writer.drain()


def main() -> None:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    server = MCPServer()
    try:
        asyncio.run(_stdio_loop(server))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
