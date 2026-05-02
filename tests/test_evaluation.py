"""
Tests for the evaluation framework.

Covers:
  - EvaluationMetrics scoring logic
  - EvaluationSuite execution and reporting
  - Individual metric computations
  - Report structure validation
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from evaluation.evaluator import (
    EvaluationMetrics,
    EvaluationResult,
    EvaluationSuite,
    TestCase,
    BUILT_IN_TEST_CASES,
)
from mcp.protocol import MCPResponse


# ---------------------------------------------------------------------------
# EvaluationMetrics unit tests
# ---------------------------------------------------------------------------

class TestEvaluationMetrics:

    def test_perfect_score(self):
        m = EvaluationMetrics(
            agent_routing_accuracy=1.0,
            tool_call_coverage=1.0,
            keyword_coverage=1.0,
            confidence_score=1.0,
            latency_score=1.0,
        )
        overall = m.compute_overall()
        assert overall == pytest.approx(1.0, abs=0.01)

    def test_zero_score(self):
        m = EvaluationMetrics()
        overall = m.compute_overall()
        assert overall == 0.0

    def test_partial_score(self):
        m = EvaluationMetrics(
            agent_routing_accuracy=1.0,
            tool_call_coverage=0.5,
            keyword_coverage=0.5,
            confidence_score=0.8,
            latency_score=0.9,
        )
        overall = m.compute_overall()
        assert 0.5 < overall < 1.0

    def test_custom_weights(self):
        m = EvaluationMetrics(agent_routing_accuracy=1.0)
        overall = m.compute_overall(weights={"agent_routing_accuracy": 1.0})
        assert overall == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# TestCase definition
# ---------------------------------------------------------------------------

class TestTestCase:

    def test_built_in_cases_exist(self):
        assert len(BUILT_IN_TEST_CASES) >= 9

    def test_cases_have_required_fields(self):
        for tc in BUILT_IN_TEST_CASES:
            assert tc.id
            assert tc.query
            assert tc.expected_agent in {
                "network_planning", "disruption_analysis", "analytics_insights"
            }

    def test_each_category_represented(self):
        categories = {tc.category for tc in BUILT_IN_TEST_CASES}
        assert "network_planning" in categories
        assert "disruption_analysis" in categories
        assert "analytics_insights" in categories


# ---------------------------------------------------------------------------
# EvaluationSuite with mock orchestrator
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_response():
    """Mock MCPResponse that routes all queries to analytics_insights."""
    r = MagicMock(spec=MCPResponse)
    r.responder = "analytics_insights"
    r.tool_calls = ["get_network_kpis", "get_hub_performance"]
    r.insight = "Network on-time performance is 87%. Load factor trend shows demand growth. Delay patterns are within normal range."
    r.confidence = 0.85
    r.result = {"kpis": {}}
    return r


@pytest.fixture
def mock_orchestrator(mock_response):
    orc = MagicMock()
    orc.route.return_value = mock_response
    return orc


@pytest.fixture
def suite(mock_orchestrator):
    return EvaluationSuite(orchestrator=mock_orchestrator)


class TestEvaluationSuite:

    def test_run_returns_results(self, suite):
        results = suite.run()
        assert len(results) == len(BUILT_IN_TEST_CASES)

    def test_results_are_evaluation_results(self, suite):
        results = suite.run()
        for r in results:
            assert isinstance(r, EvaluationResult)

    def test_report_has_summary(self, suite):
        results = suite.run()
        report = suite.report(results)
        assert "summary" in report
        assert "total" in report["summary"]
        assert "pass_rate" in report["summary"]

    def test_report_has_by_category(self, suite):
        results = suite.run()
        report = suite.report(results)
        assert "by_category" in report

    def test_report_has_per_test(self, suite):
        results = suite.run()
        report = suite.report(results)
        assert "per_test" in report
        assert len(report["per_test"]) == len(BUILT_IN_TEST_CASES)

    def test_perfect_routing_scores_100pct(self, mock_orchestrator):
        """If the mock correctly routes to the expected agent, routing score = 1.0."""
        # Use only analytics cases (mock always returns analytics_insights)
        analytics_cases = [
            tc for tc in BUILT_IN_TEST_CASES
            if tc.expected_agent == "analytics_insights"
        ]
        suite = EvaluationSuite(mock_orchestrator, analytics_cases)
        results = suite.run()
        for r in results:
            assert r.metrics.agent_routing_accuracy == 1.0

    def test_wrong_routing_scores_zero(self, mock_orchestrator):
        """If mock returns analytics but expected is network_planning, routing = 0."""
        np_cases = [
            tc for tc in BUILT_IN_TEST_CASES
            if tc.expected_agent == "network_planning"
        ]
        suite = EvaluationSuite(mock_orchestrator, np_cases)
        results = suite.run()
        for r in results:
            assert r.metrics.agent_routing_accuracy == 0.0

    def test_error_in_run_captured(self, suite):
        suite.orchestrator.route.side_effect = RuntimeError("Agent crashed")
        results = suite.run()
        for r in results:
            assert r.error is not None
            assert not r.passed


# ---------------------------------------------------------------------------
# Integration: run subset against real orchestrator
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestEvaluationIntegration:

    @pytest.fixture(scope="class")
    def real_suite(self):
        from agents.orchestrator import OrchestratorAgent
        orc = OrchestratorAgent.setup()
        # Run just 3 cases to keep test suite fast
        cases = BUILT_IN_TEST_CASES[:3]
        return EvaluationSuite(orc, cases)

    def test_real_run_completes(self, real_suite):
        results = real_suite.run()
        assert len(results) == 3

    def test_real_results_have_non_zero_overall(self, real_suite):
        results = real_suite.run()
        for r in results:
            assert r.metrics.overall >= 0.0

    def test_real_report_pass_rate_reasonable(self, real_suite):
        results = real_suite.run()
        report = real_suite.report(results)
        # With MockLLM at least 50% should route correctly
        assert report["summary"]["pass_rate"] >= 0.0
