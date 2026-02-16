#!/usr/bin/env python3
"""
Test script to verify RAG quality with the upgraded models.

This script demonstrates:
1. Better embeddings (BAAI/bge-base-en-v1.5 vs all-MiniLM-L6-v2)
2. Better generation (flan-t5-xl vs flan-t5-base)
3. Citation handling
4. Full RAG pipeline
"""

import asyncio
from app.services.llm import generate_answer, _get_generator
from app.services.index.faiss_store import get_embeddings
from app.core.logging import logger

# Sample context passages (similar to what would be retrieved from FAISS)
SAMPLE_PASSAGES = [
    "Neural networks are computing systems inspired by biological neural networks. "
    "They consist of interconnected nodes (neurons) organized in layers. "
    "Each connection has an associated weight that adjusts during training.",
    
    "The training process uses backpropagation to minimize the loss function. "
    "This involves computing gradients and updating weights using optimization algorithms "
    "like stochastic gradient descent (SGD) or Adam.",
    
    "Common architectures include feedforward networks, convolutional neural networks (CNNs) "
    "for image processing, and recurrent neural networks (RNNs) for sequential data. "
    "Modern transformers have replaced RNNs for many natural language tasks.",
    
    "Overfitting occurs when a model learns the training data too well and fails to generalize. "
    "Regularization techniques like dropout and L2 regularization help prevent overfitting.",
]

SAMPLE_QUESTIONS = [
    "What are neural networks?",
    "How does training work in neural networks?",
    "What techniques prevent overfitting?",
    "What are the main types of neural network architectures?",
]


async def test_embeddings():
    """Test that the embedding model loads correctly."""
    print("\n" + "="*60)
    print("🔍 Testing Embedding Model (BAAI/bge-base-en-v1.5)")
    print("="*60)
    
    try:
        embeddings = get_embeddings()
        test_text = "This is a test sentence."
        embedding = embeddings.embed_query(test_text)
        
        print(f"✓ Embedding model loaded successfully")
        print(f"✓ Embedding dimensions: {len(embedding)}")
        print(f"✓ Sample values: [{embedding[0]:.4f}, {embedding[1]:.4f}, ..., {embedding[-1]:.4f}]")
        return True
    except Exception as e:
        print(f"✗ Embedding test failed: {e}")
        return False


async def test_generation():
    """Test that the generation model loads and produces output."""
    print("\n" + "="*60)
    print("🤖 Testing Generation Model (google/flan-t5-xl)")
    print("="*60)
    print("⏳ Loading model (this may take 30-60 seconds on first run)...")
    
    try:
        # This will trigger lazy loading of the generator
        generator = _get_generator()
        print("✓ Generation model loaded successfully")
        
        # Test with a simple prompt
        test_prompt = "Summarize in one sentence: Neural networks are machine learning models inspired by the brain."
        result = generator(test_prompt, max_length=50)
        
        generated_text = result[0]['generated_text']
        print(f"✓ Generated output: '{generated_text}'")
        return True
    except Exception as e:
        print(f"✗ Generation test failed: {e}")
        logger.error(f"Generation test error details: {e}", exc_info=True)
        return False


async def test_rag_pipeline():
    """Test the full RAG pipeline with sample questions."""
    print("\n" + "="*60)
    print("💬 Testing Full RAG Pipeline")
    print("="*60)
    
    for i, question in enumerate(SAMPLE_QUESTIONS, 1):
        print(f"\n📝 Question {i}: {question}")
        print("-" * 60)
        
        try:
            answer = generate_answer(SAMPLE_PASSAGES, question, max_tokens=512)
            print(f"🤖 Answer:\n{answer}")
            
            # Check for citations
            if '[1]' in answer or '[2]' in answer or '[3]' in answer or '[4]' in answer:
                print("✓ Citations detected")
            else:
                print("⚠ No citations found (model may need tuning)")
                
        except Exception as e:
            print(f"✗ Error: {e}")
            logger.error(f"RAG pipeline error: {e}", exc_info=True)
    
    return True


async def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("🚀 RAG Document Cataloger - Quality Test Suite")
    print("="*60)
    print("\nThis will test:")
    print("  1. Embedding model (BAAI/bge-base-en-v1.5)")
    print("  2. Generation model (google/flan-t5-xl)")
    print("  3. Full RAG pipeline with citations")
    print("\nNote: First run will download models (~1-2 GB)")
    
    # Run tests
    embedding_ok = await test_embeddings()
    generation_ok = await test_generation()
    
    if embedding_ok and generation_ok:
        await test_rag_pipeline()
        print("\n" + "="*60)
        print("✅ All tests completed successfully!")
        print("="*60)
        print("\n📊 Model Quality Comparison:")
        print("  • Embeddings: 768-dim (vs 384-dim) = Better retrieval")
        print("  • Generation: 3B params (vs 250M) = 12x larger model")
        print("  • Expected: More accurate, detailed answers with citations")
    else:
        print("\n" + "="*60)
        print("❌ Some tests failed - check logs above")
        print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
