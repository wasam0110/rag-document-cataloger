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
            page_texts = []
            
            # Process each page
            for page_num, page in enumerate(pdf.pages, start=1):
                # Extract text
                page_text = page.extract_text() or ""
                page_texts.append({"page_num": page_num, "text": page_text})
                all_text += page_text + "\n\n"
                
                # Extract tables with improved settings
                table_settings = {
                    "vertical_strategy": "lines",
                    "horizontal_strategy": "lines",
                    "snap_tolerance": 3,
                    "join_tolerance": 3,
                    "edge_min_length": 3,
                }
                
                tables = page.extract_tables(table_settings)
                
                # Also try text-based table detection
                if not tables or len(tables) == 0:
                    tables = page.extract_tables()
                
                if tables:
                    for table_idx, table_data in enumerate(tables):
                        if not table_data or len(table_data) == 0:
                            continue
                        
                        # Filter out empty or invalid tables
                        non_empty_rows = [row for row in table_data if any(cell and str(cell).strip() for cell in row)]
                        if len(non_empty_rows) < 2:  # Need at least header + 1 row
                            continue
                        
                        table_id = str(uuid.uuid4())
                        
                        # Convert table to markdown text
                        table_text = format_table_as_markdown(non_empty_rows)
                        
                        # Get table dimensions
                        rows_count = len(non_empty_rows)
                        cols_count = len(non_empty_rows[0]) if non_empty_rows else 0
                        
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
            
            # Create text chunks with page tracking
            result["chunks"] = create_chunks_with_pages(page_texts, doc_id)
            
            # Extract topics with sections (Abstract, Introduction, Background, etc.)
            result["topics"] = extract_topics_with_sections(page_texts, doc_id, result["chunks"])
        
        logger.info(f"Extracted PDF: {len(result['chunks'])} chunks, {len(result['tables'])} tables, {len(result['topics'])} topics")
        
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
    # Keywords are no longer used - return empty list
    return []


def create_chunks_with_pages(page_texts: List[Dict], doc_id: str) -> List[Dict[str, Any]]:
    """
    Create chunks with page number tracking.
    """
    chunks = []
    chunk_size = settings.chunk_size
    chunk_overlap = settings.chunk_overlap
    chunk_index = 0
    
    for page_info in page_texts:
        page_num = page_info["page_num"]
        text = page_info["text"]
        
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        
        current_chunk = ""
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
                        "page_number": page_num,
                        "metadata": {}
                    })
                    chunk_index += 1
                
                # Start new chunk with overlap
                overlap_text = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else ""
                current_chunk = overlap_text + para + "\n\n"
        
        # Add last chunk from page
        if current_chunk:
            chunk_id = str(uuid.uuid4())
            chunks.append({
                "chunk_id": chunk_id,
                "content": current_chunk.strip(),
                "chunk_index": chunk_index,
                "page_number": page_num,
                "metadata": {}
            })
            chunk_index += 1
    
    return chunks


def extract_topics_with_sections(page_texts: List[Dict], doc_id: str, chunks: List[Dict]) -> List[Dict[str, Any]]:
    """
    Extract topics and identify standard sections like Abstract, Introduction, Background.
    """
    import re
    
    topics = []
    
    # Standard section patterns (case-insensitive)
    section_patterns = {
        "abstract": r"^(abstract|summary)[\s:]*$",
        "introduction": r"^(introduction|overview)[\s:]*$",
        "background": r"^(background|related\s+work|literature\s+review|prior\s+work)[\s:]*$",
        "methodology": r"^(methodology|methods|approach|implementation)[\s:]*$",
        "results": r"^(results|findings|experiments|evaluation)[\s:]*$",
        "discussion": r"^(discussion|analysis)[\s:]*$",
        "conclusion": r"^(conclusion|conclusions|summary|future\s+work)[\s:]*$",
        "references": r"^(references|bibliography|citations)[\s:]*$"
    }
    
    all_text = "\n".join([pt["text"] for pt in page_texts])
    lines = all_text.split("\n")
    
    for idx, line in enumerate(lines):
        line_stripped = line.strip()
        
        if not line_stripped or len(line_stripped) < 3:
            continue
        
        # Check for standard sections
        section_type = None
        for sec_type, pattern in section_patterns.items():
            if re.match(pattern, line_stripped, re.IGNORECASE):
                section_type = sec_type
                break
        
        # Check if line looks like a heading
        is_heading = (
            section_type is not None or
            line_stripped.isupper() and len(line_stripped) < 100 or  # ALL CAPS
            (line_stripped[0].isdigit() and "." in line_stripped[:10]) or  # Numbered
            (len(line_stripped) < 80 and line_stripped.endswith(":"))  # Short with colon
        )
        
        if is_heading:
            # Find page number for this line
            page_num = 1
            char_count = 0
            for pt in page_texts:
                char_count += len(pt["text"])
                if char_count >= sum(len(l) for l in lines[:idx]):
                    page_num = pt["page_num"]
                    break
            
            # Find relevant chunks
            chunk_ids = []
            content_preview = ""
            for chunk in chunks:
                if chunk.get("page_number") == page_num:
                    chunk_ids.append(chunk["chunk_id"])
                    if not content_preview and len(chunk.get("content", "")) > 50:
                        content_preview = chunk["content"][:500]
            
            topic_id = str(uuid.uuid4())
            topics.append({
                "topic_id": topic_id,
                "title": line_stripped,
                "section_type": section_type,
                "start_page": page_num,
                "end_page": page_num,
                "level": 1 if section_type else 2,
                "chunk_ids": chunk_ids,
                "content": content_preview
            })
            
            # Limit topics
            if len(topics) >= 50:
                break
    
    return topics