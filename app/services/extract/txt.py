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
        
        # Extract topics
        result["topics"] = extract_topics(text, doc_id)
        
        # Extract keywords
        result["keywords"] = extract_keywords(text, doc_id)
        
        logger.info(f"Extracted TXT: {len(result['chunks'])} chunks")
        
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
    """Extract topics from text."""
    topics = []
    lines = text.split("\n")
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue
        
        is_heading = (
            line.isupper() or
            (line[0].isdigit() and "." in line[:5]) or
            (len(line) < 100 and line.endswith(":"))
        )
        
        if is_heading:
            topic_id = str(uuid.uuid4())
            topics.append({
                "topic_id": topic_id,
                "title": line,
                "start_page": 1,
                "end_page": 1,
                "level": 1
            })
            
            if len(topics) >= 20:
                break
    
    return topics


def extract_keywords(text: str, doc_id: str) -> List[Dict[str, Any]]:
    """Extract keywords."""
    from collections import Counter
    import re
    
    text_lower = text.lower()
    words = re.findall(r'\b[a-z]{4,}\b', text_lower)
    
    stop_words = {
        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'has', 'had',
        'her', 'was', 'one', 'our', 'out', 'this', 'that', 'with', 'have', 'from'
    }
    
    words = [w for w in words if w not in stop_words]
    word_counts = Counter(words)
    
    keywords = []
    for word, count in word_counts.most_common(settings.max_keywords):
        keyword_id = str(uuid.uuid4())
        score = min(count / 10, 1.0)
        keywords.append({
            "keyword_id": keyword_id,
            "keyword": word,
            "score": score
        })
    
    return keywords