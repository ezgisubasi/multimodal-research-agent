from pydantic import BaseModel, Field
from typing import Optional


class UploadRequest(BaseModel):
    """Request model for PDF upload."""
    paper_id: Optional[str] = Field(None, description="Optional custom paper ID")


class SearchRequest(BaseModel):
    """Request model for search queries."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="Number of results to return")