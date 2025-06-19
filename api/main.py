"""
Simple FastAPI Backend for Research Paper Analysis
Upload PDF -> Process with GROBID -> View Results
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging
from datetime import datetime
from typing import Dict
import uuid
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core.processor import process_research_paper
from src.schemas import DocumentUploadResponse, DocumentStatus
from src.config import settings

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Research Paper Analyzer",
    description="Upload PDF and get structured analysis",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple in-memory storage
documents: Dict[str, Dict] = {}
processing_status: Dict[str, str] = {}


@app.get("/")
async def root():
    """API information."""
    return {
        "message": "Research Paper Analyzer API",
        "version": "1.0.0",
        "description": "Upload PDF and view structured analysis results",
        "endpoints": {
            "upload": "/upload - Upload PDF file",
            "status": "/status/{doc_id} - Check processing status", 
            "documents": "/documents - List all documents",
            "delete": "/documents/{doc_id} - Delete document"
        }
    }


@app.post("/upload", response_model=DocumentUploadResponse)
async def upload_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Upload and process a research paper PDF."""
    
    # Validate file
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    if file.size and file.size > settings.max_file_size:
        raise HTTPException(status_code=400, detail=f"File too large. Max size: {settings.max_file_size // 1024 // 1024}MB")
    
    # Generate document ID
    doc_id = str(uuid.uuid4())
    processing_status[doc_id] = DocumentStatus.PROCESSING
    
    # Read file content
    try:
        pdf_content = await file.read()
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(status_code=400, detail="Error reading PDF file")
    
    # Start background processing
    background_tasks.add_task(process_document, doc_id, pdf_content, file.filename)
    
    logger.info(f"Started processing document: {file.filename}")
    
    return DocumentUploadResponse(
        document_id=doc_id,
        filename=file.filename,
        status=DocumentStatus.PROCESSING,
        message="Document uploaded successfully. Processing in background."
    )


async def process_document(doc_id: str, pdf_content: bytes, filename: str):
    """Background processing task."""
    try:
        logger.info(f"Processing document with GROBID: {doc_id}")
        
        # Process with GROBID
        result = process_research_paper(pdf_content, filename)
        
        # Store result
        documents[doc_id] = {
            'document_id': doc_id,
            'filename': filename,
            'upload_time': datetime.now().isoformat(),
            'file_size': len(pdf_content),
            'processing_result': result
        }
        
        # Update status
        if result['status'] == 'success':
            processing_status[doc_id] = DocumentStatus.COMPLETED
            logger.info(f"Successfully processed document: {doc_id}")
        else:
            processing_status[doc_id] = DocumentStatus.FAILED
            logger.error(f"Failed to process document: {doc_id} - {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        logger.error(f"Error processing document {doc_id}: {e}")
        processing_status[doc_id] = DocumentStatus.FAILED
        
        # Store error info
        documents[doc_id] = {
            'document_id': doc_id,
            'filename': filename,
            'upload_time': datetime.now().isoformat(),
            'file_size': len(pdf_content) if 'pdf_content' in locals() else 0,
            'processing_result': {
                'status': 'error',
                'error': str(e),
                'title': '',
                'authors': [],
                'abstract': '',
                'sections': [],
                'references': []
            }
        }


@app.get("/status/{doc_id}")
async def get_document_status(doc_id: str):
    """Get processing status and results of a document."""
    if doc_id not in processing_status:
        raise HTTPException(status_code=404, detail="Document not found")
    
    status = processing_status[doc_id]
    
    response = {
        'document_id': doc_id,
        'status': status
    }
    
    # Add document data if available
    if doc_id in documents:
        doc_data = documents[doc_id]
        response.update({
            'filename': doc_data['filename'],
            'upload_time': doc_data['upload_time'],
            'file_size': doc_data['file_size']
        })
        
        # Add processing results if completed
        if status == DocumentStatus.COMPLETED:
            response['result'] = doc_data['processing_result']
        elif status == DocumentStatus.FAILED:
            response['error'] = doc_data['processing_result'].get('error', 'Processing failed')
    
    return response


@app.get("/documents")
async def list_documents():
    """List all uploaded documents with their status."""
    document_list = []
    
    for doc_id, doc_data in documents.items():
        status = processing_status.get(doc_id, DocumentStatus.FAILED)
        
        doc_info = {
            'document_id': doc_id,
            'filename': doc_data['filename'],
            'status': status,
            'upload_time': doc_data['upload_time'],
            'file_size': doc_data['file_size']
        }
        
        # Add basic info if successfully processed
        if status == DocumentStatus.COMPLETED and doc_data['processing_result']['status'] == 'success':
            result = doc_data['processing_result']
            doc_info.update({
                'title': result.get('title', ''),
                'authors_count': len(result.get('authors', [])),
                'sections_count': len(result.get('sections', [])),
                'processing_time': result.get('processing_time', 0)
            })
        
        document_list.append(doc_info)
    
    # Sort by upload time (newest first)
    return sorted(document_list, key=lambda x: x['upload_time'], reverse=True)


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a processed document."""
    if doc_id not in documents:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Remove from storage
    filename = documents[doc_id]['filename']
    del documents[doc_id]
    
    if doc_id in processing_status:
        del processing_status[doc_id]
    
    logger.info(f"Deleted document: {doc_id} ({filename})")
    
    return {"message": f"Document '{filename}' deleted successfully"}


@app.get("/health")
async def health_check():
    """API health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "total_documents": len(documents),
        "processing_documents": len([d for d in processing_status.values() if d == DocumentStatus.PROCESSING]),
        "completed_documents": len([d for d in processing_status.values() if d == DocumentStatus.COMPLETED]),
        "failed_documents": len([d for d in processing_status.values() if d == DocumentStatus.FAILED])
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app", 
        host=settings.host, 
        port=settings.port, 
        reload=settings.debug
    )