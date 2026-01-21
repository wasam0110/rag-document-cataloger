#!/usr/bin/env python
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("Testing imports...")

try:
    from app.api.routes import router as api_router
    print(f"✓ api_router imported: {api_router}")
except Exception as e:
    print(f"✗ Failed to import api_router: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.core.logging import setup_logging
    print(f"✓ setup_logging imported: {setup_logging}")
except Exception as e:
    print(f"✗ Failed to import setup_logging: {e}")

try:
    from app.db.sqlite import init_db
    print(f"✓ init_db imported: {init_db}")
except Exception as e:
    print(f"✗ Failed to import init_db: {e}")

try:
    from app.services.ingest import ingest_document
    print(f"✓ ingest_document imported: {ingest_document}")
except Exception as e:
    print(f"✗ Failed to import ingest_document: {e}")
    import traceback
    traceback.print_exc()

try:
    from app.services.index.faiss_store import create_index
    print(f"✓ faiss_store imported: {create_index}")
except Exception as e:
    print(f"✗ Failed to import faiss_store: {e}")
    import traceback
    traceback.print_exc()

print("\nImport test complete!")
