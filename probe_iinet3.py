"""Find all plan data on the wireless page by examining the DOM more carefully."""
from playwright.sync_api import sync_playwright
from utils.stealth import create_stealth_browser, create_stealth_page
import re

with sync_playwright() as p:
    browser = create_stealth_browser(p)
    page = create_stealth_page(browser)
    page.goto('https://www.iinet.net.au/internet-product/broadband/nbn/plans/wireless', timeout=40000, wait_until='domcontentloaded')
    page.wait_for_timeout(8000)

    # Find the full plan section text
    body_text = page.evaluate('() => document.body.innerText')
    # Extract from "Select a plan" until end of plans
    idx_start = body_text.find('Select a plan')
    idx_end = body_text.find('Do you need a modem?')
    if idx_start >= 0 and idx_end >= 0:
        plan_section = body_text[idx_start:idx_end]
        print('=== PLAN SECTION TEXT ===')
        print(repr(plan_section))
    else:
        print(f'idx_start={idx_start}, idx_end={idx_end}')
        print(repr(body_text[800:2500]))

    # Find .plan-selector or similar wrapper
    plan_sel_selectors = [
        '[class*="plan-selector"]',
        '[class*="planSelector"]',
        '[id*="plan"]',
        '[ng-repeat*="plan"]',
        '[data-plan]',
    ]
    for s in plan_sel_selectors:
        els = page.query_selector_all(s)
        if els:
            print(f'\n[{s}] count={len(els)}')
            for i, el in enumerate(els[:2]):
                print(f'  [{i}] text: {repr(el.inner_text().strip()[:200])}')
                print(f'  [{i}] class: {el.get_attribute("class")}')

    # Try ng-repeat attribute (Angular app)
    page.evaluate('''() => {
        const all = document.querySelectorAll("[ng-repeat]");
        console.log("ng-repeat count:", all.length);
        all.forEach((el, i) => {
            if (i < 5) console.log(i, el.getAttribute("ng-repeat"), el.innerText.substring(0, 100));
        });
    }''')

    browser.close()
    print('\nProbe 3 complete.')
