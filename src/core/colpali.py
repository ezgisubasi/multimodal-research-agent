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
from tqdm import tqdm

logger = logging.getLogger(__name__)


class ColPaliSearcher:
    """Simple ColPali implementation with binary quantization."""
    
    def __init__(self, model_name: str = "vidore/colpali", device: str = "cpu", qdrant_url: str = "http://localhost:6333"):
        self.model_name = model_name
        self.device = device
        self.qdrant_client = QdrantClient(url=qdrant_url) if qdrant_url != ":memory:" else QdrantClient(":memory:")
        self.collection_name = "research_papers_binary"
        self.colpali_model = None
        self.colpali_processor = None
        self._setup_collection()
        
    def _setup_collection(self):
        """Setup Qdrant collection with binary quantization."""
        try:
            collections = self.qdrant_client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            if self.collection_name not in collection_names:
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    on_disk_payload=True,
                    vectors_config=models.VectorParams(
                        size=128,
                        distance=models.Distance.COSINE,
                        on_disk=True,
                        multivector_config=models.MultiVectorConfig(
                            comparator=models.MultiVectorComparator.MAX_SIM
                        ),
                        quantization_config=models.BinaryQuantization(
                            binary=models.BinaryQuantizationConfig(
                                always_ram=True
                            ),
                        ),
                    ),
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to setup Qdrant collection: {e}")
            raise
    
    def load_model(self):
        """Load ColPali model."""
        try:
            logger.info(f"Loading ColPali model: {self.model_name}")
            
            self.colpali_model = ColPali.from_pretrained(
                self.model_name,
                torch_dtype=torch.bfloat16,
                device_map=self.device if self.device != "cpu" else "cpu",
            )
            
            self.colpali_processor = ColPaliProcessor.from_pretrained(
                "vidore/colpaligemma-3b-pt-448-base",
                use_fast=True  # Use fast processor for speed
            )
            
            logger.info("ColPali model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load ColPali model: {e}")
            raise
    
    def index_pdf(self, pdf_path: str, paper_id: str = None, batch_size: int = 4, max_pages: int = 10) -> str:
        """Index PDF for search."""
        if self.colpali_model is None:
            self.load_model()
            
        try:
            # Generate paper ID
            if paper_id is None:
                with open(pdf_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()[:8]
                paper_id = f"paper_{file_hash}"
            
            logger.info(f"Indexing PDF: {pdf_path} as {paper_id}")
            
            # Convert PDF to images (limited pages for speed)
            images = self._pdf_to_images(pdf_path, max_pages)
            
            # Process in batches
            all_points = []
            
            with tqdm(total=len(images), desc="Processing pages") as pbar:
                for i in range(0, len(images), batch_size):
                    batch_images = images[i:i + batch_size]
                    
                    with torch.no_grad():
                        batch_processed = self.colpali_processor.process_images(batch_images).to(
                            self.colpali_model.device
                        )
                        image_embeddings = self.colpali_model(**batch_processed)
                    
                    for j, embedding in enumerate(image_embeddings):
                        page_idx = i + j
                        multivector = embedding.cpu().float().numpy().tolist()
                        
                        # Use integer ID for Qdrant compatibility
                        point_id = hash(f"{paper_id}_page_{page_idx}") % (2**63 - 1)
                        
                        point = models.PointStruct(
                            id=point_id,
                            vector=multivector,
                            payload={
                                "paper_id": paper_id,
                                "page_number": page_idx,
                                "pdf_path": pdf_path,
                                "total_pages": len(images)
                            }
                        )
                        all_points.append(point)
                    
                    pbar.update(len(batch_images))
            
            # Upload to Qdrant
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=all_points,
                wait=True,
            )
            
            logger.info(f"Successfully indexed {paper_id} with {len(images)} pages")
            return paper_id
            
        except Exception as e:
            logger.error(f"Failed to index PDF: {e}")
            raise
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search across indexed documents."""
        if self.colpali_model is None:
            self.load_model()
            
        try:
            logger.info(f"Searching for: {query}")
            
            # Process query
            with torch.no_grad():
                batch_query = self.colpali_processor.process_queries([query]).to(
                    self.colpali_model.device
                )
                query_embedding = self.colpali_model(**batch_query)
            
            # Convert to multivector
            multivector_query = query_embedding[0].cpu().float().numpy().tolist()
            
            # Search with binary quantization optimization
            search_result = self.qdrant_client.query_points(
                collection_name=self.collection_name,
                query=multivector_query,
                limit=top_k,
                with_payload=True,
                search_params=models.SearchParams(
                    quantization=models.QuantizationSearchParams(
                        ignore=False,
                        rescore=True,
                        oversampling=2.0,
                    )
                )
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
    
    def _pdf_to_images(self, pdf_path: str, max_pages: int = 10) -> List[Image.Image]:
        """Convert PDF pages to images."""
        try:
            doc = fitz.open(pdf_path)
            images = []
            
            num_pages = min(len(doc), max_pages)
            logger.info(f"Processing {num_pages} pages")
            
            for page_num in range(num_pages):
                page = doc[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))  # Reduced quality for speed
                img_data = pix.tobytes("png")
                
                from io import BytesIO
                img = Image.open(BytesIO(img_data))
                images.append(img)
                
            doc.close()
            return images
            
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            raise