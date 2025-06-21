from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from pathlib import Path
import sys
import hashlib

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from src.core.colpali import ColPaliSearcher
from src.config import settings
from api.models.requests import SearchRequest
from api.models.responses import UploadResponse, SearchResponse, SearchResult

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(title=settings.app_name, description="Multimodal Research Assistant")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global searcher
searcher = None

def get_searcher():
    """Get searcher instance."""
    global searcher
    if searcher is None:
        searcher = ColPaliSearcher(
            model_name=settings.colpali_model,
            device=settings.device,
            qdrant_url=settings.qdrant_url,
            qdrant_api_key=settings.qdrant_api_key
        )
    return searcher


@app.get("/")
async def root():
    """API info."""
    return {
        "message": f"Welcome to {settings.app_name}",
        "endpoints": {
            "upload": "POST /upload",
            "search": "POST /search", 
            "documents": "GET /documents",
            "health": "GET /health"
        }
    }


@app.post("/upload")
async def upload_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    paper_id: str = None
):
    """Upload and index PDF."""
    
    # Validate file
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files supported")
    
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(status_code=400, detail="File too large")
    
    try:
        # Save file
        file_path = settings.upload_dir / file.filename
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Generate paper_id
        if paper_id is None:
            paper_id = f"paper_{hashlib.md5(file.filename.encode()).hexdigest()[:8]}"
        
        # Index in background
        background_tasks.add_task(index_pdf_task, str(file_path), paper_id)
        
        return {
            "paper_id": paper_id,
            "message": "PDF uploaded. Indexing in progress.",
            "status": "processing"
        }
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def index_pdf_task(file_path: str, paper_id: str):
    """Background indexing task."""
    try:
        logger.info(f"Indexing: {file_path}")
        searcher = get_searcher()
        searcher.index_pdf(file_path, paper_id)
        logger.info(f"Indexed: {paper_id}")
    except Exception as e:
        logger.error(f"Indexing failed: {e}")


@app.post("/search")
async def search_documents(request: SearchRequest):
    """Search documents."""
    try:
        searcher = get_searcher()
        results = searcher.search(request.query, top_k=request.top_k)
        
        search_results = [
            {
                "paper_id": r["paper_id"],
                "page_number": r["page_number"],
                "score": r["score"],
                "pdf_path": r["pdf_path"]
            }
            for r in results
        ]
        
        return {
            "query": request.query,
            "results": search_results,
            "total_results": len(search_results)
        }
        
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
async def list_documents():
    """List indexed documents."""
    try:
        searcher = get_searcher()
        docs = searcher.get_documents()
        
        return {
            "documents": docs,
            "total_documents": len(docs)
        }
        
    except Exception as e:
        logger.error(f"List documents failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check."""
    try:
        searcher = get_searcher()
        return {
            "status": "healthy",
            "model_loaded": searcher.colpali_model is not None,
            "qdrant_connected": True
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


if __name__ == "__main__":
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)