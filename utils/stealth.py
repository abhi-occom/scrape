"""
Stealth browser utilities.
Shared helpers for creating stealth Playwright browser instances.
Uses playwright-stealth v2 API.
"""

from playwright.sync_api import Browser, BrowserContext, Page
from playwright_stealth import Stealth

_stealth = Stealth()


def create_stealth_browser(playwright, headless: bool = True) -> Browser:
    """Create a Chromium browser with anti-detection flags."""
    return playwright.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )


def create_stealth_context(browser: Browser) -> BrowserContext:
    """Create a browser context with realistic fingerprints."""
    return browser.new_context(
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


def create_stealth_page(browser: Browser) -> Page:
    """Create a stealth page with full anti-detection applied."""
    context = create_stealth_context(browser)
    page = context.new_page()
    _stealth.apply_stealth_sync(page)
    return page
