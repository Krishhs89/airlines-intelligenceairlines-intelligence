"""
Evaluation framework for the UA Network Intelligence multi-agent system.

Provides:
  - TestCase: defines a query + expected properties
  - EvaluationMetrics: scores for a single test run
  - EvaluationResult: full result for one test case
  - EvaluationSuite: runs all test cases and aggregates scores
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Test Case definition
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    """Defines one evaluation test case.

    Attributes:
        id: Unique identifier.
        query: The user query to send to the orchestrator.
        expected_agent: Which specialist agent should handle it.
        required_tool_calls: Tool names that must appear in the response.
        required_keywords: Words that should appear in the insight text.
        min_confidence: Minimum expected confidence score.
        category: Grouping label for reporting.
    """

    id: str
    query: str
    expected_agent: str
    required_tool_calls: List[str] = field(default_factory=list)
    required_keywords: List[str] = field(default_factory=list)
    min_confidence: float = 0.5
    category: str = "general"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class EvaluationMetrics:
    """Scores for a single evaluation run (all values 0.0–1.0)."""

    agent_routing_accuracy: float = 0.0    # Correct agent dispatched
    tool_call_coverage: float = 0.0        # Required tools were called
    keyword_coverage: float = 0.0          # Required keywords in output
    confidence_score: float = 0.0          # Agent confidence
    latency_score: float = 0.0             # Speed (1.0 = <1 s, 0.0 = >10 s)
    overall: float = 0.0                   # Weighted composite

    def compute_overall(
        self,
        weights: Optional[Dict[str, float]] = None,
    ) -> float:
        w = weights or {
            "agent_routing_accuracy": 0.30,
            "tool_call_coverage": 0.25,
            "keyword_coverage": 0.20,
            "confidence_score": 0.15,
            "latency_score": 0.10,
        }
        self.overall = sum(
            getattr(self, k) * v for k, v in w.items()
        )
        return self.overall


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

@dataclass
class EvaluationResult:
    """Full result for one test case."""

    test_case: TestCase
    metrics: EvaluationMetrics
    actual_agent: str
    actual_tool_calls: List[str]
    response_text: str
    latency_seconds: float
    error: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.error is None and self.metrics.overall >= 0.6


# ---------------------------------------------------------------------------
# Built-in test cases
# ---------------------------------------------------------------------------

BUILT_IN_TEST_CASES: List[TestCase] = [
    # Network planning
    TestCase(
        id="np_01",
        query="Which routes have the lowest demand score and should be reviewed for frequency reduction?",
        expected_agent="network_planning",
        required_tool_calls=["get_underperforming_routes"],
        required_keywords=["route", "demand"],
        min_confidence=0.6,
        category="network_planning",
    ),
    TestCase(
        id="np_02",
        query="Show me gate conflicts at ORD hub and suggest resolution.",
        expected_agent="network_planning",
        required_tool_calls=["get_schedule_conflicts"],
        required_keywords=["conflict"],
        min_confidence=0.6,
        category="network_planning",
    ),
    TestCase(
        id="np_03",
        query="Find schedule gaps and overlapping flights.",
        expected_agent="network_planning",
        required_tool_calls=["get_schedule_conflicts"],
        required_keywords=["schedule", "conflict"],
        min_confidence=0.5,
        category="network_planning",
    ),
    # Disruption analysis
    TestCase(
        id="da_01",
        query="Assess the weather impact on ORD operations today.",
        expected_agent="disruption_analysis",
        required_tool_calls=["simulate_weather_event"],
        required_keywords=["flight", "delay"],
        min_confidence=0.6,
        category="disruption_analysis",
    ),
    TestCase(
        id="da_02",
        query="What is the passenger impact from the current disruptions?",
        expected_agent="disruption_analysis",
        required_tool_calls=["calculate_pax_impact"],
        required_keywords=["passenger"],
        min_confidence=0.5,
        category="disruption_analysis",
    ),
    TestCase(
        id="da_03",
        query="Which flights should be cancelled first if we have a gate closure at EWR?",
        expected_agent="disruption_analysis",
        required_tool_calls=["simulate_gate_closure"],
        required_keywords=["gate"],
        min_confidence=0.5,
        category="disruption_analysis",
    ),
    # Analytics insights
    TestCase(
        id="ai_01",
        query="Give me an executive summary of today's network operations.",
        expected_agent="analytics_insights",
        required_tool_calls=["generate_executive_summary"],
        required_keywords=["on-time", "load"],
        min_confidence=0.6,
        category="analytics_insights",
    ),
    TestCase(
        id="ai_02",
        query="Detect anomalies in flight delay patterns across the hub network.",
        expected_agent="analytics_insights",
        required_tool_calls=["flag_anomalies"],
        required_keywords=["anomaly", "delay"],
        min_confidence=0.5,
        category="analytics_insights",
    ),
    TestCase(
        id="ai_03",
        query="What are the load factor trends for our top revenue routes?",
        expected_agent="analytics_insights",
        required_tool_calls=["compute_load_factor_trends"],
        required_keywords=["load factor"],
        min_confidence=0.5,
        category="analytics_insights",
    ),
]


# ---------------------------------------------------------------------------
# Evaluation Suite
# ---------------------------------------------------------------------------

class EvaluationSuite:
    """Runs a suite of test cases against the orchestrator and scores results.

    Args:
        orchestrator: An OrchestratorAgent instance.
        test_cases: List of TestCase objects. Defaults to built-in cases.
    """

    def __init__(
        self,
        orchestrator: Any,
        test_cases: Optional[List[TestCase]] = None,
    ) -> None:
        self.orchestrator = orchestrator
        self.test_cases = test_cases or BUILT_IN_TEST_CASES

    def run(self) -> List[EvaluationResult]:
        """Execute all test cases and return results."""
        results: List[EvaluationResult] = []
        for tc in self.test_cases:
            result = self._run_one(tc)
            results.append(result)
            status = "PASS" if result.passed else "FAIL"
            logger.info(
                "[%s] %s — overall=%.2f latency=%.2fs",
                status, tc.id, result.metrics.overall, result.latency_seconds,
            )
        return results

    def report(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """Aggregate results into a summary report."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        avg_overall = sum(r.metrics.overall for r in results) / total if total else 0
        avg_latency = sum(r.latency_seconds for r in results) / total if total else 0

        by_category: Dict[str, Dict] = {}
        for r in results:
            cat = r.test_case.category
            if cat not in by_category:
                by_category[cat] = {"total": 0, "passed": 0, "avg_overall": 0.0}
            by_category[cat]["total"] += 1
            by_category[cat]["passed"] += int(r.passed)
            by_category[cat]["avg_overall"] += r.metrics.overall

        for cat, stats in by_category.items():
            stats["avg_overall"] /= stats["total"]
            stats["pass_rate"] = stats["passed"] / stats["total"]

        return {
            "summary": {
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": passed / total if total else 0,
                "avg_overall_score": round(avg_overall, 3),
                "avg_latency_seconds": round(avg_latency, 3),
            },
            "by_category": by_category,
            "per_test": [
                {
                    "id": r.test_case.id,
                    "category": r.test_case.category,
                    "passed": r.passed,
                    "overall": round(r.metrics.overall, 3),
                    "agent_routing": round(r.metrics.agent_routing_accuracy, 3),
                    "tool_coverage": round(r.metrics.tool_call_coverage, 3),
                    "keyword_coverage": round(r.metrics.keyword_coverage, 3),
                    "confidence": round(r.metrics.confidence_score, 3),
                    "latency_s": round(r.latency_seconds, 3),
                    "error": r.error,
                }
                for r in results
            ],
        }

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _run_one(self, tc: TestCase) -> EvaluationResult:
        start = time.perf_counter()
        try:
            from mcp.protocol import MCPResponse
            response: MCPResponse = self.orchestrator.route(tc.query)
            latency = time.perf_counter() - start

            actual_agent = response.responder
            tool_calls = response.tool_calls or []
            insight = response.insight or ""
            confidence = response.confidence or 0.0

            metrics = self._score(tc, actual_agent, tool_calls, insight, confidence, latency)
            return EvaluationResult(
                test_case=tc,
                metrics=metrics,
                actual_agent=actual_agent,
                actual_tool_calls=tool_calls,
                response_text=insight,
                latency_seconds=latency,
            )
        except Exception as exc:
            latency = time.perf_counter() - start
            logger.warning("Test %s raised: %s", tc.id, exc)
            return EvaluationResult(
                test_case=tc,
                metrics=EvaluationMetrics(),
                actual_agent="",
                actual_tool_calls=[],
                response_text="",
                latency_seconds=latency,
                error=str(exc),
            )

    @staticmethod
    def _score(
        tc: TestCase,
        actual_agent: str,
        tool_calls: List[str],
        insight: str,
        confidence: float,
        latency: float,
    ) -> EvaluationMetrics:
        m = EvaluationMetrics()

        # 1. Agent routing accuracy
        m.agent_routing_accuracy = 1.0 if actual_agent == tc.expected_agent else 0.0

        # 2. Tool call coverage
        if tc.required_tool_calls:
            covered = sum(
                1 for t in tc.required_tool_calls if t in tool_calls
            )
            m.tool_call_coverage = covered / len(tc.required_tool_calls)
        else:
            m.tool_call_coverage = 1.0

        # 3. Keyword coverage
        if tc.required_keywords:
            lower_insight = insight.lower()
            covered = sum(
                1 for kw in tc.required_keywords if kw.lower() in lower_insight
            )
            m.keyword_coverage = covered / len(tc.required_keywords)
        else:
            m.keyword_coverage = 1.0

        # 4. Confidence score (normalised)
        m.confidence_score = min(confidence, 1.0)

        # 5. Latency score (1.0 under 1 s → 0.0 at 10 s+)
        m.latency_score = max(0.0, 1.0 - (latency - 1.0) / 9.0)

        m.compute_overall()
        return m
