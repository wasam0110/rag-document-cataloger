"""Enhanced test to verify topic, keyword, and table extraction."""
import requests

def test_enhanced_upload():
    """Upload a document and check if topics, keywords, and tables are extracted."""
    
    # Create a sample text file with clear structure
    content = """INTRODUCTION TO NEURAL NETWORKS

Neural networks are computational models inspired by biological neural networks.
They consist of interconnected nodes called neurons that process information.

ARCHITECTURE AND DESIGN

The architecture of a neural network includes input layer, hidden layers, and output layer.
Each layer contains multiple neurons that transform the input data using activation functions.

Training Process

Training involves forward propagation, loss calculation, and backpropagation.
The network learns by adjusting weights through gradient descent optimization.

Key Concepts:
    Model         Accuracy    F1-Score
    CNN           0.95        0.94
    RNN           0.88        0.87
    Transformer   0.97        0.96

APPLICATIONS AND USE CASES

Neural networks power many modern applications including image recognition,
natural language processing, speech synthesis, and autonomous vehicles.
The field continues to evolve with new architectures and techniques.

CONCLUSION

Neural networks represent a powerful approach to machine learning problems.
Their ability to learn complex patterns makes them invaluable for AI applications.
"""
    
    # Save to file
    test_file = "test_files/neural_networks_enhanced.txt"
    with open(test_file, "w") as f:
        f.write(content)
    
    print("="*70)
    print("Testing Enhanced Document Ingestion")
    print("="*70)
    
    # Upload the file
    url = "http://127.0.0.1:8000/api/upload"
    with open(test_file, "rb") as f:
        files = {"file": ("neural_networks_enhanced.txt", f, "text/plain")}
        response = requests.post(url, files=files, timeout=30)
    
    if response.status_code != 200:
        print(f"✗ Upload failed: {response.text}")
        return
    
    data = response.json()
    doc_id = data.get('doc_id')
    print(f"✓ Document uploaded: {doc_id}\n")
    
    # Get document details
    url = f"http://127.0.0.1:8000/api/documents/{doc_id}"
    response = requests.get(url, timeout=10)
    
    if response.status_code != 200:
        print(f"✗ Failed to get document: {response.text}")
        return
    
    doc = response.json()
    
    # Display results
    print(f"📄 Filename: {doc.get('filename')}")
    print(f"📅 Created: {doc.get('created_at')}")
    print(f"\n📚 CHUNKS: {len(doc.get('chunks', []))}")
    if doc.get('chunks'):
        print(f"   First chunk: {doc['chunks'][0].get('text', '')[:80]}...")
    
    print(f"\n📑 TOPICS: {len(doc.get('topics', []))}")
    for topic in doc.get('topics', []):
        print(f"   - {topic.get('title')} (Page {topic.get('start_page')})")
    
    print(f"\n🔑 KEYWORDS: {len(doc.get('keywords', []))}")
    for kw in doc.get('keywords', [])[:5]:  # Show top 5
        print(f"   - {kw.get('keyword')} (score: {kw.get('score')})")
    
    print(f"\n📊 TABLES: {len(doc.get('tables', []))}")
    for table in doc.get('tables', []):
        print(f"   - {table.get('title')} on Page {table.get('page')}")
        if table.get('table_text'):
            print(f"     Preview: {table.get('table_text')[:60]}...")
    
    print("\n" + "="*70)
    print("✓ Enhanced extraction completed!")
    print("="*70)
    
    # Summary
    topics_count = len(doc.get('topics', []))
    keywords_count = len(doc.get('keywords', []))
    tables_count = len(doc.get('tables', []))
    chunks_count = len(doc.get('chunks', []))
    
    print(f"\n📊 Summary:")
    print(f"   Chunks: {chunks_count}")
    print(f"   Topics: {topics_count}")
    print(f"   Keywords: {keywords_count}")
    print(f"   Tables: {tables_count}")
    
    if topics_count > 0 and keywords_count > 0:
        print("\n✓ SUCCESS: Topics and keywords extracted correctly!")
    else:
        print("\n⚠ WARNING: Some features may not be working")

if __name__ == "__main__":
    test_enhanced_upload()
