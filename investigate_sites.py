"""
Investigate ISP website structures to find correct selectors.
Renders each ISP page and saves the HTML + screenshots for analysis.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.render_engine import create_render_engine
from utils.html_parser import parse_html

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output', 'investigation')
os.makedirs(OUTPUT_DIR, exist_ok=True)

ISP_URLS = {
    'optus': 'https://www.optus.com.au/broadband/home-broadband',
    'aussie': 'https://www.aussiebroadband.com.au/internet/',
    'superloop': 'https://www.superloop.com/internet',
}

def investigate_site(engine, name, url):
    """Render a site and analyze its structure."""
    print(f"\n{'='*60}")
    print(f"Investigating: {name} ({url})")
    print(f"{'='*60}")

    screenshot_path = os.path.join(OUTPUT_DIR, f"{name}.png")
    # Try domcontentloaded first (faster, less strict)
    result = engine.render(
        url=url,
        wait_condition="domcontentloaded",
        wait_time=5000,
        screenshot_path=screenshot_path,
    )

    print(f"  Status: {result.status}")
    print(f"  HTML Length: {len(result.html)}")
    print(f"  Error: {result.error}")

    if not result.html:
        print(f"  SKIPPED - no HTML captured")
        return

    # Save raw HTML
    html_path = os.path.join(OUTPUT_DIR, f"{name}.html")
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(result.html)
    print(f"  Saved HTML -> {html_path}")
    print(f"  Saved Screenshot -> {screenshot_path}")

    # Parse and look for common plan-related patterns
    parser = parse_html(result.html)
    if not parser:
        print("  FAILED to parse HTML")
        return

    print(f"\n  --- Structural Analysis ---")

    # Title
    title = parser.extract_text('title')
    print(f"  Page title: {title}")

    # Look for price-like patterns
    price_selectors = [
        '[class*="price"]', '[class*="Price"]',
        '[class*="cost"]', '[class*="Cost"]',
        '[data-testid*="price"]', '[data-price]',
        '.price', '.plan-price',
    ]
    for sel in price_selectors:
        elems = parser.extract_by_selector(sel)
        if elems:
            texts = [e.get_text(strip=True)[:80] for e in elems[:5]]
            print(f"  PRICE match '{sel}' ({len(elems)} hits): {texts}")

    # Look for plan/product card containers
    card_selectors = [
        '[class*="plan"]', '[class*="Plan"]',
        '[class*="card"]', '[class*="Card"]',
        '[class*="product"]', '[class*="Product"]',
        '[class*="tile"]', '[class*="Tile"]',
        '[data-testid*="plan"]', '[data-testid*="card"]',
        'article', 'section',
    ]
    for sel in card_selectors:
        elems = parser.extract_by_selector(sel)
        if elems:
            # Show tag name + classes for first few
            info = []
            for e in elems[:3]:
                tag = e.name
                cls = ' '.join(e.get('class', []))[:60]
                info.append(f"<{tag} class=\"{cls}\">")
            print(f"  CARD match '{sel}' ({len(elems)} hits): {info}")

    # Look for speed-like patterns
    speed_selectors = [
        '[class*="speed"]', '[class*="Speed"]',
        '[class*="mbps"]', '[class*="Mbps"]',
        '[data-testid*="speed"]',
    ]
    for sel in speed_selectors:
        elems = parser.extract_by_selector(sel)
        if elems:
            texts = [e.get_text(strip=True)[:60] for e in elems[:5]]
            print(f"  SPEED match '{sel}' ({len(elems)} hits): {texts}")

    # Look for heading elements inside potential containers
    headings = parser.extract_multiple('h1, h2, h3, h4')
    if headings:
        print(f"  Headings ({len(headings)}): {headings[:8]}")

    # Look for dollar signs in text (strong price indicators)
    import re
    dollar_matches = re.findall(r'\$[\d,.]+(?:/\w+)?', result.html)
    unique_prices = list(dict.fromkeys(dollar_matches))[:15]
    if unique_prices:
        print(f"  Dollar amounts found: {unique_prices}")


def main():
    print("ISP Website Structure Investigation")
    print("Rendering pages with Playwright...\n")

    with create_render_engine(headless=True) as engine:
        for name, url in ISP_URLS.items():
            try:
                investigate_site(engine, name, url)
            except Exception as e:
                print(f"\n  ERROR investigating {name}: {e}")

    print(f"\n\nAll files saved to: {OUTPUT_DIR}")
    print("Review the .html and .png files for detailed structure.")


if __name__ == "__main__":
    main()
