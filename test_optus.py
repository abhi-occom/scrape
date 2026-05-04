"""Quick test: run Optus scraper and display + save results."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers.optus import scrape_via_playwright
from scraper_service import save_output

print("Running Optus scraper (Firefox)...")
plans = scrape_via_playwright()

print(f"\n{'='*90}")
print(f"  OPTUS — {len(plans)} plans scraped")
print(f"{'='*90}")
print(f"  {'Plan Name':<45} {'Network':<25} {'Speed':>10} {'Price':>10} {'Promo':>10}")
print(f"  {'-'*45} {'-'*25} {'-'*10} {'-'*10} {'-'*10}")

for p in plans:
    name = p['plan_name'][:45]
    net = p.get('network_type', '')[:25]
    speed = f"{p['download_speed']}/{p['upload_speed']}"
    price = f"${p['price']:.0f}/mth"
    promo = f"${p['promo_price']:.0f}/mth" if p.get('promo_price') else "-"
    period = p.get('promo_period', '')
    print(f"  {name:<45} {net:<25} {speed:>10} {price:>10} {promo:>10}  {period}")

if plans:
    prices = [p['price'] for p in plans]
    speeds = [p['download_speed'] for p in plans]
    print(f"\n  Total plans: {len(plans)}")
    print(f"  Price range: ${min(prices):.0f} - ${max(prices):.0f}/mth")
    print(f"  Speed range: {min(speeds)} - {max(speeds)} Mbps")

    # Save output
    files = save_output('optus', plans)
    print(f"\n  Saved files:")
    for fmt, paths in files.items():
        for fp in paths:
            print(f"    {fmt}: {fp}")
else:
    print("\n  No plans extracted!")
