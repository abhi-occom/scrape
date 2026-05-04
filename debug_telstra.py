"""Debug script to test Telstra selectors."""
import sys
sys.path.insert(0, 'c:/xampp/htdocs/staging/scrape')
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720},
        locale="en-AU",
    )
    page = context.new_page()
    page.goto("https://www.telstra.com.au/internet/nbn", timeout=30000, wait_until="domcontentloaded")
    page.wait_for_timeout(5000)
    
    headers = page.query_selector_all("h3.tcom-fixed-plan-card-header__headline")
    prices = page.query_selector_all("[data-fixed-plan-card-price]")
    downloads = page.query_selector_all("[data-tcom-fixed-plancard-dsq-evening-download]")
    uploads = page.query_selector_all("[data-tcom-fixed-plancard-dsq-evening-upload]")
    
    print(f"Headers: {len(headers)}")
    print(f"Prices: {len(prices)}")
    print(f"Downloads: {len(downloads)}")
    print(f"Uploads: {len(uploads)}")
    
    for i, h in enumerate(headers[:10]):
        name = h.inner_text().strip().replace("\n", " ")
        print(f"  Plan {i}: {name[:60]}")
    
    for i, pr in enumerate(prices[:10]):
        val = pr.get_attribute("data-fixed-plan-card-price")
        print(f"  Price {i}: ${val}/mth")
    
    for i, d in enumerate(downloads[:10]):
        val = d.get_attribute("data-tcom-fixed-plancard-dsq-evening-download")
        print(f"  Download {i}: {val} Mbps")
    
    for i, u in enumerate(uploads[:10]):
        val = u.get_attribute("data-tcom-fixed-plancard-dsq-evening-upload")
        print(f"  Upload {i}: {val} Mbps")
    
    browser.close()
