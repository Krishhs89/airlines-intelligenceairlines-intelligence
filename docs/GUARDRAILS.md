# Guardrails Guide

## Overview

The guardrails module (`guardrails/validators.py`) applies layered safety and quality controls to every user query and agent response in the UA Network Intelligence system.

Guardrails run automatically in the Orchestrator's `route()` method — no manual calls needed.

---

## Guardrail Layers

### Layer 1: Rate Limiting
- **Default**: 60 queries per 60-second sliding window
- **Mechanism**: In-memory timestamp deque; oldest entries pruned per call
- **Behavior on violation**: Raises `ValidationError` immediately (before all other checks)
- **Config**: `GUARDRAIL_RATE_LIMIT_PER_MINUTE` in `config.py`

### Layer 2: Input Length Enforcement
- **Default**: 2000 characters maximum
- **Behavior on violation**: Raises `ValidationError`
- **Config**: `GUARDRAIL_MAX_QUERY_LENGTH` in `config.py`

### Layer 3: Content Safety
Blocks queries containing any of these categories:
- **Security/hacking**: hack, exploit, sql injection, xss, csrf, malware, ransomware, phishing
- **Competitive intelligence abuse**: competitor sabotage, rival references
- **Sensitive operational data**: fuel dump coordinates, emergency override codes, ATC override
- **Off-topic**: recipes, sports scores, stock tips, crypto
- **Behavior on violation**: Raises `ValidationError` with matched terms

### Layer 4: PII Detection and Redaction
Detects and redacts these patterns (does NOT block — just sanitizes):
| PII Type | Pattern |
|----------|---------|
| Email | `user@domain.com` |
| Phone | `555-867-5309`, `(800) 555-1234` |
| SSN | `123-45-6789` |
| Credit Card | 13–16 digit sequences |
| Passport | `A1234567` style |

- **Behavior**: Returns `GuardrailResult.sanitized_text` with `[REDACTED]` replacements
- **Config**: `GUARDRAIL_ENABLE_PII_DETECTION` (default True)

### Layer 5: Output Validation (Response-side)
Applied after agent generates a response:
- **Length**: Truncates to `GUARDRAIL_MAX_RESPONSE_LENGTH` (default 10,000 chars) with notice
- **Confidence**: Warns if agent confidence < `GUARDRAIL_MIN_CONFIDENCE` (default 0.2)
- **PII in output**: Redacts any PII that slipped into the response text
- **Behavior**: Never blocks; only truncates, warns, or redacts

---

## Usage

### Automatic (via Orchestrator)
```python
from agents.orchestrator import OrchestratorAgent

orc = OrchestratorAgent.setup()
# Guardrails apply automatically on every route() call
response = orc.route("Which routes have low demand scores?")
```

If a query is blocked, the response will have:
```python
response.responder == "guardrail"
response.confidence == 0.0
response.result == {"violations": ["Rate limit exceeded: ..."]}
```

### Manual Usage
```python
from guardrails.validators import GuardrailValidator, ValidationError

v = GuardrailValidator()

# Input validation
try:
    result = v.validate_input("Analyze route ORD-LAX demand")
    if result.sanitized_text:
        query = result.sanitized_text  # PII was redacted
    if result.violations:
        print("Warnings:", result.violations)  # PII warnings
except ValidationError as e:
    print("Blocked:", e.violations)

# Output validation
result = v.validate_output(response_text="Analysis complete...", confidence=0.85)
final_text = result.sanitized_text or response_text
```

---

## Configuration

In `config.py` (all overridable via environment variables):

```python
GUARDRAIL_MAX_QUERY_LENGTH: int = 2000
GUARDRAIL_MAX_RESPONSE_LENGTH: int = 10000
GUARDRAIL_MIN_CONFIDENCE: float = 0.2
GUARDRAIL_ENABLE_PII_DETECTION: bool = True
GUARDRAIL_RATE_LIMIT_PER_MINUTE: int = 60
```

Override per-instance:
```python
v = GuardrailValidator(
    max_query_length=5000,
    rate_limit_per_minute=120,
    enable_pii=False,
)
```

---

## Stats and Monitoring

```python
stats = v.get_stats()
# {
#   "calls_last_minute": 12,
#   "rate_limit": 60,
#   "pii_enabled": True
# }
```

---

## Adding Custom Blocked Terms

Edit `_BLOCKED_TERMS` list in `guardrails/validators.py`:

```python
_BLOCKED_TERMS: List[str] = [
    "hack", "exploit",
    # Add your terms here
    "your_custom_term",
]
```

---

## Adding Custom PII Patterns

Edit `_PII_PATTERNS` list in `guardrails/validators.py`:

```python
_PII_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("email", re.compile(r"...")),
    # Add your pattern
    ("employee_id", re.compile(r"\bUA-\d{6}\b")),
]
```

---

## Error Response Format

When the orchestrator blocks a query, it returns a standard `MCPResponse`:

```python
MCPResponse(
    responder="guardrail",
    confidence=0.0,
    result={"violations": ["Rate limit exceeded: max 60 queries/minute"]},
    insight="Query blocked by safety guardrails: Rate limit exceeded",
    tool_calls=[],
)
```

---

## Testing Guardrails

```bash
pytest tests/test_guardrails.py -v
```

Key test cases:
- `test_email_is_redacted` — PII redaction works
- `test_blocked_term_raises` — content safety blocks malicious queries
- `test_query_over_limit_raises` — length enforcement
- `test_rate_limit_blocks_excess` — rate limiting
- `test_low_confidence_flagged` — output quality check
