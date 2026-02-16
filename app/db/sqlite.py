"""
SQLite database operations for document catalog.

This module owns all direct database access.  Every other module should
call these functions rather than constructing SQL directly.  The schema
consists of six tables:

  - users              – registered user accounts
  - verification_codes  – email verification OTPs
  - documents           – uploaded document metadata
  - chunks              – text chunks extracted from documents
  - tables              – table structures extracted from documents
  - topics              – detected section headings / topics
  - images              – image metadata extracted from PDFs
"""

import sqlite3
import json
from typing import Optional, List, Dict, Any
from pathlib import Path

from app.core.config import settings
from app.core.logging import logger


# Absolute path to the SQLite database file (set in config.py)
DB_PATH = settings.db_path


def get_connection() -> sqlite3.Connection:
    """Open and return a new SQLite connection.

    - ``row_factory = sqlite3.Row`` so rows behave like dicts.
    - ``PRAGMA foreign_keys`` is enabled to enforce FK constraints.
    """
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row           # Access columns by name
    conn.execute("PRAGMA foreign_keys = ON") # Enforce referential integrity
    return conn


def init_db():
    """Create all tables and indexes if they don't already exist."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE,
            hashed_password TEXT,
            oauth_provider TEXT,
            oauth_id TEXT,
            full_name TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    """)
    
    # Email verification codes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP NOT NULL,
            is_used INTEGER DEFAULT 0
        )
    """)
    
    # Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            filetype TEXT NOT NULL,
            file_size INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            chunks_count INTEGER DEFAULT 0,
            tables_count INTEGER DEFAULT 0,
            topics_count INTEGER DEFAULT 0,
            images_count INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )
    """)
    
    # Chunks table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            content TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            page_number INTEGER,
            metadata TEXT,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
        )
    """)
    
    # Tables table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tables (
            table_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            table_index INTEGER NOT NULL,
            bbox TEXT,
            table_text TEXT,
            rows_count INTEGER,
            cols_count INTEGER,
            confidence REAL,
            full_image_path TEXT,
            preview_image_path TEXT,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
        )
    """)
    
    # Topics table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            topic_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            title TEXT NOT NULL,
            section_type TEXT,
            start_page INTEGER,
            end_page INTEGER,
            level INTEGER,
            chunk_ids TEXT,
            content TEXT,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
        )
    """)
    
    # Images table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            image_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            page_number INTEGER NOT NULL,
            image_index INTEGER NOT NULL,
            bbox TEXT,
            width INTEGER,
            height INTEGER,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
        )
    """)
    
    # Create indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tables_doc_id ON tables(doc_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_topics_doc_id ON topics(doc_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_topics_section ON topics(section_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_images_doc_id ON images(doc_id)")
    
    # ── Schema migrations for existing databases ────────────────────
    # Add user_id column if the table was created before auth was added
    try:
        cursor.execute("SELECT user_id FROM documents LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Migrating documents table: adding user_id column")
        cursor.execute("ALTER TABLE documents ADD COLUMN user_id TEXT DEFAULT 'anonymous'")
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")


def save_document_metadata(doc_id: str, filename: str, filetype: str, file_size: int = 0, user_id: str = "anonymous") -> bool:
    """Insert or update the top-level metadata row for a document."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # INSERT OR REPLACE ensures idempotency if the same doc_id is re-ingested
        cursor.execute("""
            INSERT OR REPLACE INTO documents (doc_id, filename, filetype, file_size, user_id)
            VALUES (?, ?, ?, ?, ?)
        """, (doc_id, filename, filetype, file_size, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving document: {e}")
        return False


def save_chunks(doc_id: str, chunks: List[Dict[str, Any]]) -> bool:
    """Persist extracted text chunks and update the document's chunk count."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for chunk in chunks:
            # Metadata (e.g. splitter type) is serialized as a JSON string
            cursor.execute("""
                INSERT OR REPLACE INTO chunks (chunk_id, doc_id, content, chunk_index, page_number, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                chunk.get("chunk_id"),
                doc_id,
                chunk.get("content"),
                chunk.get("chunk_index"),
                chunk.get("page_number"),
                json.dumps(chunk.get("metadata", {}))
            ))
        # Keep the denormalized count in sync for quick dashboard queries
        cursor.execute("UPDATE documents SET chunks_count = ? WHERE doc_id = ?", (len(chunks), doc_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving chunks: {e}")
        return False


def save_tables(doc_id: str, tables: List[Dict[str, Any]]) -> bool:
    """Persist extracted table metadata (bbox, image paths, etc.) and update the count."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for table in tables:
            # bbox is stored as a JSON array string
            cursor.execute("""
                INSERT OR REPLACE INTO tables (
                    table_id, doc_id, page_number, table_index, bbox,
                    table_text, rows_count, cols_count, confidence,
                    full_image_path, preview_image_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                table.get("table_id"),
                doc_id,
                table.get("page_number", 1),
                table.get("table_index", 0),
                json.dumps(table.get("bbox")),
                table.get("table_text", ""),
                table.get("rows_count", 0),
                table.get("cols_count", 0),
                table.get("confidence", 0.0),
                table.get("full_image_path"),
                table.get("preview_image_path")
            ))
        cursor.execute("UPDATE documents SET tables_count = ? WHERE doc_id = ?", (len(tables), doc_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving tables: {e}")
        return False


def save_topics(doc_id: str, topics: List[Dict[str, Any]]) -> bool:
    """Persist detected section/topic headings and update the document's topic count."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for topic in topics:
            # chunk_ids is a JSON-encoded list linking topics to their chunks
            cursor.execute("""
                INSERT OR REPLACE INTO topics (
                    topic_id, doc_id, title, section_type, start_page, end_page, level, chunk_ids, content
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                topic.get("topic_id"),
                doc_id,
                topic.get("title"),
                topic.get("section_type"),
                topic.get("start_page"),
                topic.get("end_page"),
                topic.get("level"),
                json.dumps(topic.get("chunk_ids", [])),
                topic.get("content", "")
            ))
        cursor.execute("UPDATE documents SET topics_count = ? WHERE doc_id = ?", (len(topics), doc_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving topics: {e}")
        return False


def save_images(doc_id: str, images: List[Dict[str, Any]]) -> bool:
    """Persist image metadata (page, bounding box, dimensions) and update the count."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for image in images:
            cursor.execute("""
                INSERT OR REPLACE INTO images (
                    image_id, doc_id, page_number, image_index, bbox, width, height
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                image.get("image_id"),
                doc_id,
                image.get("page_number"),
                image.get("image_index"),
                json.dumps(image.get("bbox", [])),  # Serialize bounding box as JSON
                image.get("width"),
                image.get("height")
            ))
        # Keep the denormalized image count up-to-date
        cursor.execute("UPDATE documents SET images_count = ? WHERE doc_id = ?", (len(images), doc_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving images: {e}")
        return False


def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single document's metadata row by its primary key."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None  # Convert sqlite3.Row → dict
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        return None


def list_documents() -> List[Dict[str, Any]]:
    """Return all documents ordered by creation time (newest first)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]  # Convert each Row → dict
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        return []


def get_document_chunks(doc_id: str) -> List[Dict[str, Any]]:
    """Retrieve all chunks for a document, ordered by chunk_index.

    The JSON-encoded ``metadata`` column is deserialized back into a dict.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM chunks WHERE doc_id = ? ORDER BY chunk_index", (doc_id,))
        rows = cursor.fetchall()
        conn.close()
        chunks = []
        for row in rows:
            chunk = dict(row)
            if chunk.get("metadata"):
                chunk["metadata"] = json.loads(chunk["metadata"])
            chunks.append(chunk)
        return chunks
    except Exception as e:
        logger.error(f"Error getting chunks: {e}")
        return []


def get_document_tables(doc_id: str) -> List[Dict[str, Any]]:
    """Retrieve all tables for a document, ordered by page then table index.

    The ``bbox`` column (stored as JSON) is deserialized into a Python list.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tables WHERE doc_id = ? ORDER BY page_number, table_index", (doc_id,))
        rows = cursor.fetchall()
        conn.close()
        tables = []
        for row in rows:
            table = dict(row)
            if table.get("bbox"):
                table["bbox"] = json.loads(table["bbox"])
            tables.append(table)
        return tables
    except Exception as e:
        logger.error(f"Error getting tables: {e}")
        return []


def get_table_by_id(table_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single table row by its unique table_id."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tables WHERE table_id = ?", (table_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            table = dict(row)
            if table.get("bbox"):
                table["bbox"] = json.loads(table["bbox"])
            return table
        return None
    except Exception as e:
        logger.error(f"Error getting table: {e}")
        return None


def get_document_topics(doc_id: str) -> List[Dict[str, Any]]:
    """Retrieve all topics for a document, ordered by page then heading level.

    The ``chunk_ids`` column (stored as JSON) is deserialized into a Python list.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM topics WHERE doc_id = ? ORDER BY start_page, level", (doc_id,))
        rows = cursor.fetchall()
        conn.close()
        topics = []
        for row in rows:
            topic = dict(row)
            if topic.get("chunk_ids"):
                topic["chunk_ids"] = json.loads(topic["chunk_ids"])
            topics.append(topic)
        return topics
    except Exception as e:
        logger.error(f"Error getting topics: {e}")
        return []


def get_document_images(doc_id: str) -> List[Dict[str, Any]]:
    """Retrieve all image metadata for a document, ordered by page then index."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM images WHERE doc_id = ? ORDER BY page_number, image_index", (doc_id,))
        rows = cursor.fetchall()
        conn.close()
        images = []
        for row in rows:
            image = dict(row)
            if image.get("bbox"):
                image["bbox"] = json.loads(image["bbox"])
            images.append(image)
        return images
    except Exception as e:
        logger.error(f"Error getting images: {e}")
        return []


def get_sections_by_type(doc_id: str, section_type: str) -> List[Dict[str, Any]]:
    """Get topics filtered by section_type (e.g. 'abstract', 'introduction')."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM topics WHERE doc_id = ? AND section_type = ? ORDER BY start_page", (doc_id, section_type))
        rows = cursor.fetchall()
        conn.close()
        sections = []
        for row in rows:
            section = dict(row)
            if section.get("chunk_ids"):
                section["chunk_ids"] = json.loads(section["chunk_ids"])
            sections.append(section)
        return sections
    except Exception as e:
        logger.error(f"Error getting sections: {e}")
        return []


# ==================== User Management ====================

def create_user(user_id: str, email: str, username: Optional[str], hashed_password: Optional[str], 
                oauth_provider: Optional[str], oauth_id: Optional[str], full_name: Optional[str]) -> bool:
    """Insert a new user row.  Returns True on success, False on failure (e.g. duplicate email)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (user_id, email, username, hashed_password, oauth_provider, oauth_id, full_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, email, username, hashed_password, oauth_provider, oauth_id, full_name))
        conn.commit()
        conn.close()
        logger.info(f"User created: {email}")
        return True
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return False


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Look up a user by their unique email address."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting user by email: {e}")
        return None


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Look up a user by their primary-key user_id."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting user by ID: {e}")
        return None


def get_user_by_oauth(oauth_provider: str, oauth_id: str) -> Optional[Dict[str, Any]]:
    """Look up a user by their OAuth provider and external provider ID."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE oauth_provider = ? AND oauth_id = ?", (oauth_provider, oauth_id))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting user by OAuth: {e}")
        return None


def update_user_login(user_id: str) -> bool:
    """Set the user's ``last_login`` column to the current time."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error updating user login: {e}")
        return False


def store_verification_code(email: str, code: str, expires_at: str) -> bool:
    """Store a new email verification code, invalidating any previous unused codes for the same email."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Invalidate all earlier unused codes for this email to prevent confusion
        cursor.execute("UPDATE verification_codes SET is_used = 1 WHERE email = ? AND is_used = 0", (email,))
        # Insert the fresh code with its expiry timestamp
        cursor.execute(
            "INSERT INTO verification_codes (email, code, expires_at) VALUES (?, ?, ?)",
            (email, code, expires_at)
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error storing verification code: {e}")
        return False


def verify_code(email: str, code: str) -> bool:
    """Verify an email verification code.

    Returns True only if the code matches, belongs to the given email,
    has not already been used, and has not expired.  A valid code is
    immediately marked as used to prevent replay.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Find the most recent unused, non-expired code for this email
        cursor.execute("""
            SELECT * FROM verification_codes 
            WHERE email = ? AND code = ? AND is_used = 0 
            AND datetime(expires_at) > datetime('now')
            ORDER BY created_at DESC LIMIT 1
        """, (email, code))
        row = cursor.fetchone()
        
        if row:
            # Mark the code as used so it cannot be reused
            cursor.execute("UPDATE verification_codes SET is_used = 1 WHERE id = ?", (row['id'],))
            conn.commit()
            conn.close()
            return True
        
        conn.close()
        return False
    except Exception as e:
        logger.error(f"Error verifying code: {e}")
        return False


def cleanup_expired_codes():
    """Housekeeping: remove verification codes whose expiry has passed."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM verification_codes WHERE datetime(expires_at) < datetime('now')")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error cleaning up expired codes: {e}")



def delete_document(doc_id: str) -> bool:
    """Delete a document and all of its related child rows (chunks, tables, topics, images).

    Child tables are deleted explicitly (rather than relying solely on
    ON DELETE CASCADE) for extra safety and portability.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Remove child records in dependency order
        cursor.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        cursor.execute("DELETE FROM tables WHERE doc_id = ?", (doc_id,))
        cursor.execute("DELETE FROM topics WHERE doc_id = ?", (doc_id,))
        cursor.execute("DELETE FROM images WHERE doc_id = ?", (doc_id,))
        # Finally remove the parent document row
        cursor.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        return False