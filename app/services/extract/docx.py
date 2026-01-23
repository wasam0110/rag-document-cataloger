"""
DOCX file extraction.
"""

import uuid
from pathlib import Path
from typing import Dict, Any, List
from docx import Document

from app.core.config import settings
from app.core.logging import logger


async def extract_docx(file_path: Path, doc_id: str) -> Dict[str, Any]:
    """Extract content from DOCX file."""
    result = {
        "chunks": [],
        "tables": [],
        "topics": [],
        "keywords": []
    }
    
    try:
        doc = Document(file_path)
        
        # Extract text
        all_text = "\n\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        
        # Extract tables
        for table_idx, table in enumerate(doc.tables):
            table_id = str(uuid.uuid4())
            table_data = []
            
            for row in table.rows:
                row_data = [cell.text for cell in row.cells]
                table_data.append(row_data)
            
            if not table_data:
                continue
            
            table_text = format_table_as_markdown(table_data)
            
            table_entry = {
                "table_id": table_id,
                "page_number": 1,
                "table_index": table_idx,
                "table_text": table_text,
                "rows_count": len(table_data),
                "cols_count": len(table_data[0]) if table_data else 0,
                "confidence": 1.0,
                "bbox": None,
                "full_image_path": None,
                "preview_image_path": None
            }
            
            result["tables"].append(table_entry)
        
        # Create chunks
        result["chunks"] = create_chunks(all_text, doc_id)
        
        # Extract topics (headings) with section detection
        section_keywords = {
            "abstract": ["abstract", "summary"],
            "introduction": ["introduction", "overview"],
            "background": ["background", "related work", "literature review"],
            "methodology": ["methodology", "methods", "approach"],
            "results": ["results", "findings", "experiments"],
            "discussion": ["discussion", "analysis"],
            "conclusion": ["conclusion", "summary", "future work"],
            "references": ["references", "bibliography"]
        }
        
        for para in doc.paragraphs:
            if para.style.name.startswith('Heading'):
                topic_id = str(uuid.uuid4())
                title_lower = para.text.lower()
                
                # Detect section type
                section_type = None
                for sec_type, keywords in section_keywords.items():
                    if any(kw in title_lower for kw in keywords):
                        section_type = sec_type
                        break
                
                result["topics"].append({
                    "topic_id": topic_id,
                    "title": para.text,
                    "section_type": section_type,
                    "start_page": 1,
                    "end_page": 1,
                    "level": int(para.style.name[-1]) if para.style.name[-1].isdigit() else 1,
                    "chunk_ids": [],
                    "content": ""
                })
        
        logger.info(f"Extracted DOCX: {len(result['chunks'])} chunks, {len(result['tables'])} tables, {len(result['topics'])} topics")
        
    except Exception as e:
        logger.error(f"DOCX extraction error: {e}")
    
    return result


def format_table_as_markdown(table_data: List[List[str]]) -> str:
    """Convert table to markdown."""
    if not table_data:
        return ""
    
    lines = []
    header = [str(cell) for cell in table_data[0]]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    
    for row in table_data[1:]:
        row_str = [str(cell) for cell in row]
        lines.append("| " + " | ".join(row_str) + " |")
    
    return "\n".join(lines)


def create_chunks(text: str, doc_id: str) -> List[Dict[str, Any]]:
    """Create chunks."""
    chunks = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    chunk_size = settings.chunk_size
    current_chunk = ""
    chunk_index = 0
    
    for para in paragraphs:
        if len(current_chunk) + len(para) < chunk_size:
            current_chunk += para + "\n\n"
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
            current_chunk = para + "\n\n"
    
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