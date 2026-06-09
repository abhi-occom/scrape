"""
Enhanced Flask API for ISP Plans - Production Ready Version
"""
from flask import Flask, jsonify, request, send_file, render_template
import json
import os
import sys
from datetime import datetime
import time
import hashlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper_service import (
    scrape_provider,
    save_output,
    load_all_plans_snapshot,
    get_provider_list,
    download_json,
    download_csv
)

# ============================================================
# CONFIGURATION
# ============================================================

app = Flask(__name__, template_folder='templates')

# API Key - Change this in production!
API_KEY = os.environ.get('API_KEY', 'ispPlans2024SecureKey123')

# Simple in-memory cache
CACHE = {}
CACHE_TIMEOUT = 300  # 5 minutes

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def generate_cache_key(*args, **kwargs):
    """Generate a unique cache key from request params."""
    key_data = f"{args}{sorted(kwargs.items())}"
    return hashlib.md5(key_data.encode()).hexdigest()

def get_cached_response(cache_key):
    """Get response from cache if not expired."""
    if cache_key in CACHE:
        data, timestamp = CACHE[cache_key]
        if time.time() - timestamp < CACHE_TIMEOUT:
            return data
    return None

def set_cached_response(cache_key, data):
    """Store response in cache."""
    CACHE[cache_key] = (data, time.time())

def standardize_response(success=True, data=None, error=None, message=None):
    """Standardize all API responses."""
    response = {
        'success': success,
        'timestamp': datetime.now().isoformat(),
    }
    if data is not None:
        response['data'] = data
    if error is not None:
        response['error'] = error
    if message is not None:
        response['message'] = message
    return response

def require_api_key(f):
    """Decorator to require API key for protected endpoints."""
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if api_key != API_KEY:
            return jsonify(standardize_response(
                success=False, 
                error='Unauthorized', 
                message='Invalid or missing API key'
            )), 401
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def filter_plans(plans, provider=None, network_type=None, min_speed=None, 
                 max_speed=None, min_price=None, max_price=None):
    """Filter plans based on query parameters."""
    if not plans:
        return []
    
    filtered = []
    for plan in plans:
        # Provider filter
        if provider and plan.get('provider', '').lower() != provider.lower():
            continue
        
        # Network type filter
        if network_type and plan.get('network_type', '').lower() != network_type.lower():
            continue
        
        # Speed filters
        speed = plan.get('download_speed', 0)
        if min_speed and speed < int(min_speed):
            continue
        if max_speed and speed > int(max_speed):
            continue
        
        # Price filters
        price = plan.get('price', 999999)
        if min_price and price < float(min_price):
            continue
        if max_price and price > float(max_price):
            continue
        
        filtered.append(plan)
    
    return filtered

# ============================================================
# MAIN ROUTES
# ============================================================

@app.route('/')
def index():
    """Serve the frontend dashboard."""
    return render_template('index.html')

# ============================================================
# PUBLIC ENDPOINTS (No API Key Required)
# ============================================================

@app.route('/api/status', methods=['GET'])
def api_status():
    """Get system status - public endpoint."""
    providers = get_provider_list()
    working = [p for p in providers if p['has_saved_data']]
    
    return jsonify(standardize_response(
        data={
            'status': 'operational',
            'total_providers': len(providers),
            'working_providers': len(working),
            'providers': [p['name'] for p in working]
        }
    ))

@app.route('/api/providers', methods=['GET'])
def api_get_providers():
    """Get list of all providers - public endpoint."""
    providers = get_provider_list()
    return jsonify(standardize_response(
        data={
            'providers': providers,
            'total': len(providers)
        }
    ))

@app.route('/api/docs', methods=['GET'])
def api_docs():
    """API Documentation - public endpoint."""
    docs = {
        'name': 'ISP Plans API',
        'version': '2.0.0',
        'description': 'API for accessing Australian ISP plan data',
        'base_url': request.host_url.rstrip('/'),
        'authentication': {
            'type': 'API Key (Header Only - More Secure!)',
            'header': 'X-API-Key',
            'example': 'X-API-Key: your_api_key_here',
            'warning': 'Never pass API key in URL parameters!'
        },
        'endpoints': {
            'public': {
                '/api/status': 'Get API status',
                '/api/providers': 'List all providers',
                '/api/docs': 'API documentation',
                '/api/plans': 'Get all plans (with filters) - NO KEY NEEDED',
            },
            'protected': {
                '/api/plans/all': 'Get all plans data (requires header key)',
                '/api/plans/<provider>': 'Get plans for specific provider (requires header key)',
            }
        },
        'examples': {
            'curl': 'curl -H "X-API-Key: YOUR_KEY" ' + request.host_url + 'api/plans/all',
            'javascript': 'fetch(url, { headers: { "X-API-Key": "YOUR_KEY" } })',
            'python': 'requests.get(url, headers={"X-API-Key": "YOUR_KEY"})',
            'filter_by_provider': f'{request.host_url}api/plans?provider=telstra',
            'filter_by_speed': f'{request.host_url}api/plans?min_speed=100&max_price=80',
        }
    }
    return jsonify(standardize_response(data=docs))

# ============================================================
# PLANS ENDPOINTS
# ============================================================

@app.route('/api/plans', methods=['GET'])
def api_get_plans():
    """
    Get all plans with optional filters.
    Public endpoint with optional API key for higher rate limits.
    """
    # Check cache
    cache_key = generate_cache_key('plans', request.args)
    cached = get_cached_response(cache_key)
    if cached:
        return jsonify(cached)
    
    # Parse query parameters
    provider = request.args.get('provider')
    network_type = request.args.get('network_type')
    min_speed = request.args.get('min_speed')
    max_speed = request.args.get('max_speed')
    min_price = request.args.get('min_price')
    max_price = request.args.get('max_price')
    sort_by = request.args.get('sort_by', 'price')  # price, speed
    order = request.args.get('order', 'asc')  # asc, desc
    
    snapshot = load_all_plans_snapshot()
    all_plans = [dict(plan) for plan in snapshot.get('plans', [])]
    
    # Apply filters
    filtered_plans = filter_plans(
        all_plans, 
        provider=provider,
        network_type=network_type,
        min_speed=min_speed,
        max_speed=max_speed,
        min_price=min_price,
        max_price=max_price
    )
    
    # Sort results
    reverse = order == 'desc'
    if sort_by == 'price':
        filtered_plans.sort(key=lambda x: x.get('price', 999999), reverse=reverse)
    elif sort_by == 'speed':
        filtered_plans.sort(key=lambda x: x.get('download_speed', 0), reverse=reverse)
    
    response = standardize_response(data={
        'plans': filtered_plans,
        'total': len(filtered_plans),
        'source': snapshot.get('source'),
        'scraped_at': snapshot.get('scraped_at'),
        'total_available': snapshot.get('total_plans', len(all_plans)),
        'filters': {
            'provider': provider,
            'network_type': network_type,
            'min_speed': min_speed,
            'max_speed': max_speed,
            'min_price': min_price,
            'max_price': max_price,
            'sort_by': sort_by,
            'order': order
        }
    })
    
    # Cache the response
    set_cached_response(cache_key, response)
    
    return jsonify(response)

@app.route('/api/plans/all', methods=['GET'])
def api_get_all_plans():
    """Get all plans - requires API key in HEADER only (not URL)."""
    # Only accept key from HEADER (secure)
    api_key = request.headers.get('X-API-Key')
    if api_key != API_KEY:
        return jsonify(standardize_response(
            success=False, 
            error='Unauthorized', 
            message='Invalid or missing API key. Use header: X-API-Key: your_key'
        )), 401
    
    snapshot = load_all_plans_snapshot()
    return jsonify(standardize_response(data=snapshot))

@app.route('/api/plans/<provider_name>', methods=['GET'])
def api_get_provider_plans(provider_name):
    """Get plans for a specific provider - requires API key in HEADER only."""
    # Only accept key from HEADER (secure)
    api_key = request.headers.get('X-API-Key')
    if api_key != API_KEY:
        return jsonify(standardize_response(
            success=False, 
            error='Unauthorized', 
            message='Invalid or missing API key. Use header: X-API-Key: your_key'
        )), 401
    
    snapshot = load_all_plans_snapshot()
    plans = [
        plan for plan in snapshot.get('plans', [])
        if plan.get('provider', '').lower() == provider_name.lower()
    ]
    
    if not plans:
        return jsonify(standardize_response(
            success=False,
            error='Provider not found',
            message=f'No data found for provider: {provider_name}'
        )), 404
    
    return jsonify(standardize_response(data={
        'provider': provider_name,
        'plans': plans,
        'total': len(plans),
        'source': snapshot.get('source'),
        'scraped_at': snapshot.get('scraped_at')
    }))

# ============================================================
# HEALTH CHECK
# ============================================================

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for monitoring."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'cache_size': len(CACHE)
    })

# ============================================================
# MAIN
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 ISP Plans API - Production Ready")
    print("=" * 60)
    print(f"📌 API Key: {API_KEY}")
    print(f"📌 Access dashboard: http://localhost:5000")
    print(f"📌 API Docs: http://localhost:5000/api/docs")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000)
