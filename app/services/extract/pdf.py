"""
PDF extraction with semantic chunking and intelligent section detection.

Uses pdfplumber for text / table extraction and PIL for table image rendering.
When LangChain's RecursiveCharacterTextSplitter is available it is used for
semantic-aware chunking; otherwise a basic sentence-based fallback is used.

Pipeline:
  1. Iterate over each PDF page – extract images, text, and tables.
  2. Chunk the full text using sentence-boundary-aware splitting.
  3. Detect section headings with strict validation to avoid noise.
"""

import uuid
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple
import pdfplumber
from PIL import Image

from app.core.config import settings
from app.core.logging import logger

# LangChain's text splitter is optional – fall back to basic chunking if absent
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    HAS_LANGCHAIN = True
except ImportError:
    HAS_LANGCHAIN = False
    logger.warning("langchain_text_splitters not available, using basic chunking")


async def extract_pdf(file_path: Path, doc_id: str) -> Dict[str, Any]:
    """Extract content from a PDF with intelligent section detection.

    Returns a dict with keys: chunks, tables, topics, keywords, images, categories.
    """
    logger.info(f"Starting PDF extraction for {file_path.name}")
    # Initialize the result container with empty lists for each artifact type
    result = {
        "chunks": [],
        "tables": [],
        "topics": [],
        "keywords": [],
        "images": [],
        "categories": []
    }
    
    try:
        with pdfplumber.open(file_path) as pdf:
            logger.info(f"PDF opened: {len(pdf.pages)} pages")
            all_text = ""        # Accumulate full document text
            page_texts = []      # Per-page text for chunking
            
            for page_num, page in enumerate(pdf.pages, start=1):
                # ── Extract embedded image metadata from the page ───
                try:
                    for img_idx, img_obj in enumerate(page.images):
                        image_id = str(uuid.uuid4())
                        result["images"].append({
                            "image_id": image_id,
                            "page_number": page_num,
                            "image_index": img_idx,
                            "bbox": [img_obj.get("x0"), img_obj.get("top"), 
                                    img_obj.get("x1"), img_obj.get("bottom")],
                            "width": img_obj.get("width"),
                            "height": img_obj.get("height")
                        })
                except Exception as e:
                    logger.warning(f"Image extraction failed on page {page_num}: {e}")
                
                # ── Extract the page’s plain text ──────────────────────
                page_text = page.extract_text() or ""
                page_texts.append({"page_num": page_num, "text": page_text})
                all_text += page_text + "\n\n"  # Separate pages with blank line
                
                # ── Detect and extract tables from the page ───────────
                tables = extract_tables_from_page(page, doc_id, page_num)
                result["tables"].extend(tables)
            
            # ── Create semantically meaningful chunks from page texts ─
            result["chunks"] = create_semantic_chunks(page_texts, doc_id)
            
            # ── Detect section headings and classify them ─────────────
            result["topics"], result["categories"] = extract_validated_sections(
                page_texts, doc_id, result["chunks"]
            )
        
        logger.info(f"Extracted: {len(result['chunks'])} chunks, {len(result['tables'])} tables, "
                   f"{len(result['topics'])} sections")
        
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        import traceback
        traceback.print_exc()
    
    return result


def extract_tables_from_page(page, doc_id: str, page_num: int) -> List[Dict]:
    """Detect and extract tables from a single PDF page.

    Uses pdfplumber’s line-based strategy first; falls back to the
    default strategy if no tables are found.  Each valid table gets a
    markdown text representation and optional PNG images (full + thumbnail).
    """
    tables = []
    
    try:
        # Configure extraction: prefer line-based detection (more accurate)
        table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "snap_tolerance": 3,   # Pixel tolerance for aligning lines
            "join_tolerance": 3,   # Pixel tolerance for merging close lines
        }
        
        # First attempt with explicit line strategy
        extracted = page.extract_tables(table_settings)
        if not extracted:
            # Fallback to default (text-based) strategy
            extracted = page.extract_tables()
        
        if extracted:
            for table_idx, table_data in enumerate(extracted):
                # Skip tables with fewer than 2 rows (header + at least one data row)
                if not table_data or len(table_data) < 2:
                    continue
                
                # Remove rows that are entirely empty / whitespace
                valid_rows = [row for row in table_data 
                             if any(cell and str(cell).strip() for cell in row)]
                if len(valid_rows) < 2:
                    continue
                
                table_id = str(uuid.uuid4())
                # Render the table as a markdown-formatted string
                table_text = format_table_markdown(valid_rows)
                
                # Render the full page as a PNG and create a thumbnail
                table_images = save_table_image(page, doc_id, table_id, page_num)
                
                tables.append({
                    "table_id": table_id,
                    "page_number": page_num,
                    "table_index": table_idx,
                    "table_text": table_text,
                    "rows_count": len(valid_rows),
                    "cols_count": len(valid_rows[0]) if valid_rows else 0,
                    "confidence": 0.9,
                    "bbox": None,
                    "full_image_path": table_images.get("full_image_path"),
                    "preview_image_path": table_images.get("preview_image_path")
                })
    except Exception as e:
        logger.warning(f"Table extraction error on page {page_num}: {e}")
    
    return tables


def format_table_markdown(table_data: List[List[str]]) -> str:
    """Convert a 2-D list of cells into a GitHub-flavoured Markdown table.

    The first row is treated as the header; a separator row of '---' is
    inserted automatically.  Short data rows are padded to match the
    header width.
    """
    if not table_data:
        return ""
    
    lines = []
    header = [str(cell or "").strip() for cell in table_data[0]]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    
    for row in table_data[1:]:
        row_str = [str(cell or "").strip() for cell in row]
        while len(row_str) < len(header):
            row_str.append("")
        lines.append("| " + " | ".join(row_str[:len(header)]) + " |")
    
    return "\n".join(lines)


def save_table_image(page, doc_id: str, table_id: str, page_num: int) -> Dict[str, str]:
    """Render the PDF page as a PNG and create a thumbnail for the table.

    Both images are saved under ``data/table_images/<doc_id>/`` and their
    relative paths are returned for storage in the DB.
    """
    result = {"full_image_path": None, "preview_image_path": None}
    
    try:
        # Create a per-document subdirectory for table images
        table_dir = settings.data_dir / "table_images" / doc_id
        table_dir.mkdir(parents=True, exist_ok=True)
        
        # Render the page to a PIL Image at 150 DPI
        img = page.to_image(resolution=150)
        pil_img = img.original  # Access the underlying PIL.Image
        
        # Save full-resolution image
        full_path = table_dir / f"{table_id}_full.png"
        pil_img.save(full_path)
        result["full_image_path"] = f"table_images/{doc_id}/{table_id}_full.png"
        
        # Create a 300px-wide thumbnail preserving aspect ratio
        width, height = pil_img.size
        thumb_width = 300
        thumb_height = int((thumb_width / width) * height)
        thumbnail = pil_img.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        
        preview_path = table_dir / f"{table_id}_thumbnail.png"
        thumbnail.save(preview_path)
        result["preview_image_path"] = f"table_images/{doc_id}/{table_id}_thumbnail.png"
    except Exception as e:
        logger.warning(f"Could not save table image: {e}")
    
    return result


def create_semantic_chunks(page_texts: List[Dict], doc_id: str) -> List[Dict[str, Any]]:
    """Split page texts into semantically meaningful chunks.

    Prefers LangChain’s RecursiveCharacterTextSplitter which splits at
    natural boundaries (paragraphs → sentences → words) and preserves
    overlap between consecutive chunks for context continuity.
    Falls back to a simpler sentence-based splitter if LangChain is absent.
    """
    chunks = []
    chunk_size = settings.chunk_size
    chunk_overlap = settings.chunk_overlap
    
    if HAS_LANGCHAIN:
        # Configure the splitter with a hierarchy of separators.
        # It tries the first separator; if the resulting pieces are still
        # too large, it falls through to finer-grained separators.
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n",      # Paragraph breaks
                "\n",        # Line breaks  
                ". ",        # Sentence ends
                "? ",        # Questions
                "! ",        # Exclamations
                "; ",        # Semicolons
                ", ",        # Commas
                " ",         # Words
                ""           # Characters
            ],
            length_function=len,
            is_separator_regex=False,
        )
        
        chunk_index = 0
        for page_info in page_texts:
            page_num = page_info["page_num"]
            text = page_info["text"]
            
            if not text or not text.strip():
                continue
            
            # Remove PDF artifacts (multiple spaces, stray page numbers, etc.)
            text = clean_text(text)
            
            page_chunks = text_splitter.split_text(text)
            
            for chunk_text in page_chunks:
                chunk_text = chunk_text.strip()
                # Discard very short chunks – they rarely carry useful meaning
                if chunk_text and len(chunk_text) > 20:
                    chunk_id = str(uuid.uuid4())
                    chunks.append({
                        "chunk_id": chunk_id,
                        "content": chunk_text,
                        "chunk_index": chunk_index,
                        "page_number": page_num,
                        "metadata": {"splitter": "langchain_recursive"}
                    })
                    chunk_index += 1
    else:
        # Fallback: sentence-based chunking
        chunks = fallback_sentence_chunking(page_texts, doc_id, chunk_size, chunk_overlap)
    
    logger.info(f"Created {len(chunks)} semantic chunks")
    return chunks


def clean_text(text: str) -> str:
    """Remove common PDF artifacts and normalize whitespace."""
    text = re.sub(r' +', ' ', text)                        # Collapse multiple spaces
    text = re.sub(r'\n{3,}', '\n\n', text)                 # Limit consecutive newlines to 2
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)  # Strip standalone page numbers
    return text.strip()


def fallback_sentence_chunking(page_texts: List[Dict], doc_id: str, 
                               chunk_size: int, chunk_overlap: int) -> List[Dict]:
    """Sentence-based chunking fallback when LangChain is not installed.

    Splits text at sentence-ending punctuation, accumulates sentences
    until ``chunk_size`` is reached, then starts a new chunk with an
    overlap of approximately 20 words from the previous chunk.
    """
    chunks = []
    chunk_index = 0
    
    for page_info in page_texts:
        page_num = page_info["page_num"]
        text = clean_text(page_info["text"])
        
        if not text:
            continue
        
        # Split by sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) < chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk.strip():
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
                words = current_chunk.split()
                overlap_words = words[-min(20, len(words)):]
                current_chunk = " ".join(overlap_words) + " " + sentence + " "
        
        if current_chunk.strip():
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


def extract_validated_sections(
    page_texts: List[Dict], 
    doc_id: str, 
    chunks: List[Dict]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Detect section headings with STRICT validation to avoid noise.

    Only text lines that closely match known academic headings or follow
    a numbered-heading pattern (e.g. '2.1 Methods') are accepted.
    Returns a tuple of (topics_list, sorted_categories).
    """
    topics = []
    discovered_categories = set()
    
    # Map of canonical section types → keyword variants used to match them
    standard_sections = {
        'abstract': ['abstract', 'summary', 'executive summary'],
        'introduction': ['introduction', 'overview', 'background'],
        'related work': ['related work', 'literature review', 'prior work'],
        'methodology': ['methodology', 'methods', 'approach', 'materials and methods', 
                       'experimental setup', 'experimental design'],
        'model': ['model', 'architecture', 'proposed method', 'our approach'],
        'results': ['results', 'findings', 'experiments', 'evaluation', 'experimental results'],
        'discussion': ['discussion', 'analysis', 'interpretation'],
        'conclusion': ['conclusion', 'conclusions', 'concluding remarks', 'future work'],
        'references': ['references', 'bibliography', 'citations'],
        'appendix': ['appendix', 'supplementary material', 'supplementary'],
        'acknowledgments': ['acknowledgments', 'acknowledgements'],
    }
    
    # Collect all lines
    all_lines = []
    for pt in page_texts:
        page_num = pt["page_num"]
        for line in pt["text"].split("\n"):
            line = line.strip()
            if line:
                all_lines.append({"text": line, "page": page_num})
    
    for line_info in all_lines:
        line = line_info["text"]
        page_num = line_info["page"]
        
        # Skip if line is too short or too long
        if len(line) < 4 or len(line) > 80:
            continue
        
        # Skip lines that look like noise (numbers, coordinates, etc.)
        if is_noise_line(line):
            continue
        
        # Check for standard sections
        section_type = detect_standard_section(line, standard_sections)
        
        if section_type:
            # Found a standard section
            discovered_categories.add(section_type)
            
            content = get_section_content(chunks, page_num, line)
            chunk_ids = [c["chunk_id"] for c in chunks if c.get("page_number") == page_num]
            
            topic_id = str(uuid.uuid4())
            topics.append({
                "topic_id": topic_id,
                "title": line,
                "section_type": section_type,
                "start_page": page_num,
                "end_page": page_num,
                "level": 1,
                "chunk_ids": chunk_ids,
                "content": content
            })
        
        # Check for numbered sections like "1 Introduction" or "2.1 Related Work"
        elif is_numbered_heading(line):
            heading_text = extract_heading_text(line)
            if heading_text and is_valid_heading(heading_text):
                # Check if it maps to a standard section
                section_type = detect_standard_section(heading_text, standard_sections)
                if not section_type:
                    # Try AI-powered categorization as fallback
                    try:
                        from app.services.llm import categorize_heading
                        section_type = categorize_heading(heading_text)
                    except Exception as e:
                        logger.warning(f"LLM categorization failed: {e}, using fallback")
                        section_type = normalize_category(heading_text)
                
                discovered_categories.add(section_type)
                
                content = get_section_content(chunks, page_num, line)
                chunk_ids = [c["chunk_id"] for c in chunks if c.get("page_number") == page_num]
                
                topic_id = str(uuid.uuid4())
                topics.append({
                    "topic_id": topic_id,
                    "title": line,
                    "section_type": section_type,
                    "start_page": page_num,
                    "end_page": page_num,
                    "level": 2,
                    "chunk_ids": chunk_ids,
                    "content": content
                })
        
        # Limit sections
        if len(topics) >= 30:
            break
    
    # If no sections found, create page-based sections
    if not topics:
        topics, discovered_categories = create_page_sections(chunks, doc_id)
    
    # Ensure at least 'content' category
    if not discovered_categories:
        discovered_categories = {"content"}
    
    # Sort categories with standard ones first
    categories = sort_categories(list(discovered_categories))
    
    logger.info(f"Found {len(topics)} sections in {len(categories)} categories")
    return topics, categories


def is_noise_line(line: str) -> bool:
    """Heuristically determine if a line is noise (page numbers, coordinates, etc.).

    A line is considered noise when it is predominantly digits, matches
    common non-heading patterns, or lacks enough alphabetic characters.
    """
    # Skip lines that are mostly numbers
    digits = sum(c.isdigit() for c in line)
    if len(line) > 0 and digits / len(line) > 0.5:
        return True
    
    # Skip lines that look like coordinates or dimensions
    if re.match(r'^[\d\s\.]+$', line):
        return True
    
    # Skip lines that look like figure/table captions with just numbers
    if re.match(r'^(fig|figure|table|tab)?\s*[\d\.\s]+$', line.lower()):
        return True
    
    # Skip lines that are just special characters
    if re.match(r'^[\W\d\s]+$', line):
        return True
    
    # Skip email addresses and URLs
    if '@' in line or 'http' in line.lower() or 'www.' in line.lower():
        return True
    
    # Skip lines that look like page numbers
    if re.match(r'^\d{1,3}$', line.strip()):
        return True
    
    # Must have at least some letters
    letters = sum(c.isalpha() for c in line)
    if letters < 3:
        return True
    
    return False


def detect_standard_section(line: str, standard_sections: Dict) -> str:
    """Match a text line against the standard section keyword map.

    Leading numbers / punctuation are stripped before comparison so that
    headings like '3. Results' still match 'results'.
    """
    line_lower = line.lower().strip()
    
    # Remove leading numbers/punctuation for matching
    clean_line = re.sub(r'^[\d\.\s]+', '', line_lower).strip()
    clean_line = re.sub(r'[:\.]$', '', clean_line).strip()
    
    for section_type, keywords in standard_sections.items():
        for keyword in keywords:
            if clean_line == keyword or clean_line.startswith(keyword + " "):
                return section_type
    
    return None


def is_numbered_heading(line: str) -> bool:
    """Return True if the line follows a numbered heading pattern (e.g. '1 Introduction', '2.1 Methods')."""
    pattern = r'^(\d+(?:\.\d+)*)\s+([A-Za-z].+)$'
    return bool(re.match(pattern, line))


def extract_heading_text(line: str) -> str:
    """Strip the leading number from a numbered heading and return the text portion."""
    match = re.match(r'^(\d+(?:\.\d+)*)\s+(.+)$', line)
    if match:
        return match.group(2).strip()
    return line


def is_valid_heading(text: str) -> bool:
    """Check whether extracted heading text looks like a real section title.

    Rejects text that doesn’t start with a capital letter, is too long,
    or contains too many non-letter characters.
    """
    # Must start with capital letter
    if not text or not text[0].isupper():
        return False
    
    # Should not be too long
    if len(text) > 60:
        return False
    
    # Should have mostly letters
    letters = sum(c.isalpha() for c in text)
    if letters < len(text) * 0.6:
        return False
    
    # Should not look like a sentence (no periods except at end)
    if text.count('.') > 1:
        return False
    
    return True


def normalize_category(text: str) -> str:
    """Convert heading text to a short, lowercase, punctuation-free category label."""
    category = text.lower().strip()
    category = re.sub(r'[^\w\s]', '', category)   # Remove punctuation
    category = ' '.join(category.split())          # Normalize whitespace
    if len(category) > 25:
        # Truncate at a word boundary to keep the label readable
        category = category[:25].rsplit(' ', 1)[0]
    return category


def get_section_content(chunks: List[Dict], page_num: int, heading: str) -> str:
    """Return a ~500-char content preview for a section.

    Tries to locate the heading within a chunk on the same page and
    returns the text immediately after it.  Falls back to the start
    of the first chunk on that page.
    """
    for chunk in chunks:
        if chunk.get("page_number") == page_num:
            content = chunk.get("content", "")
            # Try to find content after the heading
            if heading.lower() in content.lower():
                idx = content.lower().find(heading.lower())
                return content[idx + len(heading):].strip()[:500]
            return content[:500]
    return ""


def create_page_sections(chunks: List[Dict], doc_id: str) -> Tuple[List[Dict], set]:
    """Fallback: create one topic per page when no real headings are found.

    The first meaningful sentence on each page is used as the topic title.
    """
    topics = []
    categories = set()
    
    pages = {}
    for chunk in chunks:
        page = chunk.get("page_number", 1)
        if page not in pages:
            pages[page] = []
        pages[page].append(chunk)
    
    for page_num in sorted(pages.keys()):
        page_chunks = pages[page_num]
        
        # Get meaningful title from content
        content = ""
        title = f"Page {page_num}"
        
        for chunk in page_chunks:
            text = chunk.get("content", "")
            if text:
                # Try to get first meaningful sentence
                sentences = re.split(r'[.!?]\s+', text)
                for sent in sentences:
                    sent = sent.strip()
                    if 15 < len(sent) < 80 and sent[0].isupper():
                        title = sent
                        break
                content = text[:500]
                break
        
        category = f"page {page_num}"
        categories.add(category)
        
        topic_id = str(uuid.uuid4())
        topics.append({
            "topic_id": topic_id,
            "title": title,
            "section_type": category,
            "start_page": page_num,
            "end_page": page_num,
            "level": 2,
            "chunk_ids": [c["chunk_id"] for c in page_chunks],
            "content": content
        })
    
    return topics, categories


def sort_categories(categories: List[str]) -> List[str]:
    """Sort category labels with standard academic sections first, then alphabetical."""
    standard_order = [
        'abstract', 'introduction', 'related work', 'background',
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
    
    # Add remaining sorted alphabetically
    sorted_cats.extend(sorted(remaining))
    
    return sorted_cats
