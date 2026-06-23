"""
Flask API backend for ISP scraper frontend dashboard.
Provides REST endpoints for scraping, viewing results, and downloading files.
"""
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

from flask import Flask, jsonify, redirect, request, send_file, render_template, send_from_directory, session, url_for
from flask_cors import CORS
import json
import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper_service import (
    scrape_provider,
    save_output,
    get_saved_results,
    load_all_plans_snapshot,
    get_provider_list,
    download_json,
    download_csv
)
from utils.progress import (
    finish_progress,
    finish_provider,
    get_progress,
    publish_provider_result,
    reset_progress,
    update_progress,
)
from utils.benchmark import run_benchmark, load_all_plans, save_benchmark_report, save_benchmark_csv
from utils.alerts import run_alerts
from benchmark_report import generate_html_report, run_and_save_benchmark
from roi_calculator import compute_roi_data, generate_roi_page, run_and_save_roi
from utils.screenshots import SCREENSHOT_ROOT
from utils.stealth import has_virtual_display_support
from google_sheets_sync import (
    authorization_url,
    dry_run_with_known_sheet,
    fetch_token,
    get_config as get_sheets_config,
    status_payload as sheets_status_payload,
    sync_sheet,
)

# Import ISP Mini Crawler routes
from isp.routes import isp_bp

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-only-change-me')
CORS(app)

# Register ISP crawler blueprint
app.register_blueprint(isp_bp)

# API Routes


def get_scrape_options():
    """Read optional browser debug settings from a scrape request."""
    payload = request.get_json(silent=True) or {}
    slow_mo = payload.get('slow_mo', 0)
    try:
        slow_mo = int(slow_mo)
    except (TypeError, ValueError):
        slow_mo = 0
    return {
        'visible_browser': bool(payload.get('visible_browser')),
        'slow_mo': max(0, min(slow_mo, 3000)),
    }


@app.route('/api/plans/all', methods=['GET'])
def api_get_all_plans():
    """Get all plans from all providers."""
    snapshot = load_all_plans_snapshot()
    all_plans = snapshot.get('plans', [])
    
    return jsonify({
        'success': True,
        'plans': all_plans,
        'total': len(all_plans),
        'providers': snapshot.get('providers', []),
        'total_providers': snapshot.get('total_providers', 0),
        'source': snapshot.get('source'),
        'scraped_at': snapshot.get('scraped_at')
    })


@app.route('/sheets')
def sheets_dashboard():
    """Serve the Google Sheets price sync page."""
    snapshot = load_all_plans_snapshot()
    return render_template(
        'sheets.html',
        sheet_id=get_sheets_config().get('sheet_id'),
        snapshot=snapshot,
    )


@app.route('/api/sheets/status', methods=['GET'])
def api_sheets_status():
    """Return Google OAuth and target spreadsheet status."""
    try:
        status = sheets_status_payload(include_metadata=True)
        snapshot = load_all_plans_snapshot()
        status['snapshot'] = {
            'scraped_at': snapshot.get('scraped_at'),
            'source': snapshot.get('source'),
            'total_plans': snapshot.get('total_plans', len(snapshot.get('plans', []))),
            'total_providers': snapshot.get('total_providers', len(snapshot.get('providers', []))),
        }
        return jsonify({'success': True, **status})
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/api/google/auth/start', methods=['GET'])
def api_google_auth_start():
    """Start Google OAuth for Sheets access."""
    try:
        auth_url, state, code_verifier = authorization_url()
        session['google_oauth_state'] = state
        session['google_oauth_code_verifier'] = code_verifier
        return redirect(auth_url)
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/oauth2callback', methods=['GET'])
def oauth2callback():
    """Handle Google OAuth redirect with enhanced error handling."""
    try:
        fetch_token(
            request.url,
            state=session.get('google_oauth_state'),
            code_verifier=session.get('google_oauth_code_verifier'),
        )
        session.pop('google_oauth_state', None)
        session.pop('google_oauth_code_verifier', None)
        return redirect(url_for('sheets_dashboard', connected='1'))
    except RuntimeError as exc:
        # Custom errors from fetch_token with helpful messages
        error_msg = str(exc)
        session.pop('google_oauth_state', None)
        session.pop('google_oauth_code_verifier', None)
        return render_template(
            'sheets.html',
            sheet_id=get_sheets_config().get('sheet_id'),
            snapshot=load_all_plans_snapshot(),
            oauth_error=error_msg
        ), 500
    except Exception as exc:
        # Generic error fallback
        session.pop('google_oauth_state', None)
        session.pop('google_oauth_code_verifier', None)
        return render_template(
            'sheets.html',
            sheet_id=get_sheets_config().get('sheet_id'),
            snapshot=load_all_plans_snapshot(),
            oauth_error=f"OAuth connection failed: {str(exc)}"
        ), 500


@app.route('/api/sheets/sync', methods=['POST'])
def api_sheets_sync():
    """Sync the current saved plan snapshot to Google Sheets."""
    payload = request.get_json(silent=True) or {}
    dry_run = bool(payload.get('dry_run'))
    snapshot = load_all_plans_snapshot()
    if not snapshot.get('plans'):
        return jsonify({'success': False, 'error': 'No plan data available in /api/plans/all'}), 404

    try:
        if dry_run:
            result = dry_run_with_known_sheet(snapshot)
        else:
            result = sync_sheet(snapshot, dry_run=False)
        result['snapshot'] = {
            'scraped_at': snapshot.get('scraped_at'),
            'source': snapshot.get('source'),
            'total_plans': snapshot.get('total_plans', len(snapshot.get('plans', []))),
        }
        return jsonify(result)
    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


@app.route('/')
def index():
    """Serve the frontend dashboard."""
    return render_template('index.html')


@app.route('/api/capabilities', methods=['GET'])
def api_get_capabilities():
    """Get server capabilities for visible browser debugging."""
    import platform
    import shutil
    
    system = platform.system()
    has_display = bool(os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'))
    has_xvfb = shutil.which('Xvfb') is not None
    has_virtual_support = has_virtual_display_support()
    
    # Determine if visible browser is available
    # Windows/Mac: Always works (native browser opening)
    # Linux: Needs either DISPLAY or Xvfb
    if system in ('Windows', 'Darwin'):  # Darwin = macOS
        visible_browser_available = True
        reason = None
    elif system == 'Linux':
        visible_browser_available = has_display or has_virtual_support
        if not visible_browser_available:
            reason = 'No display server available. Install Xvfb to enable visible browser debugging.'
        else:
            reason = None
    else:
        # Unknown platform, assume it works
        visible_browser_available = True
        reason = None
    
    return jsonify({
        'success': True,
        'visible_browser': visible_browser_available,
        'platform': system,
        'has_display': has_display,
        'has_xvfb': has_xvfb,
        'has_virtual_support': has_virtual_support,
        'reason': reason
    })


@app.route('/api/providers', methods=['GET'])
def api_get_providers():
    """Get list of all providers with their status."""
    providers = get_provider_list()
    return jsonify({
        'success': True,
        'providers': providers,
        'total': len(providers)
    })


@app.route('/api/scrape/progress', methods=['GET'])
def api_scrape_progress():
    """Get live progress for the currently running scrape."""
    return jsonify({
        'success': True,
        'progress': get_progress(),
    })


@app.route('/screenshots/<path:filename>', methods=['GET'])
def serve_screenshot(filename):
    """Serve scraper screenshots from output/screenshots."""
    return send_from_directory(SCREENSHOT_ROOT, filename)


@app.route('/api/scrape/<provider_name>', methods=['POST'])
def api_scrape_provider(provider_name):
    """
    Scrape a specific provider.
    Returns scraped plans and saves to JSON/CSV.
    """
    options = get_scrape_options()
    reset_progress(mode='single', providers_total=1)
    update_progress(
        provider=provider_name,
        status='starting',
        message=f"Starting {provider_name}",
    )

    result = scrape_provider(provider_name, options=options)
    
    if result['success']:
        # Save output
        files = save_output(provider_name, result['plans'])
        result['files'] = files
    publish_provider_result(
        provider_name,
        result.get('plans', []),
        result['success'],
        result.get('error'),
    )
    finish_provider(provider_name, result.get('total_plans', 0), result['success'], result.get('error'))
    finish_progress(result['success'], f"{provider_name} scrape finished")
    
    return jsonify(result)


@app.route('/api/scrape/all', methods=['POST'])
def api_scrape_all():
    """Scrape or report every configured provider without stopping on failures."""
    results = {}
    total_plans = 0
    options = get_scrape_options()
    providers = get_provider_list()
    successful = 0
    failed = 0
    blocked = 0

    reset_progress(mode='all', providers_total=len(providers))
    
    for provider in providers:
        if provider.get('blocked'):
            reason = provider.get('blocked_reason') or 'Provider is blocked'
            result = {
                'success': False,
                'provider': provider['key'],
                'plans': [],
                'total_plans': 0,
                'error': reason,
                'status': 'blocked',
            }
            results[provider['key']] = result
            blocked += 1
            publish_provider_result(
                provider['key'],
                [],
                False,
                reason,
                status='blocked',
            )
            finish_provider(provider['key'], 0, False, reason, status='blocked')
            continue

        if not provider.get('enabled'):
            reason = 'Provider is disabled'
            result = {
                'success': False,
                'provider': provider['key'],
                'plans': [],
                'total_plans': 0,
                'error': reason,
                'status': 'disabled',
            }
            results[provider['key']] = result
            blocked += 1
            publish_provider_result(
                provider['key'],
                [],
                False,
                reason,
                status='disabled',
            )
            finish_provider(provider['key'], 0, False, reason, status='disabled')
            continue

        update_progress(
            provider=provider['key'],
            status='running',
            message=f"Scraping {provider['name']}",
        )
        result = scrape_provider(provider['key'], options=options)
        if result['success']:
            files = save_output(provider['key'], result['plans'])
            result['files'] = files
            successful += 1
        else:
            failed += 1
        results[provider['key']] = result
        total_plans += result.get('total_plans', 0)
        publish_provider_result(
            provider['key'],
            result.get('plans', []),
            result['success'],
            result.get('error'),
        )
        finish_provider(provider['key'], result.get('total_plans', 0), result['success'], result.get('error'))

    finish_progress(
        True,
        f"Completed {len(results)} providers: {successful} successful, {failed} failed, {blocked} blocked",
    )
    
    return jsonify({
        'success': True,
        'results': results,
        'total_plans': total_plans,
        'providers_scraped': len(results),
        'providers_successful': successful,
        'providers_failed': failed,
        'providers_blocked': blocked,
    })


@app.route('/api/results', methods=['GET'])
def api_get_all_results():
    """Get all saved results from all providers."""
    results = get_saved_results()
    total_plans = sum(
        len(data.get('all_plans', []) if isinstance(data, dict) else data)
        for provider_data in results.values()
        for data in provider_data.values()
    )
    
    return jsonify({
        'success': True,
        'results': results,
        'total_plans': total_plans,
        'providers': list(results.keys())
    })


@app.route('/api/results/<provider_name>', methods=['GET'])
def api_get_provider_results(provider_name):
    """Get saved results for a specific provider."""
    results = get_saved_results(provider_name)
    
    if not results:
        return jsonify({
            'success': False,
            'error': f'No saved results found for {provider_name}'
        }), 404
    
    total_plans = sum(
        len(data) for data in results.values() if isinstance(data, list)
    )
    
    return jsonify({
        'success': True,
        'results': results,
        'total_plans': total_plans,
        'provider': provider_name
    })


@app.route('/api/download/<provider_name>/<filename>.json', methods=['GET'])
def api_download_json(provider_name, filename):
    """Download JSON file."""
    filepath = download_json(provider_name, filename)
    if filepath:
        return send_file(filepath, as_attachment=True, download_name=f"{filename}.json")
    return jsonify({'success': False, 'error': 'File not found'}), 404


@app.route('/api/download/<provider_name>/<filename>.csv', methods=['GET'])
def api_download_csv(provider_name, filename):
    """Download CSV file."""
    filepath = download_csv(provider_name, filename)
    if filepath:
        return send_file(filepath, as_attachment=True, download_name=f"{filename}.csv")
    return jsonify({'success': False, 'error': 'File not found'}), 404


@app.route('/api/status', methods=['GET'])
def api_status():
    """Get system status."""
    providers = get_provider_list()
    working = [p for p in providers if p['has_saved_data']]
    
    return jsonify({
        'success': True,
        'status': 'operational',
        'total_providers': len(providers),
        'working_providers': len(working),
        'blocked_providers': len(providers) - len(working)
    })


# ── Benchmark Routes ──────────────────────────────────────────────


@app.route('/api/benchmark', methods=['GET'])
def api_get_benchmark():
    """Get the latest benchmark report (from saved file or generate fresh)."""
    report_path = os.path.join('output', 'benchmark_report.json')
    if os.path.exists(report_path):
        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
        return jsonify({'success': True, 'report': report})
    return jsonify({'success': False, 'error': 'No benchmark report found. Run /api/benchmark/run first.'}), 404


@app.route('/api/benchmark/run', methods=['POST'])
def api_run_benchmark():
    """Run a fresh benchmark analysis and generate all reports."""
    result = run_and_save_benchmark()
    if 'error' in result and 'report' not in result:
        return jsonify({'success': False, 'error': result['error']}), 500
    return jsonify({
        'success': True,
        'summary': result['report']['summary'],
        'files': result['files'],
    })


@app.route('/api/benchmark/advantages', methods=['GET'])
def api_benchmark_advantages():
    """Get tiers where Occom is the cheapest provider."""
    report_path = os.path.join('output', 'benchmark_report.json')
    if not os.path.exists(report_path):
        return jsonify({'success': False, 'error': 'Run benchmark first'}), 404
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)
    return jsonify({
        'success': True,
        'advantages': report.get('occom_advantages', []),
        'total': len(report.get('occom_advantages', []))
    })


@app.route('/api/benchmark/gaps', methods=['GET'])
def api_benchmark_gaps():
    """Get tiers where Occom is NOT the cheapest provider."""
    report_path = os.path.join('output', 'benchmark_report.json')
    if not os.path.exists(report_path):
        return jsonify({'success': False, 'error': 'Run benchmark first'}), 404
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)
    return jsonify({
        'success': True,
        'gaps': report.get('occom_gaps', []),
        'total': len(report.get('occom_gaps', []))
    })


@app.route('/api/alerts', methods=['GET'])
def api_get_alerts():
    """Get the latest alerts."""
    alerts_path = os.path.join('output', 'alerts.json')
    if not os.path.exists(alerts_path):
        return jsonify({'success': True, 'alerts': [], 'total': 0})
    with open(alerts_path, 'r', encoding='utf-8') as f:
        history = json.load(f)
    latest = history[-1] if history else {'alerts': [], 'total_alerts': 0}
    return jsonify({
        'success': True,
        'total': latest.get('total_alerts', 0),
        'high': latest.get('high', 0),
        'medium': latest.get('medium', 0),
        'low': latest.get('low', 0),
        'alerts': latest.get('alerts', []),
        'generated_at': latest.get('generated_at', '')
    })


@app.route('/api/alerts/run', methods=['POST'])
def api_run_alerts():
    """Run alert checks against current plans data."""
    plans = load_all_plans()
    if not plans:
        return jsonify({'success': False, 'error': 'No plan data available'}), 404

    # Load benchmark report if available
    benchmark_report = None
    report_path = os.path.join('output', 'benchmark_report.json')
    if os.path.exists(report_path):
        with open(report_path, 'r', encoding='utf-8') as f:
            benchmark_report = json.load(f)

    alert_report = run_alerts(plans, benchmark_report)
    return jsonify({
        'success': True,
        'total': alert_report['total_alerts'],
        'high': alert_report['high'],
        'medium': alert_report['medium'],
        'low': alert_report['low'],
        'alerts': alert_report['alerts'],
    })


@app.route('/benchmark')
def benchmark_dashboard():
    """Serve the benchmark HTML dashboard."""
    dashboard_path = os.path.join('output', 'benchmark_dashboard.html')
    if os.path.exists(dashboard_path):
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "No benchmark dashboard generated yet. <a href='/api/benchmark/run'>Run benchmark</a> first.", 404


# ── ROI Calculator Routes ─────────────────────────────────────────


@app.route('/roi')
def roi_dashboard():
    """Serve the ROI Calculator HTML page."""
    roi_path = os.path.join('output', 'roi_calculator.html')
    if os.path.exists(roi_path):
        with open(roi_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "No ROI calculator generated yet. <a href='/api/roi/generate'>Generate now</a>.", 404


@app.route('/api/roi', methods=['GET'])
def api_get_roi():
    """Get ROI data for all plans (JSON)."""
    data = compute_roi_data()
    if 'error' in data:
        return jsonify({'success': False, 'error': data['error']}), 404
    return jsonify({'success': True, **data})


@app.route('/api/roi/generate', methods=['POST'])
def api_generate_roi():
    """Regenerate the ROI calculator page from latest data."""
    result = run_and_save_roi()
    if 'error' in result:
        return jsonify({'success': False, 'error': result['error']}), 500
    return jsonify({
        'success': True,
        'total_plans': result['data']['total_plans'],
        'avg_roi': result['data']['avg_roi'],
        'file': result['file'],
    })


if __name__ == '__main__':
    print("Starting ISP Scraper API Server...")
    print("Access dashboard at: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
