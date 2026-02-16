"""
Main FastAPI application entry point.

This module bootstraps the FastAPI application, configures middleware,
registers routers, sets up static file serving, and handles application
startup tasks such as database initialization and directory creation.
"""

# --- Standard library & third-party imports ---
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

# --- Internal project imports ---
from app.api.routes import router as api_router          # Document-related API endpoints
from app.api.auth_routes import router as auth_router    # Authentication API endpoints
from app.db.sqlite import init_db                        # Database schema initializer
from app.core.config import settings                     # Centralized application settings
from app.core.logging import logger                      # Pre-configured application logger


# ──────────────────────────────────────────────
# FastAPI Application Instance
# ──────────────────────────────────────────────
# Create the main FastAPI app with metadata used by the auto-generated docs (/docs).
app = FastAPI(
    title="RAG Document Cataloger",
    description="Upload, catalog, and query documents with email verification authentication",
    version="2.0.0"
)

# ──────────────────────────────────────────────
# CORS Middleware
# ──────────────────────────────────────────────
# Allow all origins so the front-end (served from the same host or elsewhere)
# can call the API without cross-origin restrictions.  Tighten allow_origins
# in production to limit which domains are permitted.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Accept requests from any origin
    allow_credentials=True,       # Allow cookies / Authorization headers
    allow_methods=["*"],          # Permit all HTTP methods (GET, POST, DELETE, …)
    allow_headers=["*"],          # Accept any request header
)

# ──────────────────────────────────────────────
# Router Registration
# ──────────────────────────────────────────────
# Mount the document API routes (prefix /api) and auth routes (prefix /auth).
app.include_router(api_router)
app.include_router(auth_router)

# ──────────────────────────────────────────────
# Static Files Configuration
# ──────────────────────────────────────────────
# Resolve the absolute path to the static assets directory next to this file.
STATIC_DIR = Path(__file__).parent / "static"


@app.on_event("startup")
async def startup_event():
    """Run one-time initialization tasks when the server starts.

    1. Initialize the SQLite database schema (creates tables if missing).
    2. Ensure the upload and data directories exist on disk.
    """
    try:
        from app.core.logging import logger
        logger.info("Starting RAG Document Cataloger...")

        # Re-import at runtime to guarantee the latest module state
        from app.db.sqlite import init_db
        init_db()  # Create DB tables if they don't already exist

        from app.core.config import settings
        # Ensure required directories are present; exist_ok avoids errors if they already exist
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        settings.data_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Application started")
    except Exception as e:
        # Print to stderr as a fallback in case the logger itself is misconfigured
        print(f"Startup error: {e}")
        raise


@app.get("/")
async def root():
    """Serve the authentication page as the default landing page.

    If the auth.html file exists on disk, serve it directly;
    otherwise fall back to a redirect to the /static/ mount point.
    """
    auth_path = STATIC_DIR / "auth.html"
    if auth_path.exists():
        return FileResponse(str(auth_path))
    return RedirectResponse(url="/static/auth.html")


# Mount the /static route so HTML, CSS, and JS assets are served by FastAPI.
# The guard prevents a startup crash if the directory hasn't been created yet.
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")