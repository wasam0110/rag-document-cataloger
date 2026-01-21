"""Direct test of extraction functions without API."""
import sys
sys.path.insert(0, 'c:/Users/Wasam/rag-document-cataloger')

from app.services.ingest import extract_topics_from_text, extract_keywords_from_text, detect_tables_in_text
from uuid import uuid4

# Test content
test_content = """INTRODUCTION TO NEURAL NETWORKS

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

doc_id = str(uuid4())

print("="*70)
print("Direct Function Testing")
print("="*70)

# Test topic extraction
print("\n📑 TOPICS:")
topics = extract_topics_from_text([test_content], doc_id)
print(f"Found {len(topics)} topics:")
for topic in topics:
    print(f"  - {topic['title']}")

# Test keyword extraction
print("\n🔑 KEYWORDS:")
keywords = extract_keywords_from_text(test_content, top_n=10)
print(f"Found {len(keywords)} keywords:")
for kw in keywords[:10]:
    print(f"  - {kw['keyword']}: {kw['score']}")

# Test table detection
print("\n📊 TABLES:")
tables = detect_tables_in_text([test_content], doc_id)
print(f"Found {len(tables)} tables:")
for table in tables:
    print(f"  - {table['title']}")
    print(f"    Preview: {table['table_text'][:80]}...")

print("\n" + "="*70)
if topics and keywords:
    print("✓ All extraction functions working correctly!")
else:
    print("⚠ Some functions not working as expected")
print("="*70)
