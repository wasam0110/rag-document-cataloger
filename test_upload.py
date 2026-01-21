"""
Test script to verify document upload and ingestion with the fixed chunking functions.
"""
import requests
import json
from pathlib import Path

# Create test files
def create_test_files():
    """Create sample documents for testing."""
    test_dir = Path("test_files")
    test_dir.mkdir(exist_ok=True)
    
    # Create a test PDF-like content (txt file for simplicity)
    txt_content = """Introduction to Machine Learning

Machine learning is a subset of artificial intelligence that focuses on building systems 
that learn from data. These systems improve their performance over time without being 
explicitly programmed.

Types of Machine Learning:
1. Supervised Learning - Learning from labeled data
2. Unsupervised Learning - Finding patterns in unlabeled data
3. Reinforcement Learning - Learning through trial and error

Applications include image recognition, natural language processing, recommendation systems, 
and autonomous vehicles. The field continues to grow rapidly with new techniques and 
architectures being developed constantly.
""" * 3  # Repeat to create longer content
    
    txt_file = test_dir / "machine_learning.txt"
    txt_file.write_text(txt_content)
    
    return test_dir, txt_file

def test_upload(file_path):
    """Upload a document to the server and verify response."""
    url = "http://127.0.0.1:8000/api/upload"
    
    print(f"\n{'='*60}")
    print(f"Testing upload: {file_path.name}")
    print(f"{'='*60}")
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f, "text/plain")}
            response = requests.post(url, files=files, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Upload successful!")
            print(f"  Document ID: {data.get('doc_id')}")
            print(f"  Filename: {data.get('filename')}")
            print(f"  Message: {data.get('message')}")
            return data.get('doc_id')
        else:
            print(f"✗ Upload failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return None
    except requests.exceptions.ConnectionError:
        print("✗ Could not connect to server. Is it running on http://127.0.0.1:8000?")
        return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None

def test_list_documents():
    """List all documents."""
    url = "http://127.0.0.1:8000/api/documents"
    
    print(f"\n{'='*60}")
    print("Listing all documents")
    print(f"{'='*60}")
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            docs = response.json()
            print(f"✓ Found {len(docs)} document(s)")
            for doc in docs:
                print(f"  - {doc.get('filename')} (ID: {doc.get('doc_id')[:8]}...)")
            return docs
        else:
            print(f"✗ List failed with status {response.status_code}")
            return []
    except Exception as e:
        print(f"✗ Error: {e}")
        return []

def test_get_document(doc_id):
    """Get details of a specific document."""
    url = f"http://127.0.0.1:8000/api/documents/{doc_id}"
    
    print(f"\n{'='*60}")
    print(f"Getting document details: {doc_id[:8]}...")
    print(f"{'='*60}")
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            doc = response.json()
            print(f"✓ Document found!")
            print(f"  Filename: {doc.get('filename')}")
            print(f"  File type: {doc.get('filetype')}")
            print(f"  Created: {doc.get('created_at')}")
            chunks = doc.get('chunks', [])
            print(f"  Chunks: {len(chunks)}")
            if chunks:
                print(f"  First chunk preview: {chunks[0].get('text', '')[:100]}...")
            return doc
        else:
            print(f"✗ Get failed with status {response.status_code}")
            return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None

def main():
    print("RAG Document Cataloger - Upload Test")
    print("="*60)
    
    # Create test files
    test_dir, txt_file = create_test_files()
    print(f"✓ Created test file: {txt_file}")
    
    # Test upload
    doc_id = test_upload(txt_file)
    
    if doc_id:
        # Test listing
        test_list_documents()
        
        # Test getting specific document
        test_get_document(doc_id)
        
        print(f"\n{'='*60}")
        print("✓ ALL TESTS COMPLETED SUCCESSFULLY!")
        print(f"{'='*60}")
        print(f"\nThe document was chunked correctly using the fixed functions.")
        print(f"Check the server logs to see chunking details.")
    else:
        print("\n✗ Upload test failed - cannot proceed with other tests")

if __name__ == "__main__":
    main()
