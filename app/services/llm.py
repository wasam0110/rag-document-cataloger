"""
LLM wrapper using Groq API for fast, high-quality generation in the RAG pipeline.

Uses Groq's free API with Llama 3.3 70B Versatile - one of the best free
models available. Falls back to simple keyword-based responses if the API
key is not configured or the service is unavailable.

Set the GROQ_API_KEY environment variable (or add it to .env) to enable.
"""

import os
from typing import List
from app.core.logging import logger

# Groq client - lazily initialized
_client = None


def _get_client():
    """Lazily create and return a Groq client."""
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        logger.warning("GROQ_API_KEY not set - AI answers will be limited")
        return None

    try:
        from groq import Groq
        _client = Groq(api_key=api_key)
        logger.info("Groq client initialized (llama-3.3-70b-versatile)")
        return _client
    except Exception as e:
        logger.error(f"Failed to initialize Groq client: {e}")
        return None


def generate_answer(retrieved_texts: List[str], question: str, max_tokens: int = 1024) -> str:
    """Generate an answer using retrieved context + user question via Groq API.

    Args:
        retrieved_texts: Ordered list of context passages (most relevant first).
        question: The user's natural language question.
        max_tokens: Maximum tokens for the generated answer.

    Returns:
        Generated answer as a string.
    """
    if not retrieved_texts:
        return "I couldn't find relevant information in the document to answer this question."

    client = _get_client()

    # Build context from top passages
    context_blocks = []
    for i, text in enumerate(retrieved_texts[:5], 1):
        context_blocks.append(f"[Passage {i}]:\n{text.strip()}")
    context = "\n\n".join(context_blocks)

    if client is None:
        # Fallback: return a summary of retrieved passages without LLM
        return _fallback_answer(retrieved_texts, question)

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful document assistant. Answer the question based ONLY on "
                        "the provided context passages. Be comprehensive, clear and accurate. "
                        "When referencing information, cite the passage number in brackets like [1] or [2]. "
                        "If the context doesn't contain enough information to answer, say so honestly."
                    )
                },
                {
                    "role": "user",
                    "content": f"Context passages:\n\n{context}\n\nQuestion: {question}"
                }
            ],
            temperature=0.3,
            max_tokens=max_tokens,
            top_p=0.9,
        )

        answer = response.choices[0].message.content.strip()
        if not answer or len(answer) < 10:
            return _fallback_answer(retrieved_texts, question)
        return answer

    except Exception as e:
        logger.error(f"Groq generation error: {e}")
        return _fallback_answer(retrieved_texts, question)


def _fallback_answer(retrieved_texts: List[str], question: str) -> str:
    """Simple fallback when the Groq API is unavailable."""
    if not retrieved_texts:
        return "No relevant information found."

    # Return the most relevant passage as-is
    top = retrieved_texts[0].strip()
    if len(top) > 500:
        top = top[:500] + "..."
    return f"Based on the document, here is the most relevant passage:\n\n{top}"


def categorize_heading(heading_text: str) -> str:
    """Use AI to categorize a document heading into a standard section type.

    Args:
        heading_text: The heading text to categorize.

    Returns:
        A standardized category name.
    """
    if not heading_text or len(heading_text) < 3:
        return "content"

    valid_categories = {
        'abstract', 'introduction', 'related work', 'methodology',
        'model', 'results', 'discussion', 'conclusion',
        'references', 'appendix', 'acknowledgments'
    }

    # Try Groq first for accurate categorization
    client = _get_client()
    if client:
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Categorize the following document section heading into exactly ONE of these types: "
                            "abstract, introduction, related work, methodology, model, results, discussion, "
                            "conclusion, references, appendix, acknowledgments. "
                            "Respond with ONLY the category name in lowercase, nothing else."
                        )
                    },
                    {"role": "user", "content": heading_text}
                ],
                temperature=0,
                max_tokens=10,
            )
            category = response.choices[0].message.content.strip().lower()
            if category in valid_categories:
                return category
            for cat in valid_categories:
                if cat in category:
                    return cat
        except Exception as e:
            logger.warning(f"Groq categorization failed: {e}")

    # Keyword-based fallback
    heading_lower = heading_text.lower()
    keyword_map = {
        'abstract': ['abstract', 'summary', 'executive summary'],
        'introduction': ['introduction', 'overview', 'background'],
        'related work': ['related work', 'literature review', 'prior work'],
        'methodology': ['methodology', 'methods', 'approach', 'materials and methods'],
        'model': ['model', 'architecture', 'proposed method'],
        'results': ['results', 'findings', 'experiments', 'evaluation'],
        'discussion': ['discussion', 'analysis', 'interpretation'],
        'conclusion': ['conclusion', 'conclusions', 'concluding remarks', 'future work'],
        'references': ['references', 'bibliography', 'citations'],
        'appendix': ['appendix', 'supplementary'],
        'acknowledgments': ['acknowledgments', 'acknowledgements'],
    }
    for cat, keywords in keyword_map.items():
        for kw in keywords:
            if kw in heading_lower:
                return cat

    return "content"
