import os
import logging
import csv
import re
import pdfplumber
from docx import Document
from typing import List, Dict

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Processes various document types with semantic chunking and parent document retrieval."""
    
    def __init__(self, max_chunk_size: int = 1500, min_chunk_size: int = 100):
        try:
            self.max_chunk_size = int(os.getenv("CHUNK_MAX_CHARS", str(max_chunk_size)))
        except ValueError:
            self.max_chunk_size = max_chunk_size
        try:
            self.min_chunk_size = int(os.getenv("CHUNK_MIN_CHARS", str(min_chunk_size)))
        except ValueError:
            self.min_chunk_size = min_chunk_size
        # Lightweight overlap to improve recall without heavy compute
        try:
            self.overlap_chars = int(os.getenv("CHUNK_OVERLAP_CHARS", "150"))
        except ValueError:
            self.overlap_chars = 150

    def process_file(self, file_path: str) -> List[Dict[str, str]]:
        """Extracts text from a file and returns semantically chunked pieces with parent context."""
        ext = os.path.splitext(file_path)[1].lower()
        text = ""
        
        try:
            is_ocr = file_path.lower().endswith('.ocr.txt')
            
            if ext == '.pdf':
                text = self._extract_pdf(file_path)
            elif ext in ('.docx', '.doc'):
                text = self._extract_docx(file_path)
            elif ext == '.txt' or is_ocr:
                text = self._extract_txt(file_path)
            elif ext == '.csv':
                text = self._extract_csv(file_path)
            else:
                logger.warning(f"Unsupported file extension: {ext}")
                return []
                
            if not text.strip():
                logger.warning(f"No text extracted from {file_path}")
                return []
            
            # Semantic chunking with parent context
            chunks = self._semantic_split(text)
            
            # Return chunks with metadata and parent context
            file_name = os.path.basename(file_path)
            # Если это OCR, пытаемся получить имя оригинального файла (убираем .ocr.txt)
            original_source = file_name.replace('.ocr.txt', '') if is_ocr else file_name
            
            result = []
            for i, (chunk, parent) in enumerate(chunks):
                result.append({
                    "content": chunk,
                    "metadata": {
                        "source": original_source,
                        "is_ocr": is_ocr,
                        "chunk_index": i,  # Ключевой индекс для Sentence Window
                        "parent_content": parent,  # Parent Document Retrieval
                        "total_chunks": len(chunks)
                    }
                })
            return result
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return []

    def _extract_pdf(self, file_path: str) -> str:
        text = []
        max_pages = int(os.getenv("MAX_PDF_PAGES", "30"))
        min_chars = int(os.getenv("MIN_PDF_TEXT_CHARS", "200"))
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:max_pages]:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
        result = "\n".join(text)
        if len(result.strip()) < min_chars:
            logger.warning(f"PDF has too little text (likely scanned): {file_path}")
            return ""
        return result

    def _extract_docx(self, file_path: str) -> str:
        doc = Document(file_path)
        return "\n".join([para.text for para in doc.paragraphs])

    def _extract_txt(self, file_path: str) -> str:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()

    def _extract_csv(self, file_path: str) -> str:
        text = []
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            for row in reader:
                text.append(" ".join(row))
        return "\n".join(text)

    def _semantic_split(self, text: str) -> List[tuple]:
        """
        Semantic Chunking: splits text by paragraphs first, then by sentences if needed.
        Returns list of (chunk, parent_context) tuples for Parent Document Retrieval.
        """
        # Step 1: Split by double newlines (paragraphs)
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        
        chunks_with_parents = []
        
        for para in paragraphs:
            if len(para) <= self.max_chunk_size:
                # Paragraph fits, use it as-is
                # Parent = the paragraph itself (or could be expanded)
                chunks_with_parents.append((para, para))
            else:
                # Paragraph too long, split by sentences
                sentences = self._split_sentences(para)
                current_chunk = ""
                
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) <= self.max_chunk_size:
                        current_chunk += sentence + " "
                    else:
                        if current_chunk.strip():
                            # Parent = full paragraph for context
                            chunks_with_parents.append((current_chunk.strip(), para))
                        current_chunk = sentence + " "
                
                if current_chunk.strip():
                    chunks_with_parents.append((current_chunk.strip(), para))
        
        # Filter out too small chunks
        chunks_with_parents = [
            (c, p) for c, p in chunks_with_parents
            if len(c) >= self.min_chunk_size
        ]

        # Add small overlap between adjacent chunks to preserve continuity
        if self.overlap_chars > 0 and len(chunks_with_parents) > 1:
            overlapped = [chunks_with_parents[0]]
            for (chunk, parent) in chunks_with_parents[1:]:
                prev_chunk = overlapped[-1][0]
                overlap = prev_chunk[-self.overlap_chars:] if len(prev_chunk) > self.overlap_chars else prev_chunk
                merged = (overlap + " " + chunk).strip()
                overlapped.append((merged, parent))
            chunks_with_parents = overlapped
        
        logger.info(f"Semantic chunking: {len(paragraphs)} paragraphs -> {len(chunks_with_parents)} chunks")
        return chunks_with_parents

    def _split_sentences(self, text: str) -> List[str]:
        """Splits text into sentences (handles Russian and English)."""
        # Simple sentence splitter for RU/EN
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]
