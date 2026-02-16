"""Plain text extraction with semantic chunking and section detection.

Handles .txt files by:
  1. Reading the raw UTF-8 content.
  2. Splitting into semantically meaningful chunks (LangChain preferred).
  3. Detecting standard academic section headings (case-insensitive).
"""

import uuid
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple

from app.core.config import settings
from app.core.logging import logger

# LangChain splitter is optional; the fallback uses paragraph-based chunking
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False


async def extract_txt(file_path: Path, doc_id: str) -> Dict[str, Any]:
    """Extract content from a plain-text file.

    Returns a dict with: chunks, tables (always empty for .txt), topics,
    keywords, images, and categories.
    """
    # Initialize empty result; tables/images stay empty for plain text
    result = {
        "chunks": [],
        "tables": [],
        "topics": [],
        "keywords": [],
        "images": [],
        "categories": []
    }
    
    try:
        # Read the entire file with a lenient error policy
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
        
        # Step 1 – split text into overlapping chunks
        result["chunks"] = create_semantic_chunks(text, doc_id)
        
        # Step 2 – detect section headings and categorize them
        result["topics"], result["categories"] = extract_sections(text, doc_id, result["chunks"])
        
        logger.info(f"Extracted TXT: {len(result['chunks'])} chunks, {len(result['topics'])} sections in {len(result['categories'])} categories")
        
    except Exception as e:
        logger.error(f"TXT extraction error: {e}")
    
    return result


def create_semantic_chunks(text: str, doc_id: str) -> List[Dict[str, Any]]:
    """Split text into overlapping chunks for vector indexing.

    Uses LangChain's RecursiveCharacterTextSplitter when available;
    falls back to simple paragraph-based splitting otherwise.
    """
    chunks = []
    chunk_size = settings.chunk_size
    chunk_overlap = settings.chunk_overlap
    
    # Normalize whitespace before splitting
    text = clean_text(text)
    
    if HAS_LANGCHAIN:
        # Sentence-boundary-aware splitter – tries the coarsest separator
        # first (double newline) then falls through to finer ones.
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
            # Discard very short fragments that carry little meaning
            if chunk_text and len(chunk_text) > 20:
                chunk_id = str(uuid.uuid4())
                chunks.append({
                    "chunk_id": chunk_id,
                    "content": chunk_text,
                    "chunk_index": idx,
                    "page_number": 1,           # TXT files are treated as single-page
                    "metadata": {"splitter": "langchain_recursive"}
                })
    else:
        # ── Fallback: paragraph-based chunking ──────────────────────
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        current_chunk = ""
        chunk_index = 0
        
        for para in paragraphs:
            # Accumulate paragraphs until the chunk size limit is reached
            if len(current_chunk) + len(para) < chunk_size:
                current_chunk += para + "\n\n"
            else:
                # Flush the current chunk
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
                # Start a new chunk with the current paragraph
                current_chunk = para + "\n\n"
        
        # Flush the final accumulated chunk
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
    """Normalize whitespace: collapse runs of spaces and excessive blank lines."""
    text = re.sub(r' +', ' ', text)              # Multiple spaces → single space
    text = re.sub(r'\n{3,}', '\n\n', text)        # 3+ newlines → double newline
    return text.strip()


def extract_sections(text: str, doc_id: str, chunks: List[Dict]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Detect section headings in plain text and classify them.

    Scans every line and checks against a map of known academic section
    keywords.  Numbered headings (e.g. '2.1 Methods') and ALL-CAPS
    headings are also recognized.  Returns (topics_list, sorted_categories).
    """
    topics = []
    discovered_categories = set()
    seen_titles = set()  # Guard against duplicate headings
    
    # Map of canonical section types → keyword variants
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
        
        # Skip empty, too-short, or too-long lines
        if not line or len(line) < 3 or len(line) > 100:
            continue
        
        # Filter out noise (page numbers, URLs, coordinate-like strings)
        if is_noise_line(line):
            continue
        
        # Skip list items – they are content, not headings
        if line.startswith('-') or line.startswith('*') or line.startswith('•'):
            continue
        
        # Normalize for deduplication
        norm_title = line.lower().strip()
        if norm_title in seen_titles:
            continue
        
        section_type = None
        
        # Strategy 1: direct keyword match against standard sections
        section_type = detect_standard_section(line, standard_sections)
        
        # Strategy 2: numbered headings like '1. Introduction' or '2.1 Methods'
        if not section_type:
            match = re.match(r'^(\d+(?:\.\d+)*\.?\s*)([A-Z][A-Za-z\s]+)$', line)
            if match:
                heading_text = match.group(2).strip()
                section_type = detect_standard_section(heading_text, standard_sections)
        
        # Strategy 3: title-cased short lines (e.g. 'Introduction')
        if not section_type and line.istitle() and len(line.split()) <= 3 and is_valid_heading(line):
            section_type = detect_standard_section(line, standard_sections)
        
        # Strategy 4: ALL-CAPS headers (e.g. 'RESULTS')
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
            
            # Cap the number of detected sections to avoid noise
            if len(topics) >= 25:
                break
    
    # If nothing was detected, synthesize a single "content" section
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
    """Return True if the line is likely noise rather than heading text."""
    # More than half digits → probably a number string
    digits = sum(c.isdigit() for c in line)
    if len(line) > 0 and digits / len(line) > 0.5:
        return True
    
    # All digits / dots / spaces → coordinates or page numbers
    if re.match(r'^[\d\s\.]+$', line):
        return True
    
    # Email addresses or URLs are not headings
    if '@' in line or 'http' in line.lower() or 'www.' in line.lower():
        return True
    
    # Require at least 3 alphabetic characters
    letters = sum(c.isalpha() for c in line)
    if letters < 3:
        return True
    
    return False


def detect_standard_section(line: str, standard_sections: Dict) -> str:
    """Match a line against the standard-section keyword map.

    Strips leading numbering and trailing punctuation before comparison.
    Returns the section type key on match, else None.
    """
    line_lower = line.lower().strip()
    
    # Strip leading numbering (e.g. '3.1 ') and trailing colons / dots
    clean_line = re.sub(r'^[\d\.\s]+', '', line_lower).strip()
    clean_line = re.sub(r'[:\.]$', '', clean_line).strip()
    
    for section_type, keywords in standard_sections.items():
        for keyword in keywords:
            # Exact match or keyword prefix followed by a space
            if clean_line == keyword or clean_line.startswith(keyword + " "):
                return section_type
    
    return None


def is_valid_heading(text: str) -> bool:
    """Return True if text is structurally plausible as a heading.

    Headings should be mostly alphabetic and not look like a sentence.
    """
    if not text:
        return False
    
    # Require at least 60 % letters
    letters = sum(c.isalpha() for c in text)
    if letters < len(text) * 0.6:
        return False
    
    # Reject sentence-like text (period in the middle)
    if text.count('.') > 1 or (text.count('.') == 1 and not text.endswith('.')):
        return False
    
    return True


def normalize_category(text: str) -> str:
    """Convert heading text to a short, lowercase, punctuation-free label."""
    category = text.lower().strip()
    category = re.sub(r'[^\w\s]', '', category)   # Drop punctuation
    category = ' '.join(category.split())          # Normalize whitespace
    
    # Truncate at a word boundary to keep the label readable
    if len(category) > 25:
        category = category[:25].rsplit(' ', 1)[0]
    
    return category


def get_section_content(lines: List[str], heading_index: int, chunks: List[Dict]) -> str:
    """Return a ~500-char content preview starting just below the heading.

    Reads up to 5 non-noise lines after the heading, stopping early if
    another heading is encountered.  Falls back to the first chunk.
    """
    content_lines = []
    for j in range(heading_index + 1, min(heading_index + 6, len(lines))):
        line = lines[j].strip()
        if line and not is_noise_line(line):
            # Stop if we hit what looks like the next heading
            if line.isupper() and len(line) < 50:
                break
            if re.match(r'^(\d+\.?\s*)?[A-Z][A-Za-z\s]+$', line) and len(line) < 50:
                break
            content_lines.append(line)
    
    content = " ".join(content_lines)
    
    # Fallback: use the beginning of the first chunk
    if not content and chunks:
        content = chunks[0]["content"][:500]
    
    return content[:500]


def sort_categories(categories: List[str]) -> List[str]:
    """Sort categories with standard academic sections first, then alphabetical."""
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
