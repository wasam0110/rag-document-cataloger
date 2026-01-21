"""
Simple test script to verify the chunking functions work correctly.
"""
from typing import List, Dict, Any
from uuid import uuid4

# Mock the text splitter
class MockTextSplitter:
    def __init__(self, chunk_size=500, chunk_overlap=50, **kwargs):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def split_text(self, text: str) -> List[str]:
        """Simple chunking by character count."""
        if not text:
            return []
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            start = end - self.chunk_overlap
        return chunks

text_splitter = MockTextSplitter(chunk_size=500, chunk_overlap=50)


def create_chunks_from_pdf(content: List[str], doc_id: str) -> List[Dict[str, Any]]:
    """Convert PDF page texts to smaller chunks using the configured text splitter.

    Args:
        content: List of page texts (one entry per PDF page).
        doc_id: Document UUID used to construct item IDs.

    Returns:
        List of chunk dictionaries containing `item_id`, `page`, `section`, `text`, and character offsets.
    """
    chunks: List[Dict[str, Any]] = []
    chunk_counter = 0

    for page_num, page_text in enumerate(content):
        if not page_text or not page_text.strip():
            continue

        page_chunks = text_splitter.split_text(page_text)
        for chunk_text in page_chunks:
            if not chunk_text or not chunk_text.strip():
                continue

            chunks.append({
                "item_id": f"{doc_id}-chunk-{chunk_counter}",
                "page": page_num + 1,
                "section": f"Page {page_num + 1}",
                "text": chunk_text,
                "char_start": 0,
                "char_end": len(chunk_text)
            })
            chunk_counter += 1

    return chunks


def create_chunks_from_docx(content: Any, doc_id: str) -> List[Dict[str, Any]]:
    """Convert DOCX extractor output into chunks.

    The extractor may return a dict with `text` (list of paragraphs) and `headings`,
    or a simple list of paragraphs. This function handles both formats and
    uses the text splitter to produce smaller chunks while preserving heading info
    where reasonable.
    """
    chunks: List[Dict[str, Any]] = []
    chunk_counter = 0

    # Normalize paragraphs and headings
    if isinstance(content, dict):
        paragraphs = content.get("text", []) or []
        headings = content.get("headings", []) or []
    elif isinstance(content, list):
        paragraphs = content
        headings = []
    else:
        paragraphs = [str(content)]
        headings = []

    # Create a single full-text string to split into natural chunks
    full_text = "\n\n".join([p for p in paragraphs if p and p.strip()])
    text_chunks = text_splitter.split_text(full_text)

    for chunk_text in text_chunks:
        if not chunk_text or not chunk_text.strip():
            continue

        chunks.append({
            "item_id": f"{doc_id}-chunk-{chunk_counter}",
            "page": 1,
            "section": "Document Content",
            "text": chunk_text,
            "char_start": 0,
            "char_end": len(chunk_text)
        })
        chunk_counter += 1

    # Fallback: if no chunks produced, fall back to paragraph-level items
    if not chunks:
        for i, para in enumerate(paragraphs):
            if not para or not para.strip():
                continue
            chunks.append({
                "item_id": f"{doc_id}-para-{i}",
                "page": 1,
                "section": headings[i] if i < len(headings) else f"Paragraph {i + 1}",
                "text": para,
                "char_start": 0,
                "char_end": len(para)
            })

    return chunks


def create_chunks_from_csv(content: Dict[str, Any], doc_id: str) -> List[Dict[str, Any]]:
    """Convert CSV content to chunks."""
    table_text = str(content.get("data_json", ""))
    return [{
        "item_id": content.get("item_id", f"{doc_id}-table"),
        "page": 1,
        "section": "Table",
        "text": table_text,
        "char_start": 0,
        "char_end": len(table_text)
    }]


# Test cases
def test_pdf_chunking():
    print("Testing PDF chunking...")
    doc_id = str(uuid4())
    pdf_content = [
        "This is page 1 with some content. " * 50,  # Long text
        "This is page 2 with different content. " * 30,
        ""  # Empty page should be skipped
    ]
    
    chunks = create_chunks_from_pdf(pdf_content, doc_id)
    
    print(f"✓ Created {len(chunks)} chunks from 3 pages (1 empty)")
    assert len(chunks) > 0, "Should create at least one chunk"
    assert all("item_id" in c for c in chunks), "All chunks should have item_id"
    assert all("page" in c for c in chunks), "All chunks should have page number"
    assert all("text" in c for c in chunks), "All chunks should have text"
    assert chunks[0]["page"] == 1, "First chunk should be from page 1"
    print(f"  First chunk: {chunks[0]['item_id']}, page {chunks[0]['page']}, {len(chunks[0]['text'])} chars")
    

def test_docx_chunking_with_dict():
    print("\nTesting DOCX chunking (dict format)...")
    doc_id = str(uuid4())
    docx_content = {
        "text": [
            "Introduction paragraph. " * 40,
            "Body paragraph with more details. " * 40,
            "Conclusion paragraph. " * 40
        ],
        "headings": ["Intro", "Body", "Conclusion"]
    }
    
    chunks = create_chunks_from_docx(docx_content, doc_id)
    
    print(f"✓ Created {len(chunks)} chunks from dict with 3 paragraphs")
    assert len(chunks) > 0, "Should create at least one chunk"
    assert all("item_id" in c for c in chunks), "All chunks should have item_id"
    print(f"  First chunk: {chunks[0]['item_id']}, {len(chunks[0]['text'])} chars")


def test_docx_chunking_with_list():
    print("\nTesting DOCX chunking (list format)...")
    doc_id = str(uuid4())
    docx_content = [
        "First paragraph. " * 30,
        "Second paragraph. " * 30,
        "Third paragraph. " * 30
    ]
    
    chunks = create_chunks_from_docx(docx_content, doc_id)
    
    print(f"✓ Created {len(chunks)} chunks from list with 3 paragraphs")
    assert len(chunks) > 0, "Should create at least one chunk"
    print(f"  First chunk: {chunks[0]['item_id']}, {len(chunks[0]['text'])} chars")


def test_csv_chunking():
    print("\nTesting CSV chunking...")
    doc_id = str(uuid4())
    csv_content = {
        "data_json": '{"columns": ["Name", "Age"], "rows": [["Alice", 30], ["Bob", 25]]}',
        "item_id": f"{doc_id}-custom"
    }
    
    chunks = create_chunks_from_csv(csv_content, doc_id)
    
    print(f"✓ Created {len(chunks)} chunk from CSV data")
    assert len(chunks) == 1, "CSV should create exactly one chunk"
    assert chunks[0]["section"] == "Table", "CSV chunk should have Table section"
    assert chunks[0]["item_id"] == f"{doc_id}-custom", "Should use custom item_id"
    print(f"  Chunk: {chunks[0]['item_id']}, {len(chunks[0]['text'])} chars")


if __name__ == "__main__":
    print("=" * 60)
    print("Running chunking function tests")
    print("=" * 60)
    
    try:
        test_pdf_chunking()
        test_docx_chunking_with_dict()
        test_docx_chunking_with_list()
        test_csv_chunking()
        
        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
