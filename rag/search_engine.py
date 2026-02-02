import logging
import re
import numpy as np
from typing import List, Dict, Optional, Any
from rank_bm25 import BM25Okapi
import faiss
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class SearchEngine:
    """Hybrid search engine using BM25 and Vector (FAISS) search."""
    
    def __init__(self, model_name: str = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'):
        self.chunks: List[Dict[str, Any]] = []
        self.bm25: Optional[BM25Okapi] = None
        self.index: Optional[faiss.IndexFlatL2] = None
        self.model = SentenceTransformer(model_name)
        self.is_indexed = False

    def add_chunks(self, new_chunks: List[Dict[str, Any]]):
        """Adds new text chunks and re-initializes both BM25 and FAISS indexes."""
        if not new_chunks:
            return
            
        self.chunks.extend(new_chunks)
        self._build_indexes()
        logger.info(f"Search index updated. Total chunks: {len(self.chunks)}")

    def clear(self):
        """Clears all data."""
        self.chunks = []
        self.bm25 = None
        self.index = None
        self.is_indexed = False

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenizer: lowercase, strip punctuation, split by words."""
        text = text.lower()
        tokens = re.findall(r'[a-zа-я0-9]+', text)
        return tokens

    def _build_indexes(self):
        """Builds BM25 and FAISS indexes from all current chunks."""
        if not self.chunks:
            self.bm25 = None
            self.index = None
            self.is_indexed = False
            return
            
        # 1. BM25 Index
        tokenized_corpus = [self._tokenize(c['content']) for c in self.chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        # 2. FAISS Vector Index
        contents = [c['content'] for c in self.chunks]
        embeddings = self.model.encode(contents, convert_to_numpy=True)
        
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(embeddings.astype('float32'))
        
        self.is_indexed = True

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Hybrid Search: Combines keyword (BM25) and Semantic (FAISS) scores."""
        if not self.is_indexed or not self.bm25 or not self.index:
            logger.warning("Search query received but index is empty or not built.")
            return []
            
        # 1. Keyword search (BM25)
        tokenized_query = self._tokenize(query)
        bm25_scores = self.bm25.get_scores(tokenized_query)
        
        # 2. Semantic search (FAISS)
        query_embedding = self.model.encode([query], convert_to_numpy=True).astype('float32')
        distances, indices = self.index.search(query_embedding, k=min(len(self.chunks), 20))
        
        # 3. Reranking / Fusion (Simple Reciprocal Rank Fusion or Normalized Weighted Sum)
        # For MVP, we use a simple top_k union with priority to vector search
        semantic_results = [self.chunks[idx] for idx in indices[0] if idx != -1]
        
        # Get top from BM25 as well
        bm25_top_indices = np.argsort(bm25_scores)[-top_k:][::-1]
        keyword_results = [self.chunks[idx] for idx in bm25_top_indices]
        
        # Combine and deduplicate by content
        seen_content = set()
        combined_results = []
        
        # Add semantic results first (usually higher quality for chat)
        for res in semantic_results:
            if res['content'] not in seen_content:
                combined_results.append(res)
                seen_content.add(res['content'])
        
        # Then add keyword results if missing
        for res in keyword_results:
            if res['content'] not in seen_content:
                combined_results.append(res)
                seen_content.add(res['content'])
                
        return combined_results[:top_k]

