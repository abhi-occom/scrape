"""Phase 2 translator backend: Google Gemini.

Same narrow job as claude_translator.py — turn one sentence into the
shared job dict, nothing else. See base.py for the shared prompt/parsing.

Requires:
    pip install google-genai
    GEMINI_API_KEY set in the environment (see .env.example)

If either is missing, is_available() returns False and the factory falls
back to the next backend — this module never raises on import.

Note: the Google GenAI SDK's exact call shape has changed across versions.
If `google-genai` on your machine differs from what's used below, this
backend will simply fail its try/except and the factory will fall back to
rule-based — it will not break the chat endpoint. Worth re-checking this
file against the SDK actually installed if Gemini responses seem to
silently never come through.
"""
import os
from typing import Any, Dict, Optional

from config import PROVIDERS
from agent.translators.base import AI_SYSTEM_PROMPT, Translator, empty_job, parse_ai_job

try:
    from google import genai
    _GENAI_IMPORT_ERROR = None
except ImportError as exc:  # pragma: no cover - exercised only when uninstalled
    genai = None
    _GENAI_IMPORT_ERROR = exc

MODEL = os.environ.get('GEMINI_TRANSLATOR_MODEL', 'gemini-2.5-flash')


class GeminiTranslator(Translator):
    name = 'gemini'

    def is_available(self) -> bool:
        return genai is not None and bool(os.environ.get('GEMINI_API_KEY'))

    def translate(self, message: str) -> Optional[Dict[str, Any]]:
        if not self.is_available():
            return None

        text = (message or '').strip()
        if not text:
            return empty_job(text, 'empty', ['Type a request, e.g. "scrape TPG NBN plans and compare to Occom".'])

        try:
            client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
            provider_keys = ', '.join(sorted(PROVIDERS.keys()))
            prompt = AI_SYSTEM_PROMPT.format(provider_keys=provider_keys) + f"\n\nSentence: {text}"
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config={'response_mime_type': 'application/json'},
            )
            raw_text = getattr(response, 'text', '') or ''
            return parse_ai_job(text, raw_text)
        except Exception:
            # Any SDK/network/parsing failure -> let the factory fall back
            # to the next backend rather than breaking the chat response.
            return None
