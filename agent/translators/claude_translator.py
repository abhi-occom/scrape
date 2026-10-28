"""Phase 2 translator backend: Anthropic Claude.

Kept deliberately narrow — this backend's only job is turning one sentence
into the same structured job dict the rule-based translator produces. It
never touches scraping, validation, or comparison logic.

Requires:
    pip install anthropic
    ANTHROPIC_API_KEY set in the environment (see .env.example)

If either is missing, is_available() returns False and the factory falls
back to the next backend — this module never raises on import.
"""
import os
from typing import Any, Dict, Optional

from config import PROVIDERS
from agent.translators.base import AI_SYSTEM_PROMPT, Translator, empty_job, parse_ai_job

try:
    import anthropic
    _ANTHROPIC_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover - exercised only when uninstalled
    anthropic = None
    _ANTHROPIC_IMPORT_ERROR = exc

MODEL = os.environ.get('ANTHROPIC_TRANSLATOR_MODEL', 'claude-haiku-4-5')


class ClaudeTranslator(Translator):
    name = 'claude'

    def is_available(self) -> bool:
        return anthropic is not None and bool(os.environ.get('ANTHROPIC_API_KEY'))

    def translate(self, message: str) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            return None

        text = (message or '').strip()
        if not text:
            return empty_job(text, 'empty', ['Type a request, e.g. "scrape TPG NBN plans and compare to Occom".'])

        try:
            client = anthropic.Anthropic()
            provider_keys = ', '.join(sorted(PROVIDERS.keys()))
            response = client.messages.create(
                model=MODEL,
                max_tokens=512,
                system=AI_SYSTEM_PROMPT.format(provider_keys=provider_keys),
                messages=[{'role': 'user', 'content': text}],
            )
            raw_text = next(
                (block.text for block in response.content if block.type == 'text'), ''
            )
            return parse_ai_job(text, raw_text)
        except Exception:
            # Any SDK/network/parsing failure -> let the factory fall back
            # to the next backend rather than breaking the chat response.
            return None
