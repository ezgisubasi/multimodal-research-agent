"""
Enhanced Research Paper Processor - Text + Images
Combines GROBID text extraction with PyMuPDF image extraction and saves data
"""

import requests
from bs4 import BeautifulSoup
import time
import logging
import warnings
from typing import Dict, List
import fitz  # PyMuPDF
from PIL import Image
import io
import json
import os
from pathlib import Path
import hashlib

warnings.filterwarnings("ignore", message="Unverified HTTPS request")
logger = logging.getLogger(__name__)


class EnhancedGROBIDProcessor:
    """GROBID processor with image extraction and storage."""
    
    def __init__(self, storage_dir: str = "data/papers"):
        self.server_url = "https://kermitt2-grobid.hf.space"
        self.timeout = 60
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def process_pdf(self, pdf_content: bytes, filename: str = "paper.pdf") -> Dict:
        """Process PDF, extract data, and save to storage."""
        logger.info(f"Processing: {filename}")
        start_time = time.time()
        
        # Generate unique paper ID
        paper_id = self._generate_paper_id(pdf_content, filename)
        paper_dir = self.storage_dir / paper_id
        
        try:
            # Check if already processed
            if (paper_dir / "data.json").exists():
                logger.info(f"Paper already processed: {paper_id}")
                with open(paper_dir / "data.json", 'r', encoding='utf-8') as f:
                    data = json.load(f)
                data['status'] = 'loaded_from_cache'
                return data
            
            # Create directories
            paper_dir.mkdir(parents=True, exist_ok=True)
            figures_dir = paper_dir / "figures"
            figures_dir.mkdir(exist_ok=True)
            
            # Extract text using GROBID
            text_result = self._extract_text_content(pdf_content, filename)
            
            # Extract and save images
            image_result = self._extract_and_save_images(pdf_content, figures_dir)
            
            # Combine results
            result = {
                'paper_id': paper_id,
                'filename': filename,
                'storage_path': str(paper_dir),
                **text_result, 
                **image_result
            }
            result['processing_time'] = time.time() - start_time
            result['status'] = 'success'
            
            # Save metadata as JSON
            with open(paper_dir / "data.json", 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Successfully processed in {result['processing_time']:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'processing_time': time.time() - start_time,
                'paper_id': paper_id
            }
    
    def _extract_text_content(self, pdf_content: bytes, filename: str) -> Dict:
        """Extract text using GROBID."""
        try:
            files_data = {'input': (filename, pdf_content, 'application/pdf')}
            response = requests.post(
                f"{self.server_url}/api/processFulltextDocument",
                files=files_data, timeout=self.timeout, verify=False
            )
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'xml')
                return {
                    'title': self._get_title(soup),
                    'authors': self._get_authors(soup),
                    'abstract': self._get_abstract(soup),
                    'sections': self._get_sections(soup),
                    'references': self._get_references(soup),
                    'keywords': self._get_keywords(soup)
                }
            else:
                raise Exception(f"GROBID HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return {
                'title': '', 'authors': [], 'abstract': '',
                'sections': [], 'references': [], 'keywords': []
            }
    
    def _extract_and_save_images(self, pdf_content: bytes, figures_dir: Path) -> Dict:
        """Extract images and save to disk."""
        try:
            pdf_doc = fitz.open(stream=pdf_content, filetype="pdf")
            figures = []
            
            for page_num in range(min(len(pdf_doc), 15)):
                page = pdf_doc[page_num]
                image_list = page.get_images(full=True)
                
                for img_index, img in enumerate(image_list[:5]):
                    try:
                        xref = img[0]
                        pix = fitz.Pixmap(pdf_doc, xref)
                        
                        if pix.n - pix.alpha < 4:
                            img_data = pix.tobytes("png")
                            pil_image = Image.open(io.BytesIO(img_data))
                            
                            # Save image
                            figure_id = f"page_{page_num + 1}_img_{img_index + 1}"
                            image_path = figures_dir / f"{figure_id}.png"
                            pil_image.save(image_path)
                            
                            figures.append({
                                'figure_id': figure_id,
                                'page': page_num + 1,
                                'size': pil_image.size,
                                'file_path': str(image_path)
                            })
                        
                        pix = None
                        
                    except Exception as e:
                        logger.warning(f"Failed to extract image {img_index} from page {page_num}: {e}")
                        continue
            
            pdf_doc.close()
            return {'figures': figures, 'total_figures': len(figures)}
            
        except Exception as e:
            logger.error(f"Image extraction failed: {e}")
            return {'figures': [], 'total_figures': 0}
    
    def _generate_paper_id(self, pdf_content: bytes, filename: str) -> str:
        """Generate unique ID for paper."""
        content_hash = hashlib.md5(pdf_content).hexdigest()[:12]
        clean_filename = "".join(c for c in filename if c.isalnum() or c in "._-")[:20]
        return f"{clean_filename}_{content_hash}"
    
    def _get_title(self, soup: BeautifulSoup) -> str:
        """Extract title."""
        title_elem = soup.find('title', {'type': 'main'}) or soup.find('title')
        return title_elem.get_text().strip() if title_elem else "Title not found"
    
    def _get_authors(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract authors."""
        authors = []
        
        for author in soup.find_all('author')[:10]:
            name_elem = author.find('persName')
            if name_elem:
                first_name = name_elem.find('forename')
                last_name = name_elem.find('surname')
                
                if first_name and last_name:
                    name = f"{first_name.get_text().strip()} {last_name.get_text().strip()}"
                elif last_name:
                    name = last_name.get_text().strip()
                else:
                    continue
                
                affiliation = author.find('affiliation')
                org = affiliation.find('orgName') if affiliation else None
                
                authors.append({
                    'name': name,
                    'affiliation': org.get_text().strip() if org else "Unknown"
                })
        
        return authors
    
    def _get_abstract(self, soup: BeautifulSoup) -> str:
        """Extract abstract."""
        abstract_elem = soup.find('abstract')
        if abstract_elem:
            text = abstract_elem.get_text().strip()
            if text.lower().startswith('abstract'):
                text = text[8:].strip()
            return text
        return "Abstract not found"
    
    def _get_sections(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract sections."""
        sections = []
        
        for div in soup.find_all('div')[:15]:
            head = div.find('head')
            if head and head.get_text().strip():
                title = head.get_text().strip()
                
                paragraphs = div.find_all('p')[:2]
                content = ' '.join([p.get_text().strip() for p in paragraphs])
                
                if len(content) > 300:
                    content = content[:300] + "..."
                
                sections.append({
                    'title': title,
                    'content': content
                })
        
        return sections
    
    def _get_references(self, soup: BeautifulSoup) -> List[str]:
        """Extract references."""
        references = []
        
        for biblStruct in soup.find_all('biblStruct')[:10]:
            parts = []
            
            authors = biblStruct.find_all('author')[:2]
            if authors:
                names = []
                for author in authors:
                    name = author.find('persName')
                    if name:
                        surname = name.find('surname')
                        if surname:
                            names.append(surname.get_text().strip())
                if names:
                    parts.append(', '.join(names))
            
            title = biblStruct.find('title')
            if title:
                parts.append(f'"{title.get_text().strip()}"')
            
            if parts:
                ref = '. '.join(parts)
                if len(ref) > 100:
                    ref = ref[:100] + "..."
                references.append(ref)
        
        return references
    
    def _get_keywords(self, soup: BeautifulSoup) -> List[str]:
        """Extract keywords."""
        keywords = []
        keywords_elem = soup.find('keywords')
        if keywords_elem:
            for term in keywords_elem.find_all('term'):
                keyword = term.get_text().strip()
                if keyword:
                    keywords.append(keyword)
        return keywords


def process_research_paper(pdf_content: bytes, filename: str = "paper.pdf", storage_dir: str = "data/papers") -> Dict:
    """Process a research paper PDF with text, images, and storage."""
    processor = EnhancedGROBIDProcessor(storage_dir=storage_dir)
    return processor.process_pdf(pdf_content, filename)