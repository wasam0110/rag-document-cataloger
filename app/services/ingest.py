"""
Document ingestion service.
"""

import uuid
from pathlib import Path
from typing import Dict, Any
from typing import List

from fastapi import UploadFile

from app.core.config import settings
from app.core.logging import logger
from app.db.sqlite import (
    save_document_metadata,
    save_chunks,
    save_tables,
    save_topics
)

SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".csv": "csv",
    ".txt": "txt"
}


async def ingest_document(file: UploadFile) -> str:
    """Ingest a document."""
    doc_id = str(uuid.uuid4())
    
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    filetype = SUPPORTED_EXTENSIONS.get(ext, "unknown")
    
    if filetype == "unknown":
        raise ValueError(f"Unsupported file type: {ext}")
    
    file_path = settings.upload_dir / f"{doc_id}{ext}"
    
    try:
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Save to disk
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"Saved file: {file_path}")
        
        # Save metadata
        save_document_metadata(doc_id, filename, filetype, file_size)
        
        # Extract content
        extracted = await extract_content(file_path, filetype, doc_id)
        
        # Save extracted data
        if extracted.get("chunks"):
            save_chunks(doc_id, extracted["chunks"])
        
        if extracted.get("tables"):
            save_tables(doc_id, extracted["tables"])
        
        if extracted.get("topics"):
            save_topics(doc_id, extracted["topics"])
        
        # Build index
        if extracted.get("chunks"):
            try:
                await build_index(doc_id, extracted["chunks"])
            except Exception as e:
                logger.warning(f"Index building failed: {e}")
        
        logger.info(f"Ingested document {doc_id}")
        return doc_id
        
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        if file_path.exists():
            file_path.unlink()
        raise


async def extract_content(file_path: Path, filetype: str, doc_id: str) -> Dict[str, Any]:
    """Extract content from document."""
    result = {
        "chunks": [],
        "tables": [],
        "topics": [],
        "keywords": []
    }
    
    try:
        if filetype == "pdf":
            from app.services.extract.pdf import extract_pdf
            result = await extract_pdf(file_path, doc_id)
        elif filetype == "docx":
            from app.services.extract.docx import extract_docx
            result = await extract_docx(file_path, doc_id)
        elif filetype == "csv":
            from app.services.extract.csv import extract_csv
            result = await extract_csv(file_path, doc_id)
        elif filetype == "txt":
            from app.services.extract.txt import extract_txt
            result = await extract_txt(file_path, doc_id)
    except Exception as e:
        logger.error(f"Extraction error: {e}")
        # Return empty result but don't fail
        pass
    
    return result


async def build_index(doc_id: str, chunks: list) -> bool:
    """Build FAISS index."""
    try:
        from app.services.index.faiss_store import create_index
        
        # Convert chunks to the format expected by create_index
        items = []
        for idx, chunk in enumerate(chunks):
            items.append({
                "item_id": chunk.get("chunk_id", f"chunk_{idx}"),
                "text": chunk.get("content", ""),
                "category": "chunk",
                "page": chunk.get("page_number")
            })
        
        create_index(doc_id, items)
        logger.info(f"Built index for {doc_id}")
        return True
    except Exception as e:
        logger.error(f"Index error: {e}")
        return False


    # --- Backwards-compatible helper wrappers -------------------------------------------------
    def extract_topics_from_text(pages: List[str], doc_id: str) -> List[Dict[str, Any]]:
        """Compatibility wrapper: extract topics from a list of page texts."""
        try:
            text = "\n\n".join(pages)
            # Prefer the TXT extractor which implements topic heuristics
            from app.services.extract.txt import extract_topics as _extract_topics
            return _extract_topics(text, doc_id)
        except Exception:
            return []


    def extract_keywords_from_text(text: str, doc_id: str = None, top_n: int = 10) -> List[Dict[str, Any]]:
        """Compatibility wrapper: extract keywords from a text string.

        The original tests call this synchronously and expect a list of keyword dicts.
        """
        try:
            # Many extractors expose `extract_keywords(text, doc_id)`; call TXT implementation.
            from app.services.extract.txt import extract_keywords as _extract_keywords
            # Some implementations expect a doc_id; pass an empty one if not provided
            doc_id = doc_id or ""
            kws = _extract_keywords(text, doc_id)
            # Respect `top_n` if provided
            return kws[:top_n]
        except Exception:
            return []


    def detect_tables_in_text(pages: List[str], doc_id: str) -> List[Dict[str, Any]]:
        """Simple heuristic table detector for plain text.

        Detects contiguous lines that look like columnar data (multiple spaces or pipe separators).
        """
        import re
        tables = []
        table_index = 0

        for page_num, page in enumerate(pages, start=1):
            lines = page.splitlines()
            buffer = []

            for line in lines + [""]:  # sentinel to flush buffer at end
                # Consider a line as table-like if it contains a pipe or multiple consecutive spaces/tabs
                if re.search(r"\|", line) or re.search(r"\s{2,}", line):
                    buffer.append(line.rstrip())
                    continue

                # Non-table line: if we have accumulated at least two table-like lines, emit a table
                if len(buffer) >= 2:
                    table_id = str(uuid.uuid4())
                    table_text = "\n".join(buffer)
                    rows_count = len(buffer)
                    # Estimate columns by splitting the first line
                    first = buffer[0]
                    if "|" in first:
                        cols_count = len([c for c in first.split("|") if c.strip()])
                    else:
                        cols_count = len(re.split(r"\s{2,}", first))

                    tables.append({
                        "table_id": table_id,
                        "page_number": page_num,
                        "table_index": table_index,
                        "table_text": table_text,
                        "rows_count": rows_count,
                        "cols_count": cols_count,
                        "confidence": 0.6
                    })

                    table_index += 1

                buffer = []

        return tables
