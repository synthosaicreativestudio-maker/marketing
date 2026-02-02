import sqlite3
import json
import logging
import hashlib
from typing import Optional, Dict, List
from collections import OrderedDict

logger = logging.getLogger(__name__)


class PersistentCache:
    """SQLite-based persistent cache for responses and embeddings."""
    
    def __init__(self, db_path: str = "rag_cache.db", max_responses: int = 100):
        self.db_path = db_path
        self.max_responses = max_responses
        self._init_db()
        # In-memory LRU for fast access
        self._memory_cache: OrderedDict = OrderedDict()
        self._load_responses_to_memory()
    
    def _init_db(self):
        """Initialize SQLite database with tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Response cache table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS response_cache (
                        query_hash TEXT PRIMARY KEY,
                        query_normalized TEXT,
                        response TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Embeddings cache table (for pre-computed embeddings)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS embeddings_cache (
                        file_hash TEXT PRIMARY KEY,
                        file_name TEXT,
                        chunks_json TEXT,
                        tfidf_features TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.commit()
                logger.info(f"Persistent cache initialized: {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize cache DB: {e}")
    
    def _load_responses_to_memory(self):
        """Load cached responses into memory for fast access."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT query_hash, response FROM response_cache 
                    ORDER BY created_at DESC LIMIT ?
                """, (self.max_responses,))
                
                for row in cursor.fetchall():
                    self._memory_cache[row[0]] = row[1]
                
                logger.info(f"Loaded {len(self._memory_cache)} cached responses to memory")
        except Exception as e:
            logger.error(f"Failed to load cache to memory: {e}")
    
    def _hash_query(self, query: str) -> str:
        """Create hash from normalized query."""
        return hashlib.md5(query.encode()).hexdigest()
    
    def get_response(self, query_normalized: str) -> Optional[str]:
        """Get cached response for a query."""
        query_hash = self._hash_query(query_normalized)
        
        # Check memory first
        if query_hash in self._memory_cache:
            self._memory_cache.move_to_end(query_hash)
            return self._memory_cache[query_hash]
        
        return None
    
    def set_response(self, query_normalized: str, response: str):
        """Cache a response."""
        query_hash = self._hash_query(query_normalized)
        
        # Update memory cache
        if query_hash in self._memory_cache:
            self._memory_cache.move_to_end(query_hash)
        else:
            if len(self._memory_cache) >= self.max_responses:
                # Remove oldest from memory and DB
                oldest_hash = next(iter(self._memory_cache))
                del self._memory_cache[oldest_hash]
                self._delete_response_from_db(oldest_hash)
        
        self._memory_cache[query_hash] = response
        
        # Persist to DB
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO response_cache (query_hash, query_normalized, response)
                    VALUES (?, ?, ?)
                """, (query_hash, query_normalized, response))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to persist response: {e}")
    
    def _delete_response_from_db(self, query_hash: str):
        """Delete a response from database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM response_cache WHERE query_hash = ?", (query_hash,))
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to delete response: {e}")
    
    # === Embeddings Cache Methods ===
    
    def get_file_hash(self, file_path: str) -> str:
        """Calculate hash of file content."""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return ""
    
    def get_cached_chunks(self, file_hash: str) -> Optional[List[Dict]]:
        """Get cached chunks for a file."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT chunks_json FROM embeddings_cache WHERE file_hash = ?",
                    (file_hash,)
                )
                row = cursor.fetchone()
                if row:
                    return json.loads(row[0])
        except Exception as e:
            logger.error(f"Failed to get cached chunks: {e}")
        return None
    
    def cache_chunks(self, file_hash: str, file_name: str, chunks: List[Dict]):
        """Cache processed chunks for a file."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO embeddings_cache (file_hash, file_name, chunks_json)
                    VALUES (?, ?, ?)
                """, (file_hash, file_name, json.dumps(chunks, ensure_ascii=False)))
                conn.commit()
                logger.debug(f"Cached {len(chunks)} chunks for {file_name}")
        except Exception as e:
            logger.error(f"Failed to cache chunks: {e}")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        stats = {"responses": 0, "files": 0}
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM response_cache")
                stats["responses"] = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM embeddings_cache")
                stats["files"] = cursor.fetchone()[0]
        except Exception:
            pass
        return stats
