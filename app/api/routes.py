"""
FastAPI API routes for document catalog.
"""

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import settings
from app.core.logging import logger
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

# Create router
router = APIRouter(prefix="/api", tags=["documents"])

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".csv": "csv",
    ".txt": "txt"
}


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and process a document."""
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        ext = Path(file.filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Supported: {list(SUPPORTED_EXTENSIONS.keys())}"
            )
        
        # Import here to avoid circular imports
        from app.services.ingest import ingest_document
        
        doc_id = await ingest_document(file)
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
async def get_all_documents():
    """List all documents."""
    try:
        documents = list_documents()
        return {"success": True, "documents": documents, "total": len(documents)}
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog/{doc_id}")
async def get_catalog(doc_id: str):
    """Get full catalog for a document."""
    try:
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
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
        
        # Organize topics by section type
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
async def get_table_data(table_id: str):
    """Get table data."""
    try:
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
    """Get table thumbnail image."""
    try:
        table = get_table_by_id(table_id)
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        
        preview_path = table.get("preview_image_path")
        if not preview_path:
            raise HTTPException(status_code=404, detail="Thumbnail not available")
        
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
    """Get full table image."""
    try:
        table = get_table_by_id(table_id)
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        
        image_path = table.get("full_image_path")
        if not image_path:
            raise HTTPException(status_code=404, detail="Image not available")
        
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
    """Serve PDF file for inline viewing (not download)."""
    try:
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        if doc.get("filetype") != "pdf":
            raise HTTPException(status_code=400, detail="Document is not a PDF")
        
        pdf_path = settings.upload_dir / f"{doc_id}.pdf"
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF file not found")
        
        # Return PDF for inline viewing (not as attachment/download)
        response = FileResponse(
            str(pdf_path), 
            media_type="application/pdf",
            headers={
                "Content-Disposition": "inline",  # Forces browser to display, not download
            }
        )
        if page:
            response.headers["X-PDF-Page"] = str(page)
        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}")
async def delete_doc(doc_id: str):
    """Delete a document."""
    try:
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        deleted = delete_document(doc_id)
        if deleted:
            # Try to delete files
            ext_map = {"pdf": ".pdf", "docx": ".docx", "csv": ".csv", "txt": ".txt"}
            ext = ext_map.get(doc.get("filetype"), "")
            file_path = settings.upload_dir / f"{doc_id}{ext}"
            if file_path.exists():
                try:
                    os.remove(file_path)
                except:
                    pass
        
        return {"success": True, "doc_id": doc_id, "message": "Document deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query")
async def query_documents(doc_id: str = Query(...), query: str = Query(...), top_k: int = Query(5)):
    """Query a document using semantic search."""
    try:
        from app.services.query import query_document
        
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        results = await query_document(doc_id, query, top_k)
        
        return {
            "success": True,
            "doc_id": doc_id,
            "query": query,
            "results": results,
            "total": len(results)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{doc_id}/sections")
async def get_document_sections(doc_id: str):
    """Get all sections organized by dynamically detected categories."""
    try:
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get all topics to discover categories
        all_topics = get_document_topics(doc_id)
        
        # Group topics by section_type (dynamic categories)
        sections = {}
        categories = set()
        
        for topic in all_topics:
            section_type = topic.get("section_type") or "other"
            categories.add(section_type)
            if section_type not in sections:
                sections[section_type] = []
            sections[section_type].append(topic)
        
        # Always include tables and images
        sections["tables"] = get_document_tables(doc_id)
        sections["images"] = get_document_images(doc_id)
        
        # Add tables/images to categories if they exist
        if sections["tables"]:
            categories.add("tables")
        if sections["images"]:
            categories.add("images")
        
        # Sort categories - standard ones first, then alphabetical
        standard_order = ['abstract', 'introduction', 'methodology', 'results', 'discussion', 'conclusion', 'references']
        sorted_categories = []
        for std in standard_order:
            if std in categories:
                sorted_categories.append(std)
                categories.discard(std)
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
async def get_section_content(doc_id: str, section_type: str):
    """Get content for a specific section type with view options."""
    try:
        doc = get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        valid_sections = ["abstract", "introduction", "results", "conclusion", "references", "tables", "images"]
        if section_type not in valid_sections:
            raise HTTPException(status_code=400, detail=f"Invalid section type. Must be one of: {valid_sections}")
        
        # Get section content
        if section_type == "tables":
            content = get_document_tables(doc_id)
        elif section_type == "images":
            content = get_document_images(doc_id)
        else:
            content = get_sections_by_type(doc_id, section_type)
        
        # Add PDF viewing URL for each item
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