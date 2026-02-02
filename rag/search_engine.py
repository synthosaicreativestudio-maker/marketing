import logging
import re
import numpy as np
from typing import List, Dict, Optional, Any
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

class SearchEngine:
    """Lightweight Hybrid search engine using BM25 + TF-IDF (no heavy dependencies)."""
    
    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.bm25: Optional[BM25Okapi] = None
        self.tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self.is_indexed = False

    def add_chunks(self, new_chunks: List[Dict[str, Any]]):
        """Adds new text chunks and re-initializes both BM25 and TF-IDF indexes."""
        if not new_chunks:
            return
            
        self.chunks.extend(new_chunks)
        self._build_indexes()
        logger.info(f"Search index updated. Total chunks: {len(self.chunks)}")

    def clear(self):
        """Clears all data."""
        self.chunks = []
        self.bm25 = None
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        self.is_indexed = False

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer: lowercase, strip punctuation, split by words."""
        text = text.lower()
        tokens = re.findall(r'[a-zа-я0-9]+', text)
        return tokens

    def _build_indexes(self):
        """Builds BM25 and TF-IDF indexes from all current chunks."""
        if not self.chunks:
            self.bm25 = None
            self.tfidf_vectorizer = None
            self.tfidf_matrix = None
            self.is_indexed = False
            return
            
        # 1. BM25 Index (keyword search)
        tokenized_corpus = [self._tokenize(c['content']) for c in self.chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        # 2. TF-IDF Index (lightweight semantic-like search)
        contents = [c['content'] for c in self.chunks]
        self.tfidf_vectorizer = TfidfVectorizer(
            lowercase=True,
            token_pattern=r'[a-zа-яё0-9]+',
            max_features=5000,
            ngram_range=(1, 2)  # Unigrams + bigrams for better context
        )
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(contents)
        
        self.is_indexed = True
        logger.info(f"Indexes built: BM25 + TF-IDF ({self.tfidf_matrix.shape[1]} features)")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Hybrid Search: Combines keyword (BM25) and TF-IDF scores."""
        if not self.is_indexed or not self.bm25 or self.tfidf_matrix is None:
            logger.warning("Search query received but index is empty or not built.")
            return []
            
        # 1. Keyword search (BM25)
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # 2. TF-IDF similarity search
        query_vec = self.tfidf_vectorizer.transform([query])
        tfidf_scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # 3. Combine scores (Reciprocal Rank Fusion style)
        # Normalize both score arrays to 0-1 range
        bm25_norm = (bm25_scores - bm25_scores.min()) / (bm25_scores.max() - bm25_scores.min() + 1e-8)
        tfidf_norm = tfidf_scores  # Already 0-1 from cosine similarity
        
        # Weighted combination (60% TF-IDF, 40% BM25)
        combined_scores = 0.6 * tfidf_norm + 0.4 * bm25_norm
        
        # Get top-k indices
        top_indices = np.argsort(combined_scores)[-top_k:][::-1]
        
        results = [self.chunks[idx] for idx in top_indices]
        logger.debug(f"Hybrid search for '{query[:50]}...' returned {len(results)} chunks")
        return results

