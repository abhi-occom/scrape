"""
Aussie Broadband ISP plan scraper.

CURRENT STATUS: BLOCKED
Aussie Broadband uses Cloudflare Turnstile (managed challenge) on every page and
API endpoint. All automated scraping approaches have been tried and blocked (403):
  - Playwright Chromium (headless + stealth)
  - Playwright Firefox (headless + headed)
  - curl_cffi with Chrome/Safari TLS impersonation (chrome110–124, safari17_0)
  - Direct API endpoints (/api/plans, /api/products, /_next/data/)
  - Wayback Machine (no archived copies exist — Cloudflare blocks archiving too)

To add Aussie Broadband data, either:
  1. Arrange API access directly with Aussie Broadband
  2. Manually populate output/scrape_isp_aussie/json/aussie_all_plans.json
"""

from typing import List, Dict, Any
import config
from utils.logger import log_info, log_warning


AUSSIE_WEBSITE_URL = "https://www.aussiebroadband.com.au/broadband/nbn/"
BLOCKED_REASON = "Cloudflare Turnstile (managed challenge) — all automated methods blocked"


def scrape_aussie_plans() -> List[Dict[str, Any]]:
    """
    Scrape Aussie Broadband ISP plans.

    BLOCKED: Aussie Broadband uses Cloudflare Turnstile (managed) on all pages.
    Every automated method has been tested and returns HTTP 403:
      - Playwright Chromium stealth, Firefox headless/headed
      - curl_cffi Chrome/Safari TLS impersonation
      - Direct API endpoint probing
    Returns empty list immediately to avoid wasting time on each scrape run.
    """
    log_warning(
        f"Aussie Broadband scraper skipped — {BLOCKED_REASON}",
        provider="aussie",
        data={"status": "blocked", "reason": BLOCKED_REASON}
    )
    return []


def scrape_via_playwright() -> List[Dict[str, Any]]:
    """Stub — blocked by Cloudflare Turnstile. See module docstring."""
    log_warning(f"Aussie Broadband blocked — {BLOCKED_REASON}", provider="aussie")
    return []

