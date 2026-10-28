"""Picks the active translator backend and chains a safe fallback.

Selection is one setting: the AI_PROVIDER env var (`claude`, `gemini`, or
`rule_based`/unset). Whichever is chosen, RuleBasedTranslator is ALWAYS the
final fallback — if the configured AI backend is unavailable (no key, SDK
not installed) or its call fails/returns something unusable, the rule-based
translator answers instead so the chat endpoint never breaks.
"""
import os
from typing import Any, Dict, List

from agent.translators.base import Translator
from agent.translators.rule_based import RuleBasedTranslator

_RULE_BASED = RuleBasedTranslator()


def _build_ai_backend(provider: str) -> Translator | None:
    if provider == 'claude':
        from agent.translators.claude_translator import ClaudeTranslator
        return ClaudeTranslator()
    if provider == 'gemini':
        from agent.translators.gemini_translator import GeminiTranslator
        return GeminiTranslator()
    return None


def active_backend_chain() -> List[Translator]:
    """The ordered list of backends to try for this request, built fresh
    each call so an env var change takes effect without a restart-free
    hot-reload assumption."""
    provider = (os.environ.get('AI_PROVIDER') or 'rule_based').strip().lower()
    chain: List[Translator] = []

    ai_backend = _build_ai_backend(provider)
    if ai_backend is not None:
        chain.append(ai_backend)

    chain.append(_RULE_BASED)  # always last — guaranteed to answer
    return chain


def translate(message: str) -> Dict[str, Any]:
    """Try each backend in order, returning the first usable job dict.
    RuleBasedTranslator.translate() never returns None, so this always
    returns a valid job dict."""
    for backend in active_backend_chain():
        if not backend.is_available():
            continue
        job = backend.translate(message)
        if job is not None:
            job['_translator'] = backend.name
            return job

    # Should be unreachable (rule-based is always available and never
    # returns None), but keep a safe floor rather than raising.
    return _RULE_BASED.translate(message) or {
        'message': message, 'providers': [], 'networks': [], 'action': 'unrecognized',
        'compare_against': None, 'notes': ['Something went wrong understanding that.'],
        '_translator': 'rule_based',
    }


def active_provider_status() -> Dict[str, Any]:
    """For an optional /agent/api/config endpoint / debugging: which
    backend is configured, and whether it's actually usable right now."""
    provider = (os.environ.get('AI_PROVIDER') or 'rule_based').strip().lower()
    ai_backend = _build_ai_backend(provider)
    return {
        'configured_provider': provider,
        'ai_backend_available': bool(ai_backend and ai_backend.is_available()),
        'fallback': 'rule_based',
    }
