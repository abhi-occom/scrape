"""
HTML Parser - Utilities for parsing and extracting data from rendered HTML.
Uses BeautifulSoup for HTML parsing with lxml for XPath support.
"""

from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from bs4 import BeautifulSoup, Tag
try:
    from lxml import etree
    LXML_AVAILABLE = True
except ImportError:
    LXML_AVAILABLE = False


@dataclass
class ParseResult:
    """Result of an HTML parsing operation."""
    success: bool
    data: Union[Any, List[Any]]
    error: Optional[str] = None


class HTMLParser:
    """
    Parses HTML content and extracts structured data.
    Supports CSS selectors and XPath expressions.
    """
    
    def __init__(self, html: str = ""):
        """
        Initialize parser with optional HTML content.
        
        Args:
            html: HTML content to parse (optional, can set later)
        """
        self.html = html
        self.soup = None
        if html:
            self.parse(html)
            
    def parse(self, html: str) -> bool:
        """
        Parse HTML content into BeautifulSoup object.
        
        Args:
            html: HTML string to parse
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.html = html
            self.soup = BeautifulSoup(html, 'lxml')
            return True
        except Exception as e:
            self.soup = None
            return False
            
    def extract_by_selector(self, selector: str, single: bool = False) -> Union[Optional[Tag], List[Tag]]:
        """
        Extract elements using CSS selector.
        
        Args:
            selector: CSS selector string
            single: If True, return single element, otherwise return list
            
        Returns:
            Tag(s) matching selector or None
        """
        if not self.soup:
            return None if single else []
            
        try:
            if single:
                return self.soup.select_one(selector)
            return self.soup.select(selector)
        except Exception:
            return None if single else []
            
    def extract_text(self, selector: str, default: str = "") -> str:
        """
        Extract text content from element(s) matching selector.
        
        Args:
            selector: CSS selector
            default: Default value if no match found
            
        Returns:
            Extracted text or default
        """
        element = self.extract_by_selector(selector, single=True)
        if element:
            return element.get_text(strip=True)
        return default
        
    def extract_attribute(
        self, 
        selector: str, 
        attr: str, 
        default: Optional[str] = None
    ) -> Optional[str]:
        """
        Extract attribute value from element matching selector.
        
        Args:
            selector: CSS selector
            attr: Attribute name to extract
            default: Default value if no match
            
        Returns:
            Attribute value or default
        """
        element = self.extract_by_selector(selector, single=True)
        if element and element.has_attr(attr):
            return element[attr]
        return default
        
    def extract_multiple(
        self, 
        selector: str, 
        attr: Optional[str] = None
    ) -> List[str]:
        """
        Extract text or attribute values from multiple elements.
        
        Args:
            selector: CSS selector
            attr: Optional attribute name (if None, extracts text)
            
        Returns:
            List of extracted values
        """
        elements = self.extract_by_selector(selector, single=False)
        results = []
        
        for elem in elements:
            if attr:
                if elem.has_attr(attr):
                    results.append(elem[attr])
            else:
                text = elem.get_text(strip=True)
                if text:
                    results.append(text)
                    
        return results
        
    def extract_table(self, table_selector: str) -> List[Dict[str, str]]:
        """
        Extract data from HTML table.
        
        Args:
            table_selector: CSS selector for the table
            
        Returns:
            List of row dictionaries
        """
        table = self.extract_by_selector(table_selector, single=True)
        if not table:
            return []
            
        rows = []
        headers = []
        
        # Get headers
        header_cells = table.select('thead th, thead td')
        if header_cells:
            headers = [cell.get_text(strip=True) for cell in header_cells]
            
        # Get body rows
        body_rows = table.select('tbody tr')
        if not body_rows:
            body_rows = table.select('tr')
            
        for row in body_rows:
            cells = row.select('td, th')
            if cells:
                row_data = {}
                for i, cell in enumerate(cells):
                    key = headers[i] if i < len(headers) else f"col_{i}"
                    row_data[key] = cell.get_text(strip=True)
                    
                if any(row_data.values()):  # Skip empty rows
                    rows.append(row_data)
                    
        return rows
        
    def find_by_xpath(self, xpath: str) -> List[str]:
        """
        Find elements using XPath expression.
        Requires lxml to be installed.
        
        Args:
            xpath: XPath expression
            
        Returns:
            List of matching element text content
        """
        if not LXML_AVAILABLE or not self.html:
            return []
            
        try:
            tree = etree.HTML(self.html)
            elements = tree.xpath(xpath)
            return [elem.text_content().strip() if hasattr(elem, 'text_content') else str(elem) for elem in elements]
        except Exception:
            return []
            
    def get_page_links(self, base_url: Optional[str] = None) -> List[str]:
        """
        Extract all links from the parsed HTML.
        
        Args:
            base_url: Optional base URL to make relative links absolute
            
        Returns:
            List of URLs
        """
        if not self.soup:
            return []
            
        links = []
        for a in self.soup.find_all('a', href=True):
            href = a['href']
            if base_url and not href.startswith(('http://', 'https://')):
                from urllib.parse import urljoin
                href = urljoin(base_url, href)
            links.append(href)
            
        return links
        
    def save_html(self, path: str) -> bool:
        """
        Save parsed HTML to file.
        
        Args:
            path: File path to save HTML
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.html)
            return True
        except Exception:
            return False


def parse_html(html: str) -> Optional[HTMLParser]:
    """
    Factory function to create parser and parse HTML.
    
    Args:
        html: HTML string to parse
        
    Returns:
        HTMLParser instance or None if parsing fails
    """
    parser = HTMLParser()
    if parser.parse(html):
        return parser
    return None