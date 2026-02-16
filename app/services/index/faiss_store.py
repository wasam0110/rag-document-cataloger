"""
FAISS vector-store operations for per-document semantic search.

Each document gets its own FAISS index persisted on disk under
``faiss_index/<doc_id>/``.  Text is embedded via a HuggingFace
sentence-transformer model (lazy-loaded as a module-level singleton).

Public API (all functions, **not** a class):
  - create_index(doc_id, items)
  - load_index(doc_id) -> Optional[FAISS]
  - search_index(doc_id, query, top_k) -> List[Dict]
  - delete_index(doc_id) -> bool
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Any

from langchain_huggingface import HuggingFaceEmbeddings           # Embedding wrapper
from langchain_community.vectorstores import FAISS                # FAISS vector store
from langchain_core.documents import Document                     # LangChain document type

from app.core.config import settings
from app.core.logging import logger

# Module-level cache for the embedding model (heavy to load, so we only do it once).
_embeddings = None


def get_embeddings():
    """Lazily load and return the HuggingFace embedding model.

    The model is cached in the module-level ``_embeddings`` variable so
    subsequent calls are essentially free.  Embeddings are L2-normalized
    to make cosine similarity equivalent to inner-product search.
    """
    global _embeddings
    if _embeddings is None:
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={'device': 'cpu'},                       # Force CPU inference
            encode_kwargs={'normalize_embeddings': True}           # L2-normalize for cosine sim
        )
        logger.info("Embedding model loaded successfully")
    return _embeddings


def get_index_path(doc_id: str) -> Path:
    """Return the directory where a document's FAISS index is stored."""
    return settings.faiss_index_dir / doc_id


def create_index(doc_id: str, items: List[Dict[str, Any]]) -> bool:
    """Create and persist a FAISS index for the given document.

    Args:
        doc_id: Unique document identifier.
        items:  List of dicts, each with keys ``text``, ``item_id``,
                ``category``, and optional ``page`` / ``section``.

    Returns:
        True on success, False if there were no items to index.
    """
    logger.info(f"Creating FAISS index for document: {doc_id}")
    
    if not items:
        logger.warning("No items to index")
        return False
    
    # Convert each item dict into a LangChain Document so FAISS can process it.
    # Metadata is stored alongside the vector and returned with search results.
    documents = []
    for item in items:
        doc = Document(
            page_content=item["text"],
            metadata={
                "item_id": item["item_id"],
                "category": item["category"],
                "page": item.get("page"),
                "section": item.get("section", ""),
                "doc_id": doc_id
            }
        )
        documents.append(doc)
    
    logger.info(f"Indexing {len(documents)} items")
    
    # Get (or lazily load) the shared embedding model
    embeddings = get_embeddings()
    
    # Build an in-memory FAISS index from the documents + embeddings
    vectorstore = FAISS.from_documents(documents, embeddings)
    
    # Persist the index to disk so it survives server restarts
    index_path = get_index_path(doc_id)
    index_path.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(index_path))
    
    logger.info(f"FAISS index saved to {index_path}")
    return True


def load_index(doc_id: str) -> Optional[FAISS]:
    """Load a previously persisted FAISS index from disk.

    Returns None if the index directory does not exist (e.g. the
    document was never indexed or the index was deleted).
    """
    index_path = get_index_path(doc_id)
    
    if not index_path.exists():
        logger.warning(f"Index not found for document: {doc_id}")
        return None
    
    logger.info(f"Loading FAISS index for document: {doc_id}")
    embeddings = get_embeddings()
    
    # allow_dangerous_deserialization is required by LangChain when
    # loading pickle-serialized metadata from untrusted sources.
    vectorstore = FAISS.load_local(
        str(index_path), 
        embeddings,
        allow_dangerous_deserialization=True
    )
    
    return vectorstore


def search_index(doc_id: str, query: str, top_k: int = 4) -> List[Dict]:
    """Search a document's FAISS index for chunks similar to ``query``.

    Args:
        doc_id: Document whose index to search.
        query:  Natural-language query string.
        top_k:  Number of nearest neighbors to return.

    Returns:
        List of result dicts with keys: item_id, category, page,
        section, text, and score (L2 distance – lower is better).
    """
    # Load the persisted index (returns None if missing)
    vectorstore = load_index(doc_id)
    
    if vectorstore is None:
        return []
    
    logger.info(f"Searching index for: {query[:50]}...")
    
    # Perform similarity search and get (Document, score) tuples
    results = vectorstore.similarity_search_with_score(query, k=top_k)
    
    # Flatten results into simple dicts for the API response
    search_results = []
    for doc, score in results:
        search_results.append({
            "item_id": doc.metadata.get("item_id"),
            "category": doc.metadata.get("category"),
            "page": doc.metadata.get("page"),
            "section": doc.metadata.get("section", ""),
            "text": doc.page_content,
            "score": float(score)       # Convert numpy float → Python float
        })
    
    logger.info(f"Found {len(search_results)} results")
    return search_results


def delete_index(doc_id: str) -> bool:
    """Delete the FAISS index directory for a document.

    Returns True if the directory existed and was removed, False otherwise.
    """
    import shutil
    index_path = get_index_path(doc_id)
    
    if index_path.exists():
        shutil.rmtree(index_path)  # Recursively remove the index directory
        logger.info(f"Deleted index for document: {doc_id}")
        return True
    return False