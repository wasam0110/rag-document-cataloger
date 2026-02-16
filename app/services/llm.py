"""
LLM wrapper using Groq or Gemini API for high-quality generation in the RAG pipeline.

Supports two free API options with automatic fallback:
1. Groq (Llama 3.3 70B Versatile) - Fast and powerful
2. Google Gemini (gemini-2.0-flash-exp) - Free and high-quality

Priority: Groq → Gemini → Simple keyword-based responses
Set GROQ_API_KEY or GEMINI_API_KEY in .env to enable.
"""

import os
from typing import List, Optional, Tuple
from app.core.logging import logger

# LLM clients - lazily initialized
_groq_client = None
_gemini_model = None
_active_provider = None  # 'groq', 'gemini', or None


def _get_llm_client() -> Tuple[Optional[object], str]:
    """Lazily initialize and return the best available LLM client.
    
    Returns:
        Tuple of (client/model, provider_name)
    """
    global _groq_client, _gemini_model, _active_provider
    
    # Return cached client if available
    if _active_provider == 'groq' and _groq_client:
        return (_groq_client, 'groq')
    if _active_provider == 'gemini' and _gemini_model:
        return (_gemini_model, 'gemini')
    
    # Try Groq first
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        try:
            from groq import Groq
            _groq_client = Groq(api_key=groq_key)
            _active_provider = 'groq'
            logger.info("✅ Groq client initialized (llama-3.3-70b-versatile)")
            return (_groq_client, 'groq')
        except Exception as e:
            logger.warning(f"Groq initialization failed: {e}, trying Gemini...")
    
    # Try Gemini as fallback
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=gemini_key)
            _gemini_model = genai.GenerativeModel('gemini-2.0-flash-exp')
            _active_provider = 'gemini'
            logger.info("✅ Gemini client initialized (gemini-2.0-flash-exp)")
            return (_gemini_model, 'gemini')
        except Exception as e:
            logger.warning(f"Gemini initialization failed: {e}")
    
    logger.warning("⚠️  No LLM API key found (GROQ_API_KEY or GEMINI_API_KEY) - AI answers will be limited")
    _active_provider = None
    return (None, 'none')


def generate_answer(retrieved_texts: List[str], question: str, max_tokens: int = 1024) -> str:
    """Generate an answer using retrieved context + user question via Groq or Gemini API.

    Args:
        retrieved_texts: Ordered list of context passages (most relevant first).
        question: The user's natural language question.
        max_tokens: Maximum tokens for the generated answer.

    Returns:
        Generated answer as a string.
    """
    if not retrieved_texts:
        return "I couldn't find relevant information in the document to answer this question."

    client, provider = _get_llm_client()

    # Build context from top passages
    context_blocks = []
    for i, text in enumerate(retrieved_texts[:5], 1):
        context_blocks.append(f"[Passage {i}]:\n{text.strip()}")
    context = "\n\n".join(context_blocks)

    if client is None:
        # Fallback: return a summary of retrieved passages without LLM
        return _fallback_answer(retrieved_texts, question)

    # System prompt for both providers
    system_prompt = (
        "You are a helpful document assistant. Answer the question based ONLY on "
        "the provided context passages. Be comprehensive, clear and accurate. "
        "Use bullet points to organize information clearly. "
        "When referencing information, cite the passage number in brackets like [1] or [2]. "
        "If the context doesn't contain enough information to answer, say so honestly."
    )
    
    user_prompt = f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer clearly with bullet points where helpful:"

    try:
        if provider == 'groq':
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=max_tokens,
                top_p=0.9,
            )
            answer = response.choices[0].message.content.strip()
            
        elif provider == 'gemini':
            # Gemini uses a simpler API - combine system + user prompt
            full_prompt = f"{system_prompt}\n\n{user_prompt}"
            response = client.generate_content(
                full_prompt,
                generation_config={
                    "temperature": 0.3,
                    "max_output_tokens": max_tokens,
                }
            )
            answer = response.text.strip()
        else:
            return _fallback_answer(retrieved_texts, question)

        if not answer or len(answer) < 10:
            return _fallback_answer(retrieved_texts, question)
        
        logger.info(f"✅ Answer generated using {provider}")
        return answer

    except Exception as e:
        logger.error(f"{provider.title()} generation error: {e}")
        return _fallback_answer(retrieved_texts, question)


def _fallback_answer(retrieved_texts: List[str], question: str) -> str:
    """Simple fallback when LLM APIs (Groq/Gemini) are unavailable."""
    if not retrieved_texts:
        return "No relevant information found."

    # Return the most relevant passage as-is
    top = retrieved_texts[0].strip()
    if len(top) > 500:
        top = top[:500] + "..."
    return f"Based on the document, here is the most relevant passage:\n\n{top}"


def categorize_heading(heading_text: str) -> str:
    """Use AI (Groq or Gemini) to categorize a document heading into a standard section type.

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

    # Try LLM (Groq or Gemini) for accurate categorization
    client, provider = _get_llm_client()
    if client:
        system_msg = (
            "Categorize the following document section heading into exactly ONE of these types: "
            "abstract, introduction, related work, methodology, model, results, discussion, "
            "conclusion, references, appendix, acknowledgments. "
            "Respond with ONLY the category name in lowercase, nothing else."
        )
        
        try:
            if provider == 'groq':
                response = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": heading_text}
                    ],
                    temperature=0,
                    max_tokens=10,
                )
                category = response.choices[0].message.content.strip().lower()
            elif provider == 'gemini':
                prompt = f"{system_msg}\n\nHeading: {heading_text}\n\nCategory:"
                response = client.generate_content(
                    prompt,
                    generation_config={"temperature": 0, "max_output_tokens": 10}
                )
                category = response.text.strip().lower()
            else:
                category = None
            
            if category and category in valid_categories:
                return category
            # Check if any valid category is in the response
            if category:
                for cat in valid_categories:
                    if cat in category:
                        return cat
        except Exception as e:
            logger.warning(f"{provider.title()} categorization failed: {e}")

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
