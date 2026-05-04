"""
Flask API backend for ISP scraper frontend dashboard.
Provides REST endpoints for scraping, viewing results, and downloading files.
"""
from flask import Flask, jsonify, request, send_file, render_template
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper_service import (
    scrape_provider,
    save_output,
    get_saved_results,
    get_provider_list,
    download_json,
    download_csv
)
from utils.benchmark import run_benchmark, load_all_plans, save_benchmark_report, save_benchmark_csv
from utils.alerts import run_alerts
from benchmark_report import generate_html_report, run_and_save_benchmark
from roi_calculator import compute_roi_data, generate_roi_page, run_and_save_roi

app = Flask(__name__, template_folder='templates')

# API Routes


@app.route('/')
def index():
    """Serve the frontend dashboard."""
    return render_template('index.html')


@app.route('/api/providers', methods=['GET'])
def api_get_providers():
    """Get list of all providers with their status."""
    providers = get_provider_list()
    return jsonify({
        'success': True,
        'providers': providers,
        'total': len(providers)
    })


@app.route('/api/scrape/<provider_name>', methods=['POST'])
def api_scrape_provider(provider_name):
    """
    Scrape a specific provider.
    Returns scraped plans and saves to JSON/CSV.
    """
    result = scrape_provider(provider_name)
    
    if result['success']:
        # Save output
        files = save_output(provider_name, result['plans'])
        result['files'] = files
    
    return jsonify(result)


@app.route('/api/scrape/all', methods=['POST'])
def api_scrape_all():
    """Scrape all enabled providers."""
    results = {}
    total_plans = 0
    
    for provider in get_provider_list():
        if provider['enabled']:
            result = scrape_provider(provider['key'])
            if result['success']:
                files = save_output(provider['key'], result['plans'])
                result['files'] = files
            results[provider['key']] = result
            total_plans += result.get('total_plans', 0)
    
    return jsonify({
        'success': True,
        'results': results,
        'total_plans': total_plans,
        'providers_scraped': len(results)
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
