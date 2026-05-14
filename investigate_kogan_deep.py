"""Deep inspection of Kogan plan pages to find actual plan card selectors and structure."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

URL = 'https://www.koganinternet.com.au/plans/'

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)

    print(f'\n{"="*70}')
    print(f'DEEP INVESTIGATION: {URL}')
    print('='*70)

    page.goto(URL, timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(8000)

    # Get the full page text to understand structure
    page_text = page.inner_text('body')
    lines = page_text.split('\n')
    
    print("\n[1] Looking for price patterns in page text:")
    price_lines = [l.strip() for l in lines if '$' in l and ('Mbps' in l or 'mth' in l or 'month' in l)]
    print(f"Found {len(price_lines)} lines with prices")
    for line in price_lines[:10]:
        print(f"  {repr(line[:100])}")

    # Try to find the actual data in the HTML
    print("\n[2] Searching for data attributes and specific classes:")
    html = page.content()
    
    # Look for rows in table
    tables = page.query_selector_all('table')
    print(f"\nFound {len(tables)} tables on page")
    
    if tables:
        for t_idx, table in enumerate(tables[:1]):
            rows = table.query_selector_all('tr')
            print(f"\nTable {t_idx}: {len(rows)} rows")
            for r_idx, row in enumerate(rows[:8]):
                cells = row.query_selector_all('td, th')
                cell_texts = [cell.inner_text().strip()[:30] for cell in cells]
                print(f"  Row {r_idx}: {cell_texts}")

    # Look for data-plan or similar attributes
    print("\n[3] Searching for data attributes:")
    data_elems = page.query_selector_all('[data-plan], [data-product], [data-testid]')
    print(f"Found {len(data_elems)} elements with data attributes")
    
    for idx, elem in enumerate(data_elems[:5]):
        data_attrs = elem.evaluate('el => ({...el.dataset})')
        text = elem.inner_text().strip()[:50]
        print(f"  [{idx}] data={data_attrs}, text={repr(text)}")

    # Look for elements containing "Mbps"
    print("\n[4] Looking for all elements containing 'Mbps':")
    all_elems = page.query_selector_all('*')
    mbps_elems = [el for el in all_elems if 'Mbps' in el.inner_text()]
    print(f"Found {len(mbps_elems)} elements with 'Mbps'")
    
    for idx, elem in enumerate(mbps_elems[:10]):
        tag = elem.evaluate('el => el.tagName')
        cls = elem.get_attribute('class') or ''
        text = elem.inner_text().strip()[:80]
        parent_cls = elem.evaluate('el => el.parentElement?.className') or ''
        print(f"  [{idx}] <{tag}> class='{cls[:50]}' parent='{parent_cls[:50]}'")
        print(f"       text={repr(text)}")

    # Look for elements containing price ($)
    print("\n[5] Looking for all elements containing '$':")
    price_elems = [el for el in all_elems if '$' in el.inner_text() and len(el.inner_text().strip()) < 100]
    print(f"Found {len(price_elems)} elements with '$'")
    
    for idx, elem in enumerate(price_elems[:15]):
        tag = elem.evaluate('el => el.tagName')
        cls = elem.get_attribute('class') or ''
        text = elem.inner_text().strip()
        if not text.startswith('$') or len(text) > 50:
            continue
        parent_cls = elem.evaluate('el => el.parentElement?.className') or ''
        print(f"  [{idx}] <{tag}> text={repr(text)} parent='{parent_cls[:40]}'")

    # Check specific high-level structure
    print("\n[6] Main content structure:")
    main = page.query_selector('main, [role="main"], .main-content, #main')
    if main:
        children_count = main.evaluate('el => el.children.length')
        print(f"Main container: {children_count} children")
        
        # Get direct children types
        for idx in range(min(5, children_count)):
            child = main.evaluate(f'el => ({{tag: el.children[{idx}].tagName, class: el.children[{idx}].className, id: el.children[{idx}].id}})')
            print(f"  Child {idx}: {child}")

    # Get entire outer HTML of first table row
    print("\n[7] Full HTML of first table row:")
    first_row = page.query_selector('table tr:nth-child(2)')
    if first_row:
        outer = first_row.evaluate('el => el.outerHTML')
        print(outer[:1500])

    browser.close()
    print(f"\n{'='*70}")
    print("Investigation complete.")
