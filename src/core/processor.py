"""
Enhanced Research Paper Processor - Text + Images
Combines GROBID text extraction with PyMuPDF image extraction
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
import base64

# Suppress SSL warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

logger = logging.getLogger(__name__)


class EnhancedGROBIDProcessor:
    """Enhanced GROBID processor with image extraction."""
    
    def __init__(self):
        self.server_url = "https://kermitt2-grobid.hf.space"
        self.timeout = 60
    
    def process_pdf(self, pdf_content: bytes, filename: str = "paper.pdf") -> Dict:
        """Process PDF and return text + image information."""
        logger.info(f"Processing: {filename}")
        start_time = time.time()
        
        try:
            # 1. Extract text using GROBID
            text_result = self._extract_text_content(pdf_content, filename)
            
            # 2. Extract images using PyMuPDF
            image_result = self._extract_images(pdf_content)
            
            # 3. Combine results
            result = {**text_result, **image_result}
            result['processing_time'] = time.time() - start_time
            result['status'] = 'success'
            
            logger.info(f"Successfully processed in {result['processing_time']:.2f}s")
            logger.info(f"Found {len(result.get('figures', []))} figures")
            
            return result
            
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'processing_time': time.time() - start_time,
                'title': '', 'authors': [], 'abstract': '', 'sections': [],
                'references': [], 'figures': [], 'total_figures': 0
            }
    
    def _extract_text_content(self, pdf_content: bytes, filename: str) -> Dict:
        """Extract text using GROBID."""
        try:
            # Call GROBID API
            files_data = {'input': (filename, pdf_content, 'application/pdf')}
            
            response = requests.post(
                f"{self.server_url}/api/processFulltextDocument",
                files=files_data,
                timeout=self.timeout,
                verify=False
            )
            
            if response.status_code == 200:
                # Parse XML response
                soup = BeautifulSoup(response.text, 'xml')
                return self._extract_info(soup)
            else:
                raise Exception(f"GROBID HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return {
                'title': '', 'authors': [], 'abstract': '',
                'sections': [], 'references': [], 'keywords': []
            }
    
    def _extract_images(self, pdf_content: bytes) -> Dict:
        """Extract images using PyMuPDF."""
        try:
            # Open PDF
            pdf_doc = fitz.open(stream=pdf_content, filetype="pdf")
            figures = []
            
            # Extract images from each page
            for page_num in range(min(len(pdf_doc), 15)):  # First 15 pages
                page = pdf_doc[page_num]
                image_list = page.get_images(full=True)
                
                for img_index, img in enumerate(image_list[:5]):  # Max 5 per page
                    try:
                        # Extract image data
                        xref = img[0]
                        pix = fitz.Pixmap(pdf_doc, xref)
                        
                        if pix.n - pix.alpha < 4:  # Valid image
                            # Convert to PIL Image
                            img_data = pix.tobytes("png")
                            pil_image = Image.open(io.BytesIO(img_data))
                            
                            # Convert to base64 for storage
                            buffer = io.BytesIO()
                            pil_image.save(buffer, format='PNG')
                            img_base64 = base64.b64encode(buffer.getvalue()).decode()
                            
                            figures.append({
                                'figure_id': f"page_{page_num + 1}_img_{img_index + 1}",
                                'page': page_num + 1,
                                'image_index': img_index + 1,
                                'size': pil_image.size,
                                'format': 'PNG',
                                'image_data': img_base64[:100] + "...",  # Truncated for display
                                'full_size': len(img_base64)
                            })
                        
                        pix = None  # Free memory
                        
                    except Exception as e:
                        logger.warning(f"Failed to extract image {img_index} from page {page_num}: {e}")
                        continue
            
            pdf_doc.close()
            
            return {
                'figures': figures,
                'total_figures': len(figures)
            }
            
        except Exception as e:
            logger.error(f"Image extraction failed: {e}")
            return {'figures': [], 'total_figures': 0}
    
    def _extract_info(self, soup: BeautifulSoup) -> Dict:
        """Extract information from GROBID XML."""
        return {
            'title': self._get_title(soup),
            'authors': self._get_authors(soup),
            'abstract': self._get_abstract(soup),
            'sections': self._get_sections(soup),
            'references': self._get_references(soup),
            'keywords': self._get_keywords(soup)
        }
    
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
                
                # Get affiliation
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
                
                # Get content
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
            
            # Authors
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
            
            # Title
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


# Simple function for direct use
def process_research_paper(pdf_content: bytes, filename: str = "paper.pdf") -> Dict:
    """Process a research paper PDF with text and images."""
    processor = EnhancedGROBIDProcessor()
    return processor.process_pdf(pdf_content, filename)