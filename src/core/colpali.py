import torch
from PIL import Image
import fitz  # PyMuPDF
from colpali_engine.models import ColPali, ColPaliProcessor
from pathlib import Path
import hashlib
from typing import List, Dict
import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models
import numpy as np

logger = logging.getLogger(__name__)


class ColPaliSearcher:
    """Simple ColPali implementation following the demo approach."""
    
    def __init__(self, model_name: str = "vidore/colpali", device: str = "cpu", qdrant_url: str = "http://localhost:6333"):
        self.model_name = model_name
        self.device = device
        self.qdrant_client = QdrantClient(url=qdrant_url)
        self.collection_name = "research_papers"
        self.colpali_model = None
        self.colpali_processor = None
        self.setup_qdrant_collection()
        
    def setup_qdrant_collection(self):
        """Setup Qdrant collection for ColPali multivectors."""
        try:
            # Check if collection exists
            collections = self.qdrant_client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            if self.collection_name not in collection_names:
                # Create collection with multivector config like in demo
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=128,
                        distance=models.Distance.COSINE,
                        multivector_config=models.MultiVectorConfig(
                            comparator=models.MultiVectorComparator.MAX_SIM
                        ),
                    ),
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            else:
                logger.info(f"Using existing Qdrant collection: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"Failed to setup Qdrant collection: {e}")
            raise
    
    def load_model(self):
        """Load ColPali model exactly like in demo."""
        try:
            logger.info(f"Loading ColPali model: {self.model_name}")
            
            # Load model and processor like in demo
            self.colpali_model = ColPali.from_pretrained(
                self.model_name,
                torch_dtype=torch.bfloat16,
                device_map=self.device if self.device != "cpu" else "cpu",
            )
            
            self.colpali_processor = ColPaliProcessor.from_pretrained(
                "vidore/colpaligemma-3b-pt-448-base"
            )
            
            logger.info("ColPali model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load ColPali model: {e}")
            raise
    
    def pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """Convert PDF pages to PIL Images."""
        try:
            doc = fitz.open(pdf_path)
            images = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                # Convert page to image with good quality
                pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
                img_data = pix.tobytes("png")
                
                # Convert to PIL Image
                from io import BytesIO
                img = Image.open(BytesIO(img_data))
                images.append(img)
                
            doc.close()
            logger.info(f"Converted {len(images)} pages to images")
            return images
            
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            raise
    
    def index_pdf(self, pdf_path: str, paper_id: str = None) -> str:
        """Index PDF following demo approach."""
        if self.colpali_model is None:
            self.load_model()
            
        try:
            # Generate paper ID
            if paper_id is None:
                with open(pdf_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()[:8]
                paper_id = f"paper_{file_hash}"
            
            logger.info(f"Indexing PDF: {pdf_path} as {paper_id}")
            
            # Convert PDF to images
            images = self.pdf_to_images(pdf_path)
            
            # Process images like in demo
            with torch.no_grad():
                batch_images = self.colpali_processor.process_images(images).to(
                    self.colpali_model.device
                )
                image_embeddings = self.colpali_model(**batch_images)
            
            # Prepare points for Qdrant (following demo exactly)
            points = []
            for page_idx, embedding in enumerate(image_embeddings):
                # Convert to multivector like in demo
                multivector = embedding.cpu().float().numpy().tolist()
                
                point = models.PointStruct(
                    id=f"{paper_id}_page_{page_idx}",
                    vector=multivector,  # This is a list of vectors (multivector)
                    payload={
                        "paper_id": paper_id,
                        "page_number": page_idx,
                        "pdf_path": pdf_path,
                        "total_pages": len(images)
                    }
                )
                points.append(point)
            
            # Upload to Qdrant
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True,
            )
            
            logger.info(f"Successfully indexed {paper_id} with {len(images)} pages")
            return paper_id
            
        except Exception as e:
            logger.error(f"Failed to index PDF: {e}")
            raise
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search following demo approach."""
        if self.colpali_model is None:
            self.load_model()
            
        try:
            logger.info(f"Searching for: {query}")
            
            # Process query like in demo
            with torch.no_grad():
                batch_query = self.colpali_processor.process_queries([query]).to(
                    self.colpali_model.device
                )
                query_embedding = self.colpali_model(**batch_query)
            
            # Convert to multivector like in demo
            multivector_query = query_embedding[0].cpu().float().numpy().tolist()
            
            # Search in Qdrant using query_points like in demo
            search_result = self.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=multivector_query,
                limit=top_k,
                with_payload=True
            )
            
            # Format results
            results = []
            for point in search_result.points:
                results.append({
                    "paper_id": point.payload["paper_id"],
                    "page_number": point.payload["page_number"],
                    "score": point.score,
                    "pdf_path": point.payload["pdf_path"]
                })
            
            logger.info(f"Found {len(results)} results")
            return results
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise
    
    def get_document_info(self, paper_id: str) -> Dict:
        """Get document info from Qdrant."""
        try:
            # Search for any page of this document
            search_results = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="paper_id",
                            match=models.MatchValue(value=paper_id)
                        )
                    ]
                ),
                limit=1,
                with_payload=True
            )
            
            if search_results[0]:
                payload = search_results[0][0].payload
                return {
                    "paper_id": paper_id,
                    "pdf_path": payload["pdf_path"],
                    "num_pages": payload["total_pages"],
                    "indexed": True
                }
            return None
                
        except Exception as e:
            logger.error(f"Failed to get document info: {e}")
            return None
    
    def list_documents(self) -> List[Dict]:
        """List all indexed documents."""
        try:
            # Get all points and extract unique documents
            all_points = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                with_payload=True
            )
            
            documents = {}
            for point in all_points[0]:
                paper_id = point.payload["paper_id"]
                if paper_id not in documents:
                    documents[paper_id] = {
                        "paper_id": paper_id,
                        "pdf_path": point.payload["pdf_path"],
                        "num_pages": point.payload["total_pages"],
                        "indexed": True
                    }
            
            return list(documents.values())
            
        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            return []