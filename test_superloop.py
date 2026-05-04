"""Test: run multi-page Superloop scraper and display + save results."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers.superloop import scrape_superloop_plans
from scraper_service import save_output

print("Running Superloop multi-page scraper...")
results = scrape_superloop_plans()

grand_total = 0
for page_key, plans in results.items():
    count = len(plans)
    grand_total += count
    print(f"\n{'='*90}")
    print(f"  SUPERLOOP / {page_key.upper()} — {count} plans")
    print(f"{'='*90}")
    print(f"  {'Plan Name':<40} {'Network':<18} {'Speed':>10} {'Price':>10} {'Promo':>10} {'Period'}")
    print(f"  {'-'*40} {'-'*18} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")
    for p in plans:
        name = p['plan_name'][:40]
        net = p.get('network_type', '')[:18]
        speed = f"{p['download_speed']}/{p['upload_speed']}"
        price = f"${p['price']:.0f}/mth"
        promo = f"${p['promo_price']:.0f}/mth" if p.get('promo_price') else "-"
        period = p.get('promo_period', '') or ''
        print(f"  {name:<40} {net:<18} {speed:>10} {price:>10} {promo:>10} {period}")

print(f"\n{'='*90}")
print(f"  GRAND TOTAL: {grand_total} plans across {len(results)} pages")
print(f"{'='*90}")

# Save output
files = save_output('superloop', results)
print(f"\n  Saved files:")
for fmt, paths in files.items():
    for fp in paths:
        print(f"    {fmt}: {fp}")
