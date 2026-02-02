import logging
import re
import os
import numpy as np
from typing import List, Dict, Optional, Any, Set
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from rag.persistent_cache import PersistentCache

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

# Document type categories for metadata filtering
DOC_TYPES = {
    ".pdf": "document",
    ".docx": "document", 
    ".doc": "document",
    ".txt": "text",
    ".csv": "data",
    ".xlsx": "data",
    ".xls": "data",
}


class SearchEngine:
    """Hybrid search engine with Query Expansion, Metadata Filtering, and Persistent Cache."""
    
    def __init__(self, cache_dir: str = "."):
        self.chunks: List[Dict[str, Any]] = []
        self.bm25: Optional[BM25Okapi] = None
        self.tfidf_vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix = None
        self.is_indexed = False
        
        # Persistent cache (survives restarts)
        cache_path = os.path.join(cache_dir, "rag_cache.db")
        self.persistent_cache = PersistentCache(db_path=cache_path, max_responses=100)
        
        # Metadata index for filtering
        self.source_to_indices: Dict[str, List[int]] = {}  # source -> chunk indices
        self.doc_type_to_indices: Dict[str, List[int]] = {}  # doc_type -> chunk indices

    def add_chunks(self, new_chunks: List[Dict[str, Any]]):
        """Adds new text chunks and re-initializes indexes."""
        if not new_chunks:
            return
        
        start_idx = len(self.chunks)
        self.chunks.extend(new_chunks)
        
        # Update metadata indexes
        for i, chunk in enumerate(new_chunks, start=start_idx):
            source = chunk.get('metadata', {}).get('source', 'unknown')
            
            # Source index
            if source not in self.source_to_indices:
                self.source_to_indices[source] = []
            self.source_to_indices[source].append(i)
            
            # Doc type index
            ext = os.path.splitext(source)[1].lower()
            doc_type = DOC_TYPES.get(ext, "other")
            if doc_type not in self.doc_type_to_indices:
                self.doc_type_to_indices[doc_type] = []
            self.doc_type_to_indices[doc_type].append(i)
        
        self._build_indexes()
        logger.info(f"Search index updated. Total chunks: {len(self.chunks)}, Sources: {len(self.source_to_indices)}")

    def clear(self):
        """Clears all data (but keeps persistent cache)."""
        self.chunks = []
        self.bm25 = None
        self.tfidf_vectorizer = None
        self.tfidf_matrix = None
        self.is_indexed = False
        self.source_to_indices = {}
        self.doc_type_to_indices = {}

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

    def _get_filtered_indices(self, sources: Optional[List[str]] = None, 
                               doc_types: Optional[List[str]] = None) -> Optional[Set[int]]:
        """Get chunk indices matching metadata filters."""
        if not sources and not doc_types:
            return None  # No filtering
        
        result_indices: Optional[Set[int]] = None
        
        if sources:
            source_indices: Set[int] = set()
            for source in sources:
                source_indices.update(self.source_to_indices.get(source, []))
            result_indices = source_indices
        
        if doc_types:
            type_indices: Set[int] = set()
            for doc_type in doc_types:
                type_indices.update(self.doc_type_to_indices.get(doc_type, []))
            if result_indices is not None:
                result_indices = result_indices.intersection(type_indices)
            else:
                result_indices = type_indices
        
        return result_indices

    def search(self, query: str, top_k: int = 5, use_parent: bool = True,
               sources: Optional[List[str]] = None,
               doc_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Hybrid Search with Query Expansion, Metadata Filtering, and Parent Document Retrieval."""
        if not self.is_indexed or not self.bm25 or self.tfidf_matrix is None:
            logger.warning("Search query received but index is empty or not built.")
            return []
        
        # Get filtered indices (if any filters applied)
        filtered_indices = self._get_filtered_indices(sources, doc_types)
        
        # Query Expansion
        expanded_query = self._expand_query(query)
            
        # 1. Keyword search (BM25) with expanded query
        tokenized_query = self._tokenize(expanded_query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # 2. TF-IDF similarity search
        query_vec = self.tfidf_vectorizer.transform([expanded_query])
        tfidf_scores = cosine_similarity(query_vec, self.tfidf_matrix).flatten()
        
        # 3. Apply metadata filtering (mask out non-matching chunks)
        if filtered_indices is not None:
            mask = np.zeros(len(self.chunks), dtype=bool)
            for idx in filtered_indices:
                mask[idx] = True
            bm25_scores = np.where(mask, bm25_scores, -np.inf)
            tfidf_scores = np.where(mask, tfidf_scores, -np.inf)
        
        # 4. Combine scores (Reciprocal Rank Fusion style)
        # Handle case when all scores are -inf after filtering
        valid_bm25 = bm25_scores[bm25_scores > -np.inf]
        
        if len(valid_bm25) == 0:
            return []
        
        bm25_min, bm25_max = valid_bm25.min(), valid_bm25.max()
        bm25_norm = np.where(
            bm25_scores > -np.inf,
            (bm25_scores - bm25_min) / (bm25_max - bm25_min + 1e-8),
            -np.inf
        )
        tfidf_norm = tfidf_scores
        
        # Weighted combination (60% TF-IDF, 40% BM25)
        combined_scores = np.where(
            bm25_scores > -np.inf,
            0.6 * tfidf_norm + 0.4 * bm25_norm,
            -np.inf
        )
        
        # Get top-k indices
        top_indices = np.argsort(combined_scores)[-top_k:][::-1]
        top_indices = [i for i in top_indices if combined_scores[i] > -np.inf]
        
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
        normalized = " ".join(self._tokenize(query))
        return self.persistent_cache.get_response(normalized)

    def cache_response(self, query: str, response: str):
        """Cache a response for future similar queries."""
        normalized = " ".join(self._tokenize(query))
        self.persistent_cache.set_response(normalized, response)
        stats = self.persistent_cache.get_cache_stats()
        logger.debug(f"Response cached. Cache size: {stats['responses']}")

    def get_available_sources(self) -> List[str]:
        """Get list of all available source files."""
        return list(self.source_to_indices.keys())

    def get_available_doc_types(self) -> List[str]:
        """Get list of all available document types."""
        return list(self.doc_type_to_indices.keys())



