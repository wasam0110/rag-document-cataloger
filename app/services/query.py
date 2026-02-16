"""
Query service for semantic search across documents using FAISS.

Provides a thin async wrapper around the FAISS search so that the
API layer can ``await`` the result without blocking the event loop
for longer than necessary (the actual FAISS search is CPU-bound but
fast enough for single-query use).
"""

from typing import List, Dict, Any
from app.core.logging import logger
from app.services.index.faiss_store import search_index  # Low-level vector search
from app.services.llm import generate_answer


async def query_document(doc_id: str, query: str, top_k: int = 5) -> Dict[str, Any]:
    """
    Query a document using semantic (vector) similarity search.
    
    Args:
        doc_id: Document ID whose FAISS index will be searched.
        query: Natural-language search query text.
        top_k: Maximum number of nearest-neighbor results to return.
        
    Returns:
        List of dicts, each containing item_id, category, page,
        section, text, and similarity score.
    """
    try:
        # Log a truncated version of the query to avoid flooding the logs
        logger.info(f"Querying document {doc_id} with: {query[:50]}...")
        
        # Delegate to the FAISS store which handles embedding + similarity search
        results = search_index(doc_id, query, top_k)

        logger.info(f"Found {len(results)} results")

        # Build context passages for generation (use the retrieved texts)
        passages = [r.get("text", "") for r in results if r.get("text")]

        # Generate a comprehensive answer using the retrieved passages + the question
        # Using increased token limit for more complete answers
        answer = generate_answer(passages, query, max_tokens=512)

        return {"results": results, "answer": answer}
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        # Return an empty-but-valid dict so callers can safely call .get()
        return {"results": [], "answer": ""}