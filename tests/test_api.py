"""
FastAPI API routes for document catalog.
Provides endpoints for upload, catalog, tables, and PDF viewing.
"""

import os  # OS operations
from pathlib import Path  # Path handling
from typing import Optional, List  # Type hints

from fastapi import APIRouter, UploadFile, File, HTTPException, Query  # FastAPI components
from fastapi.responses import FileResponse, JSONResponse  # Response types

# Import services and database functions
from app.services.ingest import ingest_document, SUPPORTED_EXTENSIONS
from app.services.query import query_document
from app.db.sqlite import (
    get_document, 
    get_document_tables, 
    get_document_chunks,
    get_document_topics,
    get_document_keywords,
    get_table_by_id,
    list_documents,
    delete_document
)
from app.core.config import settings  # Application settings
from app.core.logging import logger  # Logging utility


# Create API router with prefix
router = APIRouter(prefix="/api", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and ingest a document.
    Accepts PDF, DOCX, CSV, and TXT files.
    
    Args:
        file: Uploaded file
        
    Returns:
        JSON with doc_id and summary counts
    """
    try:
        # Validate file exists
        if not file.filename:
            raise HTTPException(status_code=400, detail="No filename provided")
        
        # Get file extension
        ext = Path(file.filename).suffix.lower()
        
        # Validate file type
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported file type: {ext}. Supported: {list(SUPPORTED_EXTENSIONS.keys())}"
            )
        
        # Ingest the document
        doc_id = await ingest_document(file)
        
        # Get document metadata for response
        doc = get_document(doc_id)
        
        # Build response with summary counts
        return {
            "success": True,
            "doc_id": doc_id,
            "filename": file.filename,
            "filetype": SUPPORTED_EXTENSIONS[ext],
            "counts": {
                "chunks": doc.get("chunks_count", 0) if doc else 0,
                "tables": doc.get("tables_count", 0) if doc else 0,
                "topics": doc.get("topics_count", 0) if doc else 0,
                "keywords": doc.get("keywords_count", 0) if doc else 0
            }
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log and wrap other exceptions
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def list_all_documents():
    """
    List all uploaded documents.
    
    Returns:
        JSON array of document summaries
    """
    try:
        # Get all documents from database
        documents = list_documents()
        
        return {
            "success": True,
            "documents": documents,
            "total": len(documents)
        }
        
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/catalog/{doc_id}")
async def get_catalog(doc_id: str):
    """
    Get full catalog for a document.
    Includes document info, counts, tables, topics, and keywords.
    
    Args:
        doc_id: Document identifier
        
    Returns:
        JSON with complete catalog data
    """
    try:
        # Get document metadata
        doc = get_document(doc_id)
        
        # Check if document exists
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get tables with thumbnail URLs
        tables = get_document_tables(doc_id)
        
        # Add URLs to each table
        tables_with_urls = []
        for table in tables:
            table_data = {
                "table_id": table.get("table_id"),
                "page_number": table.get("page_number"),
                "table_index": table.get("table_index"),
                "rows_count": table.get("rows_count"),
                "cols_count": table.get("cols_count"),
                "confidence": table.get("confidence"),
                # URL for thumbnail image
                "thumbnail_url": f"/api/tables/{table.get('table_id')}/thumbnail" if table.get("preview_image_path") else None,
                # URL for inline view (full image + data)
                "inline_view_url": f"/api/tables/{table.get('table_id')}",
                # URL to open PDF at this page
                "pdf_page_url": f"/api/pdf/{doc_id}?page={table.get('page_number')}"
            }
            tables_with_urls.append(table_data)
        
        # Get topics
        topics = get_document_topics(doc_id)
        
        # Get keywords
        keywords = get_document_keywords(doc_id)
        
        # Build catalog response
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
                "topics": doc.get("topics_count", 0),
                "keywords": doc.get("keywords_count", 0)
            },
            "tables": tables_with_urls,
            "topics": topics,
            "keywords": keywords
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting catalog: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_id}")
async def get_table_data(table_id: str):
    """
    Get full table data including image and text.
    
    Args:
        table_id: Table identifier
        
    Returns:
        JSON with table metadata, text, and image URL
    """
    try:
        # Get table from database
        table = get_table_by_id(table_id)
        
        # Check if table exists
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        
        # Build response
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
            # Table as markdown text
            "table_text": table.get("table_text", ""),
            # URL for full-size image
            "full_image_url": f"/api/tables/{table_id}/image" if table.get("full_image_path") else None,
            # URL for thumbnail
            "thumbnail_url": f"/api/tables/{table_id}/thumbnail" if table.get("preview_image_path") else None,
            # URL to view in PDF
            "pdf_page_url": f"/api/pdf/{table.get('doc_id')}?page={table.get('page_number')}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting table data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_id}/thumbnail")
async def get_table_thumbnail(table_id: str):
    """
    Get table thumbnail image.
    
    Args:
        table_id: Table identifier
        
    Returns:
        PNG image file
    """
    try:
        # Get table from database
        table = get_table_by_id(table_id)
        
        # Check if table exists
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        
        # Get preview image path
        preview_path = table.get("preview_image_path")
        
        # Check if image exists
        if not preview_path:
            raise HTTPException(status_code=404, detail="Thumbnail not available")
        
        # Build full path
        full_path = settings.data_dir / preview_path
        
        # Check if file exists
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Thumbnail file not found")
        
        # Return image file
        return FileResponse(
            path=str(full_path),
            media_type="image/png",
            filename=f"{table_id}_thumbnail.png"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting thumbnail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tables/{table_id}/image")
async def get_table_image(table_id: str):
    """
    Get full-size table image.
    
    Args:
        table_id: Table identifier
        
    Returns:
        PNG image file
    """
    try:
        # Get table from database
        table = get_table_by_id(table_id)
        
        # Check if table exists
        if not table:
            raise HTTPException(status_code=404, detail="Table not found")
        
        # Get full image path
        full_image_path = table.get("full_image_path")
        
        # Check if image exists
        if not full_image_path:
            raise HTTPException(status_code=404, detail="Image not available")
        
        # Build full path
        full_path = settings.data_dir / full_image_path
        
        # Check if file exists
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Image file not found")
        
        # Return image file
        return FileResponse(
            path=str(full_path),
            media_type="image/png",
            filename=f"{table_id}_full.png"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pdf/{doc_id}")
async def serve_pdf(doc_id: str, page: Optional[int] = Query(None, ge=1)):
    """
    Serve PDF file with optional page parameter.
    Frontend can use page parameter for navigation.
    
    Args:
        doc_id: Document identifier
        page: Optional page number (1-indexed)
        
    Returns:
        PDF file response with page hint header
    """
    try:
        # Get document metadata
        doc = get_document(doc_id)
        
        # Check if document exists
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Check if it's a PDF
        if doc.get("filetype") != "pdf":
            raise HTTPException(status_code=400, detail="Document is not a PDF")
        
        # Build PDF file path
        pdf_path = settings.upload_dir / f"{doc_id}.pdf"
        
        # Check if file exists
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="PDF file not found")
        
        # Create response with page hint header
        response = FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=doc.get("filename", f"{doc_id}.pdf")
        )
        
        # Add page hint header if specified
        if page:
            response.headers["X-PDF-Page"] = str(page)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error serving PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/{doc_id}")
async def query_doc(doc_id: str, query: dict):
    """
    Query a document using semantic search.
    
    Args:
        doc_id: Document identifier
        query: Query object with 'text' field
        
    Returns:
        JSON with search results
    """
    try:
        # Extract query text
        query_text = query.get("text", "")
        
        # Validate query
        if not query_text:
            raise HTTPException(status_code=400, detail="Query text required")
        
        # Perform semantic search
        results = query_document(doc_id, query_text)
        
        return {
            "success": True,
            "doc_id": doc_id,
            "query": query_text,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}")
async def delete_doc(doc_id: str):
    """
    Delete a document and all related data.
    
    Args:
        doc_id: Document identifier
        
    Returns:
        JSON with success status
    """
    try:
        # Get document first to find file
        doc = get_document(doc_id)
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete from database
        deleted = delete_document(doc_id)
        
        if deleted:
            # Try to delete the uploaded file
            ext = {
                'pdf': '.pdf',
                'docx': '.docx',
                'csv': '.csv',
                'txt': '.txt'
            }.get(doc.get("filetype"), "")
            
            file_path = settings.upload_dir / f"{doc_id}{ext}"
            if file_path.exists():
                try:
                    os.remove(file_path)
                except Exception as e:
                    logger.warning(f"Could not delete file: {e}")
            
            # Try to delete table images
            table_images_dir = settings.data_dir / "table_images" / doc_id
            if table_images_dir.exists():
                try:
                    import shutil
                    shutil.rmtree(table_images_dir)
                except Exception as e:
                    logger.warning(f"Could not delete table images: {e}")
        
        return {
            "success": True,
            "doc_id": doc_id,
            "message": "Document deleted"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete error: {e}")
        raise HTTPException(status_code=500, detail=str(e))