import logging
import re
from typing import List, Dict, Optional
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

class SearchEngine:
    """local search engine using BM25 algorithm."""
    
    def __init__(self):
        self.chunks: List[Dict[str, str]] = []
        self.bm25: Optional[BM25Okapi] = None
        self.is_indexed = False

    def add_chunks(self, new_chunks: List[Dict[str, str]]):
        """Adds new text chunks and re-initializes BM25 index."""
        if not new_chunks:
            return
            
        self.chunks.extend(new_chunks)
        self._build_index()
        logger.info(f"Search index updated. Total chunks: {len(self.chunks)}")

    def clear(self):
        """Clears all data."""
        self.chunks = []
        self.bm25 = None
        self.is_indexed = False

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer: lowercase, strip punctuation, split by words."""
        # Lowercase and remove non-alphanumeric (keep RU and EN)
        text = text.lower()
        tokens = re.findall(r'[a-zа-я0-9]+', text)
        return tokens

    def _build_index(self):
        """Builds BM25 index from all current chunks."""
        if not self.chunks:
            self.bm25 = None
            self.is_indexed = False
            return
            
        tokenized_corpus = [self._tokenize(c['content']) for c in self.chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)
        self.is_indexed = True

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, str]]:
        """Returns top K relevant chunks for the query."""
        if not self.is_indexed or not self.bm25:
            logger.warning("Search query received but index is empty or not built.")
            return []
            
        tokenized_query = self._tokenize(query)
        # Get top N indices based on BM25 scores
        top_indices = self.bm25.get_top_n(tokenized_query, list(range(len(self.chunks))), n=top_k)
        
        results = []
        for idx in top_indices:
            results.append(self.chunks[idx])
            
        logger.debug(f"Search for '{query}' returned {len(results)} chunks")
        return results
