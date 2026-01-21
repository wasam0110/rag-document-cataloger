"""Standalone test of extraction logic."""
import re
from collections import Counter
from uuid import uuid4

# Copy extraction functions here to test independently
def extract_topics_from_text(content, doc_id):
    """Extract topics/sections from document pages by detecting headings."""
    topics = []
    topic_counter = 0
    
    # Common heading patterns
    heading_patterns = [
        r'^(?:[A-Z][A-Z\s]{2,}|\d+\.?\s+[A-Z][A-Za-z\s]+)$',
        r'^(?:Abstract|Introduction|Conclusion|References|Appendix|Background|Methods|Results|Discussion)',
        r'^(?:Chapter|Section|Part)\s+\d+',
    ]
    
    for page_num, page_text in enumerate(content):
        lines = page_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line or len(line) > 100:
                continue
            
            for pattern in heading_patterns:
                if re.match(pattern, line, re.IGNORECASE):
                    topics.append({
                        "topic_id": f"{doc_id}-topic-{topic_counter}",
                        "title": line,
                        "start_page": page_num + 1,
                        "end_page": page_num + 1,
                        "item_ids": []
                    })
                    topic_counter += 1
                    break
    
    return topics


def extract_keywords_from_text(content, top_n=10):
    """Extract keywords using simple TF-IDF-like scoring."""
    stop_words = set([
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those', 'it'
    ])
    
    words = re.findall(r'\b[a-z]{3,}\b', content.lower())
    filtered_words = [w for w in words if w not in stop_words]
    
    word_counts = Counter(filtered_words)
    
    total_words = len(filtered_words) if filtered_words else 1
    keywords = []
    for word, count in word_counts.most_common(top_n):
        keywords.append({
            "keyword": word,
            "score": round(count / total_words, 4)
        })
    
    return keywords


def detect_tables_in_text(content, doc_id):
    """Detect potential tables in text by looking for tabular patterns."""
    tables = []
    table_counter = 0
    
    for page_num, page_text in enumerate(content):
        lines = page_text.split('\n')
        
        for i, line in enumerate(lines):
            if '\t' in line or re.search(r'\s{3,}', line):
                table_lines = []
                j = i
                while j < len(lines) and j < i + 10:
                    if '\t' in lines[j] or re.search(r'\s{3,}', lines[j]):
                        table_lines.append(lines[j])
                        j += 1
                    else:
                        break
                
                if len(table_lines) >= 2:
                    tables.append({
                        "item_id": f"{doc_id}-table-{table_counter}",
                        "page": page_num + 1,
                        "title": f"Table {table_counter + 1}",
                        "data_json": {},
                        "table_text": '\n'.join(table_lines[:5]),
                        "confidence": 0.7
                    })
                    table_counter += 1
    
    return tables


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
print("Standalone Extraction Function Testing")
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
    if table['table_text']:
        lines = table['table_text'].split('\n')
        for line in lines[:3]:
            print(f"    {line}")

print("\n" + "="*70)
if topics and keywords and tables:
    print("✓ ALL EXTRACTION FUNCTIONS WORKING!")
    print(f"  Topics: {len(topics)}, Keywords: {len(keywords)}, Tables: {len(tables)}")
else:
    print(f"Status: Topics={len(topics)}, Keywords={len(keywords)}, Tables={len(tables)}")
print("="*70)
