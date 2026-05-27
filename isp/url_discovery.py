"""
URL Discovery Engine
--------------------
Crawls an ISP website starting from a base URL and discovers
inner pages that are likely to contain broadband plan information
(NBN, Opticomm, RedTrain, Supa, 5G, Fixed Wireless, etc.).

Strategy:
  1. Load the base URL with Playwright (handles JS-rendered nav menus).
  2. Extract every internal <a href> from the rendered DOM.
  3. Score each URL against a weighted keyword dictionary.
  4. Recursively follow high-scoring links up to *depth* levels.
  5. Return a de-duplicated, ranked list of candidate plan page URLs.
"""

import re
from urllib.parse import urljoin, urlparse, urlunparse
from typing import List, Dict, Set, Optional
from playwright.sync_api import sync_playwright, Page, Browser

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import log_info, log_warning, log_error


# ── Keyword scoring ──────────────────────────────────────────────
# Higher weight = stronger signal that the page contains plan data.

PLAN_KEYWORDS: Dict[str, int] = {
    # Network types (primary targets)
    'nbn':              10,
    'opticomm':         10,
    'redtrain':         10,
    'supa':             10,
    'red-train':        10,

    # Generic plan/broadband terms
    'plans':             8,
    'broadband':         8,
    'internet':          7,
    'home-internet':     9,
    'home-broadband':    9,
    'fibre':             7,
    'fiber':             7,
    'fttp':              7,
    'fttb':              7,
    'fttn':              7,

    # Technology variants
    '5g':                6,
    '5g-home':           8,
    'fixed-wireless':    8,
    'fixed_wireless':    8,
    'wireless':          5,
    'satellite':         5,
    'starlink':          5,

    # Pricing signals
    'pricing':           7,
    'price':             6,
    'compare':           6,
    'compare-plans':     8,

    # Business
    'small-business':    5,
    'business-internet': 6,
    'business-nbn':      8,
}

# URLs matching these patterns are always excluded.
EXCLUDE_PATTERNS = [
    r'/blog/',
    r'/news/',
    r'/support/',
    r'/help/',
    r'/contact',
    r'/about',
    r'/careers',
    r'/login',
    r'/sign-in',
    r'/my-account',
    r'/terms',
    r'/privacy',
    r'/legal',
    r'/media',
    r'/press',
    r'/assets/',
    r'/static/',
    r'/images/',
    r'/css/',
    r'/js/',
    r'\.(pdf|png|jpg|jpeg|gif|svg|css|js|zip|xml|ico)$',
    r'#',                      # anchor-only links
    r'mailto:',
    r'tel:',
    r'javascript:',
]

_exclude_re = re.compile('|'.join(EXCLUDE_PATTERNS), re.IGNORECASE)


class URLDiscovery:
    """Crawl an ISP site and return ranked plan-page candidates."""

    def __init__(
        self,
        base_url: str,
        network_types: Optional[List[str]] = None,
        max_depth: int = 2,
        max_urls: int = 200,
    ):
        self.base_url = base_url.rstrip('/')
        parsed = urlparse(self.base_url)
        self.domain = parsed.netloc
        self.scheme = parsed.scheme or 'https'
        self.origin = f"{self.scheme}://{self.domain}"
        self.network_types = [t.lower() for t in (network_types or ['nbn', 'opticomm', 'redtrain', 'supa'])]
        self.max_depth = max_depth
        self.max_urls = max_urls

        # State
        self.visited: Set[str] = set()
        self.discovered: Dict[str, dict] = {}   # url -> {score, depth, network_types}

    # ── Public API ────────────────────────────────────────────

    def crawl(self, browser: Browser) -> List[Dict]:
        """
        Run the discovery crawl using an existing Playwright browser.

        Returns:
            Sorted list of dicts: [{url, score, depth, network_types}, ...]
        """
        log_info(f"Starting URL discovery from {self.base_url}", provider="isp-crawler")

        self._crawl_page(browser, self.base_url, depth=0)

        # Sort by score descending
        ranked = sorted(self.discovered.values(), key=lambda x: x['score'], reverse=True)

        # Filter: keep only URLs that match at least one requested network type
        # OR have a high generic plan score (>= 12)
        filtered = []
        for entry in ranked:
            matched_nets = [n for n in self.network_types if n in entry.get('network_types', [])]
            if matched_nets or entry['score'] >= 12:
                entry['matched_networks'] = matched_nets
                filtered.append(entry)

        log_info(
            f"Discovery complete: {len(self.visited)} pages visited, "
            f"{len(filtered)} candidate plan pages found",
            provider="isp-crawler",
        )
        return filtered

    # ── Internal crawling ─────────────────────────────────────

    def _crawl_page(self, browser: Browser, url: str, depth: int):
        """Recursively crawl a single page and extract links."""
        if depth > self.max_depth:
            return
        if len(self.visited) >= self.max_urls:
            return

        normalised = self._normalise_url(url)
        if normalised in self.visited:
            return
        self.visited.add(normalised)

        page = None
        try:
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
            page.set_default_timeout(20000)

            log_info(f"[depth={depth}] Crawling: {normalised}", provider="isp-crawler")
            resp = page.goto(normalised, wait_until='domcontentloaded', timeout=25000)

            if not resp or resp.status >= 400:
                log_warning(f"HTTP {resp.status if resp else '?'} for {normalised}", provider="isp-crawler")
                return

            # Wait for JS rendering
            page.wait_for_timeout(3000)

            # Extract all anchor hrefs from rendered DOM
            raw_links = page.eval_on_selector_all(
                'a[href]',
                'els => els.map(a => a.href)',
            )

            internal_links = self._filter_internal(raw_links)

            # Score each link
            for link in internal_links:
                score, detected_nets = self._score_url(link)
                if score > 0 and link not in self.discovered:
                    self.discovered[link] = {
                        'url': link,
                        'score': score,
                        'depth': depth + 1,
                        'network_types': detected_nets,
                        'found_on': normalised,
                    }

            # Recurse into high-scoring pages
            for link in internal_links:
                entry = self.discovered.get(link)
                if entry and entry['score'] >= 6 and entry['depth'] <= self.max_depth:
                    self._crawl_page(browser, link, depth + 1)

        except Exception as e:
            log_error(f"Error crawling {normalised}: {str(e)}", provider="isp-crawler")
        finally:
            if page:
                try:
                    page.close()
                except Exception:
                    pass

    # ── Scoring logic ─────────────────────────────────────────

    def _score_url(self, url: str) -> tuple:
        """
        Score a URL based on keyword presence in the path/query.

        Returns:
            (score: int, detected_network_types: list[str])
        """
        lower = url.lower()
        total = 0
        detected_nets = []

        for keyword, weight in PLAN_KEYWORDS.items():
            if keyword in lower:
                total += weight
                # Track which network types this URL references
                if keyword in ('nbn',):
                    detected_nets.append('nbn')
                elif keyword in ('opticomm',):
                    detected_nets.append('opticomm')
                elif keyword in ('redtrain', 'red-train'):
                    detected_nets.append('redtrain')
                elif keyword in ('supa',):
                    detected_nets.append('supa')
                elif keyword in ('5g', '5g-home'):
                    detected_nets.append('5g')
                elif keyword in ('fixed-wireless', 'fixed_wireless'):
                    detected_nets.append('fixed_wireless')
                elif keyword in ('satellite', 'starlink'):
                    detected_nets.append('satellite')

        return total, list(set(detected_nets))

    # ── Helpers ───────────────────────────────────────────────

    def _filter_internal(self, raw_links: List[str]) -> List[str]:
        """Keep only internal, non-excluded, normalised links."""
        results = []
        seen = set()
        for link in raw_links:
            normalised = self._normalise_url(link)
            if not normalised:
                continue
            parsed = urlparse(normalised)
            if parsed.netloc != self.domain:
                continue
            if _exclude_re.search(normalised):
                continue
            if normalised in seen or normalised in self.visited:
                continue
            seen.add(normalised)
            results.append(normalised)
        return results

    def _normalise_url(self, url: str) -> Optional[str]:
        """Strip fragments, trailing slashes, and normalise scheme."""
        if not url:
            return None
        try:
            # Make absolute
            if url.startswith('/'):
                url = self.origin + url
            elif not url.startswith('http'):
                url = urljoin(self.base_url, url)

            parsed = urlparse(url)
            # Strip fragment, normalise path
            path = parsed.path.rstrip('/') or '/'
            clean = urlunparse((
                parsed.scheme or self.scheme,
                parsed.netloc,
                path,
                parsed.params,
                parsed.query,
                '',  # no fragment
            ))
            return clean
        except Exception:
            return None


# ── Standalone test ──────────────────────────────────────────────

if __name__ == "__main__":
    from utils.stealth import create_stealth_browser

    test_url = "https://www.telstra.com.au/internet"
    print(f"Testing URL discovery on: {test_url}\n")

    discovery = URLDiscovery(test_url, max_depth=1)
    with sync_playwright() as pw:
        browser = create_stealth_browser(pw)
        results = discovery.crawl(browser)
        browser.close()

    print(f"\nFound {len(results)} candidate plan pages:\n")
    for r in results[:20]:
        nets = ', '.join(r.get('matched_networks', r.get('network_types', [])))
        print(f"  [{r['score']:3d}] {r['url']}")
        if nets:
            print(f"         networks: {nets}")
