"""Probe Kogan DOM structure — find card selectors and full per-card field layout."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

URL = 'https://www.koganinternet.com.au/plans/'

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)
    page.goto(URL, timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(8000)

    # ── 1. Try known selectors ───────────────────────────────────────────────
    SELECTORS = [
        '.planItem', '.plan-item', '.PlanItem', '.plan_item',
        '[class*="planItem"]', '[class*="PlanCard"]', '[class*="planCard"]',
        '[class*="plan-card"]', '[class*="plan_card"]', '[class*="PlanItem"]',
        '[class*="slide"]', '[class*="Slide"]', '[class*="swiper-slide"]',
        'article', 'section', '[class*="item"]', '[class*="Item"]',
        '[class*="product"]', '[class*="Product"]', '[class*="tile"]',
        '[class*="Tile"]', '[class*="card"]', '[class*="Card"]',
    ]
    print('\n[1] Selector hit counts:')
    hits = {}
    for sel in SELECTORS:
        try:
            els = page.query_selector_all(sel)
            if els:
                hits[sel] = len(els)
                cls0 = els[0].get_attribute('class') or ''
                txt0 = (els[0].evaluate('el => el.innerText') or '')[:60].replace('\n', ' | ')
                print(f'  {sel}: {len(els)}  class={repr(cls0[:70])}  text={repr(txt0)}')
        except Exception as exc:
            print(f'  {sel}: ERROR {exc}')

    # ── 2. Get all unique classes matching plan/card/slide/item ─────────────
    print('\n[2] Unique class names containing plan/card/slide/item/product/price:')
    result = page.evaluate("""
        () => {
            const all = document.querySelectorAll('*');
            const seen = new Set();
            const out = [];
            for (const el of all) {
                const cls = typeof el.className === 'string' ? el.className : '';
                if (cls.match(/plan|card|slide|item|product|price/i) && !seen.has(cls)) {
                    seen.add(cls);
                    out.push({
                        tag: el.tagName,
                        cls: cls.substring(0, 120),
                        txt: (el.innerText || '').substring(0, 60).replace(/\n/g,' ')
                    });
                }
            }
            return out.slice(0, 60);
        }
    """)
    for r in result:
        print(f"  tag={r['tag']}  class={repr(r['cls'])}  text={repr(r['txt'])}")

    # ── 3. Look for swiper/carousel slides containing plan names ────────────
    print('\n[3] Candidates with 5-15 elements (likely plan cards):')
    candidates = {sel: cnt for sel, cnt in hits.items() if 4 <= cnt <= 20}
    print(f'  {candidates}')

    # ── 4. Per-card text for best candidate ─────────────────────────────────
    plan_names = ['4G Internet', 'Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond']
    for sel, cnt in sorted(hits.items(), key=lambda x: x[1]):
        try:
            cards = page.query_selector_all(sel)
            texts = [(c.evaluate('el => el.innerText') or '').strip()[:30] for c in cards[:3]]
            has_plan = any(any(n in t for n in plan_names) for t in texts)
            if has_plan:
                print(f'\n[FOUND PLAN CARDS] Selector: {sel}  ({cnt} elements)')
                for i, card in enumerate(cards[:8]):
                    txt = (card.evaluate('el => el.innerText') or '').strip()[:200].replace('\n', ' | ')
                    cls = card.get_attribute('class') or ''
                    print(f'  [{i}] cls={repr(cls[:80])}')
                    print(f'       txt={repr(txt)}')
        except Exception:
            pass

    # ── 5. Dump outer HTML of single card ────────────────────────────────────
    print('\n[5] outerHTML of first element containing "Bronze":')
    bronze_el = page.query_selector('text=Bronze')
    if bronze_el:
        # Walk up to find meaningful card container
        for depth in range(6):
            parent = bronze_el.evaluate(f'el => {{let n=el; for(let i=0;i<{depth};i++) n=n.parentElement; return {{tag:n.tagName, cls:n.className, html:n.outerHTML.substring(0,1500)}};}}')
            print(f'  Depth {depth}: tag={parent["tag"]} cls={repr(parent["cls"][:80])}')
            if depth == 4:
                print(f'  HTML: {parent["html"]}')

    browser.close()
    print('\n[Done]')
