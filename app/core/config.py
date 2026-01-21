"""
Application configuration settings.
Loads from environment variables with sensible defaults.
"""

import os
from pathlib import Path


class Settings:
    """Application settings with sensible defaults."""
    
    def __init__(self):
        # Base directory (project root)
        self.base_dir = Path(__file__).parent.parent.parent
        
        # Data directory for database and processed files
        self.data_dir = self.base_dir / "data"
        
        # Upload directory for incoming files
        self.upload_dir = self.data_dir / "uploads"
        
        # FAISS index directory
        self.faiss_index_dir = self.base_dir / "faiss_index"
        
        # Database path
        self.db_path = self.data_dir / "catalog.db"
        
        # Embedding model
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        
        # Chunk settings
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "500"))
        self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "50"))
        
        # Table extraction settings
        self.table_confidence_threshold = float(os.getenv("TABLE_CONFIDENCE_THRESHOLD", "0.7"))
        
        # Keyword extraction settings
        self.max_keywords = int(os.getenv("MAX_KEYWORDS", "20"))
        
        # Environment
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.faiss_index_dir.mkdir(parents=True, exist_ok=True)


# Create global settings instance
settings = Settings()