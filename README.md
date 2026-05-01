# UA Network Intelligence — Multi-Agent System

A Streamlit-based multi-agent system for United Airlines network planning, flight scheduling, and operational scenario analysis. Built using Model Context Protocol (MCP) architecture with supervised agents.

## Architecture

- **Orchestrator Agent** — Routes queries, classifies intent, manages session context
- **Network Planning Agent** — Route demand analysis, schedule optimization, aircraft assignment
- **Disruption Analysis Agent** — What-if scenarios, cascade delay modeling, mitigation recommendations
- **Analytics & Insights Agent** — OTD summaries, load factor trends, anomaly detection, executive reports

## Tech Stack

- **Frontend**: Streamlit with Plotly visualizations
- **Agent Framework**: Custom multi-agent system with MCP protocol
- **Data**: Synthetic airline data (200 flights, 80 aircraft, 28 routes, 40 gates)
- **LLM**: Mock LLM (swappable to AWS Bedrock Claude for production)

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Project Structure

```
├── app.py                    # Streamlit entry point
├── config.py                 # Global constants & presets
├── agents/                   # Multi-agent layer
│   ├── orchestrator.py       # Intent routing & coordination
│   ├── network_planning.py   # Route & schedule analysis
│   ├── disruption_analysis.py # What-if scenario modeling
│   └── analytics_insights.py # Metrics & summarization
├── mcp/                      # Model Context Protocol
│   ├── context_store.py      # Shared memory across agents
│   ├── tool_registry.py      # Central tool catalog
│   └── protocol.py           # Message protocol
├── data/                     # Data layer
│   ├── models.py             # Pydantic domain models
│   ├── synthetic_generator.py # Realistic data generation
│   └── store.py              # DataStore singleton
├── llm/                      # LLM abstraction
│   └── mock_llm.py           # Template-based mock (→ Bedrock)
└── ui/                       # Streamlit UI
    ├── sidebar.py
    ├── pages/                # 5 app pages
    └── components/           # Reusable widgets
```

## Key Features

- **15 registered agent tools** performing real pandas computations
- **MCP message tracing** — full observability into agent communication
- **Disruption simulator** — model gate closures, weather events, aircraft swaps
- **Network map** — interactive Plotly geo visualization of route network
- **Executive summaries** — automated insight generation

## Productionization Path

See [INTERVIEW_PREP.md](INTERVIEW_PREP.md) for the full 3-phase (15-month) production roadmap targeting AWS Bedrock, Kinesis, DynamoDB, and ECS Fargate.
