"""
CSV file extraction - treat entire CSV as a table.
"""

import uuid
from pathlib import Path
from typing import Dict, Any, List
import csv

from app.core.config import settings
from app.core.logging import logger


async def extract_csv(file_path: Path, doc_id: str) -> Dict[str, Any]:
    """Extract CSV as a single table."""
    result = {
        "chunks": [],
        "tables": [],
        "topics": [],
        "keywords": []
    }
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        if not rows:
            return result
        
        # Create table entry
        table_id = str(uuid.uuid4())
        table_text = format_csv_as_markdown(rows)
        
        table_entry = {
            "table_id": table_id,
            "page_number": 1,
            "table_index": 0,
            "table_text": table_text,
            "rows_count": len(rows),
            "cols_count": len(rows[0]) if rows else 0,
            "confidence": 1.0,
            "bbox": None,
            "full_image_path": None,
            "preview_image_path": None
        }
        
        result["tables"].append(table_entry)
        
        # Also create chunks from CSV content
        text = "\n".join([",".join(str(cell) for cell in row) for row in rows])
        result["chunks"] = create_chunks(text, doc_id)
        
        # Extract column names as topics
        if rows:
            for idx, col_name in enumerate(rows[0]):
                if col_name and str(col_name).strip():
                    topic_id = str(uuid.uuid4())
                    result["topics"].append({
                        "topic_id": topic_id,
                        "title": f"Column: {str(col_name).strip()}",
                        "section_type": None,
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
    """Convert CSV to markdown table."""
    if not rows:
        return ""
    
    lines = []
    
    # Header
    header = [str(cell) for cell in rows[0]]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    
    # Data rows (limit to 100 rows for display)
    for row in rows[1:101]:
        row_str = [str(cell) for cell in row]
        lines.append("| " + " | ".join(row_str) + " |")
    
    if len(rows) > 101:
        lines.append(f"\n... and {len(rows) - 101} more rows")
    
    return "\n".join(lines)


def create_chunks(text: str, doc_id: str) -> List[Dict[str, Any]]:
    """Create chunks from CSV text."""
    chunks = []
    lines = text.split("\n")
    
    chunk_size = settings.chunk_size
    current_chunk = ""
    chunk_index = 0
    
    for line in lines:
        if len(current_chunk) + len(line) < chunk_size:
            current_chunk += line + "\n"
        else:
            if current_chunk:
                chunk_id = str(uuid.uuid4())
                chunks.append({
                    "chunk_id": chunk_id,
                    "content": current_chunk.strip(),
                    "chunk_index": chunk_index,
                    "page_number": None,
                    "metadata": {}
                })
                chunk_index += 1
            current_chunk = line + "\n"
    
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