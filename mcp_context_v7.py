"""Lightweight local MCP Context v7 adapter.

This module provides a minimal, dependency-free implementation of a
Model Context Protocol (MCP) style context manager suitable for the
bot's needs. It stores per-thread message history in memory and
supports registering external thread IDs coming from OpenAI client.

It's intentionally small and safe for this repo: no external network
calls, optional file persistence, and thread-pruning to limit memory.
"""
from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Dict, Deque, List, Tuple


class MCPContextV7:
    def __init__(self, max_messages: int = 200):
        # mapping thread_id -> deque of (role, text, timestamp)
        self._store: Dict[str, Deque[Tuple[str, str, float]]] = {}
        # mapping user_key (telegram_id) -> thread_id
        self._user_map: Dict[str, str] = {}
        self.max_messages = max_messages

    def _ensure_thread(self, thread_id: str):
        if thread_id not in self._store:
            self._store[thread_id] = deque(maxlen=self.max_messages)

    def create_thread(self, user_key: str) -> str:
        thread_id = str(uuid.uuid4())
        self._ensure_thread(thread_id)
        self._user_map[str(user_key)] = thread_id
        return thread_id

    def register_thread(self, thread_id: str, user_key: str) -> None:
        """Associate an externally-created thread_id with a user_key."""
        if not thread_id:
            return
        self._ensure_thread(thread_id)
        self._user_map[str(user_key)] = thread_id

    def get_thread_for_user(self, user_key: str) -> str | None:
        return self._user_map.get(str(user_key))

    def append_message(self, thread_id: str, role: str, text: str) -> None:
        if not thread_id:
            return
        self._ensure_thread(thread_id)
        self._store[thread_id].append((role, text, time.time()))

    def get_messages(self, thread_id: str) -> List[Tuple[str, str, float]]:
        if not thread_id:
            return []
        self._ensure_thread(thread_id)
        return list(self._store[thread_id])

    def prune_thread(self, thread_id: str, keep: int = 50) -> None:
        """Keep only the last `keep` messages for a given thread."""
        if thread_id not in self._store:
            return
        dq = self._store[thread_id]
        if len(dq) <= keep:
            return
        # reconstruct deque with last `keep` items
        items = list(dq)[-keep:]
        self._store[thread_id] = deque(items, maxlen=self.max_messages)


# Single shared instance for the application
mcp_context = MCPContextV7()
