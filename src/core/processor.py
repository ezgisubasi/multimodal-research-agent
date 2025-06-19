"""
Simple Research Paper Processor using GROBID
Uses the working HuggingFace GROBID server.
"""

import requests
from bs4 import BeautifulSoup
import time
import logging
import warnings
from typing import Dict, List

# Suppress SSL warnings
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

logger = logging.getLogger(__name__)


class GROBIDProcessor:
    """Simple GROBID processor using HuggingFace server."""
    
    def __init__(self):
        self.server_url = "https://kermitt2-grobid.hf.space"
        self.timeout = 60
    
    def process_pdf(self, pdf_content: bytes, filename: str = "paper.pdf") -> Dict:
        """Process PDF and return structured information."""
        logger.info(f"Processing: {filename}")
        start_time = time.time()
        
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
                result = self._extract_info(soup)
                result['processing_time'] = time.time() - start_time
                result['status'] = 'success'
                
                logger.info(f"Successfully processed in {result['processing_time']:.2f}s")
                return result
            else:
                raise Exception(f"HTTP {response.status_code}")
                
        except Exception as e:
            logger.error(f"Processing failed: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'processing_time': time.time() - start_time,
                'title': '',
                'authors': [],
                'abstract': '',
                'sections': [],
                'references': []
            }
    
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
    """Process a research paper PDF."""
    processor = GROBIDProcessor()
    return processor.process_pdf(pdf_content, filename)