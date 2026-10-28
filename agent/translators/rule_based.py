"""Phase 1 rule-based English-to-job translator.

No AI model call — provider and network recognition is keyword/alias
matching against config.py's PROVIDERS dict (with fuzzy fallback via
agent/provider_matching.py). This is the ALWAYS-AVAILABLE backend: every
other translator in this package falls back to this one if it can't run
or produces an invalid response, so this file must never raise and must
never depend on an external service.
"""
import re
from typing import Any, Dict, List, Optional

from config import PROVIDERS

from agent.provider_matching import resolve_provider_names
from agent.translators.base import Translator, empty_job

# Canonical network-type labels the rest of the pipeline understands.
_NETWORK_ALIASES = {
    'opticomm': 'opticomm',
    'redtrain': 'redtrain',
    'supa': 'supa',
    'nbn': 'nbn',
    'fixed wireless': 'fixed wireless',
    'fixed-wireless': 'fixed wireless',
    'fixedwireless': 'fixed wireless',
    'wireless': 'fixed wireless',
    'fibre': 'fibre',
    'fiber': 'fibre',
    'starlink': 'starlink',
    'mobile': 'mobile',
    '5g': '5g',
}

_COMPARE_WORDS = (
    'compare', ' vs ', ' vs.', 'versus', 'against', 'stack up',
    'better than', 'cheaper than', 'how do we', 'how do they',
)
_ALL_WORDS = ('scrape all', 'all providers', 'every provider', 'everyone')
_HISTORY_WORDS = ('changed', 'change history', 'history', 'health report', 'last time', 'previous run')


# Words that must never be treated as a provider-name candidate: network
# types (some, like "fibre"/"fiber", sit close enough to a real provider
# alias — e.g. New Aus Fiber's "fiber" word — that fuzzy matching alone
# would misfire on them) and common request phrasing.
_NON_PROVIDER_WORDS = set(_NETWORK_ALIASES.keys()) | {
    'scrape', 'get', 'check', 'compare', 'show', 'tell', 'find', 'give',
    'please', 'plan', 'plans', 'and', 'the', 'for', 'to', 'me', 'us', 'we',
    'our', 'their', 'them', 'a', 'an', 'is', 'are', 'vs', 'versus', 'against',
}


def _candidate_words(lower_text: str) -> List[str]:
    """Every word AND adjacent word-pair actually present in the message —
    the only things worth testing against known provider names. (Testing
    the provider vocabulary itself, rather than the message's own words,
    would make every provider "match" every message — a real bug caught
    while testing this file.)"""
    words = [w for w in re.findall(r"[a-z0-9]+", lower_text) if w not in _NON_PROVIDER_WORDS]
    bigrams = [f"{a} {b}" for a, b in zip(words, words[1:])]
    return words + bigrams


def _find_providers(lower_text: str) -> List[str]:
    return resolve_provider_names(_candidate_words(lower_text))


def _find_networks(lower_text: str) -> List[str]:
    found: List[str] = []
    for alias, canonical in _NETWORK_ALIASES.items():
        if alias in lower_text and canonical not in found:
            found.append(canonical)
    return found


class RuleBasedTranslator(Translator):
    name = 'rule_based'

    def is_available(self) -> bool:
        return True

    def translate(self, message: str) -> Optional[Dict[str, Any]]:
        text = (message or '').strip()
        lower = f' {text.lower()} '

        if not text:
            return empty_job(text, 'empty', ['Type a request, e.g. "scrape TPG NBN plans and compare to Occom".'])

        if any(w in lower for w in _ALL_WORDS):
            return empty_job(text, 'unsupported_scrape_all', [
                'Scraping every provider from chat is not wired up in this MVP — it would run '
                'for a long time inside a single request. Use the "Scrape All" button on /isp '
                'for that instead.'
            ])

        if any(w in lower for w in _HISTORY_WORDS):
            return empty_job(text, 'unsupported_history', [
                'Run history and health reports already exist at /isp/health — this chat does not duplicate that yet.'
            ])

        providers = _find_providers(lower)
        networks = _find_networks(lower)

        compare_requested = any(w in lower for w in _COMPARE_WORDS) or 'occom' in lower
        compare_against = 'occom' if compare_requested else None
        if compare_against:
            providers = [p for p in providers if p != 'occom']

        if not providers:
            job = empty_job(text, 'unrecognized', [
                'I could not recognize a provider name in that. Try naming one directly, '
                'e.g. "scrape TPG NBN plans" or "compare Superloop to Occom".'
            ])
            job['networks'] = networks
            job['compare_against'] = compare_against
            return job

        action = 'scrape_and_compare' if compare_against else 'scrape_only'
        return {
            'message': text,
            'providers': providers,
            'networks': networks,
            'action': action,
            'compare_against': compare_against,
            'notes': [],
        }
