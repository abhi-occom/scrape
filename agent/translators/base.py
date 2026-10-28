"""Shared interface every translator backend implements.

The job dict shape is the contract the rest of the agent (executor.py,
responder.py) depends on — every backend, rule-based or AI, must return
this same shape (or None to signal "couldn't produce a confident job",
which the caller then falls back on).
"""
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

JOB_KEYS = ('message', 'providers', 'networks', 'action', 'compare_against', 'notes')

# Shared by every AI backend (claude_translator.py, gemini_translator.py) so
# both providers are asked the same question in the same shape and parsed
# by the same validation path.
AI_SYSTEM_PROMPT = """You turn one sentence about Australian internet/ISP plans into JSON.

Known provider keys: {provider_keys}

Return ONLY a JSON object, no prose, shaped exactly like:
{{
  "providers": ["<provider key from the known list, or your best guess of the name if unsure>"],
  "networks": ["nbn" | "opticomm" | "supa" | "redtrain" | "fixed wireless" | "fibre" | "mobile" | "5g" | "starlink"],
  "action": "scrape_only" | "scrape_and_compare" | "unsupported_scrape_all" | "unsupported_history" | "unrecognized",
  "compare_against": "occom" | null
}}

Rules:
- "scrape_and_compare" + compare_against="occom" whenever the sentence compares to Occom, "us", or asks how a provider stacks up.
- "unsupported_scrape_all" if the sentence asks to scrape every/all providers.
- "unsupported_history" if the sentence asks about price history, health, or what changed since last time.
- "unrecognized" if no provider is mentioned at all.
- networks: [] if no network type is mentioned.
- Never invent an action or field not listed above.
"""


def empty_job(message: str, action: str, notes: Optional[list] = None) -> Dict[str, Any]:
    """Build a well-formed job dict for the no-op/unsupported/error cases."""
    return {
        'message': message,
        'providers': [],
        'networks': [],
        'action': action,
        'compare_against': None,
        'notes': notes or [],
    }


class Translator(ABC):
    """A translator turns one free-text message into a structured job dict."""

    name = 'base'

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this backend is usable right now (e.g. API key present,
        SDK installed). Cheap and side-effect-free — called before every
        translate() attempt."""
        raise NotImplementedError

    @abstractmethod
    def translate(self, message: str) -> Optional[Dict[str, Any]]:
        """Return a job dict, or None if this backend could not produce one
        (missing dependency, API error, invalid response) — callers should
        fall back to the next backend in that case, never raise."""
        raise NotImplementedError


def parse_ai_job(original_message: str, raw_text: str) -> Optional[Dict[str, Any]]:
    """Shared by every AI translator backend: parse the model's JSON reply
    into a validated job dict, resolving provider names against the real
    config.py keys (never trust the AI's spelling as-is).

    Import is local to avoid a hard dependency between this base module and
    agent.provider_matching at package-import time.
    """
    from agent.provider_matching import resolve_provider_names

    try:
        data = json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return None

    action = data.get('action')
    valid_actions = {
        'scrape_only', 'scrape_and_compare', 'unsupported_scrape_all',
        'unsupported_history', 'unrecognized',
    }
    if action not in valid_actions:
        return None

    providers = resolve_provider_names(data.get('providers') or [])
    networks = [n for n in (data.get('networks') or []) if isinstance(n, str)]
    compare_against = data.get('compare_against') if data.get('compare_against') in ('occom', None) else None

    if compare_against:
        providers = [p for p in providers if p != 'occom']

    if action in ('scrape_only', 'scrape_and_compare') and not providers:
        action = 'unrecognized'

    notes: List[str] = []
    if action == 'unrecognized':
        notes.append(
            'I could not confidently match a provider name in that. Try naming one directly, '
            'e.g. "scrape TPG NBN plans" or "compare Superloop to Occom".'
        )
    elif action == 'unsupported_scrape_all':
        notes.append(
            'Scraping every provider from chat is not wired up in this MVP — use the "Scrape All" '
            'button on /isp for that instead.'
        )
    elif action == 'unsupported_history':
        notes.append('Run history and health reports already exist at /isp/health.')

    return {
        'message': original_message,
        'providers': providers,
        'networks': networks,
        'action': action,
        'compare_against': compare_against,
        'notes': notes,
    }
