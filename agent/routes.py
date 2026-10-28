"""Flask routes for the natural-language ISP scraping agent.

See AI_AGENT_BROWSER_PLAN.md for the full design across all phases:
  - Phase 1: rule-based translator (agent/translators/rule_based.py) — always available.
  - Phase 2: pluggable Claude/Gemini translator (agent/translators/), selected via AI_PROVIDER.
  - Phase 3: Chrome extension (agent/chrome_extension/) calling this same API.
  - Phase 4: optional local Ollama fallback extractor (agent/local_llm_extractor.py).

Mounted at /agent via app.py.
"""
from flask import Blueprint, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from agent.executor import run_job
from agent.responder import format_reply
from agent.translator import translate
from agent.translators.factory import active_provider_status

agent_bp = Blueprint(
    'agent',
    __name__,
    template_folder='templates',
    url_prefix='/agent',
)

# Rate limiting the chat endpoint specifically: it's the one route that can
# trigger paid AI-API calls (Phase 2) and real scrape jobs, so an unbounded
# number of requests has a real cost, unlike the rest of the dashboard.
# init_app(app) is called from app.py once the Flask app object exists.
limiter = Limiter(key_func=get_remote_address)


@agent_bp.route('/')
def agent_ui():
    """Serve the chat-style agent page."""
    return render_template('chat_ui.html')


@agent_bp.route('/api/chat', methods=['POST'])
@limiter.limit('10/minute')
def api_chat():
    """Accept one free-text message and return a plain-English reply.

    Request JSON: {"message": "scrape TPG NBN plans and compare to Occom"}
    """
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()

    if not message:
        return jsonify({'success': False, 'error': 'message is required'}), 400

    job = translate(message)
    result = run_job(job)
    reply = format_reply(job, result)

    return jsonify({
        'success': True,
        'job': job,
        'reply': reply,
    })


@agent_bp.route('/api/config', methods=['GET'])
def api_config():
    """Report which translator backend is configured/active and whether the
    Phase 4 local LLM fallback is reachable — mainly for debugging/UI
    display, not required for the chat flow to work."""
    from agent.local_llm_extractor import is_ollama_available, DEFAULT_MODEL

    return jsonify({
        'success': True,
        'translator': active_provider_status(),
        'local_llm_fallback': {
            'ollama_available': is_ollama_available(),
            'model': DEFAULT_MODEL,
        },
    })
