import os
from pathlib import Path
from typing import List, Dict, Optional, Any

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from app.core.config import settings
from app.core.logging import logger

# Global embeddings model (lazy loaded)
_embeddings = None


def get_embeddings():
    """Get or create embeddings model."""
    global _embeddings
    if _embeddings is None:
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
            model_kwargs={'device': 'cpu'},
            encode_kwargs={'normalize_embeddings': True}
        )
        logger.info("Embedding model loaded successfully")
    return _embeddings


def get_index_path(doc_id: str) -> Path:
    """Get the path for a document's FAISS index."""
    return settings.faiss_index_dir / doc_id


def create_index(doc_id: str, items: List[Dict[str, Any]]) -> bool:
    """Create FAISS index for a document."""
    logger.info(f"Creating FAISS index for document: {doc_id}")
    
    if not items:
        logger.warning("No items to index")
        return False
    
    # Convert items to LangChain documents
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
    
    embeddings = get_embeddings()
    
    # Create FAISS index
    vectorstore = FAISS.from_documents(documents, embeddings)
    
    # Save index
    index_path = get_index_path(doc_id)
    index_path.mkdir(parents=True, exist_ok=True)
    vectorstore.save_local(str(index_path))
    
    logger.info(f"FAISS index saved to {index_path}")
    return True


def load_index(doc_id: str) -> Optional[FAISS]:
    """Load FAISS index for a document."""
    index_path = get_index_path(doc_id)
    
    if not index_path.exists():
        logger.warning(f"Index not found for document: {doc_id}")
        return None
    
    logger.info(f"Loading FAISS index for document: {doc_id}")
    embeddings = get_embeddings()
    
    vectorstore = FAISS.load_local(
        str(index_path), 
        embeddings,
        allow_dangerous_deserialization=True
    )
    
    return vectorstore


def search_index(doc_id: str, query: str, top_k: int = 4) -> List[Dict]:
    """Search the FAISS index."""
    vectorstore = load_index(doc_id)
    
    if vectorstore is None:
        return []
    
    logger.info(f"Searching index for: {query[:50]}...")
    
    results = vectorstore.similarity_search_with_score(query, k=top_k)
    
    search_results = []
    for doc, score in results:
        search_results.append({
            "item_id": doc.metadata.get("item_id"),
            "category": doc.metadata.get("category"),
            "page": doc.metadata.get("page"),
            "section": doc.metadata.get("section", ""),
            "text": doc.page_content,
            "score": float(score)
        })
    
    logger.info(f"Found {len(search_results)} results")
    return search_results


def delete_index(doc_id: str) -> bool:
    """Delete FAISS index for a document."""
    import shutil
    index_path = get_index_path(doc_id)
    
    if index_path.exists():
        shutil.rmtree(index_path)
        logger.info(f"Deleted index for document: {doc_id}")
        return True
    return False