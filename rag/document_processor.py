import os
import logging
import csv
import pdfplumber
from docx import Document
from typing import List, Dict

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """Processes various document types and extracts text chunks."""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def process_file(self, file_path: str) -> List[Dict[str, str]]:
        """Extracts text from a file and returns a list of chunks with metadata."""
        ext = os.path.splitext(file_path)[1].lower()
        text = ""
        
        try:
            if ext == '.pdf':
                text = self._extract_pdf(file_path)
            elif ext in ('.docx', '.doc'):
                text = self._extract_docx(file_path)
            elif ext == '.txt':
                text = self._extract_txt(file_path)
            elif ext == '.csv':
                text = self._extract_csv(file_path)
            else:
                logger.warning(f"Unsupported file extension: {ext}")
                return []
                
            if not text.strip():
                logger.warning(f"No text extracted from {file_path}")
                return []
                
            chunks = self._split_text(text)
            
            # Return chunks with metadata
            file_name = os.path.basename(file_path)
            return [
                {
                    "content": chunk,
                    "metadata": {
                        "source": file_name,
                        "chunk_index": i
                    }
                }
                for i, chunk in enumerate(chunks)
            ]
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return []

    def _extract_pdf(self, file_path: str) -> str:
        text = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
        return "\n".join(text)

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

    def _split_text(self, text: str) -> List[str]:
        """Splits text into overlapping chunks."""
        if not text:
            return []
            
        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            
            # Move start forward but stay within overlap
            if end >= text_len:
                break
            start += (self.chunk_size - self.chunk_overlap)
            
        return chunks
