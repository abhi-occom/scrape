"""
Scrapers package - Dynamic HTML scraping modules.
"""

from scrapers.renderer import (
    RendererScraper,
    SiteConfig,
    ScrapedPage,
    create_renderer_scraper,
    DEFAULT_SITES
)

__all__ = [
    'RendererScraper',
    'SiteConfig', 
    'ScrapedPage',
    'create_renderer_scraper',
    'DEFAULT_SITES'
]