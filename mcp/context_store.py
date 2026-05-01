"""
MCP Context Store -- thread-safe shared memory for inter-agent state.

Supports key-value storage with optional TTL, conversation history tracking,
and session management.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from mcp.protocol import MCPMessage, MCPResponse


class MCPContextStore:
    """Thread-safe shared memory store for the multi-agent system.

    Provides:
    - Key-value storage with optional TTL (seconds).
    - Ordered conversation history (messages + responses).
    - Session-scoped data isolation.

    Example::

        ctx = MCPContextStore()
        ctx.set("weather_ord", {"temp": -5, "wind": 40}, ttl=300)
        data = ctx.get("weather_ord")  # returns dict or None after 300 s
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._store: Dict[str, Tuple[Any, Optional[float]]] = {}
        # value, expiry_timestamp (None = no expiry)
        self._history: List[Dict[str, Any]] = []
        self._sessions: Dict[str, Dict[str, Any]] = defaultdict(dict)

    # ------------------------------------------------------------------ #
    # Key-value operations
    # ------------------------------------------------------------------ #

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store a value, optionally with a time-to-live.

        Args:
            key: Storage key.
            value: Arbitrary Python object to store.
            ttl: Time-to-live in seconds. ``None`` means no expiration.
        """
        expiry = (time.monotonic() + ttl) if ttl is not None else None
        with self._lock:
            self._store[key] = (value, expiry)

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a value by key, respecting TTL expiry.

        Args:
            key: Storage key.
            default: Value returned if the key is missing or expired.

        Returns:
            The stored value or *default*.
        """
        with self._lock:
            if key not in self._store:
                return default
            value, expiry = self._store[key]
            if expiry is not None and time.monotonic() > expiry:
                del self._store[key]
                return default
            return value

    def delete(self, key: str) -> bool:
        """Remove a key from the store.

        Args:
            key: Storage key to delete.

        Returns:
            True if the key existed, False otherwise.
        """
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def keys(self) -> List[str]:
        """Return all non-expired keys.

        Returns:
            List of active key names.
        """
        now = time.monotonic()
        with self._lock:
            return [
                k for k, (_, exp) in self._store.items()
                if exp is None or now <= exp
            ]

    # ------------------------------------------------------------------ #
    # Conversation history
    # ------------------------------------------------------------------ #

    def push_message(
        self, message: MCPMessage, response: Optional[MCPResponse] = None
    ) -> None:
        """Record a message (and optional response) in conversation history.

        Args:
            message: The MCPMessage that was sent.
            response: The MCPResponse received, if any.
        """
        entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": message.to_dict(),
            "response": response.to_dict() if response else None,
        }
        with self._lock:
            self._history.append(entry)

    def get_conversation_history(
        self, last_n: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Return conversation history entries.

        Args:
            last_n: If provided, only the last *n* entries are returned.

        Returns:
            List of history entry dicts.
        """
        with self._lock:
            if last_n is not None:
                return list(self._history[-last_n:])
            return list(self._history)

    def get_session_summary(self) -> Dict[str, Any]:
        """Generate a summary of the current session.

        Returns:
            Dict containing message count, unique agents, and intent
            distribution.
        """
        with self._lock:
            total = len(self._history)
            agents: set[str] = set()
            intents: Dict[str, int] = defaultdict(int)
            for entry in self._history:
                msg = entry["message"]
                agents.add(msg["sender"])
                agents.add(msg["recipient"])
                intents[msg["intent"]] += 1

            return {
                "total_messages": total,
                "unique_agents": sorted(agents),
                "intent_distribution": dict(intents),
            }

    # ------------------------------------------------------------------ #
    # Session management
    # ------------------------------------------------------------------ #

    def clear_session(self) -> None:
        """Clear all stored data and conversation history."""
        with self._lock:
            self._store.clear()
            self._history.clear()
            self._sessions.clear()
