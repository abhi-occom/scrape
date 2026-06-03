"""
ISP Crawler – Flask Routes
---------------------------
API endpoints and UI route for the mini crawler.
Mount these in the main app.py via:

    from isp.routes import isp_bp
    app.register_blueprint(isp_bp)
"""

import os
import json
import threading
from flask import Blueprint, request, jsonify, render_template

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from isp.main_crawler import ISPCrawler, OUTPUT_DIR


isp_bp = Blueprint(
    'isp',
    __name__,
    template_folder='templates',
    url_prefix='/isp',
)

# In-memory state for async crawl status
_crawl_lock = threading.Lock()
_crawl_state = {
    'running': False,
    'status': 'idle',
    'message': '',
    'result': None,
}


# ── UI ───────────────────────────────────────────────────────────

@isp_bp.route('/')
def crawler_ui():
    """Serve the mini crawler input form."""
    return render_template('crawler_ui.html')


# ── API: Start crawl ─────────────────────────────────────────────

@isp_bp.route('/api/crawl', methods=['POST'])
def api_start_crawl():
    """
    Start a crawl job.

    Request JSON:
        {
            "url": "https://www.telstra.com.au/internet",
            "name": "Telstra",               // optional
            "networks": ["nbn", "opticomm"],  // optional
            "depth": 2                        // optional
        }
    """
    with _crawl_lock:
        if _crawl_state['running']:
            return jsonify({
                'success': False,
                'error': 'A crawl is already running. Wait for it to finish.',
            }), 409

    data = request.get_json(silent=True) or {}
    base_url = data.get('url', '').strip()

    if not base_url:
        return jsonify({'success': False, 'error': 'URL is required'}), 400

    if not base_url.startswith('http'):
        base_url = 'https://' + base_url

    networks = data.get('networks', ['nbn', 'opticomm', 'redtrain', 'supa'])
    depth = min(int(data.get('depth', 2)), 3)
    name = data.get('name', '')

    # Run in background thread
    with _crawl_lock:
        _crawl_state['running'] = True
        _crawl_state['status'] = 'starting'
        _crawl_state['message'] = f'Starting crawl for {base_url}'
        _crawl_state['result'] = None

    thread = threading.Thread(
        target=_run_crawl_async,
        args=(base_url, name, networks, depth),
        daemon=True,
    )
    thread.start()

    return jsonify({
        'success': True,
        'message': f'Crawl started for {base_url}',
        'status': 'starting',
    })


def _run_crawl_async(base_url: str, name: str, networks: list, depth: int):
    """Background thread that runs the crawler."""
    global _crawl_state
    try:
        with _crawl_lock:
            _crawl_state['status'] = 'running'
            _crawl_state['message'] = f'Crawling {base_url}...'

        crawler = ISPCrawler(
            base_url=base_url,
            network_types=networks,
            max_depth=depth,
            provider_name=name,
        )
        result = crawler.run()

        with _crawl_lock:
            _crawl_state['status'] = 'success' if result.success else 'error'
            _crawl_state['message'] = (
                f'Done: crawled {result.urls_visited} URLs, found {result.valid_plans} plans '
                f'from {result.plan_pages_found} pages '
                f'in {result.duration_seconds}s'
            )
            _crawl_state['result'] = {
                'base_url': result.base_url,
                'provider': result.provider_name,
                'duration_seconds': result.duration_seconds,
                'urls_visited': result.urls_visited,
                'plan_pages_found': result.plan_pages_found,
                'total_plans_scraped': result.total_plans_scraped,
                'valid_plans': result.valid_plans,
                'invalid_plans': result.invalid_plans,
                'network_types_found': result.network_types_found,
                'discovered_urls': result.discovered_urls[:30],
                'page_analyses': result.page_analyses,
                'plans': result.plans,
                'errors': result.errors,
                'success': result.success,
            }

    except Exception as e:
        with _crawl_lock:
            _crawl_state['status'] = 'error'
            _crawl_state['message'] = f'Crawl failed: {str(e)}'
            _crawl_state['result'] = {'error': str(e), 'success': False}

    finally:
        with _crawl_lock:
            _crawl_state['running'] = False


# ── API: Get crawl status ────────────────────────────────────────

@isp_bp.route('/api/status', methods=['GET'])
def api_crawl_status():
    """Get current crawl status and results."""
    with _crawl_lock:
        return jsonify({
            'success': True,
            'running': _crawl_state['running'],
            'status': _crawl_state['status'],
            'message': _crawl_state['message'],
            'result': _crawl_state['result'],
        })


# ── API: Get saved results ───────────────────────────────────────

@isp_bp.route('/api/results', methods=['GET'])
def api_get_results():
    """List all saved crawl results."""
    if not os.path.exists(OUTPUT_DIR):
        return jsonify({'success': True, 'results': []})

    files = []
    result_files = [
        fname for fname in os.listdir(OUTPUT_DIR)
        if fname.endswith('.json') and not fname.endswith('_latest.json') and fname != 'test_report.json'
    ]
    result_files.sort(
        key=lambda fname: os.path.getmtime(os.path.join(OUTPUT_DIR, fname)),
        reverse=True,
    )

    for fname in result_files:
        fpath = os.path.join(OUTPUT_DIR, fname)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            files.append({
                'filename': fname,
                'provider': data.get('provider', '?'),
                'base_url': data.get('base_url', ''),
                'plans_count': data.get('summary', {}).get('valid_plans', 0),
                'networks': data.get('summary', {}).get('network_types', []),
                'timestamp': data.get('started_at', ''),
                'duration': data.get('duration_seconds', 0),
            })
        except Exception:
            continue

    return jsonify({'success': True, 'results': files})


@isp_bp.route('/api/results/<filename>', methods=['GET'])
def api_get_result_file(filename):
    """Get a specific crawl result file."""
    fpath = _safe_result_path(filename)
    if not fpath:
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400
    if not os.path.exists(fpath):
        return jsonify({'success': False, 'error': 'File not found'}), 404

    with open(fpath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return jsonify({'success': True, 'data': data})


@isp_bp.route('/api/results/<filename>/compare', methods=['GET'])
def api_compare_result_file(filename):
    """Compare a saved crawl result with the previous saved run for the same provider."""
    fpath = _safe_result_path(filename)
    if not fpath:
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400
    if not os.path.exists(fpath):
        return jsonify({'success': False, 'error': 'File not found'}), 404

    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            current = json.load(f)
    except Exception as e:
        return jsonify({'success': False, 'error': f'Could not read result: {e}'}), 500

    previous_entry = _find_previous_result(filename, current)
    if not previous_entry:
        return jsonify({
            'success': False,
            'error': 'No previous saved run found for this provider.',
        }), 404

    previous_filename, previous = previous_entry
    comparison = _compare_result_plans(current, previous)
    return jsonify({
        'success': True,
        'current_file': filename,
        'previous_file': previous_filename,
        'provider': current.get('provider', ''),
        'current_started_at': current.get('started_at', ''),
        'previous_started_at': previous.get('started_at', ''),
        **comparison,
    })


@isp_bp.route('/api/results/<filename>', methods=['DELETE'])
def api_delete_result_file(filename):
    """Delete a saved crawl result file and related exported files."""
    fpath = _safe_result_path(filename)
    if not fpath:
        return jsonify({'success': False, 'error': 'Invalid filename'}), 400
    if not os.path.exists(fpath):
        return jsonify({'success': False, 'error': 'File not found'}), 404

    deleted = []
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}

    try:
        os.remove(fpath)
        deleted.append(filename)
    except OSError as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    stem, _ = os.path.splitext(filename)
    csv_path = os.path.join(OUTPUT_DIR, f"{stem}.csv")
    if os.path.exists(csv_path):
        try:
            os.remove(csv_path)
            deleted.append(f"{stem}.csv")
        except OSError:
            pass

    provider = data.get('provider', '')
    started_at = data.get('started_at', '')
    if provider and started_at:
        safe_name = provider.lower().replace(' ', '_').replace('.', '')
        latest_path = os.path.join(OUTPUT_DIR, f"{safe_name}_latest.json")
        try:
            if os.path.exists(latest_path):
                with open(latest_path, 'r', encoding='utf-8') as f:
                    latest_data = json.load(f)
                if latest_data.get('started_at') == started_at:
                    os.remove(latest_path)
                    deleted.append(f"{safe_name}_latest.json")
        except Exception:
            pass

    return jsonify({'success': True, 'deleted': deleted})


def _find_previous_result(current_filename, current_data):
    """Return (filename, data) for the previous timestamped result of the same provider."""
    provider = (current_data.get('provider') or '').strip().lower()
    current_started = current_data.get('started_at') or ''
    if not provider or not os.path.exists(OUTPUT_DIR):
        return None

    candidates = []
    for fname in os.listdir(OUTPUT_DIR):
        if fname == current_filename:
            continue
        if not fname.endswith('.json') or fname.endswith('_latest.json') or fname == 'test_report.json':
            continue

        fpath = _safe_result_path(fname)
        if not fpath or not os.path.exists(fpath):
            continue

        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue

        if (data.get('provider') or '').strip().lower() != provider:
            continue

        started = data.get('started_at') or ''
        if current_started and started and started >= current_started:
            continue

        candidates.append((started, os.path.getmtime(fpath), fname, data))

    if not candidates:
        return None

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    _, _, fname, data = candidates[0]
    return fname, data


def _compare_result_plans(current, previous):
    """Build a saved-run diff for new, removed, price, and promo changes."""
    current_map = {
        _plan_key(plan): plan
        for plan in current.get('plans', [])
        if _plan_key(plan)
    }
    previous_map = {
        _plan_key(plan): plan
        for plan in previous.get('plans', [])
        if _plan_key(plan)
    }

    current_keys = set(current_map)
    previous_keys = set(previous_map)

    new_plans = [_plan_snapshot(current_map[key]) for key in sorted(current_keys - previous_keys)]
    removed_plans = [_plan_snapshot(previous_map[key]) for key in sorted(previous_keys - current_keys)]

    price_changed = []
    promo_changed = []
    for key in sorted(current_keys & previous_keys):
        current_plan = current_map[key]
        previous_plan = previous_map[key]

        current_price = _number_or_none(current_plan.get('price'))
        previous_price = _number_or_none(previous_plan.get('price'))
        if current_price != previous_price:
            price_changed.append({
                'plan': _plan_snapshot(current_plan),
                'old_price': previous_price,
                'new_price': current_price,
            })

        current_promo = _number_or_none(current_plan.get('promo_price'))
        previous_promo = _number_or_none(previous_plan.get('promo_price'))
        current_period = current_plan.get('promo_period')
        previous_period = previous_plan.get('promo_period')
        if current_promo != previous_promo or current_period != previous_period:
            promo_changed.append({
                'plan': _plan_snapshot(current_plan),
                'old_promo_price': previous_promo,
                'new_promo_price': current_promo,
                'old_promo_period': previous_period,
                'new_promo_period': current_period,
            })

    changes = {
        'new_plans': new_plans,
        'removed_plans': removed_plans,
        'price_changed': price_changed,
        'promo_changed': promo_changed,
    }
    return {
        'summary': {name: len(items) for name, items in changes.items()},
        'changes': changes,
    }


def _plan_key(plan):
    """Stable identity for comparing a plan across runs."""
    pieces = [
        plan.get('provider', ''),
        plan.get('network_type', ''),
        plan.get('plan_name', ''),
        plan.get('download_speed', ''),
        plan.get('upload_speed', ''),
    ]
    return '|'.join(str(part).strip().lower() for part in pieces)


def _plan_snapshot(plan):
    """Small plan representation for comparison UI."""
    return {
        'provider': plan.get('provider'),
        'network_type': plan.get('network_type'),
        'plan_name': plan.get('plan_name'),
        'download_speed': plan.get('download_speed'),
        'upload_speed': plan.get('upload_speed'),
        'price': plan.get('price'),
        'promo_price': plan.get('promo_price'),
        'promo_period': plan.get('promo_period'),
        'source_url': plan.get('source_url'),
    }


def _number_or_none(value):
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_result_path(filename):
    """Resolve only timestamped crawler JSON result filenames inside OUTPUT_DIR."""
    safe_name = os.path.basename(filename)
    if (
        safe_name != filename
        or not safe_name.endswith('.json')
        or safe_name.endswith('_latest.json')
        or safe_name == 'test_report.json'
    ):
        return None

    output_dir = os.path.abspath(OUTPUT_DIR)
    fpath = os.path.abspath(os.path.join(output_dir, safe_name))
    if os.path.commonpath([output_dir, fpath]) != output_dir:
        return None
    return fpath
