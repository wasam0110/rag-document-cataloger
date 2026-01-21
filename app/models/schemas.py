from pydantic import BaseModel, Field
from typing import List, Optional, Any, Dict
from datetime import datetime
import uuid

def generate_uuid() -> str:
    return str(uuid.uuid4())

class Topic(BaseModel):
    topic_id: str = Field(default_factory=generate_uuid)
    title: str
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    item_ids: List[str] = Field(default_factory=list)

class TableData(BaseModel):
    item_id: str = Field(default_factory=generate_uuid)
    page: Optional[int] = None
    title: Optional[str] = None
    data_json: Dict[str, Any] = Field(default_factory=dict)
    columns: List[str] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    bbox: Optional[List[float]] = None
    table_text: Optional[str] = None
    confidence: float = 1.0

class Chunk(BaseModel):
    item_id: str = Field(default_factory=generate_uuid)
    page: Optional[int] = None
    section: Optional[str] = None
    text: str
    char_start: int = 0
    char_end: int = 0

class Keyword(BaseModel):
    keyword: str
    score: float

class Figure(BaseModel):
    item_id: str = Field(default_factory=generate_uuid)
    page: Optional[int] = None
    description: Optional[str] = None
    bbox: Optional[List[float]] = None

class DocumentCatalog(BaseModel):
    doc_id: str = Field(default_factory=generate_uuid)
    filename: str
    filetype: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    topics: List[Topic] = Field(default_factory=list)
    tables: List[TableData] = Field(default_factory=list)
    chunks: List[Chunk] = Field(default_factory=list)
    keywords: List[Keyword] = Field(default_factory=list)
    figures: List[Figure] = Field(default_factory=list)

class Citation(BaseModel):
    item_id: str
    category: str
    page: Optional[int] = None
    snippet: str

class QueryResponse(BaseModel):
    answer: str
    citations: List[Citation] = Field(default_factory=list)

class QueryRequest(BaseModel):
    doc_id: str
    question: str
    top_k: int = 4

class UploadResponse(BaseModel):
    doc_id: str
    filename: str
    message: str

class DocumentListItem(BaseModel):
    doc_id: str
    filename: str
    filetype: str
    created_at: datetime