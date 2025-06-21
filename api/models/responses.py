from pydantic import BaseModel
from typing import List, Optional


class UploadResponse(BaseModel):
    """Response model for PDF upload."""
    paper_id: str
    message: str
    num_pages: int
    status: str


class SearchResult(BaseModel):
    """Individual search result."""
    paper_id: str
    page_number: int
    score: float
    pdf_path: str


class SearchResponse(BaseModel):
    """Response model for search queries."""
    query: str
    results: List[SearchResult]
    total_results: int


class DocumentInfo(BaseModel):
    """Document information model."""
    paper_id: str
    pdf_path: str
    num_pages: int
    indexed: bool


class ListDocumentsResponse(BaseModel):
    """Response for listing documents."""
    documents: List[DocumentInfo]
    total_documents: int