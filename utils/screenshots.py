"""Screenshot helpers for scraper debug runs."""

import os
import re
from datetime import datetime
from urllib.parse import urlparse

from utils.progress import get_progress


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENSHOT_ROOT = os.path.join(BASE_DIR, "output", "screenshots")


def capture_page_screenshot(page, provider: str = None, label: str = "loaded") -> dict:
    """Capture a screenshot for a loaded Playwright page."""
    try:
        # Check if page is closed before attempting screenshot
        if page.is_closed():
            return {}
        
        url = page.url
        if not url or url.startswith(("about:", "chrome:", "edge:")):
            return {}

        provider = provider or get_progress().get("current_provider") or "unknown"
        provider = _safe_part(provider)
        provider_dir = os.path.join(SCREENSHOT_ROOT, provider)
        os.makedirs(provider_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        parsed = urlparse(url)
        url_part = _safe_part(f"{parsed.netloc}{parsed.path}")[:90] or "page"
        filename = f"{timestamp}_{_safe_part(label)}_{url_part}.png"
        path = os.path.join(provider_dir, filename)

        # Take screenshot with timeout to avoid hanging
        page.screenshot(path=path, full_page=True, timeout=10000)

        relative_path = os.path.relpath(path, SCREENSHOT_ROOT).replace(os.sep, "/")
        return {
            "path": path,
            "relative_path": relative_path,
            "url": f"/screenshots/{relative_path}",
        }
    except Exception as e:
        # Silently fail if page closed or screenshot failed
        # Don't spam logs with screenshot errors
        if "closed" not in str(e).lower():
            print(f"Screenshot warning: {e}")
        return {}


def _safe_part(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "_", str(value or "").strip())
    return value.strip("._-") or "unknown"
