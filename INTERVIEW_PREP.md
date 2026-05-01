# Interview Preparation: Senior GenAI / Multi-Agent Architect
## Role: United Airlines (via Insight Global) — Network Intelligence Platform

**Candidate:** Krishna Kumar  
**Date Prepared:** May 1, 2026  
**Demo Project:** UA Network Intelligence — Streamlit Multi-Agent System for Airline Network Planning

---

# SECTION 1: Architecture Walkthrough / Talking Points

## How to Present the Demo in 10–15 Minutes

### Opening Frame (1 minute)
Start with the business problem, not the technology:

> "United operates roughly 500 flights a day across a network of 8 major hubs and dozens of spokes. Network planners, operations controllers, and executives all need different views of the same data — route profitability, disruption cascades, schedule gaps — but they're often pulling from separate systems and building one-off Excel models. I built a working prototype of what a unified AI-powered operations intelligence platform could look like, using a multi-agent architecture with a shared Model Context Protocol layer."

Pause. Let that framing land. Then open the browser.

---

### Step 1: System Overview (2 minutes)
Navigate to the **Dashboard** page. Walk through the fleet health metrics cards:

> "The system initializes one orchestrator agent and three specialist agents — Network Planning, Disruption Analysis, and Analytics & Insights — all sharing a single context store and a central tool registry. Everything the agents know is in one place, and every tool they can call is registered in one place. This is the MCP pattern: a shared communication substrate rather than agents that talk directly to each other and create a tightly coupled mesh."

Point to the flight map showing routes across ORD, IAH, DEN, EWR, LAX, SFO, DCA, and LAS:

> "The data layer is synthetic but production-realistic: 200 flights, 80 aircraft across four fleet types — B737-MAX9, B787-9, B777-200, and A319 — with real IATA codes, real great-circle distances, realistic load factors and OTP distributions, and Pydantic v2 validation on every model. When we swap in Bedrock and hook this to United's actual operational APIs, the agent logic doesn't change — only the data layer and the LLM client."

---

### Step 2: Data Layer (1 minute)
> "The DataStore is a singleton that loads once at startup using a seeded random generator, so every demo run is identical and reproducible. The data generator uses `random.Random(seed=42)` and `numpy.random.default_rng(seed=42)` so we get deterministic distributions that look real — 80% on-time, 12% delayed, 5% cancelled, 3% diverted, and load factors that follow a beta distribution around 0.82. All models are Pydantic v2 with field-level validation — origin and destination are validated as exactly 3 characters, load factor is bounded 0.0 to 1.0, and so on."

---

### Step 3: Agent Design — Orchestrator Pattern (2 minutes)
Navigate to the **Network Planning** page and type a query in the chat: `Analyze route ORD-LAX demand`

> "The orchestrator receives every user query. It runs a two-stage intent classification: first a keyword scan — multi-word phrases like 'gate conflict' take priority over single keywords — and if that produces no match, it falls back to the MockLLM classifier which uses a scoring model across five intent categories. Once it classifies the intent, it builds an MCPMessage envelope and dispatches to the right specialist."

Show the response appearing. Point to the tool call trace:

> "The NetworkPlanningAgent received an MCPMessage with sender='user', recipient='network_planning', intent='network_planning', and the query in the payload. It pattern-matched the IATA pair using a regex, called `get_route_demand(origin='ORD', dest='LAX')` from the tool registry, computed great-circle distance — 1,744 nautical miles — pulled demand score, revenue index, competition level, and actual OTP from the flights DataFrame, then passed the variables to MockLLM to generate the insight text. In production, that MockLLM call becomes `bedrock-runtime.invoke_model` with the Claude 3 Sonnet model ID."

---

### Step 4: MCP Implementation (2 minutes)
Navigate to the **Agent Trace** page:

> "This is the MCP layer made visible. Every MCPMessage has a UUID, a sender, a recipient, an intent, a JSON payload, an optional context reference, a timestamp, and an ordered trace list. Every time an agent processes a step, it appends to that trace — so you can see the full processing path: orchestrator:routing_to:network_planning → network_planning:received → network_planning:tool:get_route_demand(ORD,LAX) → network_planning:complete."

> "The context store is thread-safe — it uses a reentrant lock — and supports TTL-based expiry so ephemeral data like weather events doesn't pollute the session. The tool registry prevents duplicate registration and raises a RuntimeError with the owning agent's name if a tool call fails, so debugging is unambiguous. This is the key architectural principle: agents are loosely coupled through the protocol, not directly wired to each other."

---

### Step 5: Disruption Simulator (2 minutes)
Navigate to the **Disruption Simulator** page. Select the "ORD Winter Storm" preset:

> "This preset models a Critical-severity weather event at ORD with an 8-hour duration. Watch what happens when I run it: the DisruptionAnalysisAgent calls `simulate_weather_event(airport='ORD', severity='Critical', duration_hours=8)`, computes affected flights at both origin and destination, applies the Critical multiplier — 40% cancellation, 80% delayed, 240-minute average delay — then traces downstream to find all other flights operated by the same tail numbers that will cascade-delay. The pax impact is calculated by summing load_factor × capacity per aircraft type. Then it chains to `suggest_mitigation` which produces prioritized IROPS actions — ground stop, mass rebooking, crew reserve activation."

Point to the cascading flight count:

> "That cascade calculation is important: it's not just the flights at ORD. It's the B737s that were supposed to fly ORD→DEN→LAX that now can't depart on time. That's real operational thinking baked into the agent logic."

---

### Step 6: Analytics and Wrap-Up (2 minutes)
Navigate to the **Analytics & Insights** page. Run an executive summary query.

> "The AnalyticsInsightsAgent handles KPI roll-ups, anomaly detection, and trend analysis across the full dataset. In the demo it queries all DataFrames directly; in production this would hit a data warehouse via Athena or Redshift, with the agent managing query construction through registered tools. The agent stores its result in the shared context store so that if a follow-up question comes in — 'which of those anomalous routes had the worst OTP?' — the orchestrator can pass a context_ref to the next agent rather than recomputing the full dataset scan."

Wrap up:

> "What I wanted to demonstrate is that the architecture is production-ready in shape, even if the LLM and data sources are mocked. The agent contract — MCPMessage in, MCPResponse out — is stable. Swapping MockLLM for Bedrock is a one-line change in `OrchestratorAgent.setup()`. Adding a new agent is additive: implement `BaseAgent`, register your tools, and add two lines to the orchestrator's `_agents` dict and `INTENT_MAP`."

---

# SECTION 2: Possible Interview Questions & Detailed Answers

---

## Category 1: Multi-Agent Architecture

### Q1: How did you design the agent communication protocol?

I chose a message-envelope pattern rather than direct function calls between agents. Every interaction produces an `MCPMessage` dataclass with a UUID `message_id`, `sender`, `recipient`, `intent`, an arbitrary `payload` dict, an optional `context_ref` pointing to a prior result in the context store, a UTC timestamp, and an ordered `trace` list. The response side is a symmetric `MCPResponse` with `result`, `insight`, `confidence`, and `tool_calls`.

The reasoning was that a pure function call approach — agent A calling agent B's method directly — creates tight coupling and makes debugging hard because there's no audit trail. The envelope pattern means every agent interaction is inherently logged in the trace, every response is serializable to JSON for persistence, and the same message can be replayed for debugging or testing. In the `BaseAgent._build_response()` method, after constructing the response, we immediately call `self.context_store.push_message(msg, response)` so the full conversation history is always available through `get_conversation_history()`.

For production, I would extend this to use an async message bus — Amazon SQS or EventBridge — so agents can operate concurrently and messages are durable. The dataclass structure maps cleanly to a JSON schema that could be validated against a schema registry.

---

### Q2: Why did you use supervised (orchestrator-controlled) agents rather than fully autonomous agents?

The orchestrator pattern was the right choice for this domain for three reasons. First, airline operations have high stakes: a misrouted query that causes the disruption agent to recommend grounding aircraft that don't need grounding can have real-world consequences. Centralizing control in the orchestrator means every query goes through a single classification and routing step that can be logged, audited, and overridden.

Second, intent ambiguity is real in airline ops. A query like "What should we do about the ORD situation?" could mean route planning, a weather event, or a gate problem. The orchestrator's two-stage classifier — keyword matching first, LLM fallback second — handles this deterministically, and the classification decision is always visible in the trace. A fully autonomous agent would have to negotiate intent with other agents, which adds latency and failure modes.

Third, the current users — network planners, ops controllers — need to trust the system before they'll act on it. An orchestrator that routes visibly and explains which specialist answered is more trustworthy than a blackbox swarm. Once trust is established, we can move specific decision paths toward autonomy with human-in-the-loop approval for high-impact actions like route frequency changes or fleet groundings.

---

### Q3: How do you handle agent failures and fallbacks?

The system has three layers of failure handling. At the tool layer, `MCPToolRegistry.invoke()` wraps every tool call in a try/except and re-raises as `RuntimeError` with the tool name and original exception message, so the calling agent always knows which tool failed and why.

At the agent layer, each specialist's `handle()` method checks for an `"error"` key in the result dict returned by tool calls. If present, the agent constructs an MCPResponse with `confidence=0.3` and an insight string that surfaces the error to the user rather than silently failing. The fallback insight is: "Analysis could not be completed: {error}."

At the LLM layer, insight text generation is wrapped in a try/except so that even if MockLLM (or Bedrock) raises an exception, the agent still returns a structured result dict with a generic insight string like "Network planning analysis complete. 2 tool(s) invoked." The structured data is always returned; the natural language insight is best-effort.

For production, I would add: exponential backoff with jitter for Bedrock API calls (using the `tenacity` library), a circuit breaker pattern at the orchestrator level that falls back to a rule-only mode if Bedrock is unavailable, dead-letter queues for failed async messages, and CloudWatch alarms on agent error rates.

---

### Q4: How would you add a new agent — say, a Crew Scheduling Agent?

The architecture is explicitly designed for additive extension. You would: (1) Create `agents/crew_scheduling.py` implementing `BaseAgent` with a `handle(self, message: MCPMessage) -> MCPResponse` method. (2) Implement the domain tools — check crew rest compliance, find available crew for a route, check pairing constraints — as methods on the class. (3) Call `self.tool_registry.register()` for each tool inside `register_tools()`. (4) In `orchestrator.py`, add `"crew"` and relevant keywords like `"crew"`, `"pairing"`, `"rest time"`, `"duty"` to `INTENT_MAP`, add the agent instance to the `_agents` dict in `__init__`, and instantiate it in `OrchestratorAgent.setup()`.

Nothing in the existing agents changes. The context store, tool registry, and LLM instance are all shared by reference, so the new agent automatically participates in the same context and conversation history. The total change is roughly 150 lines of new code and 8 lines modified in `orchestrator.py`. This is the key benefit of the BaseAgent contract: the orchestrator doesn't need to know what any agent does internally.

---

### Q5: What is the difference between your MCP implementation and standard function calling?

Standard LLM function calling — as implemented in OpenAI's API or Bedrock's Converse API — is a protocol between the LLM and a set of callable functions. The LLM decides which function to call and with what arguments; the application executes it and returns the result; the LLM generates a final response. The LLM is the decision-maker.

My MCP implementation inverts this: the LLM is a component within an agent, not the orchestrator of the system. The `MCPToolRegistry` is the canonical catalog of available tools, independent of any LLM. Agents call tools programmatically — via `self._call_tool("get_route_demand", origin="ORD", dest="LAX")` — based on pattern matching and business logic, and the LLM is only invoked to generate the human-readable insight text from the structured result. This means the system works completely without an LLM (as demonstrated by MockLLM), which is valuable for testing, cost control, and reliability.

In production, I would combine both patterns: the LLM would have access to Bedrock function-calling to invoke tools for complex open-ended queries, while the orchestrator uses the MCP layer for structured, classified queries where latency and determinism matter. The context store then provides cross-call memory that raw function calling lacks.

---

### Q6: How do you manage shared state across agents?

The `MCPContextStore` is the single shared memory layer. It is a thread-safe key-value store backed by a `threading.RLock()` that supports TTL-based expiry. Every agent holds a reference to the same `MCPContextStore` instance (injected at construction in `OrchestratorAgent.setup()`).

Agents write to the context store after every significant computation — for example, `NetworkPlanningAgent` writes `self._store_result(f"network_planning:{message.message_id}", result)` after processing. The orchestrator also writes `last_query`, `last_agent`, and the last response dict so subsequent queries can reference prior context without re-execution.

The `context_ref` field in MCPMessage is the cross-agent reference mechanism: if the orchestrator wants to give the DisruptionAnalysisAgent the route data computed by NetworkPlanningAgent, it sets `context_ref` to the key under which that result was stored, and the DisruptionAnalysisAgent calls `self._get_context(message.context_ref)` to retrieve it.

For production scale, I would replace the in-process dict with DynamoDB (for persistence across sessions and instances) and ElastiCache/Redis (for low-latency reads within a session), with a consistent hashing scheme for the key namespace per session ID.

---

### Q7: How would you implement agent memory and learning?

There are three tiers of memory I would implement for this system. Short-term memory is already present — the `MCPContextStore` holds the full conversation history via `push_message()` and `get_conversation_history()`, so within a session, agents can see prior queries and responses. A follow-up query like "give me more detail on the third route you mentioned" would use `get_conversation_history(last_n=3)` to retrieve the prior context.

Medium-term memory would be a DynamoDB table keyed by `(user_id, session_date)` storing serialized conversation history and key context store entries. At session start, the agent system would reload the prior session's state so a user picking up where they left off doesn't have to re-establish context.

Long-term learning would be achieved through a feedback loop tracked in the data warehouse: every MCPResponse includes a `confidence` score; we would add a thumbs-up/thumbs-down UI element that writes a human rating back to S3 as a JSONL file. Periodically, a fine-tuning job on Bedrock would use high-confidence, positively-rated (query, response) pairs to improve the LLM's domain grounding. Route recommendations that matched actual network planning decisions would be the gold labels.

---

### Q8: How do agents coordinate on complex multi-step queries?

Currently the system handles single-agent dispatch per query. For multi-step coordination, I designed the `context_ref` field in MCPMessage to enable a handoff pattern. For example, a query like "Find underperforming routes and model what a weather event at their hubs would do to network performance" requires: (1) NetworkPlanningAgent identifies underperforming routes, (2) DisruptionAnalysisAgent runs weather simulations for those hub airports, (3) AnalyticsInsightsAgent aggregates the combined impact.

The orchestrator would implement this as a sequential dispatch chain: call NetworkPlanningAgent, store the result in context, build a second MCPMessage with `context_ref` pointing to that result, call DisruptionAnalysisAgent which reads the underperforming route list from context and runs simulations for each hub, store those results, then call AnalyticsInsightsAgent with a `context_ref` to both prior results for the aggregated report.

For production, I would implement this as a LangGraph StateGraph or a custom DAG executor where each node is an agent and edges carry the `context_ref` forward. The orchestrator would declare the DAG at query classification time based on the complexity of the intent, and a timeout per node would prevent a slow agent from blocking the whole chain.

---

## Category 2: AWS Bedrock & LLM Integration

### Q9: How would you swap MockLLM for AWS Bedrock Claude?

The MockLLM interface exposes two methods: `generate(template_key, variables) -> str` and `classify_intent(query) -> str`. Swapping in Bedrock requires implementing a `BedrockLLM` class with the same interface — drop-in replacement, no agent code changes.

The `generate()` method would map template keys to system prompts for Claude. For example, `route_analysis` would send a system prompt establishing Claude as a United Airlines network analyst, then a user message with the structured data as JSON, requesting a specific output format. The call would be: `bedrock_client.invoke_model(modelId="anthropic.claude-3-sonnet-20240229-v1:0", body=json.dumps({"anthropic_version": "bedrock-2023-05-31", "max_tokens": 1024, "messages": [...]}))`.

The `BEDROCK_MODEL_ID` and `BEDROCK_REGION` constants are already defined in `config.py` (`anthropic.claude-3-sonnet-20240229-v1:0`, `us-east-1`), and the `USE_MOCK_LLM` flag controls which implementation is loaded. The `classify_intent()` method would use Bedrock with a classification prompt and parse the JSON response for the intent label. For latency-sensitive classification, I would consider using Claude Haiku rather than Sonnet to reduce p99 latency from ~2 seconds to ~400ms.

---

### Q10: How do you handle prompt engineering for different agent roles?

Each agent has a distinct role and knowledge domain that needs to be reflected in its system prompt. I use a role-persona-constraint-format structure for each agent:

**NetworkPlanningAgent system prompt:** "You are a senior network planning analyst at United Airlines with expertise in route economics, fleet allocation, and schedule optimization. Your role is to analyze route data and provide specific, actionable recommendations. Always cite the specific metric values from the data you receive. Format your response with a clear recommendation followed by quantified rationale."

**DisruptionAnalysisAgent system prompt:** "You are an IROPS (Irregular Operations) coordinator at United Airlines. Your priority is minimizing passenger impact during disruptions. When analyzing scenarios, always quantify passenger impact, identify cascade effects beyond the primary disruption, and prioritize mitigation actions by operational urgency. Assume you are communicating with an operations controller who needs to act within the next 15 minutes."

**AnalyticsInsightsAgent system prompt:** "You are a data analyst supporting United Airlines' executive team. Your responses should be suitable for C-suite consumption: lead with the key finding, support with specific numbers, and close with a recommended action. Avoid jargon; translate technical metrics into business impact."

The prompts are stored as class-level constants in each agent so they can be version-controlled, A/B tested, and updated without touching the core logic.

---

### Q11: How would you implement guardrails for this system?

I would implement guardrails at four levels. First, **input validation**: the MCPMessage payload is validated before dispatch. Queries containing PII patterns (credit card numbers, SSNs) are flagged and the query is blocked. Queries that exceed a token budget are truncated with a warning.

Second, **Bedrock Guardrails**: AWS Bedrock's native guardrails feature allows configuring content filters for harmful content, PII detection, and topic restrictions. For a United Airlines deployment, I would configure a topic policy that prevents the model from discussing competitor pricing, legal matters, or unreleased schedule information.

Third, **output validation**: every MCPResponse is post-processed through a validation function that checks: (a) the confidence score — responses with confidence below 0.5 are flagged for human review; (b) the recommendation against a whitelist of valid action types (INCREASE, DECREASE, MAINTAIN for frequency recommendations; CRITICAL, HIGH, MODERATE, LOW for risk levels); (c) any monetary figures are within plausible bounds to catch hallucinated $500M revenue impacts.

Fourth, **human-in-the-loop**: for high-impact decisions — recommending a route cancellation, initiating a fleet grounding — the orchestrator routes to a "pending approval" queue rather than returning a direct answer. An operations manager reviews and approves before the recommendation is considered active.

---

### Q12: What is your approach to model selection per agent?

Different agents have different latency, cost, and quality requirements, and model selection should reflect that.

**Orchestrator intent classification:** Claude Haiku (fastest, cheapest). Classification is a simple discriminative task that doesn't require deep reasoning. Target latency: under 500ms.

**NetworkPlanningAgent:** Claude Sonnet. Route analysis recommendations require nuanced reasoning about tradeoffs between demand, competition, and revenue. The additional latency (1-2 seconds over Haiku) is acceptable because network planning decisions are not real-time.

**DisruptionAnalysisAgent:** Claude Sonnet with streaming enabled. IROPS scenarios require detailed reasoning about cascading effects, but users need to see results quickly. Streaming lets the first tokens appear within 500ms even if the full response takes 3 seconds.

**AnalyticsInsightsAgent:** Claude Opus for executive summary generation, Sonnet for routine reports. The quality bar for content going to the C-suite justifies the additional cost and latency on high-visibility queries.

I would implement model selection as a configuration per agent (not hardcoded) so it can be adjusted based on observed quality metrics and cost reports from Cost Explorer.

---

### Q13: How would you handle rate limiting and cost optimization?

Rate limiting strategy: implement token bucket rate limiting per user role at the API Gateway layer. Network planners get a higher token budget per hour than ad-hoc users. At the Bedrock layer, monitor `ThrottlingException` responses and implement exponential backoff with jitter (base 1 second, max 60 seconds, jitter 0-500ms) using the `tenacity` library.

Cost optimization: (1) **Caching** — the most impactful lever. Route demand data and executive summaries change daily, not minute-by-minute. Cache Bedrock responses for structured queries using a hash of the (template_key, key_variables) tuple as the cache key, stored in ElastiCache with a 1-hour TTL. This can reduce Bedrock calls by 60-70% for repeated or similar queries. (2) **Prompt compression** — strip whitespace and comments from system prompts before sending. Use prompt caching (Bedrock's prompt caching feature) to cache the system prompt portion across calls. (3) **Model routing** — classify query complexity before selecting a model. Simple yes/no questions route to Haiku; complex multi-factor analyses route to Sonnet. (4) **Token budgeting** — set `max_tokens` per agent role and log actual token usage to CloudWatch with a Cost Allocation Tag per agent so per-agent cost is visible.

---

### Q14: How do you evaluate LLM output quality?

I use a multi-dimensional evaluation framework. **Automated metrics**: for structured outputs (route recommendations, disruption risk levels), check that the output matches the expected enum values and that referenced metrics are within the range present in the input data (factual grounding check). For insight text, run a semantic similarity check against a reference corpus of past high-quality network planning analyses.

**Human evaluation**: a sample of 5% of agent responses is routed to a human rater queue. Raters score on: accuracy (does the recommendation align with the data?), actionability (is the next step clear?), and appropriateness (is the tone right for the audience?). These scores feed back into the fine-tuning pipeline.

**A/B testing**: new prompt versions are tested against current prompts using a traffic split at the orchestrator level, with quality metrics tracked in CloudWatch. A prompt change is promoted only if it improves the human evaluation score by a statistically significant margin (p < 0.05, minimum 100 responses per variant).

**Operational validation**: the most important evaluation is tracking whether agent recommendations were followed and what the outcome was. If the system recommended increasing ORD-LAX frequency and United did so, did yield improve? This feedback loop, materialized as a DynamoDB table tracking (recommendation_id, recommendation, outcome, delta_revenue), is the ground truth for long-term quality improvement.

---

## Category 3: Network Planning / Domain

### Q15: How does the route demand analysis work?

The `get_route_demand()` tool in `NetworkPlanningAgent` performs a multi-source join. It starts with the routes DataFrame — which contains the pre-computed `demand_score` (a normalized 0.0-1.0 score representing projected demand relative to network average) and `revenue_index` (actual/average revenue per ASM, where 1.0 = network average). It then joins to the flights DataFrame on the city pair (checking both directions — ORD-LAX and LAX-ORD are the same route) to compute actual OTP and average load factor from the operational data.

The `demand_score` in the synthetic data is generated from a combination of population of origin and destination markets, historical booking trends, and seasonal adjustments. In production, this would come from United's revenue management system — specifically the O&D demand forecasting model that produces future demand estimates by booking class and travel date.

The `_great_circle_nm()` function computes haversine distance using the airport lat/lon coordinates from `AIRPORT_COORDS` in `config.py`. This is used for aircraft assignment optimization — matching aircraft range to route distance with a 10% fuel reserve buffer.

The insight text is generated by MockLLM's `route_analysis` template, which applies rule functions to determine demand label (Strong/Moderate/Weak), recommended action (INCREASE/MAINTAIN/DECREASE frequency), and estimated revenue impact (`revenue_index × demand_score × 18.5`, a simplified revenue model).

---

### Q16: How do you model cascading disruptions?

The `simulate_weather_event()` tool implements two-tier cascade modeling. The primary tier affects all flights at the disrupted airport — both departures (origin == airport) and arrivals (destination == airport). Severity multipliers are applied: Critical disruption cancels 40% and delays 80%, with average delay of 240 minutes.

The secondary (cascade) tier identifies all tail numbers on affected flights, then finds every other flight operated by those tails in the flights DataFrame that is not already in the primary affected set. These downstream flights are delayed at 50% of the primary delay rate — reflecting that aircraft will be repositioned or recover partially. This models the real-world phenomenon where a 4-hour ground stop at ORD doesn't just affect ORD flights; the B737 that was supposed to fly ORD→DEN→LAX is now 4 hours behind its rotation, affecting every subsequent leg.

Passenger impact is calculated per flight by multiplying `load_factor × capacity` using the aircraft type's capacity from the fleet DataFrame. The result is an estimated head count, not a revenue figure (though that calculation would be straightforward to add with an average fare per route).

In production, I would enhance this with: (1) a crew availability check — does the cascade delay violate rest requirements for any crew members? (2) A fuel routing check — does the repositioning flight have enough fuel for a diversion? (3) A connecting passenger model — how many passengers miss connections at downstream hubs?

---

### Q17: How would you integrate with real United data sources?

The `DataStore` singleton is the integration point. In production, `DataStore.get()` would load from real data sources rather than the synthetic generator. The data layer abstraction means agents don't know or care where the data comes from.

For real integration, I would implement: (1) **Flight data** from ACARS (Aircraft Communications Addressing and Reporting System) — real-time tail number, gate, departure, and status updates ingested via a Kinesis Data Stream, normalized, and written to DynamoDB. The DataStore would query DynamoDB rather than a Pandas DataFrame. (2) **Route and demand data** from United's Network Planning database — likely an Oracle or Teradata system with O&D demand forecasts, revenue actuals by route, and competitive capacity data. The DataStore would expose a read-only connection with parameterized queries. (3) **Weather data** from the FAA SWIM (System Wide Information Management) feed for real-time METAR, TAF, and SIGMET data, enriched with The Weather Company aviation forecast API. (4) **Gate data** from the airport operations database (AODB) for real-time gate assignments and terminal status.

Authentication to these systems would use IAM roles for AWS services and AWS Secrets Manager for credentials to United's internal APIs, with VPC private endpoints to keep traffic off the public internet.

---

### Q18: How do you handle what-if scenario modeling?

The system handles what-if modeling through the **Disruption Simulator** page and the scenario preset system in `config.py`. The three presets — "ORD Winter Storm", "Gate C Closure", and "Fleet Grounding B737" — are parameterized scenarios with pre-defined disruption type, severity, affected airports, duration, and estimated passenger impact. Users can also input custom scenarios via the simulator's form controls.

Under the hood, each what-if scenario is a parameterized call to the appropriate simulation tool. The severity multipliers in `simulate_weather_event()` are the key modeling parameters — different severities produce different cancellation rates, delay distributions, and cascade factors, which I calibrated against historical IROPS data patterns.

For more sophisticated what-if modeling in production, I would implement: (1) **Probabilistic scenarios** — instead of a single severity level, model uncertainty with a distribution of outcomes. A "High severity" weather event might have a 20% chance of becoming Critical, modeled via Monte Carlo sampling. (2) **Constraint propagation** — the optimization engine would check whether recommended mitigations are actually feasible given crew duty time limits, aircraft maintenance windows, and slot restrictions at downstream airports. (3) **Comparative scenario analysis** — run multiple scenarios side-by-side and present the outcome distribution as a risk matrix, helping planners choose the most resilient response.

---

### Q19: How would you validate agent recommendations against actual operational outcomes?

This is the most important long-term quality problem for any production GenAI system in airline ops. I would build a recommendation tracking pipeline: every MCPResponse is written to a DynamoDB table with `recommendation_id`, `agent`, `query`, `recommendation_type`, `recommended_action`, `confidence`, and `timestamp`. A separate process, triggered daily, joins this table against actual operational outcomes.

For route frequency recommendations: the "outcome" is the network planning team's actual decision and the subsequent yield/load factor data for the route over the next 90 days. If the agent recommended INCREASE and the team agreed, did load factor improve by the expected amount? This produces an accuracy metric per recommendation type.

For disruption mitigation recommendations: the "outcome" is the actual recovery time and passenger impact count from United's IROPS log, compared to the agent's predicted `recovery_hours` and `estimated_pax_impact`. A systematic over-prediction of pax impact might indicate the cascade model's 50% secondary delay factor is too conservative.

For executive summaries: the outcome metric is engagement — did the executive who received the report ask follow-up questions that suggest the summary was clear and accurate, or did it generate confusion?

All outcome data feeds back to the fine-tuning pipeline and is also surfaced in an "Agent Performance" dashboard for operations leadership to review monthly.

---

## Category 4: MCP (Model Context Protocol) Deep Dive

### Q20: What is MCP and why is it important for multi-agent systems?

MCP — Model Context Protocol — is a standardized protocol for how AI models and agents share context, communicate intent, and invoke tools. In its most general form, it answers the question: how does one AI agent tell another what it knows, what it wants, and what capabilities it has available?

The importance in multi-agent systems is that without a shared protocol, every agent-to-agent interaction is bespoke — Agent A needs to know Agent B's internal API, data format, and calling convention. As you add more agents, the number of custom integrations grows quadratically (N*(N-1)/2 for N agents). A shared protocol reduces this to N integrations — each agent speaks the same language, and the orchestrator mediates.

In my implementation, MCP has three components: the **message protocol** (`MCPMessage` and `MCPResponse` dataclasses) that defines the envelope for all communication; the **context store** (`MCPContextStore`) that provides shared memory across agents with TTL and conversation history; and the **tool registry** (`MCPToolRegistry`) that acts as the shared catalog of capabilities, decoupling tool definition from tool invocation. Any agent can invoke any registered tool by name, regardless of which agent originally registered it — this is agent composability.

In the broader industry, Anthropic has formalized MCP as an open standard (model-context-protocol.io) for connecting AI assistants to external data sources and tools, which is what makes this architecture genuinely forward-compatible with the evolving ecosystem.

---

### Q21: How does your context store manage state across agents?

The `MCPContextStore` uses three data structures. The **key-value store** (`self._store`) is a dict mapping string keys to `(value, expiry_timestamp)` tuples, protected by a `threading.RLock()` for thread safety. Any agent can write and read any key; naming conventions (`network_planning:{message_id}`, `disruption_analysis:{message_id}`, `last_query`) provide implicit namespacing.

The **conversation history** (`self._history`) is an ordered list of message/response pairs. After every `_build_response()` call in `BaseAgent`, `context_store.push_message(msg, response)` records the full exchange. This means the analytics agent can call `get_conversation_history(last_n=5)` to see what questions were asked and answered in the past 5 turns, without any agent explicitly passing data to another.

The **session store** (`self._sessions`) is reserved for session-scoped data isolation — in a multi-user deployment, each session would have its own namespace within the store, and `clear_session()` removes all data for that session without affecting other users.

The TTL mechanism — `time.monotonic()` based, checked on read — means ephemeral data like weather simulation results (relevant for 15 minutes) doesn't persist forever and pollute subsequent analyses. TTL values would be set by convention: `context_store.set("weather_ord", result, ttl=900)` for 15-minute weather data, no TTL for route demand data that's valid for the day.

---

### Q22: How do you handle context window limitations?

The current system is not LLM-context-bound because MockLLM uses templates, not a context window. But for production Bedrock integration, context window management is critical.

My approach: (1) **Selective context injection** — agents don't dump the entire conversation history into the LLM prompt. The `get_conversation_history(last_n=3)` method retrieves only the most recent exchanges, and even those are summarized to key facts rather than passed verbatim. (2) **Structured data, not text** — structured results (DataFrames, dicts) are serialized as compact JSON rather than prose, which is far more token-efficient. A route demand result fits in ~200 tokens as JSON vs. ~800 tokens as a prose description. (3) **Context reference, not copy** — when an agent needs to reference a prior result, it passes the `context_ref` key and the receiving agent fetches from the store, rather than including the full prior result in the next LLM prompt. (4) **Summary truncation** — for long result lists (e.g., all underperforming routes), agents cap the output at the most impactful items (top 5 routes by revenue opportunity) and include a count of the total. (5) **Sliding window** — for long sessions, maintain a sliding window of the last 8,192 tokens of conversation history in the prompt, with older context available in the store for explicit retrieval.

---

### Q23: How would you implement persistent memory across sessions?

Persistent memory requires externalizing the in-process `MCPContextStore` to a durable store. The implementation would be: (1) At session end (browser tab close or explicit logout), serialize the context store's `_store` dict and `_history` list to a DynamoDB item keyed by `(user_id, session_id)`. (2) At session start, check DynamoDB for a prior session by the same user and, if found and less than 24 hours old, restore the context into a new `MCPContextStore` instance. (3) For long-term memory across many sessions, implement a "memory summarization" step: after 10 sessions, run a Bedrock call to summarize the user's most common query patterns, preferred routes, and frequently referenced disruption scenarios into a compact "user profile" stored in DynamoDB. This profile is injected into the system prompt at the start of each new session.

The key engineering challenge is that Streamlit's `st.session_state` only lives for the browser session. The DynamoDB persistence layer bridges this gap. Session IDs would be stored in a secure HTTP-only cookie, and the DynamoDB item would include a TTL attribute so stale sessions are automatically cleaned up.

---

### Q24: How does the tool registry enable agent composability?

The `MCPToolRegistry` is a flat catalog — it doesn't know or care which agent registered a tool, and it doesn't restrict which agents can invoke which tools. This is deliberate. Any agent can call `self._call_tool("simulate_weather_event", airport="ORD", ...)` even though `simulate_weather_event` is registered by `DisruptionAnalysisAgent`.

This enables composability in two ways. First, the NetworkPlanningAgent could call `simulate_weather_event` on the top underperforming route's hub to understand how weather risk compounds that route's performance problems — cross-agent tool usage without any tight coupling. Second, a new agent that doesn't need to implement its own analytics tools can simply call the tools registered by AnalyticsInsightsAgent, reusing logic rather than duplicating it.

The registry prevents conflicts: `register()` raises `ValueError` if a tool name is already registered, forcing unique names and making ownership explicit. `list_tools(agent="network_planning")` returns only the tools owned by that agent, which is useful for generating agent capability documentation or for the orchestrator to understand what each specialist can do.

In production, the tool registry would be enhanced with: (1) permission scoping — some tools (e.g., those that write schedule changes) would only be callable by authorized agents; (2) tool versioning — `get_route_demand_v2` coexists with `get_route_demand` during migration periods; (3) tool telemetry — every `invoke()` call is logged with latency and result size for performance monitoring.

---

### Q25: How would you extend MCP for tool discovery across distributed services?

In production, tools wouldn't all live in the same Python process. A crew scheduling tool might be a Lambda function, a revenue management tool might be a microservice, and a weather API wrapper might be a third-party service.

I would implement a **distributed tool registry** using a DynamoDB table as the catalog. Each tool entry would include: `tool_name`, `agent_owner`, `endpoint_type` (Lambda ARN, HTTP URL, SQS queue), `input_schema` (JSON Schema), `output_schema`, `timeout_ms`, and `auth_type` (IAM, API key, none). At agent startup, the registry would be populated by scanning this table and creating wrapper callables that invoke the appropriate endpoint type.

For tool discovery, agents could query the registry with `get_tools_for_intent("disruption_impact")` — already implemented in the current `MCPToolRegistry` — and the orchestrator could dynamically assemble a tool chain for a complex query based on what's available in the catalog. This is the path toward truly composable multi-agent systems where new capabilities can be added by registering a new tool entry in DynamoDB without redeploying any agents.

---

## Category 5: Production & Scale

### Q26: How would you deploy this to production on AWS?

The deployment architecture uses containers and managed services to avoid undifferentiated heavy lifting. The Streamlit application would run in Docker containers on **Amazon ECS Fargate** — no server management, auto-scaling, and easy blue/green deployment. An **Application Load Balancer** in front of ECS handles HTTPS termination, sticky sessions (required for Streamlit's WebSocket connection), and health checks.

The orchestrator and agents would be separated from the Streamlit UI: the UI calls an **Amazon API Gateway** endpoint that routes to an ECS service running the agent system, allowing the agent backend to scale independently of the UI. For high-throughput use cases, the agent backend could also be deployed as a set of Lambda functions (one per agent type), invoked asynchronously via SQS.

All services run inside a **VPC** with private subnets. The agent services have no public internet access — they communicate with Bedrock via a VPC endpoint (`com.amazonaws.us-east-1.bedrock-runtime`), with DynamoDB via a gateway endpoint, and with United's internal APIs via a Direct Connect link or VPN. **AWS WAF** in front of API Gateway blocks common attack vectors. **AWS KMS** encrypts DynamoDB data at rest and S3 artifacts.

**IAM roles** follow least privilege: the ECS task role has only the permissions needed — `bedrock:InvokeModel`, `dynamodb:GetItem`, `dynamodb:PutItem` on specific tables, `s3:GetObject` on the data bucket. No wildcard permissions anywhere.

---

### Q27: How would you handle real-time flight data ingestion?

Real-time flight data from ACARS and other sources would flow through a **Kinesis Data Streams** pipeline. Producers (airport operation systems, ACARS decoders) push flight status updates to a Kinesis stream partitioned by airport code. A **Kinesis Data Analytics** (Apache Flink) application processes the stream: deduplication, data validation, field normalization (converting various timestamp formats to UTC ISO 8601), and enrichment (joining flight number to aircraft tail from the fleet database).

The processed stream is consumed by two destinations: a **DynamoDB** table for the real-time "hot" data that agents query (current flight status, current gate assignments, current delay minutes), and a **Kinesis Firehose** → **S3** pipeline for the "cold" historical data that feeds the data warehouse for analytics.

The `DataStore.get()` method in production would query DynamoDB directly for real-time data, replacing the in-memory Pandas DataFrames. For analytical queries (load factor trends over 90 days), the AnalyticsInsightsAgent would query **Amazon Athena** against the S3 data lake, with a 30-second query timeout and result caching via ElastiCache.

The critical challenge is handling the eventual consistency between real-time DynamoDB data and batch-updated route planning data. I would implement a cache invalidation event: when the network planning database publishes a route change, an EventBridge event triggers a Lambda that clears the relevant ElastiCache entries and marks the DynamoDB route record as stale, forcing the next agent query to refresh from the source.

---

### Q28: What monitoring and observability would you add?

Observability for an agentic AI system requires metrics that go beyond standard application monitoring. I would implement four layers:

**Infrastructure metrics** via CloudWatch: ECS CPU and memory, API Gateway latency and error rates, DynamoDB read/write capacity units, Kinesis lag (how far behind real-time is the stream consumer). Standard alarms and dashboards.

**Agent performance metrics** via CloudWatch custom metrics: per-agent invocation count, per-agent average latency, per-agent error rate, intent classification distribution (are users asking mostly about disruptions? routes?), tool call frequency per tool name, confidence score distribution per agent, and cache hit rate. These go into a **CloudWatch Dashboard** visible to the MLOps team.

**LLM observability** via AWS X-Ray distributed tracing: every Bedrock `invoke_model` call is traced with X-Ray, capturing input token count, output token count, latency, and model ID. X-Ray service maps show the full request flow from API Gateway → orchestrator → specialist agent → Bedrock → response. This makes it possible to identify which agent is generating the most Bedrock cost and where the latency bottlenecks are.

**Business metrics** via a custom dashboard in QuickSight: recommendation acceptance rate (what fraction of agent recommendations were acted upon by planners), recommendation accuracy (comparing predicted vs. actual outcomes), session length and query count per user role, and NPS score from the in-app feedback widget. These are the metrics that matter to business leadership and justify the investment.

Alerting: PagerDuty integration for critical alarms (agent error rate > 5%, Bedrock throttling, Kinesis lag > 5 minutes). Non-critical alerts (confidence score trending down, cache hit rate dropping) go to a Slack channel.

---

### Q29: How would you handle concurrent users?

The current Streamlit demo is single-user by design (Streamlit session state is per-browser-session). For multi-user production deployment, three things need to change.

First, the `MCPContextStore` must be externalized to DynamoDB as described above, keyed by session ID. The in-process singleton cannot be shared across users or ECS tasks.

Second, the `OrchestratorAgent.setup()` call must be per-session (or per-request), not a singleton. Each user session should get its own orchestrator instance with its own context store. The shared components — tool registry and LLM client — can be initialized once at application startup and shared across sessions, but the context store must be isolated per user to prevent state leakage.

Third, the ECS service must be configured for horizontal auto-scaling based on the `RequestCountPerTarget` metric from the ALB. A target of 10 concurrent requests per ECS task (given ~2-3 second average Bedrock latency per request) would scale from 2 tasks (baseline) to 50 tasks during peak periods (pre-departure morning rush for ops controllers). A **SQS queue** between API Gateway and the agent backend provides buffering during traffic spikes so requests don't time out.

For the Streamlit layer specifically, I would evaluate migrating the UI to a React/Next.js frontend calling the agent API directly, which gives full control over session management and concurrent user handling without Streamlit's session-state limitations.

---

### Q30: What is your testing strategy for agent systems?

Agent systems require a layered testing strategy because the non-determinism of LLMs makes traditional test assertions fragile.

**Unit tests** for deterministic components: every tool function (`get_route_demand`, `simulate_weather_event`, etc.) has pytest unit tests with fixture data. Tool outputs are compared against expected dicts with tolerance for floating-point fields. MCPMessage and MCPResponse serialization/deserialization is tested. The context store TTL behavior is tested with mock time. Target: 90%+ coverage, run in CI on every commit.

**Integration tests** for agent end-to-end: each agent's `handle()` method is tested with representative queries using the MockLLM (so results are deterministic). Tests assert: correct tool selection (which tools were called?), correct response structure (required keys present?), confidence score within expected range. A query regression suite of 50 representative airline ops queries is run on every merge to main.

**Evaluation tests** for LLM quality (when Bedrock is wired in): a set of golden queries with human-labeled expected responses. LLM outputs are evaluated against these using BERTScore for semantic similarity (threshold: 0.85) and a custom factual grounding check (all numeric values in the response must be present in the input data). Run weekly against the production model.

**Chaos tests** for resilience: inject artificial failures (tool registry throwing exceptions, context store unavailable, Bedrock returning 429) and assert that the system degrades gracefully — fallback responses, not unhandled exceptions. Run monthly.

**Load tests** using Locust: simulate 100 concurrent users with realistic query patterns and assert that p99 latency is under 5 seconds and error rate is under 1%.

---

### Q31: How would you implement A/B testing for agent responses?

A/B testing for agent systems requires randomization at the request level, outcome tracking at the business metric level, and guardrails against exposing users to genuinely bad responses.

The implementation: (1) At the orchestrator level, maintain a feature flag system (AWS AppConfig) that defines experiments. Each experiment specifies: experiment ID, traffic split (e.g., 50/50), variants (e.g., Variant A uses prompt v1, Variant B uses prompt v2), and eligible user segments (e.g., only network planners, not ops controllers). (2) Each incoming request is assigned to a variant by hashing `(user_id, experiment_id)` modulo 100 and comparing to the traffic split threshold. The assignment is deterministic (same user always gets same variant within an experiment) and stored in the context store for the session. (3) The assigned variant ID is included in every CloudWatch metric and every recommendation record in DynamoDB, enabling per-variant metric computation in Athena/QuickSight. (4) A guardrail: if Variant B's error rate exceeds Variant A's by more than 10%, AppConfig automatically rolls back Variant B to 0% traffic.

**Primary metric**: recommendation acceptance rate (did the planner act on the recommendation?) per variant. **Secondary metrics**: confidence score, response latency, user session length. **Minimum sample size**: calculated based on expected effect size (5% improvement) and desired statistical power (80%), using a power analysis — typically requires 500+ exposures per variant for reliable results.

---

### Q32: What are the security considerations for airline operations data?

Airline operational data — flight plans, crew schedules, maintenance records, passenger manifests — is highly sensitive and subject to TSA, FAA, and DOT regulations, as well as GDPR for European routes.

**Data classification**: implement a tiered classification scheme. Tier 1 (Restricted): passenger PII, crew personal data — never sent to Bedrock, never stored in the context store. Tier 2 (Confidential): actual revenue data, competitive pricing, unannounced schedule changes — encrypted at rest in DynamoDB with KMS, access limited to specific IAM roles, audit logged via CloudTrail. Tier 3 (Internal): operational metrics, OTP data, load factors — encrypted at rest, accessible to agent system with appropriate IAM roles. Tier 4 (Public): published schedules, airport codes — unrestricted.

**Bedrock data privacy**: configure Bedrock model invocations with `inferenceConfig` options to disable storage of inference data for model training. United's data should never be used by AWS to improve foundation models. This requires a Bedrock enterprise agreement with data residency and privacy guarantees.

**Network security**: all agent-to-data-source communication through VPC private endpoints. No operational data traverses the public internet. United's internal APIs accessible only via Direct Connect or VPN.

**Access control**: RBAC at the application layer (network planners can only query routes; ops controllers can query disruptions; executives get read-only analytics; no user can write to the schedule database through the agent system). Attribute-based access control (ABAC) in IAM for fine-grained resource access.

**Audit trail**: every MCPMessage, every tool call, every Bedrock invocation is logged to CloudTrail and a tamper-proof S3 log bucket with Object Lock (WORM). Retention: 7 years per FAA regulatory requirements.

---

## Category 6: Behavioral / Communication

### Q33: How do you translate business requirements into technical architecture?

My approach is to work from the user decision backwards to the data and AI architecture. For this project, I started by asking: what decisions does a network planner need to make, and what information do they need to make them confidently? The answers — route viability assessment, frequency optimization, fleet matching, disruption response — drove the three-agent domain split. The orchestrator pattern emerged from the observation that a single user session often spans multiple domains ("Tell me about ORD-LAX performance, and then simulate what a storm at ORD would do to it"), requiring seamless handoff without the user having to know which system to ask.

I then identify the data available vs. data needed gap. If a business requirement says "recommend route frequency changes," I need demand forecast data, competitive capacity data, and cost data — and I need to know whether those are available in real-time or only in batch. That gap analysis drives the data architecture decisions.

For architecture choices, I document the alternatives considered and why I chose what I chose. For this demo, I considered: (1) a single monolithic LLM with all tools (rejected: no separation of concerns, harder to test, prompt becomes unwieldy); (2) a flat agent graph where any agent can call any other (rejected: too complex for the current use case, harder to audit); (3) the orchestrator-specialist pattern (chosen: clear routing, easy to extend, auditable). I write up these trade-offs so stakeholders understand not just what was built but why.

---

### Q34: Tell me about a time you had to simplify complex GenAI concepts for business stakeholders.

When presenting the multi-agent architecture to a non-technical audience, I use an analogy to a hospital. The hospital has specialist departments — cardiology, neurology, radiology — each with their own expertise and tools. When a patient comes in, the emergency department (the orchestrator) triages them and routes them to the right specialist. The specialist examines the patient (queries the data), uses their instruments (calls tools), and produces a diagnosis (the MCPResponse with insight text). The patient's file (the context store) follows them from department to department so every specialist knows the patient's history without the patient having to re-explain everything.

This analogy explains: why multiple agents (specialization), why an orchestrator (routing by expertise, not random), why shared context (coordination without tight coupling), and why human oversight (the attending physician reviews specialist recommendations before acting).

For the LLM component specifically, I explain it as "a very smart generalist who has read every airline operations manual but has no access to live data." The tools give the LLM access to live data; the agent architecture ensures it's the right kind of LLM (specialist vs. generalist) for each question.

---

### Q35: How do you handle disagreements between technical and business priorities?

My approach is to make the trade-off explicit and quantified so the decision is clearly a business choice, not a technical preference. When an engineering team wants to spend three months building a more sophisticated cascade delay model and the business wants a working demo in two weeks, I present: "Option A — the more sophisticated model — reduces the estimated error in pax impact prediction from ±20% to ±8%. The question for the business is: does that 12% improvement in accuracy justify a 6-week delay in getting the tool in front of planners?" That framing makes it a business ROI question, not a debate about technical merit.

I also distinguish between decisions that can be revisited later and decisions that are expensive to reverse. The choice of message protocol (MCPMessage vs. direct function calls) is cheap to change during development but expensive after agents are deployed and teams are integrating. The choice of whether to use B787-9 or B737-MAX9 capacity constants in the demand model is easy to update any time. I flag irreversible architectural decisions for explicit sign-off and make reversible implementation details team-level decisions.

Finally, I build trust by being right about the consequential predictions. When I say "if we skip the TTL mechanism in the context store now, we'll have a bug where stale weather data affects route recommendations in the same session," and that turns out to be true six weeks later, future trade-off discussions have more credibility.

---

# SECTION 3: Productionization Roadmap

## Phase 1: Foundation (Months 1–3)

### AWS Bedrock Integration

**Goal:** Replace `MockLLM` with `BedrockLLM`, maintaining the same interface so no agent code changes.

**Implementation Steps:**
1. Create `llm/bedrock_llm.py` implementing `generate(template_key, variables) -> str` and `classify_intent(query) -> str` using `boto3.client("bedrock-runtime", region_name="us-east-1")`.
2. Each template key maps to a structured prompt: a system prompt establishing the agent persona, a user message containing the structured data as compact JSON, and a request for the output in a specific format.
3. Set `USE_MOCK_LLM = False` in `config.py` (or via environment variable `USE_MOCK_LLM=false`) to activate.
4. Implement streaming support: `generate_stream()` using the Bedrock streaming response API, yielding chunks to the Streamlit UI via `st.write_stream()`.

**Model Selection Strategy:**
- Intent classification: `anthropic.claude-3-haiku-20240307-v1:0` (fast, cheap, ~400ms)
- Route analysis, executive summary: `anthropic.claude-3-sonnet-20240229-v1:0` (balanced)
- Complex multi-step analysis: `anthropic.claude-3-opus-20240229-v1:0` (reserved for high-value, low-frequency queries)

**Prompt Engineering:**
- Each agent class gains a `SYSTEM_PROMPT` class constant.
- A `PromptBuilder` utility class handles: system prompt injection, structured data serialization (compact JSON), few-shot examples for complex reasoning tasks, output format specification.
- All prompts are version-controlled in `prompts/` with semantic versioning.

**Cost Controls:**
- `max_tokens` set per agent: classification (256), route analysis (1024), executive summary (2048).
- ElastiCache for Redis caches Bedrock responses keyed by hash of (model_id, system_prompt_version, input_data_hash) with 1-hour TTL.
- CloudWatch custom metric: `bedrock_tokens_consumed` by agent, alarmed at 80% of monthly budget.

---

### Real Data Integration

**Flight Data (Real-Time):**
- Kinesis Data Stream ingests ACARS messages and flight status updates (sourced from United's internal OpS system).
- Kinesis Data Analytics (Flink) normalizes and validates: timestamp conversion to UTC, status mapping to `FlightStatus` enum, duplicate detection within a 5-minute window.
- Processed events written to DynamoDB table `ua-flights-realtime` with partition key `flight_number` and sort key `departure_date`.
- `DataStore.flights` property replaced with a DynamoDB query method: `get_flights_by_date(date)` returning a DataFrame for compatibility with existing agent logic.

**Route & Demand Data (Batch):**
- Daily ETL job (Lambda triggered by EventBridge Scheduler at 02:00 UTC): reads from United's Network Planning Oracle database via AWS Database Migration Service endpoint, writes to S3 as Parquet, registers in AWS Glue Data Catalog.
- `DataStore.routes` property queries Athena against the Glue Catalog for current-day route data.
- Cache: ElastiCache stores the routes DataFrame for the day, invalidated at 02:30 UTC after ETL completion.

**Weather Data:**
- The Weather Company Aviation API polled every 15 minutes per hub airport.
- Results stored in DynamoDB `ua-weather-current` with 30-minute TTL.
- DisruptionAnalysisAgent gains a new tool: `get_current_weather(airport)` that reads from this table.

---

### Authentication & Authorization

**Identity:** Amazon Cognito user pool with United's existing SAML identity provider (Active Directory) for SSO. Users authenticate via their United corporate credentials.

**RBAC Groups:**
- `network-planners`: can query all Network Planning tools, read-only Analytics.
- `ops-controllers`: can query all Disruption Analysis tools, read-only Dashboard.
- `executives`: read-only Analytics & Insights, Dashboard only.
- `admins`: full access including agent configuration and prompt management.

**Authorization Enforcement:** API Gateway Lambda authorizer validates the Cognito JWT on every request, extracts the user's group memberships, and adds them as headers forwarded to the agent service. The orchestrator checks the user's groups before dispatching to certain agents and tools.

**Audit Logging:** Every query, every tool call, and every Bedrock invocation logged to CloudTrail and a dedicated S3 bucket with Object Lock retention for 7 years.

---

### Infrastructure

**Container:** Dockerfile building the Streamlit app + agent system, pushed to ECR. Two ECS services: `ua-ni-ui` (Streamlit, 2 tasks baseline) and `ua-ni-agents` (agent API, 2 tasks baseline).

**Networking:** VPC with 3 AZs. Public subnets: ALB. Private subnets: ECS tasks, ElastiCache, Lambda. Isolated subnets: DynamoDB endpoint, Bedrock endpoint. No NAT Gateway egress for agent traffic — all AWS service communication through VPC endpoints.

**CI/CD:** CodePipeline: Source (GitHub) → Build (CodeBuild: run tests, build Docker image, push to ECR) → Deploy (CodeDeploy blue/green to ECS with ALB weighted routing). Pipeline blocked if unit test coverage drops below 80% or any test fails.

---

## Phase 2: Scale & Reliability (Months 4–8)

### Agent Orchestration Framework

**LangGraph Integration:** Replace the custom orchestrator routing logic with a LangGraph `StateGraph`. Each agent becomes a node; edges represent routing decisions. The graph state carries the `MCPMessage`, accumulated tool results, and the `MCPContextStore` reference.

Benefits over the current approach: (1) Built-in support for conditional edges (route to DisruptionAgent or NetworkAgent based on state); (2) Human-in-the-loop pause points — the graph can pause at a "human approval" node for high-impact recommendations; (3) Sub-graphs for complex multi-agent workflows (e.g., route analysis → disruption simulation → executive summary as a single graph execution); (4) Built-in retry and error handling at the graph level.

The `MCPMessage` and `MCPResponse` dataclasses are preserved as the inter-node contract within the LangGraph state, maintaining backward compatibility.

---

### Real-Time Data Pipelines

**Kinesis/Kafka Architecture:**
- Kinesis Data Streams for United's internal data (ACARS, ops events): lower latency, tighter AWS integration.
- Amazon MSK (Managed Kafka) for external data feeds (weather APIs, airport ops): better for high-volume, multi-consumer architectures.
- Kinesis Firehose for S3 archival of all events, enabling replay for debugging and historical analysis.

**Stream Processing (Flink on Kinesis Data Analytics):**
- Flight status aggregation: compute rolling 15-minute OTP per airport.
- Disruption detection: alert if delay rate at any hub exceeds 25% in a 30-minute window → trigger DisruptionAnalysisAgent proactively.
- Demand signals: compute real-time load factor trends vs. same-day-last-week baseline.

**Proactive Agent Triggers:** EventBridge Pipes connecting Kinesis Data Analytics anomaly alerts to the agent API. A detected ORD delay spike triggers `DisruptionAnalysisAgent.handle()` with `{"query": "weather disruption at ORD", "airport": "ORD", "severity": "auto-detected"}` without any user action.

---

### Caching Layer

**ElastiCache for Redis:**
- **L1 Cache (agent response cache):** Key = hash(agent_name + query_normalized + data_version). TTL: 5 minutes for operational data, 60 minutes for analytics. Cache hit: return cached MCPResponse JSON, no Bedrock call. Expected hit rate: 40-60% for operations users who run similar queries throughout a shift.
- **L2 Cache (data cache):** Key = (data_type + date). TTL: until next ETL run (route data, aircraft status) or 15 minutes (flight status). Reduces DynamoDB read costs by 70%.

**DynamoDB for Context Store Persistence:**
- Table `ua-ni-context` with partition key `session_id` and sort key `key`. TTL attribute for automatic cleanup.
- Global Secondary Index on `(user_id, timestamp)` for retrieving a user's most recent sessions.
- On-demand billing mode (traffic is spiky during shift changes).

**Cache Warming:** A Lambda function triggered at 05:00 UTC pre-warms the data cache with today's routes, flights, and aircraft status before the morning ops shift begins.

---

### Observability

**CloudWatch Custom Metrics Namespace `UA/NetworkIntelligence`:**
- `AgentLatencyMs` (dimension: AgentName) — p50, p95, p99
- `AgentErrorCount` (dimension: AgentName, ErrorType)
- `BedrockTokensConsumed` (dimension: AgentName, ModelId)
- `ToolCallCount` (dimension: ToolName)
- `ConfidenceScore` (dimension: AgentName) — average per 5-minute period
- `CacheHitRate` (dimension: CacheLayer)
- `IntentClassificationDistribution` (dimension: Intent)

**X-Ray Distributed Tracing:**
- Every API Gateway → ECS request has an X-Ray trace.
- Custom segments added in agent code: `xray_recorder.begin_subsegment("bedrock_invoke")` wrapping each Bedrock call.
- Service map in X-Ray console shows end-to-end request flow with latency breakdown.
- Trace sampling: 5% of requests (100% for error responses).

**CloudWatch Dashboards:**
- **Ops Dashboard:** Real-time agent health, error rates, latency. For the ops team.
- **Cost Dashboard:** Bedrock token consumption by agent and model, cache hit rates, projected monthly cost. For engineering and finance.
- **Quality Dashboard:** Confidence score trends, human rating distribution, recommendation acceptance rate. For the MLOps team.

**Alarms:**
- `AgentErrorRate > 5%` for 5 consecutive minutes → PagerDuty Critical.
- `BedrockThrottlingExceptions > 10` in 1 minute → PagerDuty Warning, auto-scale Bedrock retry pool.
- `ConfidenceScoreAvg < 0.6` for 30 minutes → Slack notification to MLOps team.
- `CacheHitRate < 20%` → Slack notification (potential cache misconfiguration).

---

### CI/CD Pipeline

**Pipeline Stages (AWS CodePipeline):**
1. **Source:** GitHub webhook triggers on merge to `main`.
2. **Build:** CodeBuild runs: `pytest --cov=. --cov-fail-under=80`, `mypy .` (type checking), `ruff .` (linting), `docker build`, `docker push` to ECR.
3. **Agent Regression Tests:** CodeBuild runs the 50-query agent regression suite against the new Docker image using MockLLM (fast, deterministic). Blocks promotion if any golden query produces an unexpected result.
4. **Staging Deploy:** CodeDeploy blue/green deployment to the staging ECS cluster with 100% traffic to new (blue) version. Run integration tests against staging.
5. **LLM Quality Gate:** Bedrock-based evaluation of 20 sampled queries from the golden set against the staging endpoint. BERTScore threshold 0.85, factual grounding check. If passed, automatically promote to production.
6. **Production Deploy:** CodeDeploy blue/green with 10% → 50% → 100% traffic shift over 30 minutes. ALB weighted routing. Automatic rollback if error rate spikes.

---

## Phase 3: Advanced Capabilities (Months 9–15)

### Autonomous Agents with Human-in-the-Loop

**Autonomy Tiers:**
- **Tier 1 (Fully Autonomous):** Low-risk, reversible recommendations — schedule gap alerts, anomaly notifications, informational summaries. Agent acts immediately.
- **Tier 2 (Notify + Auto-Execute):** Medium-risk, reversible actions — gate reassignments during disruptions, rebooking recommendations. Agent executes and notifies the planner simultaneously. Planner can undo within 15 minutes.
- **Tier 3 (Approval Required):** High-risk actions — route frequency changes, aircraft groundings, schedule modifications. Agent generates the recommendation and submits to an approval queue (ServiceNow integration). A network planning manager reviews and approves/rejects in the platform.
- **Tier 4 (Advisory Only):** Irreversible, high-impact decisions — route cancellations, new market entry. Agent provides analysis only; all decisions made by humans.

**Implementation:** LangGraph `interrupt_before` mechanism for Tier 3 nodes. The graph pauses, persists state to DynamoDB, sends an approval request notification (email + Slack). The planner's approval or rejection resumes or terminates the graph execution.

---

### Integration with Optimization Models

**Schedule Optimization:**
- Connect the NetworkPlanningAgent to **Amazon SageMaker** endpoints running Google OR-Tools or a custom MIP (Mixed Integer Programming) model for frequency optimization.
- The agent calls `tool: optimize_network_schedule(constraints)` which invokes the SageMaker endpoint with current route demand data, fleet availability, and regulatory constraints (slot restrictions, maintenance windows, crew pairing rules).
- The optimization model returns a candidate schedule change; the agent evaluates it against business rules and presents the recommendation with the objective function improvement (e.g., "This schedule change improves network revenue by $2.3M annually while maintaining 85%+ OTP").

**Disruption Recovery Optimization:**
- During IROPS, the DisruptionAnalysisAgent calls an optimization tool that solves a crew-aircraft-passenger reaccommodation problem in real time.
- Input: affected flights, available crew, available aircraft, passenger connections, slot availability.
- Output: optimal reassignment plan minimizing passenger delay minutes and crew cost, subject to regulatory constraints.

---

### Advanced What-If Modeling

**Monte Carlo Simulations:**
- For each disruption scenario, run 1,000 Monte Carlo iterations sampling uncertainty in duration (triangular distribution), severity progression, and cascade propagation.
- Compute: expected value, 5th/95th percentile outcomes, probability of exceeding 10,000 pax impact threshold.
- Present as a risk distribution chart: "There's a 75% chance this scenario resolves within 6 hours, but a 15% chance it extends beyond 12 hours."

**Scenario Branching:**
- The what-if engine supports branching: "If we initiate a ground stop now vs. waiting 2 hours, what are the expected outcomes?"
- Each branch runs independent simulations; the agent presents the comparative expected value and risk profile.
- Decision recommendation includes the "cost of waiting" — the additional expected pax impact per hour of delay in initiating IROPS protocol.

---

### RAG Pipeline for Policy and Playbooks

**Document Sources:**
- FAA Advisory Circulars and ADs (Airworthiness Directives)
- United Airlines Operations Specifications (OPSSPEC)
- IROPS playbooks and decision trees
- Airport facility guides for United's hub airports
- Collective Bargaining Agreement excerpts relevant to crew scheduling

**RAG Implementation:**
- Documents chunked (512 tokens with 64-token overlap) and embedded using Amazon Titan Embeddings v2.
- Embeddings stored in **Amazon OpenSearch Service** (k-NN index, cosine similarity).
- At query time, the relevant agent generates an embedding of the query, retrieves the top 5 most similar document chunks, and injects them into the LLM prompt as context before generating the response.
- This enables answers like: "Per FAA Advisory Circular 120-68J, the minimum rest period for this crew assignment is 10 hours. The proposed swap would require a waiver."

---

### Multi-Modal Inputs

**Weather Visualization Analysis:**
- Integrate with NOAA weather radar imagery API.
- Pass radar images to Claude's vision capability via Bedrock multi-modal inference.
- The DisruptionAnalysisAgent can "look at" a radar image and describe the storm track, estimated intensity, and affected airspace.

**Airport Diagram Analysis:**
- Upload airport diagrams (PDF/PNG) to S3.
- During gate reassignment scenarios, the agent can reference the airport diagram to verify that proposed alternate gates are accessible given the taxiway configuration.

**Flight Data Recorder Summary:**
- For maintenance-related disruptions, ACARS maintenance messages are text — but some aircraft health monitoring systems produce chart images. Vision capability allows the agent to interpret these charts without OCR preprocessing.

---

### Feedback Loop and Fine-Tuning

**Outcome Tracking Pipeline:**
- Every agent recommendation written to DynamoDB `ua-ni-recommendations` with: recommendation_id, agent, query, recommendation type, recommended action, confidence, timestamp.
- Daily Lambda job joins against operational outcome data: actual schedule decisions from network planning system, actual IROPS resolution times from ops log, actual load factor outcomes for recommended frequency changes.
- Outcome delta computed: `predicted_pax_impact - actual_pax_impact`, `recommended_frequency - adopted_frequency`, etc.

**Fine-Tuning Data Preparation:**
- Filter for high-quality training examples: human rating ≥ 4/5, factual grounding check passed, outcome delta within ±15%.
- Format as instruction fine-tuning pairs: `{"instruction": "<query>", "context": "<structured data>", "response": "<ideal response>"}`.
- Accumulated to S3 as JSONL, batched monthly.

**Bedrock Model Customization:**
- Submit fine-tuning job to Bedrock Custom Models using the accumulated JSONL data.
- Evaluate the fine-tuned model against the golden query set before promoting.
- A/B test the fine-tuned model against the base Sonnet model on 10% of traffic for 2 weeks before full rollout.

---

## Architecture Diagram Descriptions

### Diagram 1: Current Demo Architecture

**Title:** UA Network Intelligence — Demo System Architecture

**Components and Data Flow:**

```
User Browser
    │
    ▼
Streamlit App (app.py)
    ├── Sidebar Navigation (ui/sidebar.py)
    └── Page Dispatcher
          ├── Dashboard (ui/pages/home.py)
          ├── Network Planning (ui/pages/network_planning.py)
          ├── Disruption Simulator (ui/pages/disruption_simulator.py)
          ├── Analytics & Insights (ui/pages/analytics.py)
          └── Agent Trace (ui/pages/agent_trace.py)
                │
                ▼ (user query text)
         OrchestratorAgent (agents/orchestrator.py)
                │
                ├── 1. Intent Classification
                │     ├── Keyword Scan (INTENT_MAP dict, multi-word first)
                │     └── MockLLM Fallback (classify_intent())
                │
                ├── 2. Build MCPMessage (uuid, sender, recipient, intent, payload, trace)
                │
                └── 3. Dispatch to Specialist
                      │
          ┌───────────┼───────────────┐
          ▼           ▼               ▼
   NetworkPlanning  Disruption    AnalyticsInsights
      Agent         Analysis         Agent
          │         Agent            │
          │           │              │
          └───────────┴──────────────┘
                      │
             Shared MCP Layer
          ┌────────────────────────┐
          │  MCPContextStore       │
          │  (thread-safe KV +     │
          │   conversation history)│
          ├────────────────────────┤
          │  MCPToolRegistry       │
          │  (15 tools registered) │
          ├────────────────────────┤
          │  MockLLM               │
          │  (template + rules)    │
          └────────────────────────┘
                      │
               DataStore (singleton)
          ┌────────────────────────┐
          │  flights_df  (200 rows)│
          │  routes_df   (28 rows) │
          │  aircraft_df (80 rows) │
          │  gates_df    (64 rows) │
          │  disruptions_df(10 rows│
          └────────────────────────┘
               Generated by
         synthetic_generator.py
         (seed=42, deterministic)
```

**Data Flow Narrative:** The user submits a query via the Streamlit chat interface. The page component calls `st.session_state["orchestrator"].route(query)`. The orchestrator classifies intent, builds an MCPMessage, and dispatches to the appropriate specialist agent. The specialist agent calls registered tools via the MCPToolRegistry (which executes against the DataStore DataFrames), stores intermediate results in the MCPContextStore, generates insight text via MockLLM, and returns an MCPResponse. The page component renders the result dict as tables/metrics and the insight text in the chat interface. The Agent Trace page shows the full message trace list for any prior response.

---

### Diagram 2: Production AWS Architecture

**Title:** UA Network Intelligence — Production AWS Architecture

```
                    ┌──────────────────────────────────────┐
                    │         United Corporate Network      │
                    │   (Active Directory / SAML IdP)       │
                    └──────────────────┬───────────────────┘
                                       │ SAML SSO
                                       ▼
┌─── Public Internet ─────────────────────────────────────────┐
│                                                              │
│   User Browsers ──► AWS WAF ──► Application Load Balancer   │
│                                    (HTTPS :443)             │
└──────────────────────────────────────┬──────────────────────┘
                                       │
                    ┌──── VPC (3 AZs) ──┼─────────────────────┐
                    │  Public Subnets   │                       │
                    │  ┌─────────────────▼─────────────────┐   │
                    │  │   Amazon Cognito (Auth)            │   │
                    │  │   API Gateway (REST API)           │   │
                    │  └──────────────┬────────────────────┘   │
                    │                 │                         │
                    │  Private Subnets │                        │
                    │  ┌──────────────▼────────────────────┐   │
                    │  │   ECS Fargate Cluster             │   │
                    │  │   ┌─────────────────────────┐     │   │
                    │  │   │ ua-ni-ui Service        │     │   │
                    │  │   │ (Streamlit, 2-20 tasks) │     │   │
                    │  │   └─────────────────────────┘     │   │
                    │  │   ┌─────────────────────────┐     │   │
                    │  │   │ ua-ni-agents Service    │     │   │
                    │  │   │ (Agent API, 2-50 tasks) │     │   │
                    │  │   └────────────┬────────────┘     │   │
                    │  └───────────────┼───────────────────┘   │
                    │                  │                        │
                    │  ┌───────────────▼───────────────────┐   │
                    │  │   SQS Queue (buffering)           │   │
                    │  └───────────────┬───────────────────┘   │
                    │                  │                        │
                    │  ┌───────────────▼───────────────────┐   │
                    │  │   Data Services                   │   │
                    │  │   ┌──────────┐ ┌───────────────┐  │   │
                    │  │   │DynamoDB  │ │ElastiCache    │  │   │
                    │  │   │(context, │ │(Redis, cache) │  │   │
                    │  │   │ flights) │ └───────────────┘  │   │
                    │  │   └──────────┘                    │   │
                    │  │   ┌──────────┐ ┌───────────────┐  │   │
                    │  │   │Amazon S3 │ │OpenSearch     │  │   │
                    │  │   │(data lake│ │(RAG vectors)  │  │   │
                    │  │   │ logs)    │ └───────────────┘  │   │
                    │  │   └──────────┘                    │   │
                    │  └───────────────────────────────────┘   │
                    │                  │                        │
                    │  VPC Endpoints   │                        │
                    │  ┌───────────────▼───────────────────┐   │
                    │  │   AWS Bedrock (via VPC Endpoint)  │   │
                    │  │   Claude Haiku / Sonnet / Opus    │   │
                    │  └───────────────────────────────────┘   │
                    │                  │                        │
                    │  ┌───────────────▼───────────────────┐   │
                    │  │   Streaming Data (Kinesis)        │   │
                    │  │   ACARS → Kinesis Stream →        │   │
                    │  │   Flink (KDA) → DynamoDB          │   │
                    │  └───────────────────────────────────┘   │
                    │                  │                        │
                    │  Direct Connect ─┼─► United Internal APIs │
                    │                  │   (Schedule DB,         │
                    │                  │    Revenue Mgmt,        │
                    │                  │    Crew Planning)       │
                    └──────────────────┼────────────────────────┘
                                       │
                    ┌──────────────────▼───────────────────────┐
                    │   Observability                           │
                    │   CloudWatch (metrics, logs, dashboards)  │
                    │   AWS X-Ray (distributed tracing)         │
                    │   CloudTrail (audit trail)                │
                    │   PagerDuty (alerting)                    │
                    └──────────────────────────────────────────┘
```

---

### Diagram 3: Agent Interaction Sequence Diagram

**Title:** Agent Interaction Sequence — Route Analysis Query with Context Handoff

```
User       Streamlit    Orchestrator    NetworkPlanning    ContextStore    MockLLM/
                                           Agent                          Bedrock
  │            │              │                │                │            │
  │─ query ───►│              │                │                │            │
  │  "Analyze  │              │                │                │            │
  │  ORD-LAX"  │              │                │                │            │
  │            │─ route(q) ──►│                │                │            │
  │            │              │                │                │            │
  │            │              │─ classify ─────┤                │            │
  │            │              │  intent        │                │            │
  │            │              │  (keyword:     │                │            │
  │            │              │   "route" →    │                │            │
  │            │              │   network_     │                │            │
  │            │              │   planning)    │                │            │
  │            │              │                │                │            │
  │            │              │─ build MCPMsg ─┤                │            │
  │            │              │  {sender:user  │                │            │
  │            │              │   recipient:   │                │            │
  │            │              │   network_plan │                │            │
  │            │              │   intent:..    │                │            │
  │            │              │   trace:[orch]}│                │            │
  │            │              │                │                │            │
  │            │              │─ handle(msg) ──►│               │            │
  │            │              │                │                │            │
  │            │              │                │─ regex match ──┤            │
  │            │              │                │  "ORD-LAX"     │            │
  │            │              │                │                │            │
  │            │              │                │─ _call_tool ───┤            │
  │            │              │                │  get_route_    │            │
  │            │              │                │  demand(ORD,   │            │
  │            │              │                │  LAX)          │            │
  │            │              │                │                │            │
  │            │              │                │─ DataStore ────┤            │
  │            │              │                │  query routes_ │            │
  │            │              │                │  df + flights_ │            │
  │            │              │                │  df            │            │
  │            │              │                │                │            │
  │            │              │                │◄─ result_dict ─┤            │
  │            │              │                │  {demand:0.82  │            │
  │            │              │                │   revenue:1.24 │            │
  │            │              │                │   otp:0.87...} │            │
  │            │              │                │                │            │
  │            │              │                │─ store result ►│            │
  │            │              │                │  key:"network_ │            │
  │            │              │                │  planning:{id}"│            │
  │            │              │                │                │            │
  │            │              │                │─ generate() ───┼───────────►│
  │            │              │                │  template:     │            │
  │            │              │                │  route_analysis│            │
  │            │              │                │  vars:{demand, │            │
  │            │              │                │  revenue...}   │            │
  │            │              │                │                │            │
  │            │              │                │◄──────────────-┼── insight ─│
  │            │              │                │  text          │            │
  │            │              │                │                │            │
  │            │              │                │─ build response┤            │
  │            │              │                │  MCPResponse   │            │
  │            │              │                │  {result_dict, │            │
  │            │              │                │   insight,     │            │
  │            │              │                │   confidence:  │            │
  │            │              │                │   0.85,        │            │
  │            │              │                │   tool_calls:  │            │
  │            │              │                │   [get_route_  │            │
  │            │              │                │    demand]}    │            │
  │            │              │                │                │            │
  │            │              │                │─ push_message ►│            │
  │            │              │                │  (msg, resp)   │            │
  │            │              │                │  to history    │            │
  │            │              │                │                │            │
  │            │              │◄─ MCPResponse ─│                │            │
  │            │              │                │                │            │
  │            │              │─ store last ──►│                │            │
  │            │              │  query/agent/  │                │            │
  │            │              │  response      │                │            │
  │            │              │                │                │            │
  │            │◄─ response ──│                │                │            │
  │            │              │                │                │            │
  │◄─ render ──│              │                │                │            │
  │  result +  │              │                │                │            │
  │  insight   │              │                │                │            │
```

**Key points to explain from this diagram:**
- The MCPMessage is built once by the orchestrator and passed to the specialist — the specialist never interacts with the orchestrator's other attributes.
- The trace list grows as the message passes through processing steps — this is what appears in the Agent Trace UI page.
- The context store `push_message()` call happens inside `_build_response()` — it's automatic, not something specialists need to remember to call.
- The orchestrator stores `last_query`, `last_agent`, and the response after every successful dispatch — enabling future queries to reference prior context without re-computation.
- In a multi-step query, the orchestrator would pass `context_ref="network_planning:{msg_id}"` in the second dispatch, and the second agent would retrieve the first agent's result from the context store.

---

## Quick Reference: Key Code Locations

| Component | File | Key Method |
|---|---|---|
| Application entry point | `app.py` | `OrchestratorAgent.setup()` in session_state init |
| Orchestrator routing | `agents/orchestrator.py` | `route()`, `_classify_intent()` |
| Base agent contract | `agents/base_agent.py` | `handle()`, `_call_tool()`, `_build_response()` |
| Network planning tools | `agents/network_planning.py` | `get_route_demand()`, `optimize_aircraft_assignment()` |
| Disruption simulation | `agents/disruption_analysis.py` | `simulate_weather_event()`, `suggest_mitigation()` |
| MCP message protocol | `mcp/protocol.py` | `MCPMessage`, `MCPResponse` dataclasses |
| Shared context store | `mcp/context_store.py` | `set()`, `get()`, `push_message()`, TTL logic |
| Tool registry | `mcp/tool_registry.py` | `register()`, `invoke()`, `get_tools_for_intent()` |
| LLM abstraction | `llm/mock_llm.py` | `generate()`, `classify_intent()`, `stream_response()` |
| Data models | `data/models.py` | Pydantic v2 `Flight`, `Route`, `Aircraft`, `Gate`, `Disruption` |
| Synthetic data | `data/synthetic_generator.py` | `generate_flights()`, `generate_routes()` |
| Configuration | `config.py` | `HUBS`, `AIRPORT_COORDS`, `SCENARIO_PRESETS`, `BEDROCK_MODEL_ID` |

---

## Key Numbers to Know

| Metric | Value | Context |
|---|---|---|
| Total flights in dataset | 200 | Generated with seed=42 |
| Total aircraft in fleet | 80 | 4 types: B737-MAX9, B787-9, B777-200, A319 |
| Hub airports | 8 | ORD, IAH, DEN, EWR, LAX, SFO, DCA, LAS |
| Routes in dataset | ~28 | Hub-to-hub combinations |
| Registered tools total | 15 | 5 per specialist agent |
| Flight status distribution | 80/12/5/3% | On Time / Delayed / Cancelled / Diverted |
| Average load factor | ~0.82 | Beta distribution, realistic |
| B737-MAX9 capacity | 178 seats | Range: 3,550 NM |
| B787-9 capacity | 252 seats | Range: 7,530 NM |
| B777-200 capacity | 364 seats | Range: 5,240 NM |
| A319 capacity | 128 seats | Range: 3,700 NM |
| Bedrock model (config) | claude-3-sonnet-20240229-v1:0 | In `config.py`, ready to activate |
| Context store lock type | threading.RLock | Reentrant, supports nested calls |
| Gate conflict threshold | 45 minutes | Time gap below which two flights share a gate |
| Frequency increase trigger | demand > 0.75 AND load > 0.85 | In `suggest_frequency_change()` |
| Underperforming threshold | demand < 0.30 OR load < 0.60 | In `get_underperforming_routes()` |
| Aircraft range buffer | 10% | `required_range = distance_nm * 1.1` |
| Critical weather cancellation | 40% | In `simulate_weather_event()` multipliers |
| Critical weather delay | 80% + 240 min avg | In `simulate_weather_event()` multipliers |
| Cascade delay factor | 50% of primary | Secondary flights at 50% primary delay rate |

---

*Prepared for interview with United Airlines / Insight Global — Senior GenAI / Multi-Agent Architect role.*  
*Demo project: UA Network Intelligence, built May 2026.*
