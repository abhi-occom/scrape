"""
Render Engine - Playwright wrapper for capturing fully rendered HTML.
Handles dynamic/JavaScript-heavy websites that require client-side rendering.
Includes stealth mode to bypass bot detection (Cloudflare, etc.).
"""

from typing import Optional, List
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext
from dataclasses import dataclass
from playwright_stealth import Stealth
from utils.logger import log_info, log_error, log_success

_stealth = Stealth()


@dataclass
class RenderResult:
    """Result of a render operation."""
    url: str
    html: str
    status: int
    screenshot_path: Optional[str] = None
    error: Optional[str] = None


class RenderEngine:
    """
    Manages browser automation for rendering dynamic web pages.
    Uses Playwright to capture fully rendered HTML after JavaScript execution.
    """
    
    def __init__(self, headless: bool = True, timeout: int = 30000, stealth: bool = True):
        """
        Initialize render engine.
        
        Args:
            headless: Run browser in headless mode (no visible window)
            timeout: Page load timeout in milliseconds
            stealth: Enable stealth mode to bypass bot detection
        """
        self.headless = headless
        self.timeout = timeout
        self.stealth = stealth
        self.playwright = None
        self.browser: Optional[Browser] = None
        
    def __enter__(self):
        self.launch()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        
    def launch(self) -> bool:
        """
        Launch the browser.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                ] if self.stealth else []
            )
            log_success("Render engine launched", data={'headless': self.headless, 'stealth': self.stealth})
            return True
        except Exception as e:
            log_error(f"Failed to launch browser: {str(e)}")
            return False
            
    def close(self):
        """Close the browser and cleanup resources."""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
        log_info("Render engine closed")
        
    def _create_stealth_context(self) -> BrowserContext:
        """Create a browser context with realistic fingerprints."""
        return self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720},
            locale="en-AU",
            timezone_id="Australia/Sydney",
            color_scheme="light",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-AU,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            },
        )

    def new_page(self) -> Optional[Page]:
        """
        Create a new browser page/context with stealth applied.
        
        Returns:
            Page object or None if failed
        """
        if not self.browser:
            log_error("Browser not launched")
            return None
        context = self._create_stealth_context()
        page = context.new_page()
        if self.stealth:
            _stealth.apply_stealth_sync(page)
        return page
        
    def render(
        self, 
        url: str, 
        wait_condition: str = "networkidle",
        wait_selector: Optional[str] = None,
        wait_time: int = 0,
        screenshot_path: Optional[str] = None
    ) -> RenderResult:
        """
        Navigate to URL and capture fully rendered HTML.
        
        Args:
            url: URL to navigate to
            wait_condition: Wait condition ('networkidle', 'domcontentloaded', 'load')
            wait_selector: Optional CSS selector to wait for before capturing
            wait_time: Additional wait time in ms after page load
            screenshot_path: Optional path to save screenshot
            
        Returns:
            RenderResult with HTML and metadata
        """
        page = None
        try:
            page = self.new_page()
            if not page:
                return RenderResult(url=url, html="", status=0, error="Failed to create page")
            
            page.set_viewport_size({"width": 1280, "height": 720})
            
            log_info(f"Rendering page", data={'url': url, 'wait': wait_condition})
            
            navigation = page.goto(url, timeout=self.timeout, wait_until=wait_condition)
            
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=self.timeout)
                
            if wait_time > 0:
                page.wait_for_timeout(wait_time)
                
            html = page.content()
            status = navigation.status if navigation else 0
            
            if screenshot_path:
                page.screenshot(path=screenshot_path)
                
            log_success(f"Page rendered", data={'url': url, 'length': len(html)})
            
            return RenderResult(
                url=url,
                html=html,
                status=status,
                screenshot_path=screenshot_path
            )
            
        except Exception as e:
            log_error(f"Error rendering page", data={'url': url, 'error': str(e)})
            return RenderResult(url=url, html="", status=0, error=str(e))
            
        finally:
            if page:
                page.close()
                
    def render_batch(self, urls: List[str], **kwargs) -> List[RenderResult]:
        """
        Render multiple URLs in sequence.
        
        Args:
            urls: List of URLs to render
            **kwargs: Additional arguments passed to render()
            
        Returns:
            List of RenderResult objects
        """
        results = []
        for url in urls:
            result = self.render(url, **kwargs)
            results.append(result)
        return results


def create_render_engine(headless: bool = True) -> RenderEngine:
    """
    Factory function to create a render engine instance.
    
    Args:
        headless: Run browser in headless mode
        
    Returns:
        Configured RenderEngine instance
    """
    return RenderEngine(headless=headless)