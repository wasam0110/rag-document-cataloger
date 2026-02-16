"""
Application configuration settings.
Loads from environment variables with sensible defaults.

All settings are centralized here so that every module imports a single
`settings` instance rather than reading os.environ directly.  A .env
file is loaded automatically via python-dotenv for local development.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Read key=value pairs from a .env file (if present) into os.environ
# so the Settings class can pick them up with os.getenv().
load_dotenv()


class Settings:
    """Application settings with sensible defaults.

    Each attribute is initialized from an environment variable and
    falls back to a hard-coded default when the variable is absent.
    """
    
    def __init__(self):
        # ── Directory paths ──────────────────────────────────────────
        # Project root is two levels above this file: config.py → core/ → app/ → project root
        self.base_dir = Path(__file__).parent.parent.parent
        
        # Central data directory for the SQLite DB, processed files, etc.
        self.data_dir = self.base_dir / "data"
        
        # Directory where raw uploaded files are stored on disk
        self.upload_dir = self.data_dir / "uploads"
        
        # Directory where per-document FAISS vector indexes are persisted
        self.faiss_index_dir = self.base_dir / "faiss_index"
        
        # SQLite database file path
        self.db_path = self.data_dir / "catalog.db"
        
        # ── Embedding model ──────────────────────────────────────────
        # HuggingFace model for text embeddings - using BAAI/bge-base-en-v1.5
        # which is state-of-the-art for retrieval quality (768 dimensions).
        # Significantly outperforms the smaller MiniLM models.
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5")

        # ── LLM generation model (for RAG) ───────────────────────────
        # Model for text generation - using google/flan-t5-xl (3B params)
        # which produces much higher quality answers than the base model.
        # This is the best free model that balances quality and resource usage.
        self.huggingface_model = os.getenv("HUGGINGFACE_MODEL", "google/flan-t5-xl")

        # Device to run generation on: -1 for CPU, or GPU index (0,1,...)
        try:
            self.llm_device = int(os.getenv("LLM_DEVICE", "-1"))
        except Exception:
            self.llm_device = -1
        
        # ── Text chunking parameters ────────────────────────────────
        # Maximum number of characters per chunk when splitting documents
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "500"))
        # Number of overlapping characters between consecutive chunks
        # to preserve context across chunk boundaries
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "50"))
        
        # ── Table extraction ─────────────────────────────────────────
        # Minimum confidence score (0-1) for accepting a detected table
        self.table_confidence_threshold = float(os.getenv("TABLE_CONFIDENCE_THRESHOLD", "0.7"))
        
        # ── Keyword extraction ───────────────────────────────────────
        # Upper limit on the number of keywords extracted per document
        self.max_keywords = int(os.getenv("MAX_KEYWORDS", "20"))
        
        # ── Authentication / JWT ─────────────────────────────────────
        # Secret key used to sign JWT tokens – MUST be changed in production
        self.secret_key = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
        
        # ── Email verification ───────────────────────────────────────
        # When True, verification codes are logged instead of emailed (for local dev)
        self.email_test_mode = os.getenv("EMAIL_TEST_MODE", "false").lower() == "true"
        
        # ── SMTP email delivery settings ─────────────────────────────
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")     # SMTP host
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))               # SMTP port (587 = STARTTLS)
        self.smtp_username = os.getenv("SMTP_USERNAME", "")               # SMTP login username
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")               # SMTP login password / app password
        self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "")           # "From" address on outgoing emails
        
        # ── Runtime environment ──────────────────────────────────────
        # "development" or "production" – can be used to toggle debug features
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # ── Ensure required directories exist on startup ─────────────
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.faiss_index_dir.mkdir(parents=True, exist_ok=True)


# Singleton settings instance shared across the entire application
settings = Settings()