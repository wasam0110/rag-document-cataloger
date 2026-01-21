"""
Main FastAPI application entry point.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.api.routes import router as api_router
from app.db.sqlite import init_db
from app.core.config import settings
from app.core.logging import logger


# Create FastAPI app
app = FastAPI(
    title="RAG Document Cataloger",
    description="Upload, catalog, and query documents with table extraction",
    version="1.0.0"
)

# Include API routes
app.include_router(api_router)

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    logger.info("Starting RAG Document Cataloger...")
    init_db()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Application started")


@app.get("/")
async def root():
    """Serve main HTML page."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "RAG Document Cataloger API", "docs": "/docs"}


# Mount static files
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")