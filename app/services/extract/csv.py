"""CSV file extraction – treats the entire CSV as a single table.

The file is parsed with Python's csv module.  A Markdown representation
of the table is stored for search/display, and the raw row data is also
chunked for FAISS indexing.  Each column name becomes a 'topic'.
"""

import uuid
from pathlib import Path
from typing import Dict, Any, List
import csv

from app.core.config import settings
from app.core.logging import logger


async def extract_csv(file_path: Path, doc_id: str) -> Dict[str, Any]:
    """Parse a CSV file and return its content as a single-table result.

    Returns a dict with: chunks, tables, topics (column names), keywords.
    """
    result = {
        "chunks": [],
        "tables": [],
        "topics": [],
        "keywords": []
    }
    
    try:
        # Read all rows into memory (lenient encoding)
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        if not rows:
            return result
        
        # ── Build a single table entry for the whole CSV ──────────
        table_id = str(uuid.uuid4())
        table_text = format_csv_as_markdown(rows)
        
        table_entry = {
            "table_id": table_id,
            "page_number": 1,           # CSVs are single-page by convention
            "table_index": 0,           # Only one table per CSV
            "table_text": table_text,
            "rows_count": len(rows),
            "cols_count": len(rows[0]) if rows else 0,
            "confidence": 1.0,          # Directly parsed – always high confidence
            "bbox": None,
            "full_image_path": None,
            "preview_image_path": None
        }
        
        result["tables"].append(table_entry)
        
        # ── Create text chunks for FAISS indexing ─────────────────
        # Flatten rows back to comma-separated text for the chunker
        text = "\n".join([",".join(str(cell) for cell in row) for row in rows])
        result["chunks"] = create_chunks(text, doc_id)
        
        # ── Expose each column header as a topic ──────────────────
        if rows:
            for idx, col_name in enumerate(rows[0]):
                if col_name and str(col_name).strip():
                    topic_id = str(uuid.uuid4())
                    result["topics"].append({
                        "topic_id": topic_id,
                        "title": f"Column: {str(col_name).strip()}",
                        "section_type": None,   # Columns don't map to academic sections
                        "start_page": 1,
                        "end_page": 1,
                        "level": 1,
                        "chunk_ids": [],
                        "content": ""
                    })
        
        logger.info(f"Extracted CSV: {len(rows)} rows, {len(result['tables'])} tables")
        
    except Exception as e:
        logger.error(f"CSV extraction error: {e}")
    
    return result


def format_csv_as_markdown(rows: List[List[str]]) -> str:
    """Convert CSV rows to a GitHub-flavoured Markdown table.

    Only the first 100 data rows are rendered to keep the output
    manageable; a count of omitted rows is appended if necessary.
    """
    if not rows:
        return ""
    
    lines = []
    
    # First row → header
    header = [str(cell) for cell in rows[0]]
    lines.append("| " + " | ".join(header) + " |")
    # Markdown separator row
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    
    # Data rows – capped at 100 to avoid enormous strings
    for row in rows[1:101]:
        row_str = [str(cell) for cell in row]
        lines.append("| " + " | ".join(row_str) + " |")
    
    # Indicate truncated data
    if len(rows) > 101:
        lines.append(f"\n... and {len(rows) - 101} more rows")
    
    return "\n".join(lines)


def create_chunks(text: str, doc_id: str) -> List[Dict[str, Any]]:
    """Split CSV text into line-based chunks for vector indexing.

    Lines are accumulated until the configured chunk_size is exceeded,
    then a new chunk begins.  This keeps related rows together while
    respecting the embedding model's input length.
    """
    chunks = []
    lines = text.split("\n")
    
    chunk_size = settings.chunk_size
    current_chunk = ""
    chunk_index = 0
    
    for line in lines:
        # Keep accumulating lines while under the size limit
        if len(current_chunk) + len(line) < chunk_size:
            current_chunk += line + "\n"
        else:
            # Flush the accumulated chunk
            if current_chunk:
                chunk_id = str(uuid.uuid4())
                chunks.append({
                    "chunk_id": chunk_id,
                    "content": current_chunk.strip(),
                    "chunk_index": chunk_index,
                    "page_number": None,   # CSVs don't have page numbers
                    "metadata": {}
                })
                chunk_index += 1
            # Start a new chunk with the current line
            current_chunk = line + "\n"
    
    # Flush any remaining text as the last chunk
    if current_chunk:
        chunk_id = str(uuid.uuid4())
        chunks.append({
            "chunk_id": chunk_id,
            "content": current_chunk.strip(),
            "chunk_index": chunk_index,
            "page_number": None,
            "metadata": {}
        })
    
    return chunks