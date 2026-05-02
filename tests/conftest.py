"""
Shared pytest configuration and fixtures.

Sets the working directory and Python path so imports resolve correctly
when pytest is run from any directory.
"""

import os
import sys

# Ensure project root is on the path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Force MockLLM in tests (no API key required)
os.environ.setdefault("USE_MOCK_LLM", "true")
