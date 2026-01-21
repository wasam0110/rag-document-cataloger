"""
Document ingestion service.
"""

import uuid
from pathlib import Path
from typing import Dict, Any

from fastapi import UploadFile

from app.core.config import settings
from app.core.logging import logger
from app.db.sqlite import (
    save_document_metadata,
    save_chunks,
    save_tables,
    save_topics,
    save_keywords
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
        
        if extracted.get("keywords"):
            save_keywords(doc_id, extracted["keywords"])
        
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
        from app.services.index.faiss_store import build_faiss_index
        texts = [chunk.get("content", "") for chunk in chunks]
        await build_faiss_index(doc_id, texts)
        logger.info(f"Built index for {doc_id}")
        return True
    except Exception as e:
        logger.error(f"Index error: {e}")
        return False