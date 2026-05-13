The probe/investigation scripts are part of the project's research history — they document how the selectors and data structures were discovered, which is valuable for future maintenance when the site changes.



how you do this research what are the steps you follow for this



---

## The Scraper Research Process

### Step 1 — Write a broad investigation script (`investigate_*.py`)

The first script is intentionally **dumb and wide**. It tries every common selector pattern without assuming anything about the site:

```python
selectors_to_try = [
    '[data-component*="plan"]',
    '.plan-card', '.card', '[class*="plan"]',
    '[role="group"]', '.product-card', ...
]
for selector in selectors_to_try:
    cards = page.query_selector_all(selector)
    if cards:
        # print h3s, spans, paragraphs, price lines, speed lines
```

**Goal:** Find which selectors return elements that *look like* plan cards — have `$`, `Mbps`, plan names.

---

### Step 2 — Identify the rendering strategy

From the investigation output, classify the site into one of four categories:

| Category | Signs | Approach |
|----------|-------|----------|
| **Static HTML** | Cards visible immediately, clean text | Direct selector scraping |
| **JavaScript rendered** | Cards appear after `wait_for_timeout` | Wait longer, then scrape DOM |
| **Embedded JSON** | Script tags with `monthlyCost`, `planName` etc. | Parse JSON blob directly |
| **SPA / API-driven** | Angular/React app, address lookup, empty DOM | Intercept network requests or scrape visible state |

For iiNet the classification went:
- `/plans/fibre` → **JavaScript rendered** (cards appear after 7s wait)
- `/plans/wireless` → **SPA** (Angular `iinetApp`, address-dependent)
- `/fibre-upgrade` → **Static informational** (no plans)

---

### Step 3 — Write targeted probe scripts (`probe_*.py`)

Once you know *which* selectors hit, drill into the **exact DOM structure** of individual cards:

```python
for i, card in enumerate(cards):
    h3s  = [h.inner_text() for h in card.query_selector_all('h3')]
    spans = [s.inner_text() for s in card.query_selector_all('span')]
    print(f'h3s: {h3s}')
    print(f'spans: {spans}')
    print(f'text: {repr(card.inner_text()[:300])}')
```

**Goal:** Map every piece of data (name, speed, price, promo) to a specific element or text pattern. For iiNet this revealed:

```
h3[0]   = "NBN500"           → plan name
h3[1]   = "500Mbps"          → typical DL
h3[2]   = "42Mbps"           → typical UL
span[3] = "$64"              → promo price (whole dollars)
span[5] = ".99\n/mth"        → promo price (cents)
text    = "then $94.99/mth"  → regular price
```

---

### Step 4 — Handle the hard cases with deeper probes

When something doesn't behave as expected, write another probe specifically for that problem:

| Problem | Probe strategy |
|---------|---------------|
| Wireless page showed 0 plans | Check `.plans-wrapper` children, look for Angular `ng-repeat`, check `ng-app` attribute |
| Price was split across spans | Print every span's raw text including `\n` characters |
| Suspected embedded JSON | Decode HTML entities, regex search for `"plans":`, `"monthlyCost":` |
| Suspected API calls | Intercept network responses with `page.on('response', handler)` |
| Unexpected page content | Print full `document.body.innerText` in sections |

Each probe answers **one specific question** and its output directly informs the next probe or the final implementation.

---

### Step 5 — Validate the regex patterns in isolation

Before writing the scraper, test every regex against real captured text:

```python
# From probe output, copy the real card text:
full_text = 'Save $30/mth for 6 months\n\nNBN500\n...\n$64\n.99\n/mth\nthen $94.99/mth'

import re
print(re.search(r'then\s*\$\s*([\d]+\.[\d]{2})/mth', full_text))  # → 94.99
print(re.search(r'(?:first|for)\s+(\d+)\s+months?', full_text))    # → 6
```

**Goal:** Confirm each pattern matches before it goes into production code. This is where most scraper bugs are caught early.

---

### Step 6 — Write the production scraper

Only now write `providers/iinet.py`, following the existing provider pattern:

1. `IINET_PAGES` dict — URLs + method routing
2. `scrape_iinet_plans()` — browser lifecycle, loop, dispatch
3. Extraction functions — one per page type
4. Helpers — `_parse_mbps()`, `_parse_regular_price()`, `_extract_promo_price()`
5. `build_plan()` — standardised output dict
6. `deduplicate_plans()` — deduplication

---

### Step 7 — Test the scraper standalone

```python
# test_iinet.py
from providers.iinet import scrape_iinet_plans
results = scrape_iinet_plans()
# print summary table
```

Run this repeatedly until output is correct, *before* wiring into `main.py`.

---

### Step 8 — Wire into main pipeline

Only after standalone test passes:
1. Add to `config.py` (`PROVIDERS`)
2. Add import + entry to `main.py` scrapers list
3. Run `main.py` import check

---

### Key principles throughout

- **Never assume** — always print raw text/spans before writing regex
- **One probe per question** — keep each probe focused, name it descriptively
- **Preserve probe files** — they document *why* decisions were made, invaluable when the site changes
- **The fibre page working ≠ the wireless page working** — each page is a separate investigation
- **Wait time matters** — JS-heavy sites need tuning; too short = empty DOM, too long = slow pipeline