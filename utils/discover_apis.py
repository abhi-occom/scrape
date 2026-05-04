"""
API Endpoint Discovery Tool
Helps find API endpoints used by ISP provider websites.
"""

import requests
from urllib.parse import urlparse, urljoin
import re
import json


class APIDiscoverer:
    """Tool to discover API endpoints on websites."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.found_endpoints = []
        
    def scan_page_for_apis(self, url: str = None) -> list:
        """
        Scan a webpage for API endpoints in JavaScript.
        
        Args:
            url: URL to scan (defaults to base_url)
        
        Returns:
            List of found API endpoints
        """
        url = url or self.base_url
        endpoints = []
        
        try:
            print(f"[*] Scanning {url} for API endpoints...")
            
            response = requests.get(url, timeout=30)
            html_content = response.text
            
            # Pattern 1: Look for /api/ paths
            api_pattern = r'["\'](/api/[^"\']+)|["\'](https?://[^"\']*\/api\/[^"\']+)'
            matches = re.findall(api_pattern, html_content)
            for match in matches:
                endpoint = match[0] or match[1]
                if endpoint and self.domain in endpoint or endpoint.startswith('/'):
                    endpoints.append(endpoint)
            
            # Pattern 2: Look for fetch/XHR calls
            fetch_pattern = r'fetch\(["\']([^"\']+)["\']\)'
            matches = re.findall(fetch_pattern, html_content)
            endpoints.extend(matches)
            
            # Pattern 3: Look for axios calls
            axios_pattern = r'axios\.(get|post)\(["\']([^"\']+)["\']\)'
            matches = re.findall(axios_pattern, html_content)
            for _, endpoint in matches:
                endpoints.append(endpoint)
            
            # Pattern 4: Look for GraphQL endpoints
            graphql_pattern = r'["\'](/graphql[^"\']*)["\']'
            matches = re.findall(graphql_pattern, html_content)
            endpoints.extend(matches)
            
            # Pattern 5: Look for JSON endpoints
            json_pattern = r'["\']([^"\']*\.json[^"\']*)["\']'
            matches = re.findall(json_pattern, html_content)
            endpoints.extend(matches)
            
            # Clean and deduplicate
            endpoints = list(set(endpoints))
            endpoints = [self._clean_endpoint(e) for e in endpoints if self._is_valid(e)]
            
            self.found_endpoints.extend(endpoints)
            
            print(f"[✓] Found {len(endpoints)} potential API endpoints")
            for ep in endpoints:
                print(f"    → {ep}")
            
        except Exception as e:
            print(f"[✗] Error scanning {url}: {e}")
        
        return endpoints
    
    def _clean_endpoint(self, endpoint: str) -> str:
        """Clean and normalize endpoint URL."""
        if endpoint.startswith('//'):
            endpoint = 'https:' + endpoint
        elif endpoint.startswith('/'):
            endpoint = urljoin(self.base_url, endpoint)
        return endpoint
    
    def _is_valid(self, endpoint: str) -> bool:
        """Check if endpoint is valid for our domain."""
        if not endpoint:
            return False
        if self.domain in endpoint:
            return True
        if endpoint.startswith('/api/') or endpoint.startswith('/graphql'):
            return True
        return False
    
    def test_endpoints(self, endpoints: list = None) -> list:
        """
        Test discovered endpoints to see which ones return JSON.
        
        Args:
            endpoints: List of endpoints to test (defaults to found_endpoints)
        
        Returns:
            List of working endpoints
        """
        endpoints = endpoints or self.found_endpoints
        working = []
        
        print(f"\n[*] Testing {len(endpoints)} endpoints...")
        
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=10)
                
                # Check if response is JSON
                if 'application/json' in response.headers.get('Content-Type', ''):
                    print(f"[✓] {endpoint} - Returns JSON ({response.status_code})")
                    working.append({
                        'url': endpoint,
                        'status': response.status_code,
                        'has_json': True
                    })
                else:
                    print(f"[~] {endpoint} - Returns HTML/Other ({response.status_code})")
                    
            except Exception as e:
                print(f"[✗] {endpoint} - Error: {str(e)[:50]}")
        
        return working
    
    def scan_js_files(self, url: str = None) -> list:
        """
        Scan JavaScript files for API endpoints.
        
        Args:
            url: URL to scan (defaults to base_url)
        
        Returns:
            List of found API endpoints
        """
        url = url or self.base_url
        endpoints = []
        
        try:
            response = requests.get(url, timeout=30)
            html_content = response.text
            
            # Find all JS file references
            js_pattern = r'src=["\']([^"\']+\.js[^"\']*)["\']'
            js_files = re.findall(js_pattern, html_content)
            
            print(f"[*] Found {len(js_files)} JavaScript files")
            
            for js_file in js_files[:10]:  # Limit to first 10 files
                if js_file.startswith('//'):
                    js_file = 'https:' + js_file
                elif js_file.startswith('/'):
                    js_file = urljoin(url, js_file)
                
                try:
                    js_response = requests.get(js_file, timeout=10)
                    js_content = js_response.text
                    
                    # Look for API patterns in JS
                    api_pattern = r'["\'](/api/[^"\']+)|["\'](https?://[^"\']*\/api\/[^"\']+)'
                    matches = re.findall(api_pattern, js_content)
                    
                    for match in matches:
                        endpoint = match[0] or match[1]
                        if endpoint:
                            endpoints.append(self._clean_endpoint(endpoint))
                    
                except Exception as e:
                    print(f"[!] Could not fetch JS file: {js_file}")
            
            endpoints = list(set(endpoints))
            print(f"[✓] Found {len(endpoints)} API endpoints in JS files")
            
        except Exception as e:
            print(f"[✗] Error scanning JS files: {e}")
        
        return endpoints
    
    def save_results(self, filename: str = 'discovered_apis.json'):
        """Save discovered endpoints to JSON file."""
        results = {
            'base_url': self.base_url,
            'endpoints': self.found_endpoints
        }
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"[✓] Results saved to {filename}")


def discover_provider_apis(providers: dict):
    """
    Discover APIs for multiple provider websites.
    
    Args:
        providers: Dictionary of provider names and URLs
    """
    results = {}
    
    for provider_name, url in providers.items():
        print(f"\n{'='*60}")
        print(f"Scanning {provider_name}: {url}")
        print(f"{'='*60}\n")
        
        discoverer = APIDiscoverer(url)
        
        # Scan main page
        discoverer.scan_page_for_apis(url)
        
        # Scan JS files
        js_endpoints = discoverer.scan_js_files(url)
        discoverer.found_endpoints.extend(js_endpoints)
        
        # Test endpoints
        working = discoverer.test_endpoints()
        
        # Save results
        discoverer.save_results(f'{provider_name}_apis.json')
        
        results[provider_name] = {
            'all_endpoints': discoverer.found_endpoints,
            'working_endpoints': working
        }
    
    # Save combined results
    with open('all_provider_apis.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n[✓] All results saved to all_provider_apis.json")
    return results


if __name__ == "__main__":
    # ISP Provider websites to scan
    providers = {
        'telstra': 'https://www.telstra.com.au/internet/home-nbn',
        'optus': 'https://www.optus.com.au/broadband/nbn',
        'aussie': 'https://www.aussiebroadband.com.au/broadband/nbn/',
        'superloop': 'https://www.superloop.com/au/home-broadband/nbn'
    }
    
    print("="*60)
    print("ISP API Endpoint Discovery Tool")
    print("="*60)
    
    results = discover_provider_apis(providers)
