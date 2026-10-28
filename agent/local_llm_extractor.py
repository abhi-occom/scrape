"""Phase 4 (optional): local LLM fallback extractor via Ollama.

This is a LAST-RESORT path, not a replacement for the project's existing
deterministic scraping. It only runs when a provider's own scraper
(providers/<key>.py via scraper_service.py) returns no usable plans, and
only if Ollama is actually installed and running locally — otherwise this
module is a no-op and executor.py behaves exactly as it did before Phase 4
existed.

Everything this module returns is treated as UNTRUSTED input: it goes
through the project's existing isp/validator.py checks before being used
anywhere, the same as any other scraped plan.

See AI_AGENT_BROWSER_PLAN.md section 3.D for the design rationale and the
laptop-specific model recommendation (qwen2.5:7b-instruct as the default
for a 4GB-VRAM GPU).
"""
import os
import re
import json
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

OLLAMA_BASE_URL = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
# Default matches what was actually found pulled on this machine's Ollama
# (`ollama list` / GET /api/tags) — see AI_AGENT_BROWSER_PLAN.md section
# 3.D for why this replaced the earlier generic qwen2.5 recommendation.
DEFAULT_MODEL = os.environ.get('OLLAMA_MODEL', 'qwen3:4b-instruct-2507-q4_K_M')

_AVAILABILITY_TIMEOUT = 1.5   # seconds - this is a liveness probe, must stay fast
_FETCH_TIMEOUT = 20           # seconds - fetching a real ISP page
_LLM_TIMEOUT = 120            # seconds - local inference can be slow, see the plan doc
_MAX_PAGE_TEXT_CHARS = 8000   # keep the prompt small and inference fast


def is_ollama_available() -> bool:
    """Cheap liveness check — used before every fallback attempt, and by
    /agent/api/config for debugging/UI display. Never raises."""
    try:
        resp = requests.get(f'{OLLAMA_BASE_URL}/api/tags', timeout=_AVAILABILITY_TIMEOUT)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def fetch_page_text(url: str) -> str:
    """Fetch a URL and reduce it to visible text for the LLM prompt.

    This is a plain HTTP GET (via `requests`), not a full Playwright render
    — some JS-heavy ISP sites won't expose their plan text this way. That's
    an accepted limitation of this fallback tier: it's a last resort for
    when the deterministic engine (which DOES render JS) already failed, so
    reaching for a lighter-weight fetch here keeps this path fast and
    simple rather than spinning up a second browser.
    """
    try:
        resp = requests.get(
            url,
            timeout=_FETCH_TIMEOUT,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; ISP-Scraper-Agent/1.0)'},
        )
        resp.raise_for_status()
    except requests.RequestException:
        return ''

    soup = BeautifulSoup(resp.text, 'lxml')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    text = re.sub(r'\n{2,}', '\n', soup.get_text('\n', strip=True))
    return text[:_MAX_PAGE_TEXT_CHARS]


_EXTRACTION_PROMPT = """Extract EVERY internet/broadband plan mentioned in this webpage text —
there may be several; list all of them, not just the first one.

Return ONLY a JSON array (even if there is only one plan, wrap it in [ ]),
no prose, of objects shaped exactly like:
[{{"plan_name": "...", "network_type": "...", "download_speed": <number or null>,
   "upload_speed": <number or null>, "price": <number or null>}},
 {{...another plan...}}]

Use null for anything you are not confident about. Do not invent numbers.
If no plans are found, return an empty array [].

Webpage text for provider "{provider_name}":
{page_text}
"""


def extract_plans_with_llm(
    page_text: str,
    provider_name: str,
    model: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Ask the local Ollama model to extract plans from page text.

    Returns a list of RAW (unvalidated) plan dicts — the caller
    (agent/executor.py) is responsible for running these through
    isp/validator.py before treating them as real data. Returns []
    on any failure (Ollama down, bad JSON, timeout) rather than raising.
    """
    if not page_text.strip():
        return []

    try:
        response = requests.post(
            f'{OLLAMA_BASE_URL}/api/chat',
            json={
                'model': model or DEFAULT_MODEL,
                'messages': [{
                    'role': 'user',
                    'content': _EXTRACTION_PROMPT.format(
                        provider_name=provider_name, page_text=page_text,
                    ),
                }],
                'format': 'json',
                'stream': False,
            },
            timeout=_LLM_TIMEOUT,
        )
        response.raise_for_status()
        content = response.json().get('message', {}).get('content', '')
        parsed = json.loads(content)
    except (requests.RequestException, json.JSONDecodeError, ValueError, KeyError):
        return []

    # Local models don't always follow the "always an array" instruction —
    # tolerate a bare single-object response, or a wrapper object holding
    # the array under some key, rather than discarding real data.
    if isinstance(parsed, dict):
        if parsed.get('plan_name'):
            parsed = [parsed]
        else:
            list_values = [v for v in parsed.values() if isinstance(v, list)]
            parsed = list_values[0] if list_values else []

    if not isinstance(parsed, list):
        return []

    plans: List[Dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict) or not item.get('plan_name'):
            continue
        plans.append({
            'provider': provider_name,
            'plan_name': item.get('plan_name'),
            'network_type': item.get('network_type') or 'NBN',
            'download_speed': item.get('download_speed'),
            'upload_speed': item.get('upload_speed'),
            'price': item.get('price'),
            'promo_price': None,
            'promo_period': None,
            'contract': None,
            'source_url': None,
        })
    return plans


def likely_missed_plans(page_text: str, extracted_count: int) -> bool:
    """Cheap heuristic flag for a REAL, confirmed failure mode of the small
    local models tested for this project: they sometimes return only the
    first plan on a page despite an explicit "extract ALL plans" instruction
    (reproduced with qwen3:4b-instruct-2507-q4_K_M — see
    AI_AGENT_BROWSER_PLAN.md section 3.D). This does not fix that, it just
    surfaces a "you probably got an incomplete result" signal by counting
    price-looking mentions ("$123", "123.99") against how many plans came
    back — a rough proxy, not a guarantee either way.
    """
    price_mentions = len(re.findall(r'\$\s?\d', page_text))
    return price_mentions > max(extracted_count + 1, 1)
