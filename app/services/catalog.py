from typing import List, Dict, Any, Optional, Union
from uuid import uuid4
from datetime import datetime

from app.db.sqlite import SessionLocal, DocumentCatalog as DocumentCatalogModel, init_db
from app.models.schemas import DocumentCatalog


async def get_document_catalog(doc_id: Optional[str] = None) -> Union[List[DocumentCatalog], DocumentCatalog]:
    """
    Get document catalog(s) from the database.
    If doc_id is provided, return single document. Otherwise, return all documents.
    """
    init_db()
    db = SessionLocal()
    try:
        if doc_id:
            # Get single document
            doc = db.query(DocumentCatalogModel).filter(DocumentCatalogModel.id == doc_id).first()
            if not doc:
                raise ValueError(f"Document {doc_id} not found")
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
            # Get all documents
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
        db.close()


async def delete_document(doc_id: str) -> bool:
    """Delete a document from the catalog."""
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