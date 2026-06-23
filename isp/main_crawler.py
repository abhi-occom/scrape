"""
ISP Mini Crawler – Main Orchestrator
-------------------------------------
End-to-end pipeline:
  1. Accept a base URL from the user.
  2. Crawl inner pages to discover plan URLs.
  3. Analyse each page (detect network types, find selectors).
  4. Scrape plan data using auto-detected strategies.
  5. Validate, deduplicate, and normalise results.
  6. Return structured JSON + save to output/.

Usage:
    crawler = ISPCrawler("https://www.telstra.com.au/internet")
    results = crawler.run()
"""

import json
import os
import csv
import time
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import log_info, log_error, log_success, log_warning
from utils.stealth import create_stealth_browser, create_stealth_page
from config import PROVIDERS

from isp.url_discovery import URLDiscovery
from isp.plan_detector import PlanDetector, PageAnalysis
from isp.scraper_engine import ScraperEngine
from isp.validator import ISPValidator, ComparisonLogger


# ── Output directory ─────────────────────────────────────────────

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'output', 'isp_crawler',
)
ALL_PLANS_JSON_PATH = os.path.join(os.path.dirname(OUTPUT_DIR), 'all_plans.json')

PLAN_FIELDS = [
    'provider',
    'network_type',
    'plan_name',
    'download_speed',
    'upload_speed',
    'price',
    'promo_price',
    'promo_period',
    'contract',
    'typical_evening_dl',
    'typical_evening_ul',
    'source_url',
]


@dataclass
class CrawlResult:
    """Complete result of a crawl run."""
    base_url: str
    provider_name: str
    started_at: str = ''
    finished_at: str = ''
    duration_seconds: float = 0
    urls_visited: int = 0
    plan_pages_found: int = 0
    total_plans_scraped: int = 0
    valid_plans: int = 0
    invalid_plans: int = 0
    network_types_found: List[str] = field(default_factory=list)
    discovered_urls: List[Dict] = field(default_factory=list)
    page_analyses: List[Dict] = field(default_factory=list)
    plans: List[Dict[str, Any]] = field(default_factory=list)
    invalid_plan_details: List[Dict] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    success: bool = False


class ISPCrawler:
    """
    Main crawler that chains discovery → detection → scraping → validation.
    """

    def __init__(
        self,
        base_url: str,
        network_types: Optional[List[str]] = None,
        max_depth: int = 2,
        max_urls: int = 150,
        provider_name: str = '',
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.base_url = base_url.rstrip('/')
        self.network_types = network_types or ['nbn', 'opticomm', 'redtrain', 'supa']
        self.max_depth = max_depth
        self.max_urls = max_urls
        self.provider_name = provider_name or self._guess_provider(base_url)
        self.progress_callback = progress_callback

        # Components
        self.discovery = URLDiscovery(
            base_url=self.base_url,
            network_types=self.network_types,
            max_depth=self.max_depth,
            max_urls=self.max_urls,
        )
        self.detector = PlanDetector()
        self.engine = ScraperEngine()
        self.validator = ISPValidator()

    # ── Public API ────────────────────────────────────────────

    def run(self) -> CrawlResult:
        """
        Execute the full crawl pipeline.

        Returns:
            CrawlResult with all discovered data, plans, and metadata.
        """
        result = CrawlResult(
            base_url=self.base_url,
            provider_name=self.provider_name,
            started_at=datetime.now().isoformat(),
        )
        start_time = time.time()

        log_info(f"{'='*60}", provider="isp-crawler")
        log_info(f"ISP Crawler starting for: {self.base_url}", provider="isp-crawler")
        log_info(f"Provider: {self.provider_name}", provider="isp-crawler")
        log_info(f"Network types: {self.network_types}", provider="isp-crawler")
        log_info(f"Max depth: {self.max_depth}", provider="isp-crawler")
        log_info(f"{'='*60}", provider="isp-crawler")
        self._progress('starting', 'done', f'Started crawl for {self.base_url}')

        if self._provider_key_from_url(self.base_url):
            self._progress('discovering_urls', 'done', 'Known provider detected; using provider scraper first.')
            self._progress('scraping_plans', 'running', 'Running provider-specific scraper.')
            self._try_provider_fallback(result)
            if result.success:
                self._progress('scraping_plans', 'done', f'Provider scraper returned {result.valid_plans} plans.')
                self._progress('validating', 'done', 'Provider-specific plan output accepted.')
                return self._finalise_result(result, start_time)
            self._progress('scraping_plans', 'done', 'Provider scraper did not return complete plans; trying generic crawler.')

        try:
            with sync_playwright() as pw:
                browser = create_stealth_browser(pw)

                # ── Step 1: Discover plan URLs ───────────────────
                log_info("Step 1: Discovering plan page URLs...", provider="isp-crawler")
                self._progress('discovering_urls', 'running', 'Discovering inner URLs and likely plan pages.')
                discovered = self.discovery.crawl(browser)
                result.urls_visited = len(self.discovery.visited)

                base_entry = {
                    'url': self.base_url,
                    'score': 0,
                    'depth': 0,
                    'network_types': [],
                    'matched_networks': [],
                }

                if not discovered:
                    # If discovery found nothing, try the base URL directly
                    log_warning(
                        "No plan pages discovered via crawl, trying base URL directly",
                        provider="isp-crawler",
                    )
                    discovered = [base_entry]
                elif not any(entry.get('url') == self.base_url for entry in discovered):
                    # Some ISPs put plan cards on the landing page while discovery
                    # points to gated inner pages. Always analyse the submitted URL.
                    discovered = [base_entry] + discovered

                result.discovered_urls = discovered

                log_success(
                    f"Discovered {len(discovered)} candidate plan pages",
                    provider="isp-crawler",
                )
                self._progress(
                    'discovering_urls',
                    'done',
                    f'Discovered {len(discovered)} candidate pages from {result.urls_visited} visited URLs.',
                )

                if self._provider_key_from_url(self.base_url):
                    self._progress('scraping_plans', 'running', 'Running provider-specific scraper after discovery.')
                    self._try_provider_fallback(result)
                    if result.success:
                        self._progress('scraping_plans', 'done', f'Provider scraper returned {result.valid_plans} plans.')
                        self._progress('validating', 'done', 'Provider-specific plan output accepted.')
                        try:
                            browser.close()
                        except Exception:
                            pass
                        return self._finalise_result(result, start_time)

                # ── Step 2: Analyse each page ────────────────────
                log_info("Step 2: Analysing pages for plan data...", provider="isp-crawler")
                self._progress('analyzing_pages', 'running', f'Analyzing {len(discovered)} candidate pages for plan signals.')
                plan_pages: List[Dict] = []

                for index, entry in enumerate(discovered, start=1):
                    url = entry['url']
                    self._progress('analyzing_pages', 'running', f'Analyzing page {index} of {len(discovered)}.')
                    page = create_stealth_page(browser)
                    try:
                        resp = page.goto(url, wait_until='domcontentloaded', timeout=25000)
                        if not resp or resp.status >= 400:
                            log_warning(f"HTTP {resp.status if resp else '?'}: {url}", provider="isp-crawler")
                            continue

                        page.wait_for_timeout(5000)
                        analysis = self.detector.analyse(page, url)

                        analysis_dict = {
                            'url': analysis.url,
                            'has_plans': analysis.has_plans,
                            'confidence': analysis.confidence,
                            'network_types': analysis.network_types,
                            'card_selector': analysis.card_selector,
                            'card_count': analysis.card_count,
                            'name_selector': analysis.name_selector,
                            'price_selector': analysis.price_selector,
                            'speed_selector': analysis.speed_selector,
                            'price_signals': analysis.price_signals,
                            'speed_signals': analysis.speed_signals,
                        }
                        result.page_analyses.append(analysis_dict)

                        if analysis.has_plans:
                            plan_pages.append({
                                'entry': entry,
                                'analysis': analysis,
                                'page': page,       # keep page open for scraping
                            })
                            log_success(
                                f"Plan page confirmed: {url} "
                                f"(confidence={analysis.confidence:.2f}, "
                                f"cards={analysis.card_count})",
                                provider="isp-crawler",
                            )
                        else:
                            page.close()

                    except Exception as e:
                        log_error(f"Error analysing {url}: {e}", provider="isp-crawler")
                        result.errors.append(f"Analysis error: {url} - {str(e)}")
                        try:
                            page.close()
                        except Exception:
                            pass

                result.plan_pages_found = len(plan_pages)
                self._progress(
                    'analyzing_pages',
                    'done',
                    f'Confirmed {len(plan_pages)} plan pages from {len(discovered)} candidates.',
                )
                log_info(
                    f"Found {len(plan_pages)} confirmed plan pages out of {len(discovered)} candidates",
                    provider="isp-crawler",
                )

                # ── Step 3: Scrape plans from each page ──────────
                log_info("Step 3: Extracting plan data...", provider="isp-crawler")
                self._progress('scraping_plans', 'running', f'Scraping plans from {len(plan_pages)} confirmed pages.')
                all_plans: List[Dict] = []

                for index, pp in enumerate(plan_pages, start=1):
                    url = pp['entry']['url']
                    analysis: PageAnalysis = pp['analysis']
                    page: Any = pp['page']
                    self._progress('scraping_plans', 'running', f'Scraping page {index} of {len(plan_pages)}.')

                    try:
                        plans = self.engine.extract(
                            page=page,
                            analysis=analysis,
                            provider_name=self.provider_name,
                        )

                        for p in plans:
                            p['provider'] = self.provider_name
                            p['source_url'] = url
                            if not p.get('network_type') and analysis.network_types:
                                p['network_type'] = analysis.network_types[0].upper()

                        all_plans.extend(plans)
                        log_success(
                            f"Extracted {len(plans)} plans from {url}",
                            provider="isp-crawler",
                        )

                    except Exception as e:
                        log_error(f"Scraping error on {url}: {e}", provider="isp-crawler")
                        result.errors.append(f"Scrape error: {url} - {str(e)}")
                    finally:
                        try:
                            page.close()
                        except Exception:
                            pass

                # ── Step 4: Deduplicate across pages ─────────────
                all_plans = self._global_deduplicate(all_plans)
                self._progress('scraping_plans', 'done', f'Scraped {len(all_plans)} unique plans before validation.')

                # ── Step 5: Validate ─────────────────────────────
                log_info("Step 4: Validating scraped plans...", provider="isp-crawler")
                self._progress('validating', 'running', f'Validating {len(all_plans)} scraped plans.')
                valid, invalid, _ = self.validator.validate_batch(all_plans)

                result.plans = valid
                result.invalid_plan_details = invalid
                result.total_plans_scraped = len(all_plans)
                result.valid_plans = len(valid)
                result.invalid_plans = len(invalid)
                result.network_types_found = list(set(
                    p.get('network_type', '') for p in valid if p.get('network_type')
                ))
                result.success = len(valid) > 0
                self._progress('validating', 'done', f'Validated {len(valid)} plans; rejected {len(invalid)}.')

                browser.close()

        except Exception as e:
            log_error(f"Crawler fatal error: {e}", provider="isp-crawler")
            result.errors.append(f"Fatal: {str(e)}")
            self._progress('error', 'error', f'Crawler fatal error: {str(e)}')

        self._progress('scraping_plans', 'running', 'Checking provider-specific fallback for richer data.')
        self._try_provider_fallback(result)
        if result.success:
            self._progress('scraping_plans', 'done', f'Plan extraction complete with {result.valid_plans} valid plans.')

        return self._finalise_result(result, start_time)

    def _finalise_result(self, result: CrawlResult, start_time: float) -> CrawlResult:
        """Complete timing, logging, persistence, and return the crawl result."""
        result.plans = [self._normalise_plan_fields(plan) for plan in result.plans]
        result.network_types_found = sorted(set(
            p.get('network_type', '') for p in result.plans if p.get('network_type')
        ))

        # ── Finalise ─────────────────────────────────────────
        result.finished_at = datetime.now().isoformat()
        result.duration_seconds = round(time.time() - start_time, 2)

        log_info(f"{'='*60}", provider="isp-crawler")
        log_success(
            f"Crawl complete for {self.provider_name}: "
            f"{result.valid_plans} valid plans, "
            f"{result.invalid_plans} invalid, "
            f"{result.plan_pages_found} pages scraped in {result.duration_seconds}s",
            provider="isp-crawler",
        )
        log_info(f"Network types: {result.network_types_found}", provider="isp-crawler")
        log_info(f"{'='*60}", provider="isp-crawler")

        # Save output
        self._progress('saving', 'running', 'Saving JSON and CSV output files.')
        self._save_results(result)
        self._progress('saving', 'done', 'Saved crawl output files.')
        self._progress('completed', 'done', f'Crawl complete with {result.valid_plans} valid plans.')

        return result

    def _progress(self, stage: str, status: str = 'running', message: str = '') -> None:
        """Send a UI progress event when a callback is attached."""
        if not self.progress_callback:
            return
        try:
            self.progress_callback({
                'stage': stage,
                'status': status,
                'message': message,
            })
        except Exception:
            pass

    def _try_provider_fallback(self, result: CrawlResult) -> None:
        """Use existing provider-specific scrapers when they improve known-provider results."""
        provider_key = self._provider_key_from_url(self.base_url)
        if not provider_key:
            return

        try:
            log_warning(
                f"Checking {provider_key} provider scraper fallback",
                provider="isp-crawler",
            )
            from scraper_service import scrape_provider

            fallback = scrape_provider(provider_key)
            plans = self._flatten_provider_plans(fallback.get('plans', []))

            if not fallback.get('success') or not plans:
                if result.valid_plans == 0:
                    error = fallback.get('error') or f"{provider_key} fallback returned no plans"
                    result.errors.append(f"Provider fallback failed: {error}")
                return

            requested_networks = set(n.lower() for n in self.network_types)
            supported_networks = {
                str(n).lower()
                for n in PROVIDERS.get(provider_key, {}).get('supported_networks', [])
            }
            allowed_networks = requested_networks
            if supported_networks:
                allowed_networks = requested_networks.intersection(supported_networks)

            plans = [
                plan for plan in plans
                if str(plan.get('network_type', '')).lower() in allowed_networks
            ]
            if not plans:
                if result.valid_plans == 0:
                    result.errors.append(
                        f"Provider fallback returned no plans for requested networks: "
                        f"{', '.join(sorted(allowed_networks))}"
                    )
                return

            fallback_networks = sorted(set(
                p.get('network_type', '') for p in plans if p.get('network_type')
            ))
            current_networks = set(n.lower() for n in result.network_types_found)
            fallback_networks_lower = set(n.lower() for n in fallback_networks)
            missing_requested_networks = (
                requested_networks
                and requested_networks.intersection(fallback_networks_lower)
                and not requested_networks.intersection(current_networks)
            )
            fallback_metadata_score = self._plan_metadata_score(plans)
            current_metadata_score = self._plan_metadata_score(result.plans)
            should_replace = (
                result.valid_plans == 0
                or len(plans) > result.valid_plans
                or bool(missing_requested_networks)
                or fallback_metadata_score > current_metadata_score
            )
            if not should_replace:
                return

            for plan in plans:
                plan.setdefault('provider', provider_key.capitalize())
                plan.setdefault('source_url', self.base_url)

            self.provider_name = provider_key.capitalize()
            result.provider_name = self.provider_name
            result.plans = plans
            result.total_plans_scraped = len(plans)
            result.valid_plans = len(plans)
            result.invalid_plans = 0
            result.network_types_found = fallback_networks
            source_page_count = len(set(
                p.get('source_url', '') for p in plans if p.get('source_url')
            ))
            result.plan_pages_found = max(result.plan_pages_found, source_page_count, 1)
            submitted_url_count = 1 if self.base_url else 0
            result.urls_visited = max(
                result.urls_visited,
                source_page_count + submitted_url_count,
            )
            result.success = True
            log_success(
                f"Provider fallback extracted {len(plans)} plans for {provider_key}",
                provider="isp-crawler",
            )

        except Exception as e:
            result.errors.append(f"Provider fallback error: {str(e)}")
            log_error(f"Provider fallback error: {e}", provider="isp-crawler")

    def _provider_key_from_url(self, url: str) -> Optional[str]:
        """Map known ISP domains to existing provider scraper keys."""
        domain = urlparse(url).netloc.lower().replace('www.', '')
        known_domains = {
            'optus.com.au': 'optus',
            'telstra.com.au': 'telstra',
            'superloop.com': 'superloop',
            'occom.com.au': 'occom',
            'exetel.com.au': 'exetel',
            'leaptel.com.au': 'leaptel',
            'swoop.com.au': 'swoop',
            'dodo.com': 'dodo',
            'iinet.net.au': 'iinet',
            'iprimus.com.au': 'iprimus',
            'koganinternet.com.au': 'kogan',
            'letsbemates.com.au': 'mate',
            'more.com.au': 'more',
            'originenergy.com.au': 'origin',
            'spintel.net.au': 'spintel',
            'tangerine.com.au': 'tangerine',
            'tangerinetelecom.com.au': 'tangerine',
            'tpg.com.au': 'tpg',
            'activ8me.net.au': 'activ8me',
            'aussiebroadband.com.au': 'aussie',
            'airtel.au': 'airtel',
            'alpha.net.au': 'alpha',
            'home.alpha.net.au': 'alpha',
            'city7net.com.au': 'city7net',
            'epsinet.com.au': 'epsinet',
            'iqnet.com.au': 'iqnet',
            'newausfiber.com.au': 'newausfiber',
            'vocphone.com': 'vocphone',
        }
        for known_domain, provider_key in known_domains.items():
            if domain == known_domain or domain.endswith(f".{known_domain}"):
                return provider_key
        return None

    def _flatten_provider_plans(self, plans: Any) -> List[Dict[str, Any]]:
        """Flatten provider scrapers that return network-keyed plan dictionaries."""
        if isinstance(plans, list):
            return plans
        if isinstance(plans, dict):
            flattened = []
            for group in plans.values():
                if isinstance(group, list):
                    flattened.extend(group)
            return flattened
        return []

    def _plan_metadata_score(self, plans: List[Dict[str, Any]]) -> int:
        """Score optional fields so richer provider-specific output can replace generic output."""
        score = 0
        for plan in plans or []:
            if plan.get('promo_price') not in (None, '', 0):
                score += 3
            if plan.get('promo_period') not in (None, ''):
                score += 2
            if plan.get('contract') not in (None, ''):
                score += 1
            if plan.get('typical_evening_dl') not in (None, '', 0):
                score += 1
            if plan.get('typical_evening_ul') not in (None, '', 0):
                score += 1
        return score

    def _normalise_plan_fields(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Return a plan row with exactly the saved output fields."""
        normalised = {field: plan.get(field) for field in PLAN_FIELDS}
        normalised['provider'] = normalised.get('provider') or self.provider_name
        normalised['network_type'] = self._canonical_network_type(
            normalised.get('network_type') or self._default_network_type()
        )
        normalised['plan_name'] = normalised.get('plan_name') or ''
        normalised['download_speed'] = normalised.get('download_speed') or 0
        normalised['upload_speed'] = normalised.get('upload_speed') or 0
        normalised['price'] = normalised.get('price') or 0
        normalised['promo_price'] = normalised.get('promo_price')
        normalised['promo_period'] = normalised.get('promo_period')
        normalised['contract'] = normalised.get('contract')
        normalised['typical_evening_dl'] = (
            normalised.get('typical_evening_dl')
            if normalised.get('typical_evening_dl') not in (None, '', 0)
            else normalised['download_speed']
        )
        normalised['typical_evening_ul'] = (
            normalised.get('typical_evening_ul')
            if normalised.get('typical_evening_ul') not in (None, '', 0)
            else normalised['upload_speed']
        )
        normalised['source_url'] = normalised.get('source_url') or self.base_url
        return normalised

    @staticmethod
    def _canonical_network_type(network_type: Any) -> str:
        """Collapse known private-network aliases into UI/filter friendly labels."""
        raw = str(network_type or '').strip()
        compact = re.sub(r'[\s_-]+', ' ', raw).lower()

        if 'opticomm' in compact:
            return 'Opticomm'
        if 'redtrain' in compact or 'red train' in compact:
            return 'Redtrain'
        if 'supa' in compact or 'supanetwork' in compact:
            return 'Supa'
        if compact == 'nbn':
            return 'NBN'

        return raw

    def _default_network_type(self) -> str:
        """Return provider-level network defaults when pages do not expose the network label."""
        domain = urlparse(self.base_url).netloc.lower().replace('www.', '')
        provider = (self.provider_name or '').lower()
        if domain == 'clevernet.com.au' or domain.endswith('.clevernet.com.au') or provider == 'clevernet':
            return 'Supa'
        return ''

    # ── Output ────────────────────────────────────────────────

    def _save_results(self, result: CrawlResult):
        """Save results to JSON and CSV files."""
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        safe_name = self.provider_name.lower().replace(' ', '_').replace('.', '')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # ── JSON ─────────────────────────────────────────────
        json_path = os.path.join(OUTPUT_DIR, f"{safe_name}_{timestamp}.json")
        json_data = {
            'base_url': result.base_url,
            'provider': result.provider_name,
            'started_at': result.started_at,
            'finished_at': result.finished_at,
            'duration_seconds': result.duration_seconds,
            'summary': {
                'urls_visited': result.urls_visited,
                'plan_pages_found': result.plan_pages_found,
                'total_plans_scraped': result.total_plans_scraped,
                'valid_plans': result.valid_plans,
                'invalid_plans': result.invalid_plans,
                'network_types': result.network_types_found,
            },
            'discovered_urls': result.discovered_urls,
            'page_analyses': result.page_analyses,
            'plans': result.plans,
            'invalid_plans': result.invalid_plan_details,
            'errors': result.errors,
        }

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
        log_info(f"Results saved to {json_path}", provider="isp-crawler")

        # ── Also save latest (overwrite) ─────────────────────
        latest_path = os.path.join(OUTPUT_DIR, f"{safe_name}_latest.json")
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        # ── CSV ──────────────────────────────────────────────
        if result.plans:
            csv_path = os.path.join(OUTPUT_DIR, f"{safe_name}_{timestamp}.csv")
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=PLAN_FIELDS, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(result.plans)
            log_info(f"CSV saved to {csv_path}", provider="isp-crawler")

        self._save_all_plans_snapshot()

    def _save_all_plans_snapshot(self):
        """Rebuild output/all_plans.json and CSV from every provider latest file."""
        all_plans = []
        providers = []

        for filename in sorted(os.listdir(OUTPUT_DIR)):
            if not filename.endswith('_latest.json'):
                continue
            path = os.path.join(OUTPUT_DIR, filename)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue

            plans = []
            for plan in data.get('plans') or []:
                normalised = self._normalise_plan_fields(plan)
                normalised['provider'] = plan.get('provider') or data.get('provider') or normalised['provider']
                normalised['source_url'] = plan.get('source_url') or data.get('base_url', '') or normalised['source_url']
                plans.append(normalised)
            provider = data.get('provider') or filename.replace('_latest.json', '')
            providers.append({
                'provider': provider,
                'base_url': data.get('base_url', ''),
                'latest_file': filename,
                'plans_count': len(plans),
                'started_at': data.get('started_at', ''),
            })
            all_plans.extend(plans)

        combined = {
            'scraped_at': datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
            'source': 'isp_crawler_latest_files',
            'total_providers': len(providers),
            'total_plans': len(all_plans),
            'providers': providers,
            'plans': all_plans,
        }

        with open(ALL_PLANS_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(combined, f, indent=2, ensure_ascii=False)

        csv_path = os.path.splitext(ALL_PLANS_JSON_PATH)[0] + '.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=PLAN_FIELDS, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(all_plans)

        log_info(
            f"All plans snapshot rebuilt with {len(all_plans)} plans from {len(providers)} providers",
            provider="isp-crawler",
        )

    # ── Helpers ───────────────────────────────────────────────

    def _global_deduplicate(self, plans: List[Dict]) -> List[Dict]:
        """Deduplicate plans across all pages."""
        seen = set()
        unique = []
        for p in plans:
            key = (
                p.get('plan_name', '').lower().strip(),
                round(p.get('price', 0), 2),
                p.get('download_speed', 0),
                p.get('network_type', '').lower(),
            )
            if key not in seen:
                seen.add(key)
                unique.append(p)
        if len(plans) != len(unique):
            log_info(
                f"Deduplicated: {len(plans)} → {len(unique)} plans",
                provider="isp-crawler",
            )
        return unique

    def _guess_provider(self, url: str) -> str:
        """Extract a human-readable provider name from the URL domain."""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        # Remove common prefixes/suffixes
        name = domain.replace('www.', '').split('.')[0]
        return name.capitalize()


# ── CLI Interface ────────────────────────────────────────────────

def run_from_cli():
    """Run the crawler from the command line."""
    import argparse

    parser = argparse.ArgumentParser(
        description='ISP Mini Crawler – discover and scrape broadband plans from any ISP URL',
    )
    parser.add_argument('url', help='Base URL of the ISP website (e.g. https://www.telstra.com.au/internet)')
    parser.add_argument('--name', default='', help='Provider name (auto-detected if not specified)')
    parser.add_argument('--depth', type=int, default=2, help='Max crawl depth (default: 2)')
    parser.add_argument('--networks', nargs='+', default=['nbn', 'opticomm', 'redtrain', 'supa'],
                        help='Network types to look for (default: nbn opticomm redtrain supa)')
    parser.add_argument('--max-urls', type=int, default=150, help='Max URLs to visit (default: 150)')

    args = parser.parse_args()

    crawler = ISPCrawler(
        base_url=args.url,
        network_types=args.networks,
        max_depth=args.depth,
        max_urls=args.max_urls,
        provider_name=args.name,
    )

    result = crawler.run()

    # Print summary
    print(f"\n{'='*60}")
    print(f"  CRAWL SUMMARY: {result.provider_name}")
    print(f"{'='*60}")
    print(f"  Base URL:          {result.base_url}")
    print(f"  Duration:          {result.duration_seconds}s")
    print(f"  URLs visited:      {result.urls_visited}")
    print(f"  Plan pages found:  {result.plan_pages_found}")
    print(f"  Plans scraped:     {result.total_plans_scraped}")
    print(f"  Valid plans:       {result.valid_plans}")
    print(f"  Invalid plans:     {result.invalid_plans}")
    print(f"  Network types:     {', '.join(result.network_types_found)}")
    print(f"  Success:           {'YES' if result.success else 'NO'}")
    print(f"{'='*60}")

    if result.plans:
        print(f"\n  Plans found:\n")
        for p in result.plans:
            promo = f" (promo: ${p['promo_price']})" if p.get('promo_price') else ""
            speed = f"{p.get('download_speed', '?')}/{p.get('upload_speed', '?')} Mbps"
            print(f"    {p['plan_name']:<40s} [{p.get('network_type', '?'):>15s}]  ${p.get('price', '?'):>8}/mth{promo}  {speed}")

    if result.errors:
        print(f"\n  Errors:")
        for e in result.errors:
            print(f"    - {e}")

    return result


if __name__ == "__main__":
    run_from_cli()
