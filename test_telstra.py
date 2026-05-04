"""Test: run multi-page Telstra scraper and display + save results."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers.telstra import scrape_telstra_plans
from scraper_service import save_output

print("Running Telstra multi-page scraper...")
results = scrape_telstra_plans()

grand_total = 0
for page_key, plans in results.items():
    count = len(plans)
    grand_total += count
    print(f"\n{'='*100}")
    print(f"  TELSTRA / {page_key.upper()} — {count} plans")
    print(f"{'='*100}")
    print(f"  {'Plan Name':<42} {'Network':<22} {'Speed':>10} {'Price':>10}")
    print(f"  {'-'*42} {'-'*22} {'-'*10} {'-'*10}")
    for p in plans:
        name = p['plan_name'][:42]
        net = p.get('network_type', '')[:22]
        speed = f"{p['download_speed']}/{p['upload_speed']}"
        price = f"${p['price']:.0f}/mth"
        print(f"  {name:<42} {net:<22} {speed:>10} {price:>10}")

print(f"\n{'='*100}")
print(f"  GRAND TOTAL: {grand_total} plans across {len(results)} pages")
print(f"{'='*100}")

# Save output
files = save_output('telstra', results)
print(f"\n  Saved files:")
for fmt, paths in files.items():
    for fp in paths:
        print(f"    {fmt}: {fp}")
