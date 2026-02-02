import logging
import re
import numpy as np
from typing import List, Dict, Optional, Any
from collections import OrderedDict
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)

# Russian marketing synonyms for Query Expansion
SYNONYMS = {
    "цена": ["стоимость", "прайс", "тариф", "расценка"],
    "стоимость": ["цена", "прайс", "тариф"],
    "скидка": ["акция", "распродажа", "бонус", "промо"],
    "акция": ["скидка", "промо", "спецпредложение"],
    "купить": ["заказать", "приобрести", "оформить"],
    "заказать": ["купить", "оформить", "приобрести"],
    "доставка": ["отправка", "пересылка", "логистика"],
    "товар": ["продукт", "изделие", "продукция"],
    "услуга": ["сервис", "обслуживание"],
    "клиент": ["покупатель", "заказчик", "потребитель"],
    "контакт": ["связь", "телефон", "адрес"],
    "оплата": ["платеж", "расчет", "перевод"],
    "гарантия": ["возврат", "обмен", "защита"],
    "качество": ["характеристики", "свойства"],
    "помощь": ["поддержка", "консультация", "вопрос"],
}


class LRUCache:
    """Simple LRU Cache for response caching (max 100 entries)."""
    
    def __init__(self, max_size: int = 100):
        self.cache: OrderedDict = OrderedDict()
        self.max_size = max_size
    
    def get(self, key: str) -> Optional[str]:
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        return None
    
    def set(self, key: str, value: str):
        if key in self.cache:
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)
        self.cache[key] = value
    
    def size(self) -> int:
        return len(self.cache)


class SearchEngine:
    """Lightweight Hybrid search engine with Query Expansion and Response Cache."""
    
    def __init__(self):
        self.chunks: List[Dict[str, Any]] = []
        self.bm25: Optional[BM25Okapi] = None
        self.tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self.is_indexed = False
        self.response_cache = LRUCache(max_size=100)

    def add_chunks(self, new_chunks: List[Dict[str, Any]]):
        """Adds new text chunks and re-initializes indexes."""
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
        # Keep cache - it might still be useful

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer: lowercase, strip punctuation, split by words."""
        text = text.lower()
        tokens = re.findall(r'[a-zа-яё0-9]+', text)
        return tokens

    def _expand_query(self, query: str) -> str:
        """Query Expansion: adds synonyms to improve recall."""
        words = self._tokenize(query)
        expanded_words = list(words)
        
        for word in words:
            if word in SYNONYMS:
                expanded_words.extend(SYNONYMS[word])
        
        expanded_query = " ".join(expanded_words)
        if expanded_query != query.lower():
            logger.debug(f"Query expanded: '{query}' -> '{expanded_query}'")
        return expanded_query

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
            ngram_range=(1, 2)
        )
        self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(contents)
        
        self.is_indexed = True
        logger.info(f"Indexes built: BM25 + TF-IDF ({self.tfidf_matrix.shape[1]} features)")

    def search(self, query: str, top_k: int = 5, use_parent: bool = True) -> List[Dict[str, Any]]:
        """Hybrid Search with Query Expansion and Parent Document Retrieval."""
        if not self.is_indexed or not self.bm25 or self.tfidf_matrix is None:
            logger.warning("Search query received but index is empty or not built.")
            return []
        
        # Query Expansion
        expanded_query = self._expand_query(query)
            
        # 1. Keyword search (BM25) with expanded query
        tokenized_query = self._tokenize(expanded_query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # 2. TF-IDF similarity search
        query_vec = self.tfidf_vectorizer.transform([expanded_query])
        tfidf_scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # 3. Combine scores (Reciprocal Rank Fusion style)
        bm25_norm = (bm25_scores - bm25_scores.min()) / (bm25_scores.max() - bm25_scores.min() + 1e-8)
        tfidf_norm = tfidf_scores
        
        # Weighted combination (60% TF-IDF, 40% BM25)
        combined_scores = 0.6 * tfidf_norm + 0.4 * bm25_norm
        
        # Get top-k indices
        top_indices = np.argsort(combined_scores)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            chunk = self.chunks[idx].copy()
            # Parent Document Retrieval: optionally include parent context
            if use_parent and 'parent_content' in chunk.get('metadata', {}):
                parent = chunk['metadata']['parent_content']
                if parent and parent != chunk['content']:
                    chunk['parent_context'] = parent
            results.append(chunk)
        
        logger.debug(f"Hybrid search for '{query[:50]}...' returned {len(results)} chunks")
        return results

    def get_cached_response(self, query: str) -> Optional[str]:
        """Check if we have a cached response for a similar query."""
        # Normalize query for cache lookup
        normalized = " ".join(self._tokenize(query))
        return self.response_cache.get(normalized)

    def cache_response(self, query: str, response: str):
        """Cache a response for future similar queries."""
        normalized = " ".join(self._tokenize(query))
        self.response_cache.set(normalized, response)
        logger.debug(f"Response cached. Cache size: {self.response_cache.size()}")


