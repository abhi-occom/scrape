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
_RE_PRICE_ONLY = re.compile(r'^\$?\s*\d+(?:\.\d{1,2})?(?:\s*/.*)?$', re.IGNORECASE)
_RE_SPEED_DL  = re.compile(r'(\d+)\s*(?:[Mm]bps)?\s*/\s*(\d+)\s*[Mm]bps')
_RE_SPEED_SINGLE = re.compile(r'(\d+)\s*[Mm]bps')
_RE_SPEED_IN_PLAN_NAME = re.compile(r'\bThe\s+(\d{2,4})(?:\+)?\b', re.IGNORECASE)
_RE_PROMO_PERIOD = re.compile(r'(?:first|for|after|end of|at the end of)\s+(\d+)\s+months?', re.IGNORECASE)
_RE_FREE_PERIOD = re.compile(r'(\d+)\s+days?\s+free', re.IGNORECASE)
_RE_CONTRACT     = re.compile(r'(no\s+lock[\s-]*in|no\s+contract|month[\s-]*to[\s-]*month|\d+\s+month\s+contract)', re.IGNORECASE)
_RE_PLAN_TIER = re.compile(
    r'\b(?:basic|standard|premium|ultimate|starter|essential|value|fast|superfast|ultrafast|internet|broadband|plan)\b',
    re.IGNORECASE,
)
_UPLOAD_SPEED_BY_DOWNLOAD = {
    12: 1,
    25: 5,
    50: 20,
    100: 20,
    250: 25,
    500: 50,
    750: 50,
    1000: 50,
}

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
        selector_plans: List[Dict[str, Any]] = []

        # Strategy 1: Selector-based extraction
        if analysis.card_selector and analysis.card_count >= 2:
            selector_plans = self._extract_via_selectors(page, analysis, provider_name)
            if selector_plans and self._plans_look_usable(selector_plans):
                log_success(
                    f"Selector strategy: {len(selector_plans)} plans from {analysis.url}",
                    provider="isp-crawler",
                )
                return selector_plans
            if selector_plans:
                log_warning(
                    "Selector strategy produced low-quality plan rows; trying fallback extraction",
                    provider="isp-crawler",
                )

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

        if selector_plans:
            log_warning(
                "Using low-quality selector rows because all fallback extraction strategies failed",
                provider="isp-crawler",
            )
            return selector_plans

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
                if self._is_plan_name_candidate(line):
                    name = line
                    break
        name = self._compose_plan_name(name, card_text)
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
            name_speed = self._speed_from_plan_name(plan['plan_name'])
            if name_speed:
                plan['download_speed'] = name_speed
                plan['speed_label'] = plan['download_speed']
        if plan['download_speed'] and not plan['upload_speed']:
            plan['upload_speed'] = self._infer_upload_speed(plan['download_speed'])

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
            plans = self._extract_plan_price_sentences(body_text, analysis, provider_name)
            if plans:
                return plans

            plans = self._extract_repeating_plan_blocks(body_text, analysis, provider_name)
            if plans:
                return plans

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
                    if self._is_plan_name_candidate(line):
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
                plan['contract'] = self._detect_contract(block)

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

    def _extract_plan_price_sentences(
        self,
        body_text: str,
        analysis: PageAnalysis,
        provider_name: str,
    ) -> List[Dict[str, Any]]:
        """Extract plan rows from sentences like 'The 25 is $55.14'."""
        pattern = re.compile(r'\b(The\s+\d{2,4}\+?)\s+is\s+\$\s*(\d+(?:\.\d{1,2})?)', re.IGNORECASE)
        matches = list(pattern.finditer(body_text or ''))
        if len(matches) < 2:
            return []

        plans = []
        seen = set()
        page_network = self._detect_network_from_text(body_text)
        if re.search(r'opticomm\s+network\s+only', body_text or '', re.IGNORECASE):
            page_network = 'Opticomm'
        promo = _RE_PROMO_PERIOD.search(body_text or '')
        free_period = _RE_FREE_PERIOD.search(body_text or '')
        contract = self._detect_contract(body_text)

        for match in matches:
            name = re.sub(r'\s+', ' ', match.group(1)).strip()
            price = float(match.group(2))
            download_speed = self._speed_from_plan_name(name)
            if not download_speed:
                continue

            plan = _empty_plan()
            plan['provider'] = provider_name
            plan['source_url'] = analysis.url
            plan['plan_name'] = name
            plan['price'] = price
            plan['download_speed'] = download_speed
            plan['upload_speed'] = self._infer_upload_speed(download_speed)
            plan['speed_label'] = download_speed
            plan['typical_evening_dl'] = download_speed
            plan['typical_evening_ul'] = plan['upload_speed']
            plan['network_type'] = page_network or (analysis.network_types[0].upper() if analysis.network_types else '')
            if promo:
                plan['promo_period'] = f"{promo.group(1)} months"
            elif free_period:
                plan['promo_period'] = f"{free_period.group(1)} days free"
            plan['contract'] = contract

            key = (name.lower(), price)
            if key in seen:
                continue
            seen.add(key)
            plans.append(plan)

        return plans

    def _extract_repeating_plan_blocks(
        self,
        body_text: str,
        analysis: PageAnalysis,
        provider_name: str,
    ) -> List[Dict[str, Any]]:
        """Extract repeated plan rows from linear page text around price lines."""
        lines = [line.strip().lstrip('* ').strip() for line in body_text.splitlines()]
        lines = [line for line in lines if line]
        plans = []
        seen = set()

        for index, line in enumerate(lines):
            prices = self._price_values_at(lines, index)
            if not prices:
                continue

            detail_lines = lines[index:index + 8]
            detail_text = '\n'.join(detail_lines)
            speed_match = _RE_SPEED_DL.search(detail_text) or _RE_SPEED_SINGLE.search(detail_text)

            name = self._name_before_price(lines, index)
            if not name:
                continue

            name_speed = self._speed_from_plan_name(name)
            if not speed_match and not name_speed:
                continue

            plan = _empty_plan()
            plan['provider'] = provider_name
            plan['source_url'] = analysis.url
            plan['plan_name'] = name[:150]
            plan['price'] = max(prices)
            exact_price = self._price_from_plan_sentence(body_text, plan['plan_name'])
            if exact_price:
                plan['price'] = exact_price
            if min(prices) < max(prices):
                plan['promo_price'] = min(prices)

            dl_ul = _RE_SPEED_DL.search(detail_text)
            if dl_ul:
                plan['download_speed'] = int(dl_ul.group(1))
                plan['upload_speed'] = int(dl_ul.group(2))
            elif speed_match:
                plan['download_speed'] = int(speed_match.group(1))
            else:
                plan['download_speed'] = name_speed or 0
            if plan['download_speed'] and not plan['upload_speed']:
                plan['upload_speed'] = self._infer_upload_speed(plan['download_speed'])
            plan['speed_label'] = plan['download_speed']
            plan['typical_evening_dl'] = plan['download_speed']
            plan['typical_evening_ul'] = plan['upload_speed']

            context = '\n'.join(lines[max(0, index - 4):index + 8])
            plan['network_type'] = self._detect_network_from_text(context)
            if re.search(r'opticomm\s+network\s+only', body_text, re.IGNORECASE):
                plan['network_type'] = 'Opticomm'
            if not plan['network_type']:
                plan['network_type'] = self._detect_network_from_text(body_text)
            if not plan['network_type'] and analysis.network_types:
                plan['network_type'] = analysis.network_types[0].upper()

            promo = _RE_PROMO_PERIOD.search(context)
            if not promo:
                promo = _RE_PROMO_PERIOD.search(body_text)
            if promo:
                plan['promo_period'] = f"{promo.group(1)} months"
                if plan['promo_price'] is None:
                    plan['promo_price'] = plan['price']
            else:
                free_period = _RE_FREE_PERIOD.search(context)
                if not free_period:
                    free_period = _RE_FREE_PERIOD.search(body_text)
                if free_period:
                    plan['promo_period'] = f"{free_period.group(1)} days free"

            plan['contract'] = self._detect_contract(context, body_text)

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

    def _name_before_price(self, lines: List[str], price_index: int) -> str:
        """Build a plan name from the heading/tier lines immediately before a price."""
        candidates = []
        for line in reversed(lines[max(0, price_index - 5):price_index]):
            if not self._is_plan_name_candidate(line):
                continue
            candidates.append(line)
            if len(candidates) == 2:
                break

        candidates.reverse()
        if len(candidates) >= 2 and candidates[0].lower() != candidates[1].lower():
            if _RE_PLAN_TIER.search(candidates[1]):
                return f"{candidates[0]} - {candidates[1]}"
        return candidates[-1] if candidates else ''

    def _price_values_at(self, lines: List[str], index: int) -> List[float]:
        """Return price values when a rendered page splits '$' and amount across lines."""
        line = lines[index]
        prices = [float(p) for p in _RE_PRICE.findall(line) if float(p) > 0]
        if prices:
            return prices

        clean = line.strip()
        if clean == '$' and index + 1 < len(lines):
            next_line = lines[index + 1].strip()
            if _RE_PRICE_ONLY.match(next_line):
                return [float(next_line.replace('$', '').split('/')[0])]

        if _RE_PRICE_ONLY.match(clean):
            previous = lines[index - 1].strip() if index > 0 else ''
            next_line = lines[index + 1].strip().lower() if index + 1 < len(lines) else ''
            if previous == '$' or 'gst' in next_line or 'month' in next_line or 'mth' in next_line:
                return [float(clean.replace('$', '').split('/')[0])]

        return []

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

            plan['contract'] = self._detect_contract(detail_text)

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
            if line.lower() not in skip and self._is_plan_name_candidate(line):
                return line
        return ''

    # ── Shared helpers ────────────────────────────────────────

    def _is_plan_name_candidate(self, line: str) -> bool:
        """Return true when a text line looks like a name rather than price/speed metadata."""
        text = (line or '').strip()
        if not text or len(text) < 3 or len(text) > 100:
            return False
        lower = text.lower()
        if text.startswith('$') or _RE_PRICE_ONLY.match(text):
            return False
        if _RE_PRICE.search(text) or _RE_SPEED_DL.search(text) or _RE_SPEED_SINGLE.search(text):
            return False
        skip = {
            'buy now',
            'buy now!',
            'special offer',
            'unlimited data',
            'including gst',
            'maximum potential speed is displayed, typical speed may vary.',
        }
        if lower in skip:
            return False
        return bool(re.search(r'[A-Za-z]', text))

    def _compose_plan_name(self, name: str, card_text: str) -> str:
        """Combine generic headings with a nearby tier label when available."""
        name = (name or '').strip()
        if not name:
            return ''
        lines = [line.strip() for line in card_text.splitlines() if line.strip()]
        try:
            index = next(i for i, line in enumerate(lines) if line.strip() == name)
        except StopIteration:
            return name
        for line in lines[index + 1:index + 4]:
            if self._is_plan_name_candidate(line) and line.lower() != name.lower():
                if _RE_PLAN_TIER.search(line):
                    return f"{name} - {line}"
        return name

    def _plans_look_usable(self, plans: List[Dict[str, Any]]) -> bool:
        """Detect selector output that is technically valid but clearly malformed."""
        if not plans:
            return False
        names = [str(p.get('plan_name', '')).strip() for p in plans]
        non_numeric_names = [name for name in names if self._is_plan_name_candidate(name)]
        unique_names = {name.lower() for name in non_numeric_names}
        unique_plan_identities = {
            (
                str(p.get('plan_name', '')).strip().lower(),
                p.get('download_speed') or 0,
                p.get('upload_speed') or 0,
            )
            for p in plans
        }
        duplicate_name_ratio = len(unique_names) / max(len(non_numeric_names), 1)
        duplicate_identity_ratio = len(unique_plan_identities) / max(len(plans), 1)
        zero_speed_rows = sum(1 for p in plans if not p.get('download_speed'))
        zero_upload_rows = sum(1 for p in plans if p.get('download_speed') and not p.get('upload_speed'))

        if len(non_numeric_names) < len(plans) * 0.8:
            return False
        if len(plans) >= 4 and duplicate_name_ratio < 0.6:
            return False
        if len(plans) >= 4 and duplicate_identity_ratio < 0.9:
            return False
        if zero_speed_rows > len(plans) * 0.3:
            return False
        if zero_upload_rows > len(plans) * 0.7:
            return False
        return True

    def _speed_from_plan_name(self, name: str) -> int:
        """Extract speed from plan labels such as 'The 25'."""
        match = _RE_SPEED_IN_PLAN_NAME.search(name or '')
        if match:
            return int(match.group(1))
        name_speed = _RE_SPEED_SINGLE.search(name or '')
        if name_speed:
            return int(name_speed.group(1))
        return 0

    def _infer_upload_speed(self, download_speed: int) -> int:
        """Infer upload speed for common residential tier names when absent."""
        return _UPLOAD_SPEED_BY_DOWNLOAD.get(download_speed, 0)

    def _price_from_plan_sentence(self, text: str, plan_name: str) -> float:
        """Find exact footnote prices such as 'The 25 is $55.14'."""
        name = (plan_name or '').strip()
        if not name:
            return 0.0
        pattern = re.compile(rf'\b{re.escape(name)}\s+is\s+\$\s*(\d+(?:\.\d{{1,2}})?)', re.IGNORECASE)
        match = pattern.search(text or '')
        if not match:
            return 0.0
        try:
            return float(match.group(1))
        except ValueError:
            return 0.0

    def _detect_contract(self, *texts: str) -> Optional[str]:
        """Return a normalized contract label from local or page-level text."""
        combined = '\n'.join(text or '' for text in texts)
        lower = combined.lower()
        has_no_lock = bool(re.search(r'no\s+lock[\s-]*in|no\s+contract', lower))
        has_month_to_month = bool(re.search(r'month[\s-]*to[\s-]*month', lower))
        if has_no_lock and has_month_to_month:
            return 'No lock-in / month-to-month'
        if has_no_lock:
            return 'No lock-in'
        if has_month_to_month:
            return 'Month-to-month'
        contract_match = _RE_CONTRACT.search(combined)
        if contract_match:
            return contract_match.group(1).strip()
        return None

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
