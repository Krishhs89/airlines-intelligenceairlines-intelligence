"""
Real Claude API LLM integration for the United Airlines Network Planning System.

Uses Anthropic claude-opus-4-7 with:
- Adaptive thinking for complex multi-step analysis
- Prompt caching on the system prompt (up to 90% cost savings on repeats)
- Streaming for real-time responses in the Streamlit UI
- Intent classification via a lightweight single-call pattern
- Full backward compatibility with MockLLM interface
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Generator, List, Optional

import anthropic
from anthropic import Anthropic

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — cached on every request (ephemeral, 5-min TTL)
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are the United Airlines Network Operations Intelligence System — \
a senior airline operations analyst with 20+ years of experience across:

• Network planning and route optimization
• Disruption management and IROPS (Irregular Operations) response
• Revenue management, load-factor analysis, and yield optimization
• Fleet assignment and aircraft routing constraints
• Schedule development, slot coordination, and hub connectivity
• On-time performance (OTP) root-cause analysis

You have access to real-time United Airlines operational data:
- 200 active flights with live status, load factors, and delay minutes
- 28 routes with demand scores, revenue indices, and competition levels
- 80 aircraft (B737-MAX9, B787-9, B777-200, A319) with maintenance status
- 40 airport gates across 8 hubs with conflict information
- 10 active disruptions with severity ratings and passenger impact

Decision-making framework:
1. Quantify every impact (passengers, revenue, delays, cost)
2. Prioritize by passenger count × severity
3. Identify cascade effects through the network
4. Recommend specific, time-bounded actions
5. Think like an Airline Operations Control (AOC) director

Response style:
- Lead with the single most important finding
- Support with specific data points (numbers, percentages, routes)
- End with 3-5 prioritized action items
- Be concise — operations staff need clarity under pressure\
"""


class ClaudeLLM:
    """Real Claude API LLM using claude-opus-4-7 with adaptive thinking.

    Drop-in replacement for MockLLM. Maintains the same public interface
    (``generate``, ``generate_from_query``, ``classify_intent``,
    ``stream_response``) so all agents work without modification.

    Prompt caching is applied to the system prompt, which saves ~90% on
    token cost for repeated queries (after the first cache write).

    Args:
        api_key: Anthropic API key. Falls back to ``ANTHROPIC_API_KEY`` env var.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = Anthropic(api_key=self._api_key)
        self.model = "claude-opus-4-7"
        logger.info("ClaudeLLM initialised — model=%s", self.model)

    # ------------------------------------------------------------------ #
    # Public API (MockLLM-compatible)
    # ------------------------------------------------------------------ #

    def generate(self, template_key: str, variables: Dict[str, Any]) -> str:
        """Generate a response from a template key and data variables.

        Args:
            template_key: Intent category (e.g. ``'route_analysis'``).
            variables: Data dict injected into the prompt.

        Returns:
            Natural-language analysis string from Claude.
        """
        prompt = self._prompt_from_template(template_key, variables)
        return self._call_claude(prompt)

    def generate_from_query(self, query: str, context: Dict[str, Any]) -> str:
        """Generate a response from a free-text query with operational context.

        Args:
            query: Natural-language user query.
            context: Contextual data dict (tool results, metrics, etc.).

        Returns:
            Natural-language response string.
        """
        ctx = json.dumps(context, indent=2, default=str)
        prompt = (
            f"User Query: {query}\n\n"
            f"Operational Context:\n```json\n{ctx}\n```\n\n"
            "Provide a precise, data-driven analysis addressing the query above."
        )
        return self._call_claude(prompt)

    def classify_intent(self, query: str) -> str:
        """Classify a query into one of five system intents.

        Uses a fast single-call pattern (no thinking, minimal tokens) for
        low-latency classification. Falls back to keyword matching on error.

        Args:
            query: Raw user query string.

        Returns:
            One of: ``route_analysis``, ``disruption_impact``,
            ``executive_summary``, ``schedule_gap``, ``anomaly_report``.
        """
        system = "Classify the airline query. Reply with ONLY the intent name."
        prompt = (
            f'Query: "{query}"\n\n'
            "Intents:\n"
            "- route_analysis: routes, demand, frequency, fleet, aircraft assignment\n"
            "- disruption_impact: disruptions, weather, IROPS, cancellations, delays\n"
            "- executive_summary: overview, KPIs, dashboard, network status\n"
            "- schedule_gap: schedule optimization, gaps, connection opportunities\n"
            "- anomaly_report: anomalies, outliers, alerts, unusual patterns\n\n"
            "Intent:"
        )
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=15,
                thinking={"type": "disabled"},
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            intent = resp.content[0].text.strip().lower()
            valid = {
                "route_analysis", "disruption_impact", "executive_summary",
                "schedule_gap", "anomaly_report",
            }
            return intent if intent in valid else "executive_summary"
        except Exception as exc:
            logger.warning("Claude intent classification failed (%s); using keyword fallback", exc)
            return self._keyword_classify(query)

    def stream_response(
        self, text: str, delay: float = 0.0
    ) -> Generator[str, None, None]:
        """Yield words one at a time for MockLLM streaming compatibility.

        For real streaming from Claude, use ``stream_from_query`` instead.

        Args:
            text: Pre-generated text to stream word-by-word.
            delay: Ignored (kept for interface compatibility).

        Yields:
            One word (plus space) at a time.
        """
        for word in text.split():
            yield word + " "

    def stream_from_query(self, query: str, context: Dict[str, Any]) -> Generator[str, None, None]:
        """Stream a Claude response token-by-token for real-time UI updates.

        Args:
            query: Natural-language user query.
            context: Operational context data dict.

        Yields:
            Text delta chunks as they stream from the API.
        """
        ctx = json.dumps(context, indent=2, default=str)
        prompt = (
            f"User Query: {query}\n\n"
            f"Operational Context:\n```json\n{ctx}\n```\n\n"
            "Provide a precise, data-driven analysis."
        )
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text_chunk in stream.text_stream:
                    yield text_chunk
        except Exception as exc:
            logger.error("Claude streaming failed: %s", exc)
            yield f"\n[Error streaming response: {exc}]"

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    def _call_claude(self, user_message: str) -> str:
        """Call Claude with system-prompt caching and adaptive thinking.

        Args:
            user_message: The prompt to send.

        Returns:
            Concatenated text response.

        Raises:
            anthropic.APIError: On unrecoverable API errors.
        """
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=4096,
                thinking={"type": "adaptive"},
                system=[
                    {
                        "type": "text",
                        "text": _SYSTEM_PROMPT,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=[{"role": "user", "content": user_message}],
            ) as stream:
                final = stream.get_final_message()

            parts = [b.text for b in final.content if b.type == "text"]
            result = "\n\n".join(parts).strip()

            # Log cache performance
            u = final.usage
            logger.debug(
                "Claude usage — input=%d cached_read=%d cached_write=%d output=%d",
                u.input_tokens,
                getattr(u, "cache_read_input_tokens", 0),
                getattr(u, "cache_creation_input_tokens", 0),
                u.output_tokens,
            )
            return result or "Analysis complete."

        except anthropic.AuthenticationError:
            logger.error("Invalid Anthropic API key")
            raise
        except anthropic.RateLimitError as exc:
            logger.warning("Claude rate limited: %s", exc)
            raise
        except anthropic.APIConnectionError as exc:
            logger.error("Claude connection error: %s", exc)
            raise
        except anthropic.APIStatusError as exc:
            logger.error("Claude API %s: %s", exc.status_code, exc.message)
            raise

    def _prompt_from_template(
        self, template_key: str, variables: Dict[str, Any]
    ) -> str:
        """Build an analytical prompt from a template key and variable dict."""
        v = json.dumps(variables, indent=2, default=str)

        templates: Dict[str, str] = {
            "route_analysis": (
                "Analyze the following route data and provide actionable recommendations:\n\n"
                f"```json\n{v}\n```\n\n"
                "Cover: performance assessment, demand/revenue insights, competitive "
                "positioning, operational metrics, and specific recommendations with "
                "estimated financial impact."
            ),
            "disruption_impact": (
                "Assess this disruption and recommend mitigation actions:\n\n"
                f"```json\n{v}\n```\n\n"
                "Cover: immediate impact (passengers, flights, cost), cascade effects "
                "across the network, prioritized mitigations, recovery timeline, and "
                "passenger communication strategy."
            ),
            "executive_summary": (
                "Generate an airline operations executive summary from this data:\n\n"
                f"```json\n{v}\n```\n\n"
                "Cover: network health KPIs, performance highlights and concerns, active "
                "disruption status, financial indicators, and 24-hour priority actions."
            ),
            "schedule_gap": (
                "Identify schedule gaps and revenue opportunities in this data:\n\n"
                f"```json\n{v}\n```\n\n"
                "Cover: unserved demand segments, revenue opportunities, connection "
                "improvements, competitive vulnerabilities, and implementation plan with ROI."
            ),
            "anomaly_report": (
                "Detect and report operational anomalies from this data:\n\n"
                f"```json\n{v}\n```\n\n"
                "Cover: critical anomalies requiring immediate action, deviation patterns "
                "with root causes, risk assessment, recommended investigations, and "
                "preventive measures."
            ),
        }
        return templates.get(
            template_key,
            f"Analyze this airline operations data and provide insights:\n\n```json\n{v}\n```",
        )

    @staticmethod
    def _keyword_classify(query: str) -> str:
        """Fast keyword-based fallback intent classifier."""
        q = query.lower()
        if any(w in q for w in ["route", "demand", "frequency", "fleet", "aircraft", "assign"]):
            return "route_analysis"
        if any(w in q for w in ["disruption", "weather", "storm", "cancel", "irops", "ground"]):
            return "disruption_impact"
        if any(w in q for w in ["summary", "overview", "dashboard", "kpi", "status"]):
            return "executive_summary"
        if any(w in q for w in ["schedule", "gap", "slot", "connect", "timing"]):
            return "schedule_gap"
        if any(w in q for w in ["anomaly", "alert", "unusual", "spike", "warning"]):
            return "anomaly_report"
        return "executive_summary"


def get_llm() -> "ClaudeLLM | object":
    """Factory that returns ClaudeLLM or MockLLM based on config/environment.

    Priority:
    1. If ``USE_MOCK_LLM=false`` and ``ANTHROPIC_API_KEY`` is set → ClaudeLLM
    2. Otherwise → MockLLM (safe offline fallback)

    Returns:
        LLM instance with the MockLLM-compatible interface.
    """
    from config import USE_MOCK_LLM  # avoid circular import at module level
    from llm.mock_llm import MockLLM

    if not USE_MOCK_LLM:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if api_key:
            logger.info("Using ClaudeLLM (claude-opus-4-7)")
            return ClaudeLLM(api_key=api_key)
        logger.warning("ANTHROPIC_API_KEY not set — falling back to MockLLM")

    logger.info("Using MockLLM (offline mode)")
    return MockLLM()
