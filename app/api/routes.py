"""
FastAPI API routes for document catalog.

Provides endpoints for:
  - Health check
  - Document upload, listing, deletion
  - Full catalog retrieval (chunks, tables, topics, sections)
  - Table data & image serving
  - PDF inline viewing
  - Semantic search / query
  - Section browsing by category
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import settings
from app.core.logging import logger
from app.models.schemas import User
from app.services.auth import get_current_user
from app.db.sqlite import (
    get_document,
    get_document_tables,
    get_document_chunks,
    get_document_topics,
    get_document_images,
    get_sections_by_type,
    get_table_by_id,
    list_documents,
    delete_document
)

# Create a router with the /api prefix; endpoints are grouped under "documents" in the docs.
router = APIRouter(prefix="/api", tags=["documents"])

# Map of allowed file extensions → canonical file-type names used throughout the system.
SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".csv": "csv",
    ".txt": "txt"
}


@router.get("/health")
async def health_check():
    """Simple liveness probe – returns 200 if the server is running."""
    return {"status": "healthy"}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """Upload and process a document.

    Accepts a file via multipart form data, validates its extension,
    runs the full ingestion pipeline (extract → chunk → index), and
    returns the assigned doc_id along with extraction counts.
    """
    try:
        # Guard: require a filename in the upload
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Validate the file extension against the allow-list
        ext = Path(file.filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Supported: {list(SUPPORTED_EXTENSIONS.keys())}"
            )
        
        # Lazy import to avoid circular dependency between routes and services
        from app.services.ingest import ingest_document
        
        # Run the full ingestion pipeline (save file, extract, chunk, index)
        doc_id = await ingest_document(file, current_user.user_id)
        # Fetch the persisted metadata to include extraction counts in the response
        doc = get_document(doc_id)
        
        return {
            "success": True,
            "doc_id": doc_id,
            "filename": file.filename,
            "filetype": SUPPORTED_EXTENSIONS[ext],
            "counts": {
                "chunks": doc.get("chunks_count", 0) if doc else 0,
                "tables": doc.get("tables_count", 0) if doc else 0,
                "topics": doc.get("topics_count", 0) if doc else 0
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def get_all_documents(current_user: User = Depends(get_current_user)):
    """Return a list of all uploaded documents (most recent first)."""
    try:
        documents = list_documents()  # Query all rows from the documents table
        return {"success": True, "documents": documents, "total": len(documents)}
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog/{doc_id}")
async def get_catalog(doc_id: str, current_user: User = Depends(get_current_user)):
    """Return the full catalog for a document including tables, topics, and sections.

    Enriches raw DB records with navigation URLs so the front-end can
    link directly to table thumbnails, inline table views, and PDF pages.
    """
    try:
        # Look up the document; 404 if it doesn't exist
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Fetch extracted tables and attach convenience URLs for the UI
        tables = get_document_tables(doc_id)
        tables_with_urls = []
        for table in tables:
            table_data = {
                "table_id": table.get("table_id"),
                "page_number": table.get("page_number"),
                "table_index": table.get("table_index"),
                "rows_count": table.get("rows_count"),
                "cols_count": table.get("cols_count"),
                "confidence": table.get("confidence"),
                "thumbnail_url": f"/api/tables/{table.get('table_id')}/thumbnail" if table.get("preview_image_path") else None,
                "inline_view_url": f"/api/tables/{table.get('table_id')}",
                "pdf_page_url": f"/api/pdf/{doc_id}?page={table.get('page_number')}"
            }
            tables_with_urls.append(table_data)
        
        topics = get_document_topics(doc_id)
        
        # Add navigation URLs to topics
        topics_with_urls = []
        for topic in topics:
            topic_data = {
                **topic,
                "view_url": f"/api/pdf/{doc_id}?page={topic.get('start_page')}" if doc.get("filetype") == "pdf" else None,
                "chunk_count": len(topic.get("chunk_ids", []))
            }
            topics_with_urls.append(topic_data)
        
        # Bucket topics into standard academic section types for the sidebar UI
        sections = {
            "abstract": [],
            "introduction": [],
            "background": [],
            "methodology": [],
            "results": [],
            "discussion": [],
            "conclusion": [],
            "references": [],
            "other": []
        }
        
        for topic in topics_with_urls:
            section_type = topic.get("section_type") or "other"
            if section_type in sections:
                sections[section_type].append(topic)
            else:
                sections["other"].append(topic)
        
        return {
            "success": True,
            "document": {
                "doc_id": doc_id,
                "filename": doc.get("filename"),
                "filetype": doc.get("filetype"),
                "created_at": doc.get("created_at")
            },
            "counts": {
                "chunks": doc.get("chunks_count", 0),
                "tables": doc.get("tables_count", 0),
                "topics": doc.get("topics_count", 0)
            },
            "tables": tables_with_urls,
            "topics": topics_with_urls,
            "sections": sections
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_id}")
async def get_table_data(table_id: str, current_user: User = Depends(get_current_user)):
    """Return metadata and content for a single extracted table."""
    try:
        # Fetch the table row from the DB by its unique ID
        table = get_table_by_id(table_id)
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        
        return {
            "success": True,
            "table_id": table.get("table_id"),
            "doc_id": table.get("doc_id"),
            "page_number": table.get("page_number"),
            "table_index": table.get("table_index"),
            "rows_count": table.get("rows_count"),
            "cols_count": table.get("cols_count"),
            "confidence": table.get("confidence"),
            "bbox": table.get("bbox"),
            "table_text": table.get("table_text", ""),
            "full_image_url": f"/api/tables/{table_id}/image" if table.get("full_image_path") else None,
            "thumbnail_url": f"/api/tables/{table_id}/thumbnail" if table.get("preview_image_path") else None,
            "pdf_page_url": f"/api/pdf/{table.get('doc_id')}?page={table.get('page_number')}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting table: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_id}/thumbnail")
async def get_table_thumbnail(table_id: str):
    """Serve the small preview thumbnail PNG for an extracted table."""
    try:
        table = get_table_by_id(table_id)
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        
        # The relative path stored in the DB (e.g. "table_images/<doc_id>/<id>_thumbnail.png")
        preview_path = table.get("preview_image_path")
        if not preview_path:
            raise HTTPException(status_code=404, detail="Thumbnail not available")
        
        # Resolve to an absolute filesystem path under the data directory
        full_path = settings.data_dir / preview_path
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Thumbnail file not found")
        
        return FileResponse(str(full_path), media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting thumbnail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_id}/image")
async def get_table_image(table_id: str):
    """Serve the full-resolution PNG image for an extracted table."""
    try:
        table = get_table_by_id(table_id)
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        
        # Full-resolution image path stored during extraction
        image_path = table.get("full_image_path")
        if not image_path:
            raise HTTPException(status_code=404, detail="Image not available")
        
        # Build the absolute path and verify the file exists on disk
        full_path = settings.data_dir / image_path
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Image file not found")
        
        return FileResponse(str(full_path), media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdf/{doc_id}")
async def serve_pdf(doc_id: str, page: Optional[int] = Query(None, ge=1)):
    """Serve a PDF file for inline browser viewing (not download).

    An optional ``page`` query parameter is forwarded as a custom
    X-PDF-Page header so the front-end viewer can jump to that page.
    """
    try:
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Only PDF documents can be served through this endpoint
        if doc.get("filetype") != "pdf":
            raise HTTPException(status_code=400, detail="Document is not a PDF")
        
        # Uploaded PDFs are stored as <doc_id>.pdf in the uploads directory
        pdf_path = settings.upload_dir / f"{doc_id}.pdf"
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF file not found")
        
        # "Content-Disposition: inline" tells the browser to render the PDF
        # in-page rather than prompting a download dialog.
        response = FileResponse(
            str(pdf_path), 
            media_type="application/pdf",
            headers={
                "Content-Disposition": "inline",
            }
        )
        # Pass the requested page number as a custom header
        if page:
            response.headers["X-PDF-Page"] = str(page)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}")
async def delete_doc(doc_id: str, current_user: User = Depends(get_current_user)):
    """Delete a document, its DB records, and its uploaded file from disk."""
    try:
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Remove all related rows (chunks, tables, topics, images) from the DB
        deleted = delete_document(doc_id)
        if deleted:
            # Best-effort cleanup of the uploaded file on disk
            ext_map = {"pdf": ".pdf", "docx": ".docx", "csv": ".csv", "txt": ".txt"}
            ext = ext_map.get(doc.get("filetype"), "")
            file_path = settings.upload_dir / f"{doc_id}{ext}"
            if file_path.exists():
                try:
                    os.remove(file_path)
                except:
                    pass  # Non-critical – the DB is the source of truth
        
        return {"success": True, "doc_id": doc_id, "message": "Document deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query_documents(doc_id: str = Query(...), query: str = Query(...), top_k: int = Query(5), current_user: User = Depends(get_current_user)):
    """Run a semantic similarity search against a document's FAISS index.

    Returns the top-k most relevant chunks, ranked by cosine distance.
    """
    try:
        # Lazy import to avoid heavy FAISS / embedding model load at startup
        from app.services.query import query_document
        
        # Verify the document exists before querying
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Perform the vector similarity search and generate a RAG answer
        query_response = await query_document(doc_id, query, top_k)

        # query_document returns a dict: {"results": [...], "answer": "..."}
        results = query_response.get("results", [])
        answer = query_response.get("answer", "")

        return {
            "success": True,
            "doc_id": doc_id,
            "query": query,
            "answer": answer,
            "results": results,
            "total": len(results)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{doc_id}/sections")
async def get_document_sections(doc_id: str, current_user: User = Depends(get_current_user)):
    """Return all detected sections grouped by their dynamically discovered categories.

    Categories are sorted with standard academic sections first
    (abstract → introduction → … → references), then alphabetical.
    Tables and images are always included as their own categories.
    """
    try:
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Fetch every topic associated with this document
        all_topics = get_document_topics(doc_id)
        
        # Build a dict grouping topics by their section_type label
        sections = {}
        categories = set()
        
        for topic in all_topics:
            section_type = topic.get("section_type") or "other"  # Default to 'other'
            categories.add(section_type)
            if section_type not in sections:
                sections[section_type] = []
            sections[section_type].append(topic)
        
        # Tables and images always get their own category slots
        sections["tables"] = get_document_tables(doc_id)
        sections["images"] = get_document_images(doc_id)
        
        # Only advertise the category if there's at least one item
        if sections["tables"]:
            categories.add("tables")
        if sections["images"]:
            categories.add("images")
        
        # Ensure a predictable ordering: standard academic sections first
        standard_order = ['abstract', 'introduction', 'methodology', 'results', 'discussion', 'conclusion', 'references']
        sorted_categories = []
        for std in standard_order:
            if std in categories:
                sorted_categories.append(std)
                categories.discard(std)
        # Remaining non-standard categories in alphabetical order
        sorted_categories.extend(sorted(categories))
        
        return {
            "success": True,
            "doc_id": doc_id,
            "categories": sorted_categories,
            "sections": sections
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting sections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{doc_id}/sections/{section_type}")
async def get_section_content(doc_id: str, section_type: str, current_user: User = Depends(get_current_user)):
    """Return the content items for a single section type.

    Each item is enriched with a ``pdf_view_url`` so the front-end can
    open the PDF viewer at the relevant page.
    """
    try:
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Whitelist of accepted section_type values
        valid_sections = ["abstract", "introduction", "results", "conclusion", "references", "tables", "images"]
        if section_type not in valid_sections:
            raise HTTPException(status_code=400, detail=f"Invalid section type. Must be one of: {valid_sections}")
        
        # Dispatch to the correct DB query based on the requested section type
        if section_type == "tables":
            content = get_document_tables(doc_id)
        elif section_type == "images":
            content = get_document_images(doc_id)
        else:
            content = get_sections_by_type(doc_id, section_type)
        
        # Enrich each item with a deep-link to the PDF page viewer
        for item in content:
            if "page_number" in item or "start_page" in item:
                page = item.get("page_number") or item.get("start_page")
                item["pdf_view_url"] = f"/api/pdf/{doc_id}?page={page}"
        
        return {
            "success": True,
            "doc_id": doc_id,
            "section_type": section_type,
            "content": content,
            "total": len(content)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting section content: {e}")
        raise HTTPException(status_code=500, detail=str(e))