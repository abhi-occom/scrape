"""Resolve free-text provider names (typed by a person, or returned by an AI
translator) against the real provider keys in config.py's PROVIDERS dict.

Used by both the rule-based translator and the AI translators (Phase 2), so
an AI model hallucinating a provider name that isn't real gets caught here
rather than silently passed through to the scraper.
"""
import difflib
import re
from typing import List

from config import PROVIDERS

_FUZZY_CUTOFF = 0.8


def _alias_map() -> dict:
    """lowercase alias -> real config.py key, built once per call (config.py
    is small and static at runtime, so this is cheap)."""
    aliases: dict = {}
    for key, info in PROVIDERS.items():
        aliases.setdefault(key.lower(), key)
        name = str(info.get('name') or '').lower()
        if name:
            aliases.setdefault(name, key)
            for word in re.findall(r"[a-z0-9]+", name):
                if len(word) > 3:
                    aliases.setdefault(word, key)
    return aliases


def resolve_provider_name(candidate: str) -> str | None:
    """Resolve one free-text name to a real config.py provider key.

    Tries an exact alias match first, then falls back to fuzzy matching
    (handles typos/near-misses like "Superlop" -> "superloop"). Returns
    None if nothing is a confident enough match — callers should treat
    that as "unknown provider", not guess.
    """
    if not candidate:
        return None

    text = candidate.strip().lower()
    aliases = _alias_map()

    if text in aliases:
        return aliases[text]

    matches = difflib.get_close_matches(text, aliases.keys(), n=1, cutoff=_FUZZY_CUTOFF)
    if matches:
        return aliases[matches[0]]

    return None


def resolve_provider_names(candidates: List[str]) -> List[str]:
    """Resolve a list of free-text names to real provider keys, dropping
    anything that doesn't confidently match a real provider and
    de-duplicating while preserving order."""
    resolved: List[str] = []
    for candidate in candidates or []:
        key = resolve_provider_name(candidate)
        if key and key not in resolved:
            resolved.append(key)
    return resolved
