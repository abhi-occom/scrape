"""Runs a translated job by calling the project's EXISTING scraping and
benchmark code. Nothing here re-implements scraping, validation, or
comparison logic — it only orchestrates scraper_service.py and
utils/benchmark.py, exactly the same functions the main dashboard and
/isp crawler already use.
"""
from typing import Any, Dict, List

import os

import scraper_service
from config import PROVIDERS
from utils import benchmark as benchmark_utils
from agent.local_llm_extractor import (
    extract_plans_with_llm,
    fetch_page_text,
    is_ollama_available,
    likely_missed_plans,
)

# Phase 4 is genuinely optional (see AI_AGENT_BROWSER_PLAN.md section 3.D) —
# off by default. Set AGENT_ENABLE_LOCAL_LLM_FALLBACK=true to turn it on.
_LOCAL_LLM_FALLBACK_ENABLED = os.environ.get('AGENT_ENABLE_LOCAL_LLM_FALLBACK', '').lower() in (
    '1', 'true', 'yes',
)


def is_isp_crawler_busy() -> bool:
    """Best-effort check of the /isp crawler's in-memory state, so the agent
    does not start a second Playwright job on top of a running one.

    isp/routes.py keeps this state in module-private variables (leading
    underscore) since it was never meant to be imported elsewhere. Reading
    it here is deliberately defensive (try/except) so a rename over there
    degrades to "assume not busy" instead of breaking the agent.
    """
    try:
        from isp import routes as isp_routes
        return bool(isp_routes._crawl_state.get('running')) or bool(
            isp_routes._crawl_all_state.get('running')
        )
    except Exception:
        return False


def _flatten_plans(plans: Any) -> List[Dict[str, Any]]:
    """Provider scrapers return either a flat list, or (e.g. Occom) a dict
    of network-keyed lists. Flatten to a list for filtering/display only —
    the ORIGINAL shape is still what gets passed to save_output()."""
    if isinstance(plans, dict):
        flattened: List[Dict[str, Any]] = []
        for group in plans.values():
            if isinstance(group, list):
                flattened.extend(group)
        return flattened
    return list(plans or [])


def _filter_by_networks(plans: List[Dict[str, Any]], networks: List[str]) -> List[Dict[str, Any]]:
    if not networks:
        return plans
    wanted = {n.lower() for n in networks}
    return [
        p for p in plans
        if any(n in str(p.get('network_type', '')).lower() for n in wanted)
    ]


def _try_local_llm_fallback(provider_key: str) -> Dict[str, Any]:
    """Phase 4: if the primary scraper found nothing, and the fallback is
    enabled and Ollama is actually reachable, try reading the provider's
    known page with a local LLM instead. Returns {'plans': [], 'possibly_incomplete': False}
    on any failure or if the fallback is disabled/unavailable — this must
    never raise, since it sits in the middle of the normal (already-failed)
    scrape path.

    Every plan returned here is run through the project's existing
    isp/validator.py before being trusted, same as any other scraped plan.

    `possibly_incomplete` is a real, empirically-confirmed caveat (see
    AI_AGENT_BROWSER_PLAN.md section 3.D "real-world finding"): the small
    local models tested for this project sometimes only extract the FIRST
    plan on a multi-plan page. It's a rough heuristic, not a guarantee.
    """
    empty = {'plans': [], 'possibly_incomplete': False}
    if not _LOCAL_LLM_FALLBACK_ENABLED or not is_ollama_available():
        return empty

    try:
        from isp.routes import PROVIDER_CRAWL_URLS
    except Exception:
        return empty

    url = PROVIDER_CRAWL_URLS.get(provider_key)
    if not url:
        return empty

    page_text = fetch_page_text(url)
    if not page_text:
        return empty

    provider_name = PROVIDERS.get(provider_key, {}).get('name', provider_key.title())
    raw_plans = extract_plans_with_llm(page_text, provider_name)
    if not raw_plans:
        return empty

    for plan in raw_plans:
        plan['source_url'] = url

    try:
        from isp.validator import ISPValidator
        valid, _invalid, _results = ISPValidator().validate_batch(raw_plans)
    except Exception:
        return empty

    return {
        'plans': valid,
        'possibly_incomplete': likely_missed_plans(page_text, len(valid)),
    }


def run_job(job: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a translated job. Returns raw results for responder.py to format.

    {
        'scraped': {provider_key: {'success': bool, 'plans': [...], 'error': str|None}},
        'benchmark': dict | None,   # utils.benchmark.run_benchmark() output
        'errors': [str, ...],
    }
    """
    result: Dict[str, Any] = {'scraped': {}, 'benchmark': None, 'errors': []}

    action = job.get('action')
    if action not in ('scrape_only', 'scrape_and_compare'):
        return result

    if is_isp_crawler_busy():
        result['errors'].append(
            'The /isp crawler is already running a job right now — try again once it '
            'finishes (check /isp/api/status or /isp/api/crawl-all/status).'
        )
        return result

    for provider_key in job.get('providers', []):
        if provider_key not in PROVIDERS:
            result['scraped'][provider_key] = {
                'success': False, 'plans': [], 'error': 'Unknown provider key',
            }
            continue

        try:
            scrape_result = scraper_service.scrape_provider(provider_key)
        except Exception as exc:
            result['scraped'][provider_key] = {'success': False, 'plans': [], 'error': str(exc)}
            continue

        plans_raw = scrape_result.get('plans')
        plans_list = _flatten_plans(plans_raw)

        if scrape_result.get('success') and plans_list:
            try:
                scraper_service.save_output(provider_key, plans_raw)
            except Exception as exc:
                result['errors'].append(f'Saved output failed for {provider_key}: {exc}')

        plans_list = _filter_by_networks(plans_list, job.get('networks') or [])
        used_local_llm_fallback = False
        possibly_incomplete = False

        if not plans_list:
            fallback = _try_local_llm_fallback(provider_key)
            fallback_plans = _filter_by_networks(fallback['plans'], job.get('networks') or [])
            if fallback_plans:
                plans_list = fallback_plans
                used_local_llm_fallback = True
                possibly_incomplete = fallback['possibly_incomplete']

        result['scraped'][provider_key] = {
            'success': bool(plans_list),
            'plans': plans_list,
            'error': None if plans_list else scrape_result.get('error'),
            'source': 'local_llm_fallback' if used_local_llm_fallback else 'scraper',
            'possibly_incomplete': possibly_incomplete,
        }

    if job.get('compare_against') == 'occom':
        try:
            result['benchmark'] = benchmark_utils.run_benchmark()
        except Exception as exc:
            result['errors'].append(f'Benchmark comparison failed: {exc}')

    return result
