# Copilot Instructions (rag-document-cataloger)

## Big picture

- FastAPI entrypoint is app/main.py; it sets up CORS and mounts routes from app/api/routes.py.
- Request flow: /upload -> app/services/ingest.py -> app/services/extract/\* for parsing -> app/db/sqlite.py for persistence, and app/services/index/faiss_store.py for vector indexing.
- OCR for PDFs is implemented in app/services/extract/pdf.py using pdf2image + pytesseract; it falls back to empty text if OCR is disabled or fails.

## Key modules and boundaries

- API layer: app/api/routes.py defines /upload, /documents, /documents/{doc_id}/catalog, /query.
- Extraction layer: app/services/extract/{pdf,docx,csv,txt}.py (note each file exposes different function names and return shapes).
- Indexing: app/services/index/faiss_store.py exposes functions (create_index/load_index/search_index), not a class.
- Storage: app/db/sqlite.py defines a SQLAlchemy DocumentCatalog table and init_db().
- Models: app/models/schemas.py defines Pydantic request/response and catalog models.

## Project-specific conventions and gotchas

- Several call sites expect \*\_content function names (e.g., extract_docx_content in app/services/extract/docx.py), but other modules import different names. Check for name mismatches before refactoring.
- app/services/query.py expects FAISSStore class, but app/services/index/faiss_store.py exposes functions. Align interfaces if you touch query/indexing.
- Routes are async but services are synchronous; keep that pattern unless you refactor the whole chain.

## Configuration

- Environment flags are read in app/core/config.py from .env (ENABLE_OCR, ENABLE_LLM_LABELS, OCR_MAX_PAGES, DEFAULT_TOP_K, model names).
- Logs are configured in app/core/logging.py and write to app.log + stdout.

## Developer workflows

- Run server: uvicorn app.main:app --reload
- Tests: pytest tests/ -v (see tests/test_api.py)

## External dependencies

- OCR requires Poppler (pdf2image) and Tesseract in PATH; see README.md.
- Embeddings/FAISS use LangChain + HuggingFace (app/services/index/faiss_store.py).

## Examples to follow

- PDF OCR + table heuristics: app/services/extract/pdf.py
- FAISS indexing and metadata shape: app/services/index/faiss_store.py (metadata keys: item_id, category, page, section, doc_id)
