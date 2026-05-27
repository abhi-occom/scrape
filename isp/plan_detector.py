"""
Plan Detector
-------------
Analyses a rendered page to determine:
  1. Whether it contains broadband plan data.
  2. Which network type(s) are present (NBN, Opticomm, RedTrain, Supa …).
  3. What CSS selectors can reach the plan cards.

Returns a confidence-scored report for each page so the scraper engine
knows which extraction strategy to use.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from playwright.sync_api import Page

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import log_info, log_warning


# ── Network type detection ───────────────────────────────────────

NETWORK_SIGNATURES: Dict[str, List[str]] = {
    'nbn': [
        r'\bnbn\b', r'national\s+broadband', r'\bnbn\s*\d+',
        r'nbn\s*home', r'nbn\s*plan',
    ],
    'opticomm': [
        r'\bopticomm\b', r'opticomm\s+fibre', r'opticomm\s+plan',
    ],
    'redtrain': [
        r'\bredtrain\b', r'red\s*train', r'redtrain\s+fibre',
    ],
    'supa': [
        r'\bsupa\b', r'supa\s+internet', r'supa\s+broadband',
    ],
    '5g': [
        r'\b5g\b', r'5g\s+home', r'5g\s+internet', r'5g\s+broadband',
    ],
    'fixed_wireless': [
        r'fixed\s+wireless', r'wireless\s+broadband',
    ],
    'fibre': [
        r'\bfttp\b', r'\bfttb\b', r'\bfttn\b', r'\bfttc\b',
        r'fibre\s+to', r'fiber\s+to',
    ],
    'satellite': [
        r'\bsatellite\b', r'\bstarlink\b',
    ],
}

# Compile once
_network_regexes: Dict[str, re.Pattern] = {
    name: re.compile('|'.join(patterns), re.IGNORECASE)
    for name, patterns in NETWORK_SIGNATURES.items()
}


# ── Plan card selector candidates ────────────────────────────────

CARD_SELECTORS = [
    # Data-attribute selectors (Telstra-style)
    '[data-fixed-plan-card-price]',
    '[data-plan]',
    '[data-plan-name]',
    '[data-product-name]',

    # Class-based plan card patterns
    '.plan-card',
    '.plan-container',
    '.plan-tile',
    '.plan-item',
    '.product-card',
    '.product-tile',
    '.pricing-card',
    '.price-card',
    '.card--plan',
    '.card-plan',

    # Wildcard class matches
    '[class*="plan-card"]',
    '[class*="plan_card"]',
    '[class*="planCard"]',
    '[class*="product-card"]',
    '[class*="productCard"]',
    '[class*="pricing"]',

    # Role-based
    '[role="group"]',

    # Generic card / article
    'article',
    '.card',
]

NAME_SELECTORS = [
    'h2', 'h3', 'h4',
    '.plan-name', '.plan-title',
    '[class*="plan-name"]', '[class*="planName"]',
    '[class*="plan-title"]', '[class*="planTitle"]',
    '.product-name', '.product-title',
    'strong',
]

PRICE_SELECTORS = [
    '.price', '.plan-price',
    '[class*="price"]',
    '[data-price]', '[data-fixed-plan-card-price]',
    '.card__price',
    'span',
]

SPEED_SELECTORS = [
    '.speed', '.plan-speed',
    '[class*="speed"]',
    '[data-speed]',
    '[data-tcom-fixed-plancard-dsq-evening-download]',
    '.subheading',
]


# ── Data class for detection result ──────────────────────────────

@dataclass
class PageAnalysis:
    """Result of analysing a single page for plan data."""
    url: str
    has_plans: bool = False
    confidence: float = 0.0                       # 0.0 – 1.0
    network_types: List[str] = field(default_factory=list)
    card_selector: Optional[str] = None
    card_count: int = 0
    name_selector: Optional[str] = None
    price_selector: Optional[str] = None
    speed_selector: Optional[str] = None
    price_signals: int = 0                        # count of "$" on page
    speed_signals: int = 0                        # count of "Mbps" on page
    page_title: str = ''
    raw_text_snippet: str = ''                    # first 500 chars of body
    error: Optional[str] = None


class PlanDetector:
    """Analyse a Playwright page and return structured detection results."""

    def analyse(self, page: Page, url: str) -> PageAnalysis:
        """
        Run full analysis on an already-navigated Playwright page.

        Args:
            page: Playwright Page object (already loaded and JS-waited).
            url:  The URL of the page being analysed.

        Returns:
            PageAnalysis dataclass with detection results.
        """
        result = PageAnalysis(url=url)

        try:
            # ── 1. Grab raw text ─────────────────────────────────
            body_text = page.inner_text('body')
            result.page_title = page.title() or ''
            result.raw_text_snippet = body_text[:500]

            combined_text = f"{result.page_title} {body_text}"

            # ── 2. Detect network types ──────────────────────────
            result.network_types = self._detect_networks(combined_text)

            # ── 3. Count pricing / speed signals ─────────────────
            result.price_signals = len(re.findall(r'\$\d', body_text))
            result.speed_signals = len(re.findall(r'\d+\s*[Mm]bps', body_text))

            # ── 4. Find best card selector ───────────────────────
            best_selector, best_count = self._find_best_card_selector(page)
            result.card_selector = best_selector
            result.card_count = best_count

            # ── 5. Find sub-selectors inside cards ───────────────
            if best_selector and best_count > 0:
                result.name_selector = self._probe_sub_selector(page, best_selector, NAME_SELECTORS)
                result.price_selector = self._probe_sub_selector(page, best_selector, PRICE_SELECTORS)
                result.speed_selector = self._probe_sub_selector(page, best_selector, SPEED_SELECTORS)

            # ── 6. Compute confidence ────────────────────────────
            result.confidence = self._compute_confidence(result)
            result.has_plans = result.confidence >= 0.35

            log_info(
                f"Page analysis: {url} | plans={result.has_plans} "
                f"confidence={result.confidence:.2f} networks={result.network_types} "
                f"cards={result.card_count} prices={result.price_signals} speeds={result.speed_signals}",
                provider="isp-crawler",
            )

        except Exception as e:
            result.error = str(e)
            log_warning(f"Analysis failed for {url}: {e}", provider="isp-crawler")

        return result

    # ── Network detection ─────────────────────────────────────

    def _detect_networks(self, text: str) -> List[str]:
        """Return list of network types mentioned in the text."""
        found = []
        for name, regex in _network_regexes.items():
            if regex.search(text):
                found.append(name)
        return found

    # ── Selector probing ──────────────────────────────────────

    def _find_best_card_selector(self, page: Page) -> Tuple[Optional[str], int]:
        """
        Try each candidate selector and return the one whose count
        best matches a "sensible number of plan cards" (2-30).
        """
        best_sel = None
        best_count = 0
        best_score = -1

        for sel in CARD_SELECTORS:
            try:
                count = page.eval_on_selector_all(sel, 'els => els.length')
            except Exception:
                count = 0

            if count < 2:
                continue

            # Prefer counts between 3-12 (typical plan card range)
            if 3 <= count <= 12:
                score = 100 - abs(count - 6)       # sweet spot around 6
            elif 2 <= count <= 30:
                score = 50 - abs(count - 6)
            else:
                score = 0

            if score > best_score:
                best_score = score
                best_sel = sel
                best_count = count

        return best_sel, best_count

    def _probe_sub_selector(
        self,
        page: Page,
        card_selector: str,
        candidate_selectors: List[str],
    ) -> Optional[str]:
        """
        Inside the first card element, try each candidate sub-selector
        and return the first one that finds at least one element.
        """
        for sub_sel in candidate_selectors:
            try:
                combined = f"{card_selector}:first-of-type {sub_sel}"
                count = page.eval_on_selector_all(combined, 'els => els.length')
                if count >= 1:
                    return sub_sel
            except Exception:
                continue
        return None

    # ── Confidence scoring ────────────────────────────────────

    def _compute_confidence(self, r: PageAnalysis) -> float:
        """
        Produce a 0.0-1.0 confidence score that this page has plan data.

        Scoring weights:
          - Card selector found with 3-12 cards:  +0.30
          - Price signals (>= 3):                 +0.25
          - Speed signals (>= 2):                 +0.20
          - Network type detected:                +0.15
          - Sub-selectors found:                  +0.10
        """
        score = 0.0

        # Card count
        if r.card_count >= 3:
            score += 0.30
        elif r.card_count >= 2:
            score += 0.15

        # Price signals
        if r.price_signals >= 6:
            score += 0.25
        elif r.price_signals >= 3:
            score += 0.15
        elif r.price_signals >= 1:
            score += 0.05

        # Speed signals
        if r.speed_signals >= 4:
            score += 0.20
        elif r.speed_signals >= 2:
            score += 0.12
        elif r.speed_signals >= 1:
            score += 0.05

        # Network types
        if len(r.network_types) >= 2:
            score += 0.15
        elif len(r.network_types) >= 1:
            score += 0.10

        # Sub-selectors
        sub_found = sum(1 for s in [r.name_selector, r.price_selector, r.speed_selector] if s)
        score += sub_found * 0.033   # max ~0.10

        return min(score, 1.0)


# ── Standalone test ──────────────────────────────────────────────

if __name__ == "__main__":
    from playwright.sync_api import sync_playwright
    from utils.stealth import create_stealth_browser, create_stealth_page

    test_url = "https://www.telstra.com.au/internet/plans"
    print(f"Testing plan detection on: {test_url}\n")

    detector = PlanDetector()

    with sync_playwright() as pw:
        browser = create_stealth_browser(pw)
        page = create_stealth_page(browser)
        page.goto(test_url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(5000)

        analysis = detector.analyse(page, test_url)

        page.close()
        browser.close()

    print(f"Has plans:       {analysis.has_plans}")
    print(f"Confidence:      {analysis.confidence:.2f}")
    print(f"Network types:   {analysis.network_types}")
    print(f"Card selector:   {analysis.card_selector}")
    print(f"Card count:      {analysis.card_count}")
    print(f"Name selector:   {analysis.name_selector}")
    print(f"Price selector:  {analysis.price_selector}")
    print(f"Speed selector:  {analysis.speed_selector}")
    print(f"Price signals:   {analysis.price_signals}")
    print(f"Speed signals:   {analysis.speed_signals}")
