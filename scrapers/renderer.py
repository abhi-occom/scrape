"""
Renderer Scraper - Orchestrates rendered HTML scraping.
Manages site configurations, URL queues, and result processing.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import os

from utils.render_engine import RenderEngine, RenderResult, create_render_engine
from utils.html_parser import HTMLParser, parse_html
from utils.logger import log_info, log_error, log_success, log_warning


@dataclass
class SiteConfig:
    """Configuration for scraping a specific site."""
    name: str
    base_url: str
    selectors: Dict[str, str]  # e.g., {'plan_name': '.plan-title', 'price': '.price'}
    wait_selector: Optional[str] = None
    wait_time: int = 0
    pagination: Optional[str] = None  # CSS selector for next page button
    max_pages: int = 10


@dataclass
class ScrapedPage:
    """Represents a scraped page with metadata."""
    url: str
    config_name: str
    html: str
    parsed_data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = False
    error: Optional[str] = None


class RendererScraper:
    """
    Orchestrates rendered HTML scraping across multiple sites.
    Manages site configurations, rendering, parsing, and result storage.
    """
    
    def __init__(self, headless: bool = True):
        """
        Initialize renderer scraper.
        
        Args:
            headless: Run browser in headless mode
        """
        self.headless = headless
        self.sites: Dict[str, SiteConfig] = {}
        self.results: List[ScrapedPage] = []
        
    def add_site(self, config: SiteConfig):
        """
        Add a site configuration.
        
        Args:
            config: SiteConfig instance
        """
        self.sites[config.name] = config
        log_info(f"Added site config", data={'name': config.name, 'url': config.base_url})
        
    def scrape_site(self, site_name: str) -> List[ScrapedPage]:
        """
        Scrape all pages for a configured site.
        
        Args:
            site_name: Name of site to scrape
            
        Returns:
            List of ScrapedPage results
        """
        if site_name not in self.sites:
            log_error(f"Unknown site", data={'site': site_name})
            return []
            
        config = self.sites[site_name]
        results = []
        
        with create_render_engine(headless=self.headless) as engine:
            page_url = config.base_url
            page_num = 0
            
            while page_num < config.max_pages:
                log_info(f"Scraping page", data={'site': site_name, 'url': page_url, 'page': page_num + 1})
                
                result = engine.render(
                    url=page_url,
                    wait_selector=config.wait_selector,
                    wait_time=config.wait_time
                )
                
                scraped_page = self._process_result(result, config)
                results.append(scraped_page)
                
                if not scraped_page.success:
                    log_warning(f"Failed to scrape page", data={'url': page_url})
                    
                # Check for pagination
                if not config.pagination:
                    break
                    
                # Parse next page URL
                next_url = self._get_next_page_url(scraped_page.html, config.pagination, config.base_url)
                if not next_url or next_url == page_url:
                    break
                    
                page_url = next_url
                page_num += 1
                
            log_success(f"Completed scraping site", data={'site': site_name, 'pages': len(results)})
            
        self.results.extend(results)
        return results
        
    def scrape_all_sites(self) -> Dict[str, List[ScrapedPage]]:
        """
        Scrape all configured sites.
        
        Returns:
            Dictionary mapping site names to their results
        """
        all_results = {}
        for site_name in self.sites:
            results = self.scrape_site(site_name)
            all_results[site_name] = results
        return all_results
        
    def _process_result(self, result: RenderResult, config: SiteConfig) -> ScrapedPage:
        """
        Process a render result and extract data.
        
        Args:
            result: RenderResult from engine
            config: SiteConfig for parsing
            
        Returns:
            ScrapedPage with extracted data
        """
        scraped = ScrapedPage(
            url=result.url,
            config_name=config.name,
            html=result.html,
            success=result.error is None,
            error=result.error
        )
        
        if result.error:
            return scraped
            
        # Parse HTML and extract data
        parser = parse_html(result.html)
        if parser:
            scraped.parsed_data = self._extract_data(parser, config.selectors)
            
        return scraped
        
    def _extract_data(self, parser: HTMLParser, selectors: Dict[str, str]) -> Dict[str, Any]:
        """
        Extract data from parser using configured selectors.
        
        Args:
            parser: HTMLParser instance
            selectors: Dict mapping field names to CSS selectors
            
        Returns:
            Dictionary of extracted data
        """
        data = {}
        for field_name, selector in selectors.items():
            value = parser.extract_text(selector)
            if value:
                data[field_name] = value
        return data
        
    def _get_next_page_url(
        self, 
        html: str, 
        pagination_selector: str, 
        base_url: str
    ) -> Optional[str]:
        """
        Get URL for next page using pagination selector.
        
        Args:
            html: Page HTML
            pagination_selector: CSS selector for next button/link
            base_url: Base URL for resolving relative links
            
        Returns:
            Next page URL or None
        """
        parser = parse_html(html)
        if not parser:
            return None
            
        next_link = parser.extract_attribute(pagination_selector, 'href')
        if next_link:
            from urllib.parse import urljoin
            return urljoin(base_url, next_link)
            
        return None
        
    def save_results(self, output_path: str) -> bool:
        """
        Save scraping results to JSON file.
        
        Args:
            output_path: Path to output JSON file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            results_data = []
            for page in self.results:
                results_data.append({
                    'url': page.url,
                    'config_name': page.config_name,
                    'timestamp': page.timestamp,
                    'success': page.success,
                    'error': page.error,
                    'parsed_data': page.parsed_data
                })
                
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results_data, f, indent=2, ensure_ascii=False)
                
            log_success(f"Saved results", data={'path': output_path, 'count': len(results_data)})
            return True
            
        except Exception as e:
            log_error(f"Failed to save results", data={'error': str(e)})
            return False


# Default site configurations for ISP providers
DEFAULT_SITES = [
    SiteConfig(
        name="telstra",
        base_url="https://www.telstra.com.au/internet/home-nbn",
        selectors={
            'plan_name': '.plan-name',
            'price': '.plan-price',
            'speed': '.plan-speed'
        },
        wait_selector=".plan-card",
        wait_time=1000
    ),
    SiteConfig(
        name="optus",
        base_url="https://www.optus.com.au/internet/nbn-plans",
        selectors={
            'plan_name': '.plan-title',
            'price': '.price-amount',
            'speed': '.speed-value'
        },
        wait_selector=".plan-list",
        wait_time=1000
    )
]


def create_renderer_scraper(
    sites: Optional[List[SiteConfig]] = None,
    headless: bool = True
) -> RendererScraper:
    """
    Factory function to create configured renderer scraper.
    
    Args:
        sites: Optional list of SiteConfig instances
        headless: Run browser in headless mode
        
    Returns:
        Configured RendererScraper instance
    """
    scraper = RendererScraper(headless=headless)
    
    # Add default sites if none provided
    if not sites:
        for site_config in DEFAULT_SITES:
            scraper.add_site(site_config)
    else:
        for site_config in sites:
            scraper.add_site(site_config)
            
    return scraper