"""
Plain text file extraction with semantic chunking and section detection.
"""

import uuid
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple

from app.core.config import settings
from app.core.logging import logger

# Try to import advanced text splitter
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False


async def extract_txt(file_path: Path, doc_id: str) -> Dict[str, Any]:
    """Extract content from plain text file with intelligent section detection."""
    result = {
        "chunks": [],
        "tables": [],
        "topics": [],
        "keywords": [],
        "images": [],
        "categories": []
    }
    
    try:
        # Read text file
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        
        # Create semantic chunks
        result["chunks"] = create_semantic_chunks(text, doc_id)
        
        # Extract topics with proper section types
        result["topics"], result["categories"] = extract_sections(text, doc_id, result["chunks"])
        
        logger.info(f"Extracted TXT: {len(result['chunks'])} chunks, {len(result['topics'])} sections in {len(result['categories'])} categories")
        
    except Exception as e:
        logger.error(f"TXT extraction error: {e}")
    
    return result


def create_semantic_chunks(text: str, doc_id: str) -> List[Dict[str, Any]]:
    """Create semantic chunks using sentence-aware splitting."""
    chunks = []
    chunk_size = settings.chunk_size
    chunk_overlap = settings.chunk_overlap
    
    # Clean text
    text = clean_text(text)
    
    if HAS_LANGCHAIN:
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ", ""],
            length_function=len,
            is_separator_regex=False,
        )
        
        chunk_texts = text_splitter.split_text(text)
        
        for idx, chunk_text in enumerate(chunk_texts):
            chunk_text = chunk_text.strip()
            if chunk_text and len(chunk_text) > 20:
                chunk_id = str(uuid.uuid4())
                chunks.append({
                    "chunk_id": chunk_id,
                    "content": chunk_text,
                    "chunk_index": idx,
                    "page_number": 1,
                    "metadata": {"splitter": "langchain_recursive"}
                })
    else:
        # Fallback: paragraph-based chunking
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        current_chunk = ""
        chunk_index = 0
        
        for para in paragraphs:
            if len(current_chunk) + len(para) < chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk.strip() and len(current_chunk.strip()) > 20:
                    chunk_id = str(uuid.uuid4())
                    chunks.append({
                        "chunk_id": chunk_id,
                        "content": current_chunk.strip(),
                        "chunk_index": chunk_index,
                        "page_number": 1,
                        "metadata": {}
                    })
                    chunk_index += 1
                current_chunk = para + "\n\n"
        
        if current_chunk.strip() and len(current_chunk.strip()) > 20:
            chunk_id = str(uuid.uuid4())
            chunks.append({
                "chunk_id": chunk_id,
                "content": current_chunk.strip(),
                "chunk_index": chunk_index,
                "page_number": 1,
                "metadata": {}
            })
    
    return chunks


def clean_text(text: str) -> str:
    """Clean text by normalizing spacing."""
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def extract_sections(text: str, doc_id: str, chunks: List[Dict]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Extract sections with proper section_type categorization."""
    topics = []
    discovered_categories = set()
    seen_titles = set()  # Prevent duplicates
    
    # Standard section mappings
    standard_sections = {
        'abstract': ['abstract', 'summary', 'executive summary', 'overview'],
        'introduction': ['introduction', 'intro', 'background and introduction'],
        'background': ['background', 'related work', 'literature review', 'prior work', 'previous work'],
        'methodology': ['methodology', 'methods', 'approach', 'materials and methods', 
                       'experimental setup', 'experimental design', 'implementation'],
        'model': ['model', 'architecture', 'proposed method', 'our approach', 'system design'],
        'results': ['results', 'findings', 'experiments', 'evaluation', 'experimental results'],
        'discussion': ['discussion', 'analysis', 'interpretation', 'observations'],
        'conclusion': ['conclusion', 'conclusions', 'concluding remarks', 'future work', 'summary and conclusion'],
        'references': ['references', 'bibliography', 'citations', 'works cited'],
        'appendix': ['appendix', 'supplementary material', 'supplementary'],
        'acknowledgments': ['acknowledgments', 'acknowledgements'],
    }
    
    lines = text.split("\n")
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        # Skip empty/short lines
        if not line or len(line) < 3 or len(line) > 100:
            continue
        
        # Skip noise
        if is_noise_line(line):
            continue
        
        # Skip list items (starting with -, *, •)
        if line.startswith('-') or line.startswith('*') or line.startswith('•'):
            continue
        
        # Normalize for duplicate check
        norm_title = line.lower().strip()
        if norm_title in seen_titles:
            continue
        
        # Check if this is a heading
        section_type = None
        
        # 1. Check for standard section matches (only)
        section_type = detect_standard_section(line, standard_sections)
        
        # 2. Check for numbered section headings like "1. Introduction" or "2.1 Methods"
        # Only match if the text after the number is a standard section
        if not section_type:
            match = re.match(r'^(\d+(?:\.\d+)*\.?\s*)([A-Z][A-Za-z\s]+)$', line)
            if match:
                heading_text = match.group(2).strip()
                section_type = detect_standard_section(heading_text, standard_sections)
        
        # 3. Check for capitalized single-word standard headers only
        if not section_type and line.istitle() and len(line.split()) <= 3 and is_valid_heading(line):
            section_type = detect_standard_section(line, standard_sections)
        
        # 4. Check for ALL CAPS headers that match standard sections
        if not section_type and line.isupper() and len(line) < 50 and is_valid_heading(line):
            section_type = detect_standard_section(line, standard_sections)
        
        if section_type:
            seen_titles.add(norm_title)
            discovered_categories.add(section_type)
            
            # Get content preview
            content = get_section_content(lines, i, chunks)
            
            topic_id = str(uuid.uuid4())
            topics.append({
                "topic_id": topic_id,
                "title": line,
                "section_type": section_type,
                "start_page": 1,
                "end_page": 1,
                "level": 1 if section_type in standard_sections else 2,
                "chunk_ids": [c["chunk_id"] for c in chunks[:3]],  # Link to first few chunks
                "content": content
            })
            
            # Limit sections
            if len(topics) >= 25:
                break
    
    # If no sections found, create a default "content" section
    if not topics:
        topic_id = str(uuid.uuid4())
        content = chunks[0]["content"][:500] if chunks else text[:500]
        topics.append({
            "topic_id": topic_id,
            "title": "Document Content",
            "section_type": "content",
            "start_page": 1,
            "end_page": 1,
            "level": 1,
            "chunk_ids": [c["chunk_id"] for c in chunks],
            "content": content
        })
        discovered_categories.add("content")
    
    # Sort categories
    categories = sort_categories(list(discovered_categories))
    
    return topics, categories


def is_noise_line(line: str) -> bool:
    """Check if a line is noise."""
    # Skip lines that are mostly numbers
    digits = sum(c.isdigit() for c in line)
    if len(line) > 0 and digits / len(line) > 0.5:
        return True
    
    # Skip lines that look like coordinates
    if re.match(r'^[\d\s\.]+$', line):
        return True
    
    # Skip email/URLs
    if '@' in line or 'http' in line.lower() or 'www.' in line.lower():
        return True
    
    # Must have at least some letters
    letters = sum(c.isalpha() for c in line)
    if letters < 3:
        return True
    
    return False


def detect_standard_section(line: str, standard_sections: Dict) -> str:
    """Detect if line matches a standard section."""
    line_lower = line.lower().strip()
    
    # Remove leading numbers/punctuation
    clean_line = re.sub(r'^[\d\.\s]+', '', line_lower).strip()
    clean_line = re.sub(r'[:\.]$', '', clean_line).strip()
    
    for section_type, keywords in standard_sections.items():
        for keyword in keywords:
            if clean_line == keyword or clean_line.startswith(keyword + " "):
                return section_type
    
    return None


def is_valid_heading(text: str) -> bool:
    """Check if text is a valid heading."""
    if not text:
        return False
    
    # Should have mostly letters
    letters = sum(c.isalpha() for c in text)
    if letters < len(text) * 0.6:
        return False
    
    # Should not look like a sentence (no period in middle)
    if text.count('.') > 1 or (text.count('.') == 1 and not text.endswith('.')):
        return False
    
    return True


def normalize_category(text: str) -> str:
    """Normalize heading text to category name."""
    category = text.lower().strip()
    category = re.sub(r'[^\w\s]', '', category)
    category = ' '.join(category.split())
    
    if len(category) > 25:
        category = category[:25].rsplit(' ', 1)[0]
    
    return category


def get_section_content(lines: List[str], heading_index: int, chunks: List[Dict]) -> str:
    """Get content preview for a section."""
    # Get next few lines as content preview
    content_lines = []
    for j in range(heading_index + 1, min(heading_index + 6, len(lines))):
        line = lines[j].strip()
        if line and not is_noise_line(line):
            # Stop if we hit another heading
            if line.isupper() and len(line) < 50:
                break
            if re.match(r'^(\d+\.?\s*)?[A-Z][A-Za-z\s]+$', line) and len(line) < 50:
                break
            content_lines.append(line)
    
    content = " ".join(content_lines)
    
    # If no content from lines, get from chunks
    if not content and chunks:
        content = chunks[0]["content"][:500]
    
    return content[:500]


def sort_categories(categories: List[str]) -> List[str]:
    """Sort categories with standard ones first."""
    standard_order = [
        'abstract', 'introduction', 'background', 'related work',
        'methodology', 'methods', 'model', 'approach',
        'results', 'experiments', 'evaluation',
        'discussion', 'conclusion', 'references', 'appendix'
    ]
    
    sorted_cats = []
    remaining = set(categories)
    
    for std in standard_order:
        if std in remaining:
            sorted_cats.append(std)
            remaining.discard(std)
    
    sorted_cats.extend(sorted(remaining))
    
    return sorted_cats
