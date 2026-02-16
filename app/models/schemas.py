"""
Pydantic models (schemas) for request / response validation and serialization.

These models are used across the API layer and service layer to enforce
data contracts.  They are grouped into two sections:
  1. Authentication models – users, tokens, credentials.
  2. Document models – catalog items, chunks, tables, queries, etc.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Any, Dict
from datetime import datetime
import uuid


def generate_uuid() -> str:
    """Return a new random UUID4 string.  Used as default_factory for ID fields."""
    return str(uuid.uuid4())


# ==================== Authentication Models ====================

class UserBase(BaseModel):
    """Shared base fields for any user representation."""
    email: EmailStr                            # User's email – validated format
    username: Optional[str] = None             # Display name (optional)
    full_name: Optional[str] = None            # Full legal / display name


class UserCreate(UserBase):
    """Payload required to register a new user (adds password to base)."""
    password: str  # Plain-text password; will be hashed before storage


class UserLogin(BaseModel):
    """Payload for email + password login requests."""
    email: EmailStr
    password: str


class User(UserBase):
    """Full user representation returned from the API (never includes password)."""
    user_id: str                                # Unique identifier (UUID)
    is_active: bool = True                      # Account enabled flag
    oauth_provider: Optional[str] = None        # e.g. "google", "github", or None for local
    created_at: datetime                        # Account creation timestamp


class Token(BaseModel):
    """JWT access-token response returned after successful authentication."""
    access_token: str                           # Encoded JWT string
    token_type: str = "bearer"                  # OAuth2 token type
    user: Optional[User] = None                 # Optionally include user details


class TokenData(BaseModel):
    """Claims extracted from a decoded JWT – used internally for auth checks."""
    user_id: Optional[str] = None
    email: Optional[str] = None


# ==================== Document Models ====================

class Topic(BaseModel):
    """Represents a detected section / topic within a document."""
    topic_id: str = Field(default_factory=generate_uuid)  # Unique topic identifier
    title: str                                             # Section heading text
    start_page: Optional[int] = None                       # First page of the section
    end_page: Optional[int] = None                         # Last page of the section
    item_ids: List[str] = Field(default_factory=list)      # Related chunk / table IDs


class TableData(BaseModel):
    """Metadata and content for a table extracted from a document."""
    item_id: str = Field(default_factory=generate_uuid)    # Unique table identifier
    page: Optional[int] = None                             # Page number where table appears
    title: Optional[str] = None                            # Auto-detected or user-assigned title
    data_json: Dict[str, Any] = Field(default_factory=dict)  # Raw structured data
    columns: List[str] = Field(default_factory=list)       # Column header names
    rows: List[List[Any]] = Field(default_factory=list)    # Row data (list of lists)
    bbox: Optional[List[float]] = None                     # Bounding box [x0, y0, x1, y1]
    table_text: Optional[str] = None                       # Markdown / plain-text rendering
    confidence: float = 1.0                                # Detection confidence score


class Chunk(BaseModel):
    """A contiguous text fragment produced by chunking a document."""
    item_id: str = Field(default_factory=generate_uuid)
    page: Optional[int] = None            # Source page (None for non-paged formats)
    section: Optional[str] = None         # Heading under which the chunk falls
    text: str                             # Actual chunk text content
    char_start: int = 0                   # Character offset start in full document
    char_end: int = 0                     # Character offset end in full document


class Keyword(BaseModel):
    """A keyword / key-phrase extracted from a document with its relevance score."""
    keyword: str
    score: float  # Higher = more relevant


class Figure(BaseModel):
    """Metadata for a figure / image detected in a document."""
    item_id: str = Field(default_factory=generate_uuid)
    page: Optional[int] = None
    description: Optional[str] = None     # Alt-text or caption
    bbox: Optional[List[float]] = None    # Bounding box on the page


class DocumentCatalog(BaseModel):
    """Complete catalog record for a single document, aggregating all extracted artifacts."""
    doc_id: str = Field(default_factory=generate_uuid)
    filename: str                                          # Original upload filename
    filetype: str                                          # Extension-based type (pdf, docx, csv, txt)
    created_at: datetime = Field(default_factory=datetime.utcnow)  # Ingestion timestamp
    topics: List[Topic] = Field(default_factory=list)
    tables: List[TableData] = Field(default_factory=list)
    chunks: List[Chunk] = Field(default_factory=list)
    keywords: List[Keyword] = Field(default_factory=list)
    figures: List[Figure] = Field(default_factory=list)


class Citation(BaseModel):
    """A single citation returned alongside a query answer, pointing to source material."""
    item_id: str          # ID of the chunk / table that supports the answer
    category: str         # "chunk", "table", etc.
    page: Optional[int] = None
    snippet: str          # Short excerpt from the source


class QueryResponse(BaseModel):
    """Response model for the /query endpoint."""
    answer: str                                            # Generated answer text
    citations: List[Citation] = Field(default_factory=list)  # Supporting evidence


class QueryRequest(BaseModel):
    """Request body for the /query endpoint."""
    doc_id: str       # Target document to search
    question: str     # Natural-language query
    top_k: int = 4    # Number of nearest-neighbor results to return


class UploadResponse(BaseModel):
    """Response returned after a successful document upload."""
    doc_id: str       # Assigned document identifier
    filename: str     # Original filename echoed back
    message: str      # Human-readable status message


class DocumentListItem(BaseModel):
    """Lightweight document summary used when listing all documents."""
    doc_id: str
    filename: str
    filetype: str
    created_at: datetime