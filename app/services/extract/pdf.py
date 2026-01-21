"""
PDF extraction with tables, text chunking, and metadata.
"""

import uuid
from pathlib import Path
from typing import Dict, Any, List
import pdfplumber
from PIL import Image
import io

from app.core.config import settings
from app.core.logging import logger


async def extract_pdf(file_path: Path, doc_id: str) -> Dict[str, Any]:
    """
    Extract content from PDF: text chunks, tables, topics, keywords.
    
    Args:
        file_path: Path to PDF file
        doc_id: Document ID
        
    Returns:
        Dictionary with chunks, tables, topics, keywords
    """
    result = {
        "chunks": [],
        "tables": [],
        "topics": [],
        "keywords": []
    }
    
    try:
        with pdfplumber.open(file_path) as pdf:
            all_text = ""
            
            # Process each page
            for page_num, page in enumerate(pdf.pages, start=1):
                # Extract text
                page_text = page.extract_text() or ""
                all_text += page_text + "\n\n"
                
                # Extract tables
                tables = page.extract_tables()
                if tables:
                    for table_idx, table_data in enumerate(tables):
                        if not table_data or len(table_data) == 0:
                            continue
                        
                        table_id = str(uuid.uuid4())
                        
                        # Convert table to markdown text
                        table_text = format_table_as_markdown(table_data)
                        
                        # Get table dimensions
                        rows_count = len(table_data)
                        cols_count = len(table_data[0]) if table_data else 0
                        
                        # Try to extract table image
                        table_images = extract_table_images(page, doc_id, table_id, page_num, table_idx)
                        
                        table_entry = {
                            "table_id": table_id,
                            "page_number": page_num,
                            "table_index": table_idx,
                            "table_text": table_text,
                            "rows_count": rows_count,
                            "cols_count": cols_count,
                            "confidence": 0.9,  # pdfplumber is reliable
                            "bbox": None,
                            "full_image_path": table_images.get("full_image_path"),
                            "preview_image_path": table_images.get("preview_image_path")
                        }
                        
                        result["tables"].append(table_entry)
            
            # Create text chunks
            result["chunks"] = create_chunks(all_text, doc_id)
            
            # Extract topics (simple heading detection)
            result["topics"] = extract_topics(all_text, doc_id)
            
            # Extract keywords
            result["keywords"] = extract_keywords(all_text, doc_id)
        
        logger.info(f"Extracted PDF: {len(result['chunks'])} chunks, {len(result['tables'])} tables")
        
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
    
    return result


def format_table_as_markdown(table_data: List[List[str]]) -> str:
    """Convert table data to markdown format."""
    if not table_data:
        return ""
    
    lines = []
    
    # Header row
    header = [str(cell or "") for cell in table_data[0]]
    lines.append("| " + " | ".join(header) + " |")
    
    # Separator
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    
    # Data rows
    for row in table_data[1:]:
        row_str = [str(cell or "") for cell in row]
        lines.append("| " + " | ".join(row_str) + " |")
    
    return "\n".join(lines)


def extract_table_images(page, doc_id: str, table_id: str, page_num: int, table_idx: int) -> Dict[str, str]:
    """Extract table as image (thumbnail and full size)."""
    result = {
        "full_image_path": None,
        "preview_image_path": None
    }
    
    try:
        # Create directory for table images
        table_dir = settings.data_dir / "table_images" / doc_id
        table_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert page to image
        img = page.to_image(resolution=150)
        pil_img = img.original
        
        # Save full image
        full_path = table_dir / f"{table_id}_full.png"
        pil_img.save(full_path)
        result["full_image_path"] = f"table_images/{doc_id}/{table_id}_full.png"
        
        # Create thumbnail (300px width)
        width, height = pil_img.size
        thumbnail_width = 300
        thumbnail_height = int((thumbnail_width / width) * height)
        thumbnail = pil_img.resize((thumbnail_width, thumbnail_height), Image.Resampling.LANCZOS)
        
        preview_path = table_dir / f"{table_id}_thumbnail.png"
        thumbnail.save(preview_path)
        result["preview_image_path"] = f"table_images/{doc_id}/{table_id}_thumbnail.png"
        
    except Exception as e:
        logger.warning(f"Could not extract table image: {e}")
    
    return result


def create_chunks(text: str, doc_id: str) -> List[Dict[str, Any]]:
    """
    Split text into chunks.
    
    Args:
        text: Full document text
        doc_id: Document ID
        
    Returns:
        List of chunk dictionaries
    """
    chunks = []
    
    # Simple chunking by paragraphs (you can use langchain later)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    
    chunk_size = settings.chunk_size
    chunk_overlap = settings.chunk_overlap
    
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
            
            # Start new chunk with overlap
            overlap_text = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else ""
            current_chunk = overlap_text + para + "\n\n"
    
    # Add last chunk
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
    """
    Extract topics/sections from text.
    Simple heuristic: lines that are all caps or start with numbers.
    """
    topics = []
    lines = text.split("\n")
    
    for idx, line in enumerate(lines):
        line = line.strip()
        
        # Skip empty or very short lines
        if not line or len(line) < 5:
            continue
        
        # Check if line looks like a heading
        is_heading = (
            line.isupper() or  # ALL CAPS
            (line[0].isdigit() and "." in line[:5]) or  # Numbered (1. 2. etc)
            (len(line) < 100 and line.endswith(":"))  # Short line ending with colon
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
            
            # Limit topics
            if len(topics) >= 20:
                break
    
    return topics


def extract_keywords(text: str, doc_id: str) -> List[Dict[str, Any]]:
    """
    Extract keywords using simple frequency analysis.
    """
    from collections import Counter
    import re
    
    # Clean and tokenize
    text_lower = text.lower()
    words = re.findall(r'\b[a-z]{4,}\b', text_lower)  # Words with 4+ letters
    
    # Common stop words
    stop_words = {
        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'has', 'had',
        'her', 'was', 'one', 'our', 'out', 'this', 'that', 'with', 'have', 'from',
        'they', 'been', 'were', 'will', 'would', 'there', 'their', 'what', 'which'
    }
    
    # Filter stop words
    words = [w for w in words if w not in stop_words]
    
    # Count frequencies
    word_counts = Counter(words)
    
    # Get top keywords
    keywords = []
    for word, count in word_counts.most_common(settings.max_keywords):
        keyword_id = str(uuid.uuid4())
        
        # Normalize score (0 to 1)
        score = min(count / 10, 1.0)
        
        keywords.append({
            "keyword_id": keyword_id,
            "keyword": word,
            "score": score
        })
    
    return keywords