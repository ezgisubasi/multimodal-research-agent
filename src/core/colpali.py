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
    """ColPali implementation with binary quantization following demo approach."""
    
    def __init__(self, model_name: str = "vidore/colpali", device: str = "cpu", qdrant_url: str = "http://localhost:6333"):
        self.model_name = model_name
        self.device = device
        self.qdrant_client = QdrantClient(url=qdrant_url) if qdrant_url != ":memory:" else QdrantClient(":memory:")
        self.collection_name = "research_papers_binary"
        self.colpali_model = None
        self.colpali_processor = None
        self.setup_qdrant_collection()
        
    def setup_qdrant_collection(self):
        """Setup Qdrant collection with binary quantization like demo."""
        try:
            # Check if collection exists
            collections = self.qdrant_client.get_collections().collections
            collection_names = [col.name for col in collections]
            
            if self.collection_name not in collection_names:
                # Create collection with binary quantization like in demo
                self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    on_disk_payload=True,  # store payload on disk
                    vectors_config=models.VectorParams(
                        size=128,
                        distance=models.Distance.COSINE,
                        on_disk=True,  # move original vectors to disk
                        multivector_config=models.MultiVectorConfig(
                            comparator=models.MultiVectorComparator.MAX_SIM
                        ),
                        quantization_config=models.BinaryQuantization(
                            binary=models.BinaryQuantizationConfig(
                                always_ram=True  # keep only quantized vectors in RAM
                            ),
                        ),
                    ),
                )
                logger.info(f"Created Qdrant collection with binary quantization: {self.collection_name}")
            else:
                logger.info(f"Using existing Qdrant collection: {self.collection_name}")
                
        except Exception as e:
            logger.error(f"Failed to setup Qdrant collection: {e}")
            raise
    
    def load_model(self):
        """Load ColPali model exactly like demo."""
        try:
            logger.info(f"Loading ColPali model: {self.model_name}")
            
            # Load model and processor exactly like demo
            self.colpali_model = ColPali.from_pretrained(
                self.model_name,
                torch_dtype=torch.bfloat16,
                device_map=self.device if self.device != "cpu" else "cpu",
            )
            
            self.colpali_processor = ColPaliProcessor.from_pretrained(
                "vidore/colpaligemma-3b-pt-448-base",
                use_fast=True
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
    
    def index_pdf(self, pdf_path: str, paper_id: str = None, batch_size: int = 4) -> str:
        """Index PDF with batching like demo."""
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
            
            # Process in batches like demo
            all_points = []
            
            with tqdm(total=len(images), desc="Processing pages") as pbar:
                for i in range(0, len(images), batch_size):
                    batch_images = images[i:i + batch_size]
                    
                    # Process images like in demo
                    with torch.no_grad():
                        batch_processed = self.colpali_processor.process_images(batch_images).to(
                            self.colpali_model.device
                        )
                        image_embeddings = self.colpali_model(**batch_processed)
                    
                    # Prepare points for this batch
                    for j, embedding in enumerate(image_embeddings):
                        page_idx = i + j
                        # Convert to multivector like demo
                        multivector = embedding.cpu().float().numpy().tolist()
                        
                        point = models.PointStruct(
                            id=f"{paper_id}_page_{page_idx}",
                            vector=multivector,
                            payload={
                                "paper_id": paper_id,
                                "page_number": page_idx,
                                "pdf_path": pdf_path,
                                "total_pages": len(images),
                                "source": "research_paper"
                            }
                        )
                        all_points.append(point)
                    
                    pbar.update(len(batch_images))
            
            # Upload all points to Qdrant
            self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=all_points,
                wait=True,
            )
            
            # Update indexing threshold like demo
            self.qdrant_client.update_collection(
                collection_name=self.collection_name,
                optimizer_config=models.OptimizersConfigDiff(indexing_threshold=10),
            )
            
            logger.info(f"Successfully indexed {paper_id} with {len(images)} pages")
            return paper_id
            
        except Exception as e:
            logger.error(f"Failed to index PDF: {e}")
            raise
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """Search with binary quantization settings like demo."""
        if self.colpali_model is None:
            self.load_model()
            
        try:
            logger.info(f"Searching for: {query}")
            
            # Process query exactly like demo
            with torch.no_grad():
                batch_query = self.colpali_processor.process_queries([query]).to(
                    self.colpali_model.device
                )
                query_embedding = self.colpali_model(**batch_query)
            
            # Convert to multivector like demo
            multivector_query = query_embedding[0].cpu().float().numpy().tolist()
            
            # Search with binary quantization settings like demo
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
    
    def get_document_info(self, paper_id: str) -> Dict:
        """Get document info from Qdrant."""
        try:
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