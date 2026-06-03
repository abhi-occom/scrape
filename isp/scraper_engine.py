"""
Dynamic Scraper Engine
----------------------
Extracts broadband plan data from any ISP page *without* hard-coded,
provider-specific selectors.

Three extraction strategies (tried in order):
  1. **Selector-based** – use the card/name/price/speed selectors
     discovered by PlanDetector.
  2. **Embedded JSON** – look for <script> tags or inline JSON blobs
     that contain plan data (monthlyCost, planName, etc.).
  3. **Regex text-parse** – fall back to regex patterns on the full
     visible page text.

All strategies normalise output into a standard plan dict.
"""

import re
import json
from typing import List, Dict, Any, Optional
from dataclasses import asdict
from playwright.sync_api import Page

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import log_info, log_warning, log_error, log_success
from isp.plan_detector import PageAnalysis


# ── Standard plan schema ─────────────────────────────────────────

def _empty_plan() -> Dict[str, Any]:
    return {
        'provider': '',
        'network_type': '',
        'plan_name': '',
        'download_speed': 0,
        'upload_speed': 0,
        'price': 0.0,
        'promo_price': None,
        'promo_period': None,
        'contract': None,
        'typical_evening_dl': 0,
        'typical_evening_ul': 0,
        'source_url': '',
    }


# ── Helper regexes ───────────────────────────────────────────────

_RE_PRICE     = re.compile(r'(?:[A-Z]{1,3})?\$\s*([\d]+(?:\.\d{1,2})?)')
_RE_SPEED_DL  = re.compile(r'(\d+)\s*/\s*(\d+)\s*[Mm]bps')
_RE_SPEED_SINGLE = re.compile(r'(\d+)\s*[Mm]bps')
_RE_PROMO_PERIOD = re.compile(r'(?:first|for)\s+(\d+)\s+months?', re.IGNORECASE)
_RE_FREE_PERIOD = re.compile(r'(\d+)\s+days?\s+free', re.IGNORECASE)
_RE_CONTRACT     = re.compile(r'(no\s+lock[\s-]*in|no\s+contract|month[\s-]*to[\s-]*month|\d+\s+month\s+contract)', re.IGNORECASE)

# JSON blob patterns inside <script> tags
_RE_JSON_PLAN_ARRAY = re.compile(
    r'"(?:plans|products|items)"\s*:\s*(\[[\s\S]*?\])\s*[,}]',
    re.IGNORECASE,
)


class ScraperEngine:
    """Extract plan data from a page using multiple strategies."""

    def extract(
        self,
        page: Page,
        analysis: PageAnalysis,
        provider_name: str = '',
    ) -> List[Dict[str, Any]]:
        """
        Try each extraction strategy and return the first that yields results.

        Args:
            page:           Playwright Page (already navigated and waited).
            analysis:       PageAnalysis from PlanDetector.
            provider_name:  Human-readable provider label (e.g. "Telstra").

        Returns:
            List of normalised plan dicts.
        """
        plans: List[Dict[str, Any]] = []

        # Strategy 1: Selector-based extraction
        if analysis.card_selector and analysis.card_count >= 2:
            plans = self._extract_via_selectors(page, analysis, provider_name)
            if plans:
                log_success(
                    f"Selector strategy: {len(plans)} plans from {analysis.url}",
                    provider="isp-crawler",
                )
                return plans

        # Strategy 2: Embedded JSON
        plans = self._extract_via_json(page, analysis, provider_name)
        if plans:
            log_success(
                f"JSON strategy: {len(plans)} plans from {analysis.url}",
                provider="isp-crawler",
            )
            return plans

        # Strategy 3: Regex text-parse
        plans = self._extract_via_regex(page, analysis, provider_name)
        if plans:
            log_success(
                f"Regex strategy: {len(plans)} plans from {analysis.url}",
                provider="isp-crawler",
            )
            return plans

        log_warning(f"No plans extracted from {analysis.url}", provider="isp-crawler")
        return []

    # ══════════════════════════════════════════════════════════════
    #  Strategy 1 – Selector-based
    # ══════════════════════════════════════════════════════════════

    def _extract_via_selectors(
        self, page: Page, analysis: PageAnalysis, provider_name: str,
    ) -> List[Dict[str, Any]]:
        """Extract plans by iterating over card elements."""
        plans = []
        try:
            cards = page.query_selector_all(analysis.card_selector)
            log_info(
                f"Selector extraction: {len(cards)} cards via '{analysis.card_selector}'",
                provider="isp-crawler",
            )

            for i, card in enumerate(cards):
                try:
                    plan = self._parse_card(card, analysis, provider_name)
                    if plan and plan.get('plan_name') and plan.get('price', 0) > 0:
                        plan['source_url'] = analysis.url
                        plans.append(plan)
                except Exception as e:
                    log_warning(f"Card #{i} parse error: {e}", provider="isp-crawler")

        except Exception as e:
            log_error(f"Selector extraction failed: {e}", provider="isp-crawler")

        return self._deduplicate(plans)

    def _parse_card(
        self, card, analysis: PageAnalysis, provider_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Parse a single card element into a plan dict."""
        plan = _empty_plan()
        plan['provider'] = provider_name
        network_types = analysis.network_types

        card_text = card.inner_text() or ''

        # ── Plan name ────────────────────────────────────────
        name = ''
        if analysis.name_selector:
            el = card.query_selector(analysis.name_selector)
            if el:
                name = el.inner_text().strip()
        if not name:
            # Fallback: first heading or strong text
            for tag in ['h2', 'h3', 'h4', 'strong']:
                el = card.query_selector(tag)
                if el:
                    name = el.inner_text().strip().split('\n')[0]
                    break
        if not name:
            # Fallback: first non-empty line of card text
            for line in card_text.split('\n'):
                line = line.strip()
                if line and len(line) > 2 and not line.startswith('$'):
                    name = line
                    break
        plan['plan_name'] = name[:150]   # cap length

        # ── Price ────────────────────────────────────────────
        prices = []
        if analysis.price_selector:
            price_els = card.query_selector_all(analysis.price_selector)
            for el in price_els:
                txt = el.inner_text().strip()
                m = _RE_PRICE.search(txt)
                if m:
                    prices.append(float(m.group(1)))

        # Fallback: regex on card text
        if not prices:
            prices = [float(m) for m in _RE_PRICE.findall(card_text) if float(m) > 0]

        if prices:
            # Highest is regular price, lowest is promo (if different)
            plan['price'] = max(prices)
            if min(prices) < max(prices):
                plan['promo_price'] = min(prices)

        # ── Speed ────────────────────────────────────────────
        speed_text = ''
        if analysis.speed_selector:
            speed_el = card.query_selector(analysis.speed_selector)
            if speed_el:
                speed_text = speed_el.inner_text().strip()

        if not speed_text:
            speed_text = card_text

        # Try DL/UL pair first
        pair = _RE_SPEED_DL.search(speed_text)
        if pair:
            plan['download_speed'] = int(pair.group(1))
            plan['upload_speed'] = int(pair.group(2))
        else:
            single = _RE_SPEED_SINGLE.search(speed_text)
            if single:
                plan['download_speed'] = int(single.group(1))

        plan['speed_label'] = plan['download_speed']

        # Also check plan name for embedded speed
        if plan['download_speed'] == 0:
            name_speed = _RE_SPEED_SINGLE.search(plan['plan_name'])
            if name_speed:
                plan['download_speed'] = int(name_speed.group(1))
                plan['speed_label'] = plan['download_speed']

        # ── Network type ─────────────────────────────────────
        if network_types:
            plan['network_type'] = network_types[0].upper()
        else:
            plan['network_type'] = self._detect_network_from_text(card_text)

        # ── Promo period ─────────────────────────────────────
        promo_match = _RE_PROMO_PERIOD.search(card_text)
        if promo_match:
            plan['promo_period'] = f"{promo_match.group(1)} months"

        # ── Contract ─────────────────────────────────────────
        contract_match = _RE_CONTRACT.search(card_text)
        if contract_match:
            plan['contract'] = contract_match.group(1).strip()

        return plan

    # ══════════════════════════════════════════════════════════════
    #  Strategy 2 – Embedded JSON
    # ══════════════════════════════════════════════════════════════

    def _extract_via_json(
        self, page: Page, analysis: PageAnalysis, provider_name: str,
    ) -> List[Dict[str, Any]]:
        """Look for JSON plan data inside <script> tags."""
        plans = []
        try:
            scripts = page.eval_on_selector_all(
                'script',
                'els => els.map(s => s.textContent || "")',
            )

            for script_text in scripts:
                if not script_text or len(script_text) < 50:
                    continue

                # Look for plan array pattern
                for match in _RE_JSON_PLAN_ARRAY.finditer(script_text):
                    try:
                        raw = match.group(1)
                        items = json.loads(raw)
                        if not isinstance(items, list):
                            continue

                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            plan = self._json_item_to_plan(item, analysis, provider_name)
                            if plan and plan.get('plan_name') and plan.get('price', 0) > 0:
                                plans.append(plan)

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            log_warning(f"JSON extraction error: {e}", provider="isp-crawler")

        return self._deduplicate(plans)

    def _json_item_to_plan(
        self, item: dict, analysis: PageAnalysis, provider_name: str,
    ) -> Optional[Dict[str, Any]]:
        """Map a JSON object to our standard plan schema."""
        plan = _empty_plan()
        plan['provider'] = provider_name
        plan['source_url'] = analysis.url

        # Name — try common JSON keys
        for key in ('name', 'planName', 'plan_name', 'title', 'productName', 'product_name'):
            if key in item and item[key]:
                plan['plan_name'] = str(item[key]).strip()
                break

        # Price
        for key in ('price', 'monthlyPrice', 'monthly_price', 'monthlyCost', 'cost', 'amount'):
            if key in item and item[key] is not None:
                try:
                    plan['price'] = float(str(item[key]).replace('$', '').replace(',', ''))
                    break
                except (ValueError, TypeError):
                    continue

        # Promo price
        for key in ('promoPrice', 'promo_price', 'discountPrice', 'discount_price', 'salePrice'):
            if key in item and item[key] is not None:
                try:
                    plan['promo_price'] = float(str(item[key]).replace('$', '').replace(',', ''))
                    break
                except (ValueError, TypeError):
                    continue

        # Speed
        for key in ('speed', 'downloadSpeed', 'download_speed', 'maxSpeed', 'speedLabel', 'speed_label'):
            if key in item and item[key] is not None:
                try:
                    plan['download_speed'] = int(re.search(r'\d+', str(item[key])).group())
                    plan['speed_label'] = plan['download_speed']
                    break
                except (ValueError, TypeError, AttributeError):
                    continue

        # Upload speed
        for key in ('uploadSpeed', 'upload_speed', 'maxUpload'):
            if key in item and item[key] is not None:
                try:
                    plan['upload_speed'] = int(re.search(r'\d+', str(item[key])).group())
                    break
                except (ValueError, TypeError, AttributeError):
                    continue

        # Network type
        for key in ('networkType', 'network_type', 'type', 'technology'):
            if key in item and item[key]:
                plan['network_type'] = str(item[key]).strip()
                break
        if not plan['network_type'] and analysis.network_types:
            plan['network_type'] = analysis.network_types[0].upper()

        return plan

    # ══════════════════════════════════════════════════════════════
    #  Strategy 3 – Regex text-parse
    # ══════════════════════════════════════════════════════════════

    def _extract_via_regex(
        self, page: Page, analysis: PageAnalysis, provider_name: str,
    ) -> List[Dict[str, Any]]:
        """
        Last-resort: scan full page text for speed + price patterns.
        Looks for blocks of text containing both a speed and a price.
        """
        plans = []
        try:
            body_text = page.inner_text('body')

            # Split into rough "blocks" (double-newline separated)
            blocks = re.split(r'\n{2,}', body_text)

            seen_names = set()
            for block in blocks:
                block = block.strip()
                if len(block) < 20:
                    continue

                # Must have both a price and a speed to be considered
                price_match = _RE_PRICE.search(block)
                speed_match = _RE_SPEED_DL.search(block) or _RE_SPEED_SINGLE.search(block)

                if not price_match or not speed_match:
                    continue

                plan = _empty_plan()
                plan['provider'] = provider_name
                plan['source_url'] = analysis.url

                # Price
                all_prices = [float(p) for p in _RE_PRICE.findall(block) if float(p) > 0]
                if all_prices:
                    plan['price'] = max(all_prices)
                    if min(all_prices) < max(all_prices):
                        plan['promo_price'] = min(all_prices)

                # Speed
                dl_ul = _RE_SPEED_DL.search(block)
                if dl_ul:
                    plan['download_speed'] = int(dl_ul.group(1))
                    plan['upload_speed'] = int(dl_ul.group(2))
                else:
                    single = _RE_SPEED_SINGLE.search(block)
                    if single:
                        plan['download_speed'] = int(single.group(1))
                plan['speed_label'] = plan['download_speed']

                # Name: first non-empty, non-price, non-speed line
                for line in block.split('\n'):
                    line = line.strip()
                    if (line
                            and not line.startswith('$')
                            and not re.match(r'^\d+\s*[Mm]bps', line)
                            and len(line) > 2
                            and len(line) < 100):
                        plan['plan_name'] = line
                        break

                if not plan['plan_name']:
                    plan['plan_name'] = f"{plan['download_speed']}Mbps Plan"

                # Network type
                plan['network_type'] = self._detect_network_from_text(block)
                if not plan['network_type'] and analysis.network_types:
                    plan['network_type'] = analysis.network_types[0].upper()

                # Promo period
                promo = _RE_PROMO_PERIOD.search(block)
                if promo:
                    plan['promo_period'] = f"{promo.group(1)} months"

                # Deduplicate by name
                if plan['plan_name'] in seen_names:
                    continue
                seen_names.add(plan['plan_name'])

                if plan['price'] > 0:
                    plans.append(plan)

            if not plans:
                plans = self._extract_from_nearby_blocks(blocks, analysis, provider_name)

        except Exception as e:
            log_error(f"Regex extraction failed: {e}", provider="isp-crawler")

        return plans

    def _extract_from_nearby_blocks(
        self,
        blocks: List[str],
        analysis: PageAnalysis,
        provider_name: str,
    ) -> List[Dict[str, Any]]:
        """Parse plans split across nearby text blocks."""
        plans = []
        seen = set()

        for i, block in enumerate(blocks):
            speed_match = _RE_SPEED_DL.search(block) or _RE_SPEED_SINGLE.search(block)
            if not speed_match:
                continue

            price_block = ''
            for candidate in blocks[i + 1:i + 4]:
                if _RE_PRICE.search(candidate):
                    price_block = candidate
                    break
            if not price_block:
                continue

            detail_text = '\n'.join(blocks[i:i + 6])
            plan = _empty_plan()
            plan['provider'] = provider_name
            plan['source_url'] = analysis.url

            dl_ul = _RE_SPEED_DL.search(block)
            if dl_ul:
                plan['download_speed'] = int(dl_ul.group(1))
                plan['upload_speed'] = int(dl_ul.group(2))
            else:
                plan['download_speed'] = int(speed_match.group(1))
            plan['speed_label'] = plan['download_speed']

            prices = [float(p) for p in _RE_PRICE.findall(price_block) if float(p) > 0]
            if not prices:
                continue
            plan['price'] = max(prices)
            if min(prices) < max(prices):
                plan['promo_price'] = min(prices)

            plan['plan_name'] = self._plan_name_from_previous_block(blocks[i - 1] if i else '')
            if not plan['plan_name']:
                plan['plan_name'] = f"{plan['download_speed']}Mbps Plan"

            plan['network_type'] = self._detect_network_from_text(detail_text)
            if not plan['network_type'] and analysis.network_types:
                plan['network_type'] = analysis.network_types[0].upper()

            promo = _RE_PROMO_PERIOD.search(detail_text)
            if promo:
                plan['promo_period'] = f"{promo.group(1)} months"
            else:
                free_period = _RE_FREE_PERIOD.search(detail_text)
                if free_period:
                    plan['promo_period'] = f"{free_period.group(1)} days free"

            contract_match = _RE_CONTRACT.search(detail_text)
            if contract_match:
                plan['contract'] = contract_match.group(1).strip()

            key = (
                plan['plan_name'].lower(),
                plan['download_speed'],
                plan['upload_speed'],
                plan['price'],
            )
            if key in seen:
                continue
            seen.add(key)
            plans.append(plan)

        return plans

    def _plan_name_from_previous_block(self, text: str) -> str:
        """Get a likely plan name from the block immediately before a speed block."""
        skip = {'most popular', 'fastest speed', 'get started', 'view plans'}
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        for line in reversed(lines):
            if line.lower() not in skip and len(line) < 100:
                return line
        return ''

    # ── Shared helpers ────────────────────────────────────────

    def _detect_network_from_text(self, text: str) -> str:
        """Detect network type from a text snippet."""
        lower = text.lower()
        if 'opticomm' in lower:
            return 'Opticomm'
        if 'redtrain' in lower or 'red train' in lower:
            return 'RedTrain'
        if 'supa' in lower:
            return 'Supa'
        if '5g' in lower:
            return '5G'
        if 'fixed wireless' in lower:
            return 'Fixed Wireless'
        if 'satellite' in lower or 'starlink' in lower:
            return 'Satellite'
        if 'nbn' in lower:
            return 'NBN'
        if 'fibre' in lower or 'fttp' in lower:
            return 'Fibre'
        return ''

    def _deduplicate(self, plans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate plans by name + price + speed."""
        seen = set()
        unique = []
        for p in plans:
            key = f"{p.get('plan_name', '')}|{p.get('price', 0)}|{p.get('download_speed', 0)}"
            if key not in seen:
                seen.add(key)
                unique.append(p)
        return unique


# ── Standalone test ──────────────────────────────────────────────

if __name__ == "__main__":
    from playwright.sync_api import sync_playwright
    from utils.stealth import create_stealth_browser, create_stealth_page
    from isp.plan_detector import PlanDetector

    test_url = "https://www.telstra.com.au/internet/plans"
    print(f"Testing scraper engine on: {test_url}\n")

    detector = PlanDetector()
    engine = ScraperEngine()

    with sync_playwright() as pw:
        browser = create_stealth_browser(pw)
        page = create_stealth_page(browser)
        page.goto(test_url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(6000)

        analysis = detector.analyse(page, test_url)
        plans = engine.extract(page, analysis, provider_name='Telstra')

        page.close()
        browser.close()

    print(f"\nExtracted {len(plans)} plans:\n")
    for p in plans:
        promo = f" (promo: ${p['promo_price']})" if p.get('promo_price') else ""
        print(f"  {p['plan_name']} [{p['network_type']}]: "
              f"${p['price']}/mth{promo} | {p['download_speed']}/{p['upload_speed']} Mbps")
