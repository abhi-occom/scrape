"""Quick test for the Exetel scraper."""
from providers.exetel import scrape_exetel_plans

results = scrape_exetel_plans()
for page, plans in results.items():
    print(f"{page}: {len(plans)} plans")
    for p in plans:
        name = p.get('plan_name', '')
        net = p.get('network_type', '')
        dl = p.get('download_speed', 0)
        price = p.get('price', 0)
        print(f"  - {name} | {net} | {dl}Mbps | ${price}/mth")
