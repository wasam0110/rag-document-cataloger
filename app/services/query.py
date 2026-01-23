"""
Query service for semantic search across documents using FAISS.
"""

from typing import List, Dict, Any
from app.core.logging import logger
from app.services.index.faiss_store import search_index


async def query_document(doc_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Query a document using semantic search.
    
    Args:
        doc_id: Document ID to query
        query: Search query text
        top_k: Number of results to return
        
    Returns:
        List of search results with metadata
    """
    try:
        logger.info(f"Querying document {doc_id} with: {query[:50]}...")
        
        results = search_index(doc_id, query, top_k)
        
        logger.info(f"Found {len(results)} results")
        return results
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        return []