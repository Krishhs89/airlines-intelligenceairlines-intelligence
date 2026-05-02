"""
Tests for the guardrails validation layer.

Covers:
  - Input length enforcement
  - PII detection and redaction
  - Content safety blocking
  - Output validation
  - Rate limiting
"""

from __future__ import annotations

import pytest
from guardrails.validators import GuardrailValidator, GuardrailResult, ValidationError


@pytest.fixture
def validator():
    return GuardrailValidator(
        max_query_length=500,
        max_response_length=2000,
        min_confidence=0.2,
        enable_pii=True,
        rate_limit_per_minute=100,
    )


# ---------------------------------------------------------------------------
# Input validation — length
# ---------------------------------------------------------------------------

class TestInputLength:

    def test_valid_query_passes(self, validator):
        result = validator.validate_input("What is the on-time performance at ORD?")
        assert result.passed

    def test_query_at_limit_passes(self, validator):
        query = "a" * 500
        result = validator.validate_input(query)
        assert result.passed

    def test_query_over_limit_raises(self, validator):
        query = "a" * 501
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_input(query)
        assert "too long" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# PII detection
# ---------------------------------------------------------------------------

class TestPIIDetection:

    def test_email_is_redacted(self, validator):
        result = validator.validate_input("Contact ops at john.doe@united.com for info")
        assert result.passed
        assert "email" in result.violations[0]
        assert "john.doe@united.com" not in (result.sanitized_text or "")
        assert "[REDACTED]" in (result.sanitized_text or "")

    def test_phone_is_redacted(self, validator):
        result = validator.validate_input("Call 555-867-5309 for dispatch")
        assert result.passed
        assert result.sanitized_text is not None
        assert "555-867-5309" not in result.sanitized_text

    def test_ssn_is_redacted(self, validator):
        result = validator.validate_input("Employee SSN 123-45-6789")
        assert result.passed
        assert "ssn" in [v.split(":")[1].strip() for v in result.violations]

    def test_clean_query_no_violations(self, validator):
        result = validator.validate_input("Analyze route ORD-LAX demand trends")
        assert result.passed
        assert len(result.violations) == 0
        assert result.sanitized_text is None

    def test_pii_disabled(self):
        v = GuardrailValidator(enable_pii=False)
        result = v.validate_input("Email ops@united.com for status")
        assert result.passed
        assert len(result.violations) == 0


# ---------------------------------------------------------------------------
# Content safety
# ---------------------------------------------------------------------------

class TestContentSafety:

    def test_blocked_term_raises(self, validator):
        with pytest.raises(ValidationError) as exc_info:
            validator.validate_input("How do I sql injection the flight database?")
        assert "Blocked" in str(exc_info.value)

    def test_legitimate_query_passes(self, validator):
        result = validator.validate_input("What is the delay trend for B737-MAX9?")
        assert result.passed

    def test_hacking_term_blocked(self, validator):
        with pytest.raises(ValidationError):
            validator.validate_input("hack into the ACARS system")

    def test_malware_blocked(self, validator):
        with pytest.raises(ValidationError):
            validator.validate_input("install malware on the dispatch computer")


# ---------------------------------------------------------------------------
# Output validation
# ---------------------------------------------------------------------------

class TestOutputValidation:

    def test_normal_output_passes(self, validator):
        result = validator.validate_output("Route analysis complete. On-time: 87%.", 0.85)
        assert result.passed

    def test_low_confidence_flagged(self, validator):
        result = validator.validate_output("Some analysis.", 0.1)
        assert result.passed  # output validation doesn't block, just warns
        assert any("confidence" in v.lower() for v in result.violations)

    def test_long_output_truncated(self, validator):
        long_text = "x" * 3000
        result = validator.validate_output(long_text, 0.8)
        assert result.passed
        assert len(result.sanitized_text) <= 2100  # 2000 + truncation message
        assert "truncated" in result.sanitized_text.lower()

    def test_pii_in_output_redacted(self, validator):
        result = validator.validate_output(
            "Send report to dispatch@united.com immediately.", 0.9
        )
        assert result.passed
        assert "dispatch@united.com" not in (result.sanitized_text or "")


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:

    def test_rate_limit_allows_normal_traffic(self):
        v = GuardrailValidator(rate_limit_per_minute=10)
        for _ in range(5):
            result = v.validate_input("Query about flight status")
            assert result.passed

    def test_rate_limit_blocks_excess(self):
        v = GuardrailValidator(rate_limit_per_minute=3)
        for _ in range(3):
            v.validate_input("Normal query")
        with pytest.raises(ValidationError) as exc_info:
            v.validate_input("One more query")
        assert "rate limit" in str(exc_info.value).lower()

    def test_get_stats(self, validator):
        stats = validator.get_stats()
        assert "calls_last_minute" in stats
        assert "rate_limit" in stats
        assert stats["pii_enabled"] is True
