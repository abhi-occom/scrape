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
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import PROVIDERS
from isp.main_crawler import ISPCrawler, OUTPUT_DIR, ALL_PLANS_JSON_PATH, PLAN_FIELDS


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
    'stage': 'idle',
    'message': '',
    'progress': [],
    'result': None,
}

_crawl_all_state = {
    'running': False,
    'status': 'idle',
    'message': '',
    'current_provider': None,
    'current_url': None,
    'plans_found': 0,
    'providers_total': 0,
    'providers_done': 0,
    'total_plans': 0,
    'started_at': None,
    'finished_at': None,
    'events': [],
    'errors': [],
    'completed_results': [],
    'result_version': 0,
    'result': None,
}

PROVIDER_CRAWL_URLS = {
    'telstra': 'https://www.telstra.com.au/internet/plans',
    'optus': 'https://www.optus.com.au/internet/nbn',
    'aussie': 'https://www.aussiebroadband.com.au/internet/nbn-plans/',
    'superloop': 'https://www.superloop.com/internet/nbn/',
    'occom': 'https://occom.com.au/nbn-plans/',
    'tpg': 'https://www.tpg.com.au/nbn',
    'exetel': 'https://www.exetel.com.au/broadband/nbn',
    'leaptel': 'https://leaptel.com.au/plans/?provider=nbn',
    'iinet': 'https://www.iinet.net.au/internet-product',
    'swoop': 'https://www.swoop.com.au/nbn/',
    'iprimus': 'https://www.iprimus.com.au/nbn-plans',
    'dodo': 'https://www.dodo.com/nbn',
    'kogan': 'https://www.koganinternet.com.au/plans/',
    'more': 'https://more.com.au/personal/nbn-plans',
    'tangerine': 'https://www.tangerine.com.au/nbn/nbn-broadband',
    'mate': 'https://www.letsbemates.com.au/mate/crikey-nbn-25-10/',
    'spintel': 'https://www.spintel.net.au/home-internet/nbn',
    'origin': 'https://www.originenergy.com.au/internet/plans/',
    'airtel': 'https://airtel.au/mobile',
    'alpha': 'https://home.alpha.net.au/plans/plan-supanetworks.html',
    'city7net': 'https://city7net.com.au/',
    'epsinet': 'https://epsinet.com.au/',
    'iqnet': 'https://iqnet.com.au/broadband/',
    'newausfiber': 'https://newausfiber.com.au/',
    'vocphone': 'https://vocphone.com/nbn-plans',
    'activ8me': 'https://www.activ8me.net.au/internet/nbn-fibre-fttp-hfc',
}


# ── UI ───────────────────────────────────────────────────────────

@isp_bp.route('/')
def crawler_ui():
    """Serve the mini crawler input form."""
    return render_template('crawler_ui.html')


@isp_bp.route('/health')
def health_report_ui():
    """Serve the saved-run scrape health report."""
    return render_template('health_report.html')


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
        if _crawl_state['running'] or _crawl_all_state['running']:
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
        _crawl_state['stage'] = 'starting'
        _crawl_state['message'] = f'Starting crawl for {base_url}'
        _crawl_state['progress'] = [{
            'stage': 'starting',
            'status': 'running',
            'message': f'Starting crawl for {base_url}',
        }]
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


@isp_bp.route('/api/crawl-all', methods=['POST'])
def api_start_crawl_all():
    """Start a background crawl across every enabled provider URL."""
    with _crawl_lock:
        if _crawl_state['running'] or _crawl_all_state['running']:
            return jsonify({
                'success': False,
                'error': 'A crawl is already running. Wait for it to finish.',
            }), 409

        providers = _enabled_provider_crawl_targets()
        if not providers:
            return jsonify({
                'success': False,
                'error': 'No enabled providers have crawl URLs configured.',
            }), 400

        _crawl_all_state.update({
            'running': True,
            'status': 'starting',
            'message': f'Starting scrape all for {len(providers)} providers',
            'current_provider': None,
            'current_url': None,
            'plans_found': 0,
            'providers_total': len(providers),
            'providers_done': 0,
            'total_plans': 0,
            'started_at': datetime.now().isoformat(),
            'finished_at': None,
            'events': [],
            'errors': [],
            'completed_results': [],
            'result_version': 0,
            'result': None,
        })
        _append_crawl_all_event(
            provider='All providers',
            status='running',
            message=f'Starting scrape all for {len(providers)} providers',
        )

    thread = threading.Thread(
        target=_run_crawl_all_async,
        args=(providers,),
        daemon=True,
    )
    thread.start()

    return jsonify({
        'success': True,
        'message': f'Scrape all started for {len(providers)} providers',
        'providers_total': len(providers),
        'status': 'starting',
    })


@isp_bp.route('/api/crawl-all/status', methods=['GET'])
def api_crawl_all_status():
    """Get current scrape-all status and batch results."""
    with _crawl_lock:
        return jsonify({
            'success': True,
            **_crawl_all_state,
        })


@isp_bp.route('/api/all-plans', methods=['GET'])
def api_get_all_plans_snapshot():
    """Return the combined all-plans snapshot saved by crawler runs."""
    if not os.path.exists(ALL_PLANS_JSON_PATH):
        return jsonify({
            'success': True,
            'data': {
                'scraped_at': None,
                'source': 'missing_all_plans_snapshot',
                'total_providers': 0,
                'total_plans': 0,
                'providers': [],
                'plans': [],
            },
        })

    try:
        with open(ALL_PLANS_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

    return jsonify({'success': True, 'data': data})


def _run_crawl_all_async(providers):
    """Background thread that crawls all configured providers sequentially."""
    provider_results = []

    for index, provider in enumerate(providers, start=1):
        key = provider['key']
        name = provider['name']
        url = provider['url']

        with _crawl_lock:
            _crawl_all_state.update({
                'status': 'running',
                'message': f'Scraping {name}',
                'current_provider': key,
                'current_url': url,
                'plans_found': 0,
            })
            _append_crawl_all_event(
                provider=key,
                status='running',
                message=f'Scraping {name}',
                url=url,
            )

        def progress_callback(event, provider_key=key, provider_url=url):
            event = event or {}
            message = event.get('message') or ''
            status = event.get('status') or 'running'
            stage = event.get('stage') or 'running'
            with _crawl_lock:
                _crawl_all_state['message'] = message or _crawl_all_state['message']
                _append_crawl_all_event(
                    provider=provider_key,
                    status=status,
                    message=message or stage,
                    url=provider_url,
                )

        try:
            crawler = ISPCrawler(
                base_url=url,
                provider_name=name,
                network_types=['nbn', 'opticomm', 'redtrain', 'supa'],
                max_depth=2,
                progress_callback=progress_callback,
            )
            result = crawler.run()
            provider_result = {
                'key': key,
                'provider': result.provider_name or name,
                'base_url': result.base_url,
                'started_at': result.started_at,
                'finished_at': result.finished_at,
                'duration_seconds': result.duration_seconds,
                'urls_visited': result.urls_visited,
                'plan_pages_found': result.plan_pages_found,
                'total_plans_scraped': result.total_plans_scraped,
                'valid_plans': result.valid_plans,
                'invalid_plans': result.invalid_plans,
                'network_types_found': result.network_types_found,
                'plans': result.plans,
                'errors': result.errors,
                'success': result.success,
            }
        except Exception as e:
            provider_result = {
                'key': key,
                'provider': name,
                'base_url': url,
                'valid_plans': 0,
                'plans': [],
                'errors': [str(e)],
                'success': False,
            }

        provider_results.append(provider_result)
        plans_found = len(provider_result.get('plans') or [])
        success = bool(provider_result.get('success'))
        status = 'success' if success else 'error'
        message = (
            f"{name} completed with {plans_found} plans"
            if success
            else f"{name} failed"
        )

        with _crawl_lock:
            _crawl_all_state['providers_done'] = index
            _crawl_all_state['plans_found'] = plans_found
            _crawl_all_state['total_plans'] += plans_found
            _crawl_all_state['result_version'] += 1
            _crawl_all_state['completed_results'].append({
                'version': _crawl_all_state['result_version'],
                'key': key,
                'provider': provider_result.get('provider') or name,
                'base_url': provider_result.get('base_url') or url,
                'plans': provider_result.get('plans') or [],
                'total_plans': plans_found,
                'success': success,
                'errors': provider_result.get('errors') or [],
            })
            if not success:
                _crawl_all_state['errors'].append({
                    'provider': key,
                    'message': '; '.join(provider_result.get('errors') or ['Unknown error']),
                    'time': datetime.now().isoformat(),
                })
            _append_crawl_all_event(
                provider=key,
                status=status,
                message=message,
                url=url,
                plans_found=plans_found,
            )

    try:
        snapshot = _save_batch_all_plans_snapshot(provider_results)
        status = 'success' if not _crawl_all_state['errors'] else 'partial_success'
        message = (
            f"Scraped {snapshot['total_plans']} plans from "
            f"{snapshot['total_providers']} providers"
        )
        if _crawl_all_state['errors']:
            message += f" with {len(_crawl_all_state['errors'])} provider error(s)"
    except Exception as e:
        snapshot = None
        status = 'error'
        message = f'Could not save all_plans.json: {e}'
        with _crawl_lock:
            _crawl_all_state['errors'].append({
                'provider': 'All providers',
                'message': str(e),
                'time': datetime.now().isoformat(),
            })

    with _crawl_lock:
        _crawl_all_state.update({
            'running': False,
            'status': status,
            'message': message,
            'current_provider': None,
            'current_url': None,
            'finished_at': datetime.now().isoformat(),
            'result': {
                'providers': provider_results,
                'snapshot': snapshot,
            },
        })
        _append_crawl_all_event(
            provider='All providers',
            status=status,
            message=message,
        )


def _enabled_provider_crawl_targets():
    """Return enabled provider crawl targets in config order."""
    targets = []
    for key, config in PROVIDERS.items():
        if not config.get('enabled'):
            continue
        url = PROVIDER_CRAWL_URLS.get(key)
        if not url:
            continue
        targets.append({
            'key': key,
            'name': config.get('name') or key.title(),
            'url': url,
        })
    return targets


def _append_crawl_all_event(provider, status, message, url=None, plans_found=None):
    """Append a compact scrape-all progress event to the in-memory state."""
    _crawl_all_state['events'].append({
        'time': datetime.now().isoformat(),
        'provider': provider,
        'status': status,
        'message': message,
        'url': url,
        'plans_found': plans_found,
    })
    _crawl_all_state['events'] = _crawl_all_state['events'][-120:]


def _save_batch_all_plans_snapshot(provider_results):
    """Write output/all_plans.json and CSV from this batch's successful results."""
    os.makedirs(os.path.dirname(ALL_PLANS_JSON_PATH), exist_ok=True)
    all_plans = []
    providers = []

    for result in provider_results:
        plans = result.get('plans') or []
        if not plans:
            continue
        provider_name = result.get('provider') or result.get('key') or 'Unknown'
        providers.append({
            'provider': provider_name,
            'base_url': result.get('base_url', ''),
            'plans_count': len(plans),
            'started_at': result.get('started_at', ''),
            'finished_at': result.get('finished_at', ''),
            'success': bool(result.get('success')),
            'errors': result.get('errors') or [],
        })
        for plan in plans:
            row = {field: plan.get(field) for field in PLAN_FIELDS}
            row['provider'] = row.get('provider') or provider_name
            row['source_url'] = row.get('source_url') or result.get('base_url', '')
            all_plans.append(row)

    snapshot = {
        'scraped_at': datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
        'source': 'isp_crawler_scrape_all',
        'total_providers': len(providers),
        'total_plans': len(all_plans),
        'providers': providers,
        'plans': all_plans,
    }

    with open(ALL_PLANS_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    csv_path = os.path.splitext(ALL_PLANS_JSON_PATH)[0] + '.csv'
    import csv
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=PLAN_FIELDS, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_plans)

    return snapshot


def _run_crawl_async(base_url: str, name: str, networks: list, depth: int):
    """Background thread that runs the crawler."""
    global _crawl_state

    def progress_callback(event):
        event = event or {}
        stage = event.get('stage', 'running')
        status = event.get('status', 'running')
        message = event.get('message', '')
        with _crawl_lock:
            _crawl_state['stage'] = stage
            _crawl_state['message'] = message or _crawl_state['message']
            progress = _crawl_state.setdefault('progress', [])
            for item in progress:
                if item.get('stage') == stage:
                    item.update({
                        'status': status,
                        'message': message,
                    })
                    break
            else:
                progress.append({
                    'stage': stage,
                    'status': status,
                    'message': message,
                })

    try:
        with _crawl_lock:
            _crawl_state['status'] = 'running'
            _crawl_state['stage'] = 'starting'
            _crawl_state['message'] = f'Crawling {base_url}...'

        crawler = ISPCrawler(
            base_url=base_url,
            network_types=networks,
            max_depth=depth,
            provider_name=name,
            progress_callback=progress_callback,
        )
        result = crawler.run()

        with _crawl_lock:
            _crawl_state['status'] = 'success' if result.success else 'error'
            _crawl_state['stage'] = 'completed' if result.success else 'error'
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
            _crawl_state['stage'] = 'error'
            _crawl_state['message'] = f'Crawl failed: {str(e)}'
            _crawl_state.setdefault('progress', []).append({
                'stage': 'error',
                'status': 'error',
                'message': f'Crawl failed: {str(e)}',
            })
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
            'stage': _crawl_state['stage'],
            'message': _crawl_state['message'],
            'progress': _crawl_state.get('progress', []),
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


@isp_bp.route('/api/health', methods=['GET'])
def api_health_report():
    """Build a scrape health report from saved timestamped crawl results."""
    runs = _load_saved_result_runs()
    return jsonify({
        'success': True,
        'health': _build_health_report(runs),
    })


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


def _load_saved_result_runs():
    """Load timestamped saved result files with metadata used by reports."""
    if not os.path.exists(OUTPUT_DIR):
        return []

    runs = []
    for fname in os.listdir(OUTPUT_DIR):
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

        runs.append({
            'filename': fname,
            'mtime': os.path.getmtime(fpath),
            'data': data,
        })

    runs.sort(
        key=lambda item: (item['data'].get('started_at') or '', item['mtime']),
        reverse=True,
    )
    return runs


def _build_health_report(runs):
    """Summarise scrape reliability, output volume, failures, and latest changes."""
    total_runs = len(runs)
    if total_runs == 0:
        return {
            'total_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'success_rate': 0,
            'average_duration_seconds': 0,
            'average_valid_plans': 0,
            'total_valid_plans': 0,
            'total_failed_pages': 0,
            'total_errors': 0,
            'latest_run': None,
            'changes_since_last_run': _empty_change_summary(),
            'providers': [],
            'recent_failures': [],
        }

    successful_runs = 0
    total_duration = 0.0
    total_valid_plans = 0
    total_failed_pages = 0
    total_errors = 0
    providers = {}
    recent_failures = []

    for run in runs:
        data = run['data']
        summary = data.get('summary', {})
        provider = (data.get('provider') or 'Unknown').strip() or 'Unknown'
        valid_plans = _int_value(summary.get('valid_plans'))
        duration = _float_value(data.get('duration_seconds'))
        failed_pages = _failed_page_count(data)
        error_count = len(data.get('errors') or [])
        is_success = _result_success(data)

        if is_success:
            successful_runs += 1
        else:
            recent_failures.append({
                'filename': run['filename'],
                'provider': provider,
                'started_at': data.get('started_at', ''),
                'valid_plans': valid_plans,
                'errors': (data.get('errors') or [])[:3],
                'failed_pages': failed_pages,
            })

        total_duration += duration
        total_valid_plans += valid_plans
        total_failed_pages += failed_pages
        total_errors += error_count

        bucket = providers.setdefault(provider.lower(), {
            'provider': provider,
            'runs': [],
            'successful_runs': 0,
            'total_duration': 0.0,
            'total_valid_plans': 0,
            'total_failed_pages': 0,
            'total_errors': 0,
        })
        bucket['runs'].append(run)
        bucket['successful_runs'] += 1 if is_success else 0
        bucket['total_duration'] += duration
        bucket['total_valid_plans'] += valid_plans
        bucket['total_failed_pages'] += failed_pages
        bucket['total_errors'] += error_count

    provider_reports = []
    aggregate_changes = _empty_change_summary()

    for bucket in providers.values():
        provider_runs = bucket['runs']
        provider_runs.sort(
            key=lambda item: (item['data'].get('started_at') or '', item['mtime']),
            reverse=True,
        )
        latest = provider_runs[0]
        latest_data = latest['data']
        latest_summary = latest_data.get('summary', {})
        changes = _empty_change_summary()
        previous_filename = ''

        if len(provider_runs) > 1:
            previous = provider_runs[1]
            previous_filename = previous['filename']
            comparison = _compare_result_plans(latest_data, previous['data'])
            changes = comparison.get('summary', _empty_change_summary())
            aggregate_changes = _add_change_summaries(aggregate_changes, changes)

        provider_reports.append({
            'provider': bucket['provider'],
            'runs': len(provider_runs),
            'successful_runs': bucket['successful_runs'],
            'failed_runs': len(provider_runs) - bucket['successful_runs'],
            'success_rate': _percent(bucket['successful_runs'], len(provider_runs)),
            'average_duration_seconds': round(bucket['total_duration'] / len(provider_runs), 2),
            'average_valid_plans': round(bucket['total_valid_plans'] / len(provider_runs), 2),
            'total_failed_pages': bucket['total_failed_pages'],
            'total_errors': bucket['total_errors'],
            'latest_filename': latest['filename'],
            'latest_started_at': latest_data.get('started_at', ''),
            'latest_valid_plans': _int_value(latest_summary.get('valid_plans')),
            'latest_duration_seconds': _float_value(latest_data.get('duration_seconds')),
            'previous_filename': previous_filename,
            'changes_since_last_run': changes,
        })

    provider_reports.sort(key=lambda item: item['latest_started_at'], reverse=True)
    latest_run = runs[0]
    latest_data = latest_run['data']
    latest_summary = latest_data.get('summary', {})

    return {
        'total_runs': total_runs,
        'successful_runs': successful_runs,
        'failed_runs': total_runs - successful_runs,
        'success_rate': _percent(successful_runs, total_runs),
        'average_duration_seconds': round(total_duration / total_runs, 2),
        'average_valid_plans': round(total_valid_plans / total_runs, 2),
        'total_valid_plans': total_valid_plans,
        'total_failed_pages': total_failed_pages,
        'total_errors': total_errors,
        'latest_run': {
            'filename': latest_run['filename'],
            'provider': latest_data.get('provider', ''),
            'started_at': latest_data.get('started_at', ''),
            'valid_plans': _int_value(latest_summary.get('valid_plans')),
            'duration_seconds': _float_value(latest_data.get('duration_seconds')),
        },
        'changes_since_last_run': aggregate_changes,
        'providers': provider_reports,
        'recent_failures': recent_failures[:10],
    }


def _result_success(data):
    """Treat a saved run as healthy when it produced at least one valid plan."""
    summary = data.get('summary', {})
    return _int_value(summary.get('valid_plans')) > 0


def _failed_page_count(data):
    """Count analysed pages that failed plan detection plus explicit page errors."""
    failed = 0
    for analysis in data.get('page_analyses') or []:
        if analysis.get('error') or not analysis.get('has_plans'):
            failed += 1
    return failed


def _empty_change_summary():
    return {
        'new_plans': 0,
        'removed_plans': 0,
        'price_changed': 0,
        'promo_changed': 0,
    }


def _add_change_summaries(left, right):
    return {
        key: _int_value(left.get(key)) + _int_value(right.get(key))
        for key in _empty_change_summary()
    }


def _percent(value, total):
    return round((value / total) * 100, 1) if total else 0


def _int_value(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_value(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


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
