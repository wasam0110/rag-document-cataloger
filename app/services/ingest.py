"""
Document ingestion service.

Orchestrates the entire pipeline for processing an uploaded file:
  1. Save the raw file to disk.
  2. Persist document metadata in SQLite.
  3. Delegate content extraction to the appropriate format-specific extractor.
  4. Persist extracted chunks, tables, topics, and images.
  5. Build a FAISS vector index over the text chunks.
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
    save_images
)

# Map of supported file extensions → canonical type labels.
SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".csv": "csv",
    ".txt": "txt"
}


async def ingest_document(file: UploadFile, user_id: str) -> str:
    """Ingest a single uploaded document end-to-end.

    Args:
        file: FastAPI UploadFile from the request.
        user_id: Authenticated user who owns the document.

    Returns:
        The newly assigned doc_id (UUID string).
    """
    # Generate a unique ID that will be used as the primary key everywhere
    doc_id = str(uuid.uuid4())
    
    # Determine file type from extension
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    filetype = SUPPORTED_EXTENSIONS.get(ext, "unknown")
    
    if filetype == "unknown":
        raise ValueError(f"Unsupported file type: {ext}")
    
    # Construct the on-disk path: uploads/<doc_id>.<ext>
    file_path = settings.upload_dir / f"{doc_id}{ext}"
    
    try:
        # ── Step 1: Read the uploaded bytes and persist to disk ──────
        content = await file.read()
        file_size = len(content)
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        logger.info(f"Saved file: {file_path}")
        
        # ── Step 2: Record document metadata in the database ────────
        save_document_metadata(doc_id, filename, filetype, file_size, user_id)
        
        # ── Step 3: Extract structured content (chunks, tables, …) ──
        extracted = await extract_content(file_path, filetype, doc_id)
        
        # ── Step 4: Save each category of extracted data ────────────
        if extracted.get("chunks"):
            save_chunks(doc_id, extracted["chunks"])
        
        if extracted.get("tables"):
            save_tables(doc_id, extracted["tables"])
        
        if extracted.get("topics"):
            save_topics(doc_id, extracted["topics"])
        
        if extracted.get("images"):
            save_images(doc_id, extracted["images"])
        
        # ── Step 5: Build a FAISS vector index for semantic search ──
        if extracted.get("chunks"):
            try:
                logger.info(f"Building FAISS index for {len(extracted['chunks'])} chunks...")
                await build_index(doc_id, extracted["chunks"])
                logger.info("FAISS index built successfully")
            except Exception as e:
                # Index failure is non-fatal – the document is still usable
                logger.warning(f"Index building failed: {e}")
        
        logger.info(f"Ingested document {doc_id}")
        return doc_id
        
    except Exception as e:
        logger.error(f"Ingestion error: {e}")
        # Clean up the partially-written file to avoid orphans
        if file_path.exists():
            file_path.unlink()
        raise


async def extract_content(file_path: Path, filetype: str, doc_id: str) -> Dict[str, Any]:
    """Dispatch to the correct format-specific extractor.

    Each extractor returns a dict with keys: chunks, tables, topics, keywords, etc.
    If extraction fails, an empty result dict is returned so that the
    ingestion pipeline can continue without crashing.
    """
    # Initialize with empty lists as the baseline result
    result = {
        "chunks": [],
        "tables": [],
        "topics": [],
        "keywords": []
    }
    
    try:
        # Select the extractor based on the file type
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
        # Gracefully degrade: return whatever was collected so far
        pass
    
    return result


async def build_index(doc_id: str, chunks: list) -> bool:
    """Build a FAISS vector index from the document's text chunks.

    Converts each chunk dict into the flat format expected by
    ``faiss_store.create_index`` (keys: item_id, text, category, page).

    Returns:
        True on success, False on failure.
    """
    try:
        from app.services.index.faiss_store import create_index
        
        # Re-shape chunks into the item schema that create_index expects
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
