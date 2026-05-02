"""
Guardrail validators for the UA Network Intelligence system.

Applies layered safety checks on every user query and agent response:
  1. Input length enforcement
  2. PII detection (email, phone, SSN, credit card)
  3. Content safety (blocked topics/terms)
  4. Output length and confidence validation
  5. Rate limiting (sliding-window per-minute counter)
"""

from __future__ import annotations

import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import config

# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class GuardrailResult:
    passed: bool
    violations: List[str] = field(default_factory=list)
    sanitized_text: Optional[str] = None

    @property
    def blocked(self) -> bool:
        return not self.passed


class ValidationError(Exception):
    """Raised when a guardrail blocks execution."""

    def __init__(self, violations: List[str]) -> None:
        self.violations = violations
        super().__init__("; ".join(violations))


# ---------------------------------------------------------------------------
# PII patterns
# ---------------------------------------------------------------------------

_PII_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("email", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b")),
    ("phone", re.compile(r"\b(\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}\b")),
    ("ssn", re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b")),
    ("credit_card", re.compile(r"\b(?:\d[ \-]?){13,16}\b")),
    ("passport", re.compile(r"\b[A-Z]{1,2}\d{6,9}\b")),
]

_PII_REPLACEMENT = "[REDACTED]"

# ---------------------------------------------------------------------------
# Content safety — blocked keywords/topics
# ---------------------------------------------------------------------------

_BLOCKED_TERMS: List[str] = [
    # Security / hacking
    "hack", "exploit", "vulnerability", "sql injection", "xss", "csrf",
    "malware", "ransomware", "phishing",
    # Competitor sabotage
    "competitor sabotage", "delta", "american airlines", "united rival",
    # Sensitive operational
    "fuel dump coordinates", "emergency override code", "atc override",
    # Off-topic
    "recipe", "sports score", "stock tip", "crypto",
]

# ---------------------------------------------------------------------------
# Main validator
# ---------------------------------------------------------------------------

class GuardrailValidator:
    """Applies all guardrail checks on inputs and outputs.

    Args:
        max_query_length: Character limit for user queries.
        max_response_length: Character limit for agent responses.
        min_confidence: Minimum acceptable confidence score.
        enable_pii: Whether to detect and redact PII.
        rate_limit_per_minute: Max queries per 60-second sliding window.
    """

    def __init__(
        self,
        max_query_length: int = config.GUARDRAIL_MAX_QUERY_LENGTH,
        max_response_length: int = config.GUARDRAIL_MAX_RESPONSE_LENGTH,
        min_confidence: float = config.GUARDRAIL_MIN_CONFIDENCE,
        enable_pii: bool = config.GUARDRAIL_ENABLE_PII_DETECTION,
        rate_limit_per_minute: int = config.GUARDRAIL_RATE_LIMIT_PER_MINUTE,
    ) -> None:
        self.max_query_length = max_query_length
        self.max_response_length = max_response_length
        self.min_confidence = min_confidence
        self.enable_pii = enable_pii
        self.rate_limit = rate_limit_per_minute
        self._call_timestamps: deque = deque()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def validate_input(self, query: str) -> GuardrailResult:
        """Run all input-side guardrails.

        Args:
            query: Raw user input string.

        Returns:
            GuardrailResult with pass/fail status and any violations found.
            If PII is detected, sanitized_text contains the redacted version.

        Raises:
            ValidationError: If any hard-block violation is found.
        """
        violations: List[str] = []

        # 1. Rate limit
        if not self._check_rate_limit():
            violations.append(
                f"Rate limit exceeded: max {self.rate_limit} queries/minute"
            )
            raise ValidationError(violations)

        # 2. Length
        if len(query) > self.max_query_length:
            violations.append(
                f"Query too long: {len(query)} chars (max {self.max_query_length})"
            )

        # 3. Content safety
        blocked = self._check_content_safety(query)
        if blocked:
            violations.append(f"Blocked content detected: {', '.join(blocked)}")

        if violations:
            raise ValidationError(violations)

        # 4. PII detection (soft — redact rather than block)
        sanitized, pii_found = self._redact_pii(query)
        result_violations = [f"PII redacted: {t}" for t in pii_found] if pii_found else []

        return GuardrailResult(
            passed=True,
            violations=result_violations,
            sanitized_text=sanitized if pii_found else None,
        )

    def validate_output(
        self, response_text: str, confidence: float
    ) -> GuardrailResult:
        """Run all output-side guardrails.

        Args:
            response_text: Agent response string.
            confidence: Agent's reported confidence score (0.0–1.0).

        Returns:
            GuardrailResult — always passes (truncates or warns but does not block).
        """
        violations: List[str] = []
        text = response_text

        if confidence < self.min_confidence:
            violations.append(
                f"Low confidence: {confidence:.2f} (min {self.min_confidence})"
            )

        if len(text) > self.max_response_length:
            text = text[: self.max_response_length] + "\n\n[Response truncated]"
            violations.append(
                f"Response truncated to {self.max_response_length} chars"
            )

        # Redact any PII that slipped into the output
        sanitized, pii_found = self._redact_pii(text)
        if pii_found:
            violations.append(f"PII in output redacted: {', '.join(pii_found)}")
            text = sanitized

        return GuardrailResult(passed=True, violations=violations, sanitized_text=text)

    def get_stats(self) -> Dict[str, Any]:
        """Return current rate-limit stats."""
        now = time.monotonic()
        recent = sum(1 for t in self._call_timestamps if now - t < 60)
        return {
            "calls_last_minute": recent,
            "rate_limit": self.rate_limit,
            "pii_enabled": self.enable_pii,
        }

    # ------------------------------------------------------------------ #
    # Private helpers
    # ------------------------------------------------------------------ #

    def _check_rate_limit(self) -> bool:
        now = time.monotonic()
        # Prune entries older than 60 s
        while self._call_timestamps and now - self._call_timestamps[0] > 60:
            self._call_timestamps.popleft()
        if len(self._call_timestamps) >= self.rate_limit:
            return False
        self._call_timestamps.append(now)
        return True

    def _check_content_safety(self, text: str) -> List[str]:
        lower = text.lower()
        return [term for term in _BLOCKED_TERMS if term in lower]

    def _redact_pii(self, text: str) -> Tuple[str, List[str]]:
        if not self.enable_pii:
            return text, []
        found: List[str] = []
        for label, pattern in _PII_PATTERNS:
            if pattern.search(text):
                text = pattern.sub(_PII_REPLACEMENT, text)
                found.append(label)
        return text, found
