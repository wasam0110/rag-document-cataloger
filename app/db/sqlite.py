"""
SQLite database operations for document catalog.
"""

import sqlite3
import json
from typing import Optional, List, Dict, Any
from pathlib import Path

from app.core.config import settings
from app.core.logging import logger


# Database path from settings
DB_PATH = settings.db_path


def get_connection() -> sqlite3.Connection:
    """Get SQLite database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize database schema."""
    conn = get_connection()
    cursor = conn.cursor()
    
    # Documents table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            doc_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            filetype TEXT NOT NULL,
            file_size INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            chunks_count INTEGER DEFAULT 0,
            tables_count INTEGER DEFAULT 0,
            topics_count INTEGER DEFAULT 0,
            images_count INTEGER DEFAULT 0
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
    
    conn.commit()
    conn.close()
    logger.info("Database initialized")


def save_document_metadata(doc_id: str, filename: str, filetype: str, file_size: int = 0) -> bool:
    """Save document metadata."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO documents (doc_id, filename, filetype, file_size)
            VALUES (?, ?, ?, ?)
        """, (doc_id, filename, filetype, file_size))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving document: {e}")
        return False


def save_chunks(doc_id: str, chunks: List[Dict[str, Any]]) -> bool:
    """Save document chunks."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for chunk in chunks:
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
        cursor.execute("UPDATE documents SET chunks_count = ? WHERE doc_id = ?", (len(chunks), doc_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving chunks: {e}")
        return False


def save_tables(doc_id: str, tables: List[Dict[str, Any]]) -> bool:
    """Save extracted tables."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for table in tables:
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
    """Save document topics."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        for topic in topics:
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
    """Save document images."""
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
                json.dumps(image.get("bbox", [])),
                image.get("width"),
                image.get("height")
            ))
        cursor.execute("UPDATE documents SET images_count = ? WHERE doc_id = ?", (len(images), doc_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error saving images: {e}")
        return False


def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    """Get document by ID."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        return None


def list_documents() -> List[Dict[str, Any]]:
    """List all documents."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM documents ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        return []


def get_document_chunks(doc_id: str) -> List[Dict[str, Any]]:
    """Get chunks for a document."""
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
    """Get tables for a document."""
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
    """Get table by ID."""
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
    """Get topics for a document."""
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
    """Get images for a document."""
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
    """Get topics/sections by type (abstract, introduction, results, conclusion, references)."""
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


def delete_document(doc_id: str) -> bool:
    """Delete document and related data."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Delete related records first
        cursor.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
        cursor.execute("DELETE FROM tables WHERE doc_id = ?", (doc_id,))
        cursor.execute("DELETE FROM topics WHERE doc_id = ?", (doc_id,))
        cursor.execute("DELETE FROM images WHERE doc_id = ?", (doc_id,))
        cursor.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        return False