from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from pathlib import Path
import sys
import os

# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.core.colpali import ColPaliSearcher
from src.config import settings
from api.models.requests import SearchRequest
from api.models.responses import UploadResponse, SearchResponse, SearchResult

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title=settings.app_name,
    description="Multimodal Research Assistant with ColPali",
    version=settings.version
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize ColPali searcher
searcher = ColPaliSearcher(device=settings.device, qdrant_url=settings.qdrant_url)


@app.on_event("startup")
async def startup_event():
    """Load ColPali model on startup."""
    try:
        logger.info("Loading ColPali model...")
        searcher.load_model()
        logger.info("ColPali model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load ColPali model: {e}")


@app.get("/")
async def root():
    """API information."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "version": settings.version,
        "description": "Upload PDFs and search with multimodal queries",
        "endpoints": {
            "upload": "POST /upload - Upload PDF file",
            "search": "POST /search - Search across documents"
        }
    }


@app.post("/upload", response_model=UploadResponse)
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    paper_id: str = None
):
    """Upload and index a PDF document."""
    
    # Validate file
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(
            status_code=400, 
            detail=f"File too large. Max size: {settings.max_file_size // 1024 // 1024}MB"
        )
    
    try:
        # Save uploaded file
        file_path = settings.upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        logger.info(f"Saved file: {file_path}")
        
        # Index PDF in background
        background_tasks.add_task(index_pdf_task, str(file_path), paper_id)
        
        # Return immediate response
        return UploadResponse(
            paper_id=paper_id or "processing",
            message="PDF uploaded successfully. Indexing in progress.",
            num_pages=0,
            status="processing"
        )
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


async def index_pdf_task(file_path: str, paper_id: str = None):
    """Background task to index PDF."""
    try:
        logger.info(f"Starting indexing for: {file_path}")
        indexed_id = searcher.index_pdf(file_path, paper_id)
        logger.info(f"Successfully indexed: {indexed_id}")
    except Exception as e:
        logger.error(f"Indexing failed for {file_path}: {e}")


@app.post("/search", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """Search across indexed documents."""
    try:
        logger.info(f"Search request: {request.query}")
        
        # Perform search
        results = searcher.search(request.query, top_k=request.top_k)
        
        # Convert to response format
        search_results = [
            SearchResult(
                paper_id=result["paper_id"],
                page_number=result["page_number"],
                score=result["score"],
                pdf_path=result["pdf_path"]
            )
            for result in results
        ]
        
        return SearchResponse(
            query=request.query,
            results=search_results,
            total_results=len(search_results)
        )
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/health")
async def health_check():
    """API health check."""
    return {
        "status": "healthy",
        "model_loaded": searcher.colpali_model is not None
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host=settings.host, 
        port=settings.port, 
        reload=settings.debug
    )