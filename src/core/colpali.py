import torch
from PIL import Image
import fitz  # PyMuPDF
from colpali_engine.models import ColPali, ColPaliProcessor
import hashlib
from typing import List, Dict
import logging
from qdrant_client import QdrantClient
from qdrant_client.http import models
from tqdm import tqdm

logger = logging.getLogger(__name__)


class ColPaliSearcher:
    """Simple ColPali implementation for Qdrant Cloud."""
    
    def __init__(self, model_name: str, device: str, qdrant_url: str, qdrant_api_key: str):
        self.model_name = model_name
        self.device = device
        self.collection_name = "research_papers"
        
        # Qdrant Cloud client (required)
        if not qdrant_url or not qdrant_api_key:
            raise ValueError("Qdrant Cloud URL and API key are required")
            
        self.qdrant_client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        self.colpali_model = None
        self.colpali_processor = None
        self._setup_collection()
        
    def _setup_collection(self):
        """Setup Qdrant collection."""
        try:
            collections = [col.name for col in self.qdrant_client.get_collections().collections]
            
            if self.collection_name not in collections:
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=models.VectorParams(
                        size=128,
                        distance=models.Distance.COSINE,
                        multivector_config=models.MultiVectorConfig(
                            comparator=models.MultiVectorComparator.MAX_SIM
                        ),
                        quantization_config=models.BinaryQuantization(
                            binary=models.BinaryQuantizationConfig(always_ram=True)
                        ),
                    ),
                )
                logger.info(f"Created collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to setup collection: {e}")
            raise
    
    def load_model(self):
        """Load ColPali model."""
        if self.colpali_model is not None:
            return
            
        try:
            logger.info(f"Loading ColPali model: {self.model_name}")
            
            self.colpali_model = ColPali.from_pretrained(
                self.model_name,
                torch_dtype=torch.bfloat16,
                device_map=self.device if self.device != "cpu" else "cpu",
            )
            
            self.colpali_processor = ColPaliProcessor.from_pretrained(
                "vidore/colpaligemma-3b-pt-448-base",
                use_fast = True
            )
            
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def index_pdf(self, pdf_path: str, paper_id: str = None, batch_size: int = 4) -> str:
        """Index PDF document."""
        self.load_model()
        
        # Generate paper ID
        if paper_id is None:
            with open(pdf_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()[:8]
            paper_id = f"paper_{file_hash}"
        
        logger.info(f"Indexing PDF: {paper_id}")
        
        # Convert PDF to images
        images = self._pdf_to_images(pdf_path)
        
        # Process in batches
        for i in range(0, len(images), batch_size):
            batch_images = images[i:i + batch_size]
            
            # Encode images
            with torch.no_grad():
                batch_processed = self.colpali_processor.process_images(batch_images).to(
                    self.colpali_model.device
                )
                embeddings = self.colpali_model(**batch_processed)
            
            # Create points
            points = []
            for j, embedding in enumerate(embeddings):
                page_idx = i + j
                multivector = embedding.cpu().float().numpy().tolist()
                
                points.append(
                    models.PointStruct(
                        id=hash(f"{paper_id}_{page_idx}") % (2**63),  # Unique ID
                        vector=multivector,
                        payload={
                            "paper_id": paper_id,
                            "page_number": page_idx,
                            "pdf_path": pdf_path,
                            "total_pages": len(images)
                        }
                    )
                )
            
            # Upload to Qdrant
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=points,
                wait=True
            )
        
        logger.info(f"Indexed {paper_id} with {len(images)} pages")
        return paper_id
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search documents."""
        self.load_model()
        
        logger.info(f"Searching: {query}")
        
        # Encode query
        with torch.no_grad():
            batch_query = self.colpali_processor.process_queries([query]).to(
                self.colpali_model.device
            )
            query_embedding = self.colpali_model(**batch_query)
        
        multivector_query = query_embedding[0].cpu().float().numpy().tolist()
        
        # Search
        results = self.qdrant_client.query_points(
            collection_name=self.collection_name,
            query=multivector_query,
            limit=top_k,
            timeout=60
        )
        
        # Format results
        formatted_results = []
        for point in results.points:
            formatted_results.append({
                "paper_id": point.payload["paper_id"],
                "page_number": point.payload["page_number"],
                "score": point.score,
                "pdf_path": point.payload["pdf_path"]
            })
        
        return formatted_results
    
    def get_documents(self) -> List[Dict]:
        """Get list of indexed documents."""
        try:
            # Get unique documents
            results = self.qdrant_client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                with_payload=True
            )[0]
            
            # Group by paper_id
            docs = {}
            for point in results:
                paper_id = point.payload["paper_id"]
                if paper_id not in docs:
                    docs[paper_id] = {
                        "paper_id": paper_id,
                        "pdf_path": point.payload["pdf_path"],
                        "total_pages": point.payload["total_pages"]
                    }
            
            return list(docs.values())
        except Exception as e:
            logger.error(f"Failed to get documents: {e}")
            return []
    
    def _pdf_to_images(self, pdf_path: str) -> List[Image.Image]:
        """Convert PDF to images."""
        doc = fitz.open(pdf_path)
        images = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            img_data = pix.tobytes("png")
            
            from io import BytesIO
            img = Image.open(BytesIO(img_data))
            images.append(img)
            
        doc.close()
        return images