from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class DocumentStatus(str, Enum):
    """Document processing status."""
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Upload Models
class DocumentUploadResponse(BaseModel):
    """Response after uploading a document."""
    document_id: str
    filename: str
    status: DocumentStatus
    message: str


# Query Models
class QueryRequest(BaseModel):
    """User query about a document."""
    question: str = Field(..., min_length=1, max_length=500)
    document_id: str


class QueryResponse(BaseModel):
    """Response to user query."""
    answer: str
    sources: List[str] = []
    processing_time: Optional[float] = None


# Document Info
class DocumentInfo(BaseModel):
    """Basic document information."""
    document_id: str
    filename: str
    status: DocumentStatus
    page_count: Optional[int] = None
    upload_time: datetime


# Error Response
class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    message: str