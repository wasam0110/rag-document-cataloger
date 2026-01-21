"""
Main FastAPI application entry point.
Configures the app, routes, and static file serving.
"""

from fastapi import FastAPI  # FastAPI framework
from fastapi.staticfiles import StaticFiles  # Static file serving
from fastapi.responses import FileResponse  # File response
from pathlib import Path  # Path handling

# Import API routes
from app.api.routes import router as api_router
# Import database initialization
from app.db.sqlite import init_db
# Import settings and logging
from app.core.config import settings
from app.core.logging import logger


# Create FastAPI application instance
app = FastAPI(
    title="RAG Document Cataloger",  # Application title
    description="Upload, catalog, and query documents with table extraction",  # Description
    version="1.0.0"  # Version number
)

# Include API routes with /api prefix
app.include_router(api_router)

# Get paths for static files
STATIC_DIR = Path(__file__).parent / "static"  # Static files directory


@app.on_event("startup")
async def startup_event():
    """
    Application startup event handler.
    Initializes database and creates required directories.
    """
    # Log startup
    logger.info("Starting RAG Document Cataloger...")
    
    # Initialize database schema
    init_db()
    logger.info("Database initialized")
    
    # Ensure upload directory exists
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Upload directory: {settings.upload_dir}")
    
    # Ensure data directory exists
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Data directory: {settings.data_dir}")
    
    # Ensure table images directory exists
    table_images_dir = settings.data_dir / "table_images"
    table_images_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Table images directory: {table_images_dir}")
    
    logger.info("Application started successfully")


@app.get("/")
async def root():
    """
    Serve the main HTML page.
    
    Returns:
        HTML file response
    """
    # Return the index.html file
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    else:
        return {"message": "RAG Document Cataloger API", "docs": "/docs"}


# Mount static files directory for CSS/JS
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")