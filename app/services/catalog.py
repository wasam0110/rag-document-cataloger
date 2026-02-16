"""
Catalog service – higher-level CRUD operations on the DocumentCatalog.

This module wraps raw SQLAlchemy queries with Pydantic model
serialization / deserialization.  It is used when the caller
needs typed ``DocumentCatalog`` objects rather than plain dicts.

NOTE: This service opens its own DB sessions.  Use ``get_document_catalog``
      for read operations and ``delete_document`` for removal.
"""

from typing import List, Dict, Any, Optional, Union
from uuid import uuid4
from datetime import datetime

from app.db.sqlite import SessionLocal, DocumentCatalog as DocumentCatalogModel, init_db
from app.models.schemas import DocumentCatalog


async def get_document_catalog(doc_id: Optional[str] = None) -> Union[List[DocumentCatalog], DocumentCatalog]:
    """
    Retrieve document catalog(s) from the database.

    If ``doc_id`` is provided, return the single matching catalog.
    Otherwise, return a list of **all** catalogs.

    Raises:
        ValueError: If the requested doc_id does not exist.
    """
    # Ensure tables exist before querying
    init_db()
    db = SessionLocal()
    try:
        if doc_id:
            # ── Single-document lookup ──────────────────────────────
            doc = db.query(DocumentCatalogModel).filter(DocumentCatalogModel.id == doc_id).first()
            if not doc:
                raise ValueError(f"Document {doc_id} not found")
            # Map the ORM model to the Pydantic schema
            return DocumentCatalog(
                doc_id=doc.id,
                filename=doc.filename,
                filetype=doc.filetype,
                created_at=doc.created_at,
                topics=doc.topics or [],
                tables=doc.tables or [],
                chunks=doc.chunks or [],
                keywords=doc.keywords or []
            )
        else:
            # ── List all documents ──────────────────────────────────
            docs = db.query(DocumentCatalogModel).all()
            return [
                DocumentCatalog(
                    doc_id=doc.id,
                    filename=doc.filename,
                    filetype=doc.filetype,
                    created_at=doc.created_at,
                    topics=doc.topics or [],
                    tables=doc.tables or [],
                    chunks=doc.chunks or [],
                    keywords=doc.keywords or []
                )
                for doc in docs
            ]
    finally:
        # Always close the session to return the connection to the pool
        db.close()


async def delete_document(doc_id: str) -> bool:
    """Delete a document from the catalog by its ID.

    Returns True if a document was found and removed, False otherwise.
    """
    # Ensure tables exist before attempting a delete
    init_db()
    db = SessionLocal()
    try:
        doc = db.query(DocumentCatalogModel).filter(DocumentCatalogModel.id == doc_id).first()
        if doc:
            db.delete(doc)
            db.commit()
            return True
        return False
    finally:
        db.close()