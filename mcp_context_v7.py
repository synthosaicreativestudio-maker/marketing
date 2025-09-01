"""Enhanced MCP Context v8 adapter with persistence and improved functionality.

This module provides an enhanced Model Context Protocol (MCP) style context manager
with optional file persistence, better thread management, and integration with
the marketing bot's needs. Includes automatic cleanup and session persistence.
"""
from __future__ import annotations

import json
import os
import time
import uuid
from collections import deque
from typing import Dict, Deque, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

class MCPContextV8:
    def __init__(self, max_messages: int = 200, persistence_file: Optional[str] = None):
        # mapping thread_id -> deque of (role, text, timestamp)
        self._store: Dict[str, Deque[Tuple[str, str, float]]] = {}
        # mapping user_key (telegram_id) -> thread_id
        self._user_map: Dict[str, str] = {}
        # mapping thread_id -> last_activity_time
        self._thread_activity: Dict[str, float] = {}
        
        self.max_messages = max_messages
        self.persistence_file = persistence_file or 'mcp_context_data.json'
        self.max_thread_idle_time = 3600 * 24  # 24 hours
        
        self._load_from_file()
    
    def _load_from_file(self):
        """Load context data from persistence file"""
        if not os.path.exists(self.persistence_file):
            return
            
        try:
            with open(self.persistence_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Restore thread store
            for thread_id, messages in data.get('threads', {}).items():
                self._store[thread_id] = deque(
                    [(msg['role'], msg['text'], msg['timestamp']) for msg in messages[-self.max_messages:]],
                    maxlen=self.max_messages
                )
                
            # Restore user mappings
            self._user_map = data.get('user_map', {})
            
            # Restore activity tracking
            self._thread_activity = data.get('thread_activity', {})
            
            logger.info(f'Loaded MCP context: {len(self._store)} threads, {len(self._user_map)} users')
            
        except Exception as e:
            logger.warning(f'Failed to load MCP context from {self.persistence_file}: {e}')
    
    def _save_to_file(self):
        """Save context data to persistence file"""
        try:
            # Clean up old threads before saving
            self._cleanup_old_threads()
            
            data = {
                'threads': {
                    thread_id: [
                        {'role': role, 'text': text, 'timestamp': timestamp}
                        for role, text, timestamp in messages
                    ]
                    for thread_id, messages in self._store.items()
                },
                'user_map': self._user_map,
                'thread_activity': self._thread_activity,
                'last_saved': time.time()
            }
            
            with open(self.persistence_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
            logger.debug(f'Saved MCP context to {self.persistence_file}')
            
        except Exception as e:
            logger.error(f'Failed to save MCP context to {self.persistence_file}: {e}')
    
    def _cleanup_old_threads(self):
        """Remove threads that haven't been active for too long"""
        current_time = time.time()
        old_threads = [
            thread_id for thread_id, last_activity in self._thread_activity.items()
            if current_time - last_activity > self.max_thread_idle_time
        ]
        
        for thread_id in old_threads:
            if thread_id in self._store:
                del self._store[thread_id]
            if thread_id in self._thread_activity:
                del self._thread_activity[thread_id]
                
        # Also clean up user mappings pointing to removed threads
        users_to_clean = [
            user_key for user_key, thread_id in self._user_map.items()
            if thread_id in old_threads
        ]
        
        for user_key in users_to_clean:
            del self._user_map[user_key]
            
        if old_threads:
            logger.info(f'Cleaned up {len(old_threads)} old threads')
    
    def _update_thread_activity(self, thread_id: str):
        """Update the last activity time for a thread"""
        self._thread_activity[thread_id] = time.time()
    def _ensure_thread(self, thread_id: str):
        if thread_id not in self._store:
            self._store[thread_id] = deque(maxlen=self.max_messages)
            self._update_thread_activity(thread_id)

    def create_thread(self, user_key: str) -> str:
        thread_id = str(uuid.uuid4())
        self._ensure_thread(thread_id)
        self._user_map[str(user_key)] = thread_id
        logger.info(f'Created new thread {thread_id} for user {user_key}')
        self._save_to_file()
        return thread_id

    def register_thread(self, thread_id: str, user_key: str) -> None:
        """Associate an externally-created thread_id with a user_key."""
        if not thread_id:
            return
        self._ensure_thread(thread_id)
        self._user_map[str(user_key)] = thread_id
        logger.debug(f'Registered existing thread {thread_id} for user {user_key}')
        self._save_to_file()

    def get_thread_for_user(self, user_key: str) -> str | None:
        return self._user_map.get(str(user_key))

    def append_message(self, thread_id: str, role: str, text: str) -> None:
        if not thread_id:
            return
        self._ensure_thread(thread_id)
        self._store[thread_id].append((role, text, time.time()))
        self._update_thread_activity(thread_id)
        
        # Auto-save every few messages to prevent data loss
        total_messages = sum(len(messages) for messages in self._store.values())
        if total_messages % 10 == 0:
            self._save_to_file()

    def get_messages(self, thread_id: str) -> List[Tuple[str, str, float]]:
        if not thread_id:
            return []
        self._ensure_thread(thread_id)
        self._update_thread_activity(thread_id)
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
        self._update_thread_activity(thread_id)
        logger.debug(f'Pruned thread {thread_id} to {keep} messages')
        self._save_to_file()
    
    def get_context_summary(self, thread_id: str, max_chars: int = 1000) -> str:
        """Get a summary of the conversation context for the thread"""
        messages = self.get_messages(thread_id)
        if not messages:
            return "No conversation history"
        
        # Get recent messages that fit within character limit
        summary_parts = []
        char_count = 0
        
        for role, text, timestamp in reversed(messages):
            message_part = f"{role}: {text[:200]}..."
            if char_count + len(message_part) > max_chars:
                break
            summary_parts.insert(0, message_part)
            char_count += len(message_part)
        
        return "\n".join(summary_parts)
    
    def get_stats(self) -> Dict[str, int]:
        """Get statistics about the MCP context"""
        total_messages = sum(len(messages) for messages in self._store.values())
        active_threads = sum(1 for thread_id in self._store.keys() 
                           if time.time() - self._thread_activity.get(thread_id, 0) < 3600)
        
        return {
            'total_threads': len(self._store),
            'total_users': len(self._user_map),
            'total_messages': total_messages,
            'active_threads_last_hour': active_threads
        }
    
    def cleanup_and_save(self):
        """Perform cleanup and save data"""
        self._cleanup_old_threads()
        self._save_to_file()


# Update the global instance to use the enhanced version
mcp_context = MCPContextV8()
