"""
Plain text file extraction.
"""

import uuid
from pathlib import Path
from typing import Dict, Any, List

from app.core.config import settings
from app.core.logging import logger


async def extract_txt(file_path: Path, doc_id: str) -> Dict[str, Any]:
    """Extract content from plain text file."""
    result = {
        "chunks": [],
        "tables": [],
        "topics": [],
        "keywords": []
    }
    
    try:
        # Read text file
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        
        # Create chunks
        result["chunks"] = create_chunks(text, doc_id)
        
        # Extract topics with sections
        result["topics"] = extract_topics(text, doc_id)
        
        logger.info(f"Extracted TXT: {len(result['chunks'])} chunks, {len(result['topics'])} topics")
        
    except Exception as e:
        logger.error(f"TXT extraction error: {e}")
    
    return result


def create_chunks(text: str, doc_id: str) -> List[Dict[str, Any]]:
    """Split text into chunks."""
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


def extract_topics(text: str, doc_id: str) -> List[Dict[str, Any]]:
    """Extract topics from text with section detection."""
    import re
    topics = []
    lines = text.split("\n")
    
    section_patterns = {
        "abstract": r"^(abstract|summary)[\s:]*$",
        "introduction": r"^(introduction|overview)[\s:]*$",
        "background": r"^(background|related\s+work|literature\s+review)[\s:]*$",
        "methodology": r"^(methodology|methods|approach)[\s:]*$",
        "results": r"^(results|findings|experiments)[\s:]*$",
        "discussion": r"^(discussion|analysis)[\s:]*$",
        "conclusion": r"^(conclusion|summary|future\s+work)[\s:]*$",
        "references": r"^(references|bibliography)[\s:]*$"
    }
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 3:
            continue
        
        # Check for standard sections
        section_type = None
        for sec_type, pattern in section_patterns.items():
            if re.match(pattern, line, re.IGNORECASE):
                section_type = sec_type
                break
        
        is_heading = (
            section_type is not None or
            line.isupper() and len(line) < 100 or
            (line[0].isdigit() and "." in line[:5]) or
            (len(line) < 80 and line.endswith(":"))
        )
        
        if is_heading:
            topic_id = str(uuid.uuid4())
            topics.append({
                "topic_id": topic_id,
                "title": line,
                "section_type": section_type,
                "start_page": 1,
                "end_page": 1,
                "level": 1 if section_type else 2,
                "chunk_ids": [],
                "content": ""
            })
            
            if len(topics) >= 30:
                break
    
    return topics