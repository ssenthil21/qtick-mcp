"""In-memory conversation history for agent runs."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Deque, Dict, Iterable, List


@dataclass
class ConversationTurn:
    """Represents one complete exchange between the user and the assistant."""

    user: str
    assistant: str


class ConversationMemoryStore:
    """Thread-safe store that keeps the last N conversation turns per session."""

    def __init__(self, max_turns: int = 15) -> None:
        self._max_turns = max_turns
        self._store: Dict[str, Deque[ConversationTurn]] = {}
        self._lock = Lock()

    def get_history(self, conversation_id: str) -> List[ConversationTurn]:
        """Return the stored history for the given conversation."""

        with self._lock:
            history = self._store.get(conversation_id)
            if not history:
                return []
            return list(history)

    def append(self, conversation_id: str, user_message: str, assistant_message: str) -> None:
        """Append a new turn to the history, enforcing the max window size."""

        with self._lock:
            history = self._store.setdefault(
                conversation_id, deque(maxlen=self._max_turns)
            )
            history.append(
                ConversationTurn(user=user_message.strip(), assistant=assistant_message.strip())
            )

    def reset(self, conversation_id: str) -> None:
        """Clear the stored history for a conversation."""

        with self._lock:
            self._store.pop(conversation_id, None)

    def clear(self) -> None:
        """Remove every stored conversation. Intended for tests only."""

        with self._lock:
            self._store.clear()

    def values(self) -> Iterable[List[ConversationTurn]]:
        """Return a snapshot of all stored histories."""

        with self._lock:
            return [list(history) for history in self._store.values()]


conversation_memory = ConversationMemoryStore()
"""Module-level store used by the agent endpoints."""
