# ISP Mini Crawler

The `isp` folder contains a Playwright-powered crawler for discovering and scraping Australian ISP broadband plan pages. It is designed to work from a single provider URL, discover likely plan pages, analyse rendered HTML for broadband plan signals, extract normalised plan data, validate the results, and save JSON/CSV output for later review.

The package can be used from the command line, imported from Python, or mounted into the main Flask app through the `isp` blueprint at `/isp`.

## Current Folder Summary

This folder is a self-contained crawler module inside `C:\xampp\htdocs\scrape`. It includes:

- Generic crawler pipeline modules: URL discovery, page analysis, extraction, validation, orchestration.
- Flask routes and a browser UI for starting crawls and viewing saved results.
- A test runner with known ISP scenarios.
- Documentation for quick start, examples, implementation notes, before/after comparison, and verification.
- A local `.git` directory, so this folder appears to be versioned separately from the parent workspace.
- Generated Python bytecode in `__pycache__`, which is runtime output and not part of the source design.

## Main Capabilities

- Discover internal ISP URLs using weighted broadband and network keywords.
- Analyse rendered pages with Playwright so JavaScript navigation and plan cards are visible.
- Detect network types such as NBN, Opticomm, RedTrain, Supa, 5G, fixed wireless, fibre, and satellite.
- Score pages for plan likelihood using price signals, speed signals, network mentions, card selectors, and sub-selectors.
- Extract plans using selector-based parsing, embedded JSON parsing, and regex text parsing.
- Prefer existing provider-specific scrapers for known providers when those results are richer than the generic crawler.
- Validate plan records and split valid/invalid data.
- Deduplicate results across pages.
- Save timestamped JSON, latest JSON, and CSV exports.
- Provide a web UI with progress events, saved scrape history, JSON/CSV download, delete, and previous-run comparison.

## File Inventory

| Path | Purpose |
| --- | --- |
| `__init__.py` | Package marker and brief usage docstring. |
| `main_crawler.py` | Main orchestrator. Runs discovery, analysis, extraction, validation, provider fallback, deduplication, and file persistence. Also exposes the CLI entry point. |
| `url_discovery.py` | Crawls internal rendered links and ranks candidate plan URLs with keyword scoring. |
| `plan_detector.py` | Analyses rendered pages and returns a `PageAnalysis` confidence report with network types and selector hints. |
| `scraper_engine.py` | Extracts plan data using selector, JSON, and regex strategies. |
| `validator.py` | Validates plan schema fields and provides comparison logging helpers for tests. |
| `routes.py` | Flask blueprint mounted at `/isp`; provides UI, crawl, status, saved result, compare, and delete endpoints. |
| `test_crawler.py` | End-to-end test runner for Telstra, Superloop, Swoop, Occom, Exetel, and Leaptel scenarios. |
| `templates/crawler_ui.html` | Active ISP Mini Crawler dashboard used by `/isp/`. |
| `templates/crawler_ui_base.html` | Older/larger dashboard template retained in the folder; not currently rendered by `routes.py`. |
| `QUICKSTART.md` | Short setup and first-run guide. |
| `EXAMPLES.md` | Usage examples and code snippets. |
| `IMPLEMENTATION_SUMMARY.md` | Architecture and design notes. |
| `BEFORE_AFTER_COMPARISON.md` | Notes comparing previous and current crawler/UI behavior. |
| `VERIFICATION_CHECKLIST.md` | Manual verification checklist. |
| `README_OLD.md` | Older README snapshot. |
| `README_CHANGES.md` | Prior README change summary. |

Approximate source sizes at the time of this review:

- `main_crawler.py`: 686 lines
- `routes.py`: 499 lines
- `scraper_engine.py`: 593 lines
- `plan_detector.py`: 351 lines
- `url_discovery.py`: 324 lines
- `validator.py`: 271 lines
- `test_crawler.py`: 377 lines
- `templates/crawler_ui.html`: 1052 lines

## How The Pipeline Works

1. `ISPCrawler` receives a base URL, optional provider name, network list, depth, URL limit, and optional progress callback.
2. For known provider domains, it first tries the existing provider-specific scraper through `scraper_service.scrape_provider`.
3. If provider-specific output is not enough, it launches Playwright using the shared stealth utilities from `utils.stealth`.
4. `URLDiscovery` crawls internal links up to the configured depth and ranks candidate pages.
5. `PlanDetector` opens each candidate page, waits for rendering, and computes whether the page likely contains broadband plans.
6. `ScraperEngine` extracts plans from confirmed pages.
7. The crawler deduplicates plans across pages.
8. `ISPValidator` validates each plan.
9. The provider fallback is checked again and may replace generic results if it finds more plans, missing requested networks, or richer metadata.
10. Final results are normalised into the standard output fields and saved to `output/isp_crawler`.

## URL Discovery

`url_discovery.py` starts from the base URL and follows internal links. It normalises URLs, strips fragments, excludes non-plan pages, and scores each URL with `PLAN_KEYWORDS`.

Strong signals include:

- Network terms: `nbn`, `opticomm`, `redtrain`, `supa`, `5g`, `fixed-wireless`, `satellite`, `starlink`
- Product terms: `plans`, `broadband`, `internet`, `home-internet`, `fibre`, `fttp`
- Pricing terms: `pricing`, `price`, `compare`, `compare-plans`
- Business terms: `small-business`, `business-internet`, `business-nbn`

Excluded URLs include common non-plan sections such as blog, news, support, contact, login, terms, privacy, static assets, images, scripts, PDFs, anchors, mail links, and phone links.

## Page Detection

`plan_detector.py` returns a `PageAnalysis` object. It captures:

- URL and page title
- Whether plans were detected
- Confidence score from `0.0` to `1.0`
- Detected network types
- Best card selector and card count
- Best name, price, and speed sub-selectors
- Count of price and speed signals
- First body-text snippet and any error

Confidence is based on:

- 2 or more candidate card elements
- Multiple price signals
- Multiple speed signals
- Network type mentions
- Successful name, price, or speed sub-selector probes

A page is treated as a plan page when confidence is at least `0.35`.

## Extraction Strategies

`scraper_engine.py` tries these strategies in order:

1. Selector-based extraction
   - Uses `PageAnalysis.card_selector` and sub-selectors.
   - Best for traditional card or product tile layouts.

2. Embedded JSON extraction
   - Looks through `<script>` tags for arrays under keys such as `plans`, `products`, or `items`.
   - Maps common fields like `planName`, `monthlyCost`, `downloadSpeed`, and `networkType`.

3. Regex text parsing
   - Scans visible body text for price and speed patterns.
   - Includes a nearby-block fallback for pages where plan name, speed, and price are split across adjacent text sections.

Each extracted plan is normalised toward this shape:

```json
{
  "provider": "Telstra",
  "network_type": "NBN",
  "plan_name": "Basic NBN Home",
  "download_speed": 25,
  "upload_speed": 5,
  "price": 85.0,
  "promo_price": null,
  "promo_period": null,
  "contract": null,
  "typical_evening_dl": 25,
  "typical_evening_ul": 5,
  "source_url": "https://www.telstra.com.au/internet"
}
```

## Provider-Specific Fallback

`main_crawler.py` recognises known provider domains and maps them to existing provider scraper keys. The current known-domain list includes:

- `optus.com.au`
- `telstra.com.au`
- `superloop.com`
- `occom.com.au`
- `exetel.com.au`
- `leaptel.com.au`
- `swoop.com.au`
- `dodo.com`
- `iinet.net.au`
- `iprimus.com.au`
- `koganinternet.com.au`
- `letsbemates.com.au`
- `more.com.au`
- `originenergy.com.au`
- `spintel.net.au`
- `tangerine.com.au`
- `tangerinetelecom.com.au`
- `tpg.com.au`
- `activ8me.net.au`

When a known provider is detected, the crawler calls `scraper_service.scrape_provider(provider_key)`. Provider-specific output replaces generic output when it has no current generic result, more plans, requested networks missing from the generic result, or richer metadata such as promo price, promo period, contract, and typical evening speeds.

## Validation

`validator.py` checks:

- `plan_name` exists and is not too long.
- `price` is numeric, positive, and not unusually high.
- `promo_price` is valid and lower than regular price.
- `download_speed` is numeric where possible; it can be inferred from the plan name.
- `network_type` is known or produces a warning.

Invalid records are stored separately in the saved JSON under `invalid_plans`.

Known network types include NBN, Opticomm, RedTrain, Supa, 5G, fixed wireless, fibre/FTTP/FTTB/FTTN/FTTC, satellite, and business NBN.

## Output Location

Crawler output is saved under:

```text
C:\xampp\htdocs\scrape\output\isp_crawler
```

For each successful run, the crawler writes:

- `<provider>_<timestamp>.json`: full crawl result
- `<provider>_latest.json`: latest result for that provider
- `<provider>_<timestamp>.csv`: plan rows only, when plans exist

The test runner writes:

- `test_report.json`

## Output JSON Structure

Saved JSON files use this top-level shape:

```json
{
  "base_url": "https://www.telstra.com.au/internet",
  "provider": "Telstra",
  "started_at": "2026-06-04T07:59:00",
  "finished_at": "2026-06-04T08:00:10",
  "duration_seconds": 70.25,
  "summary": {
    "urls_visited": 42,
    "plan_pages_found": 5,
    "total_plans_scraped": 17,
    "valid_plans": 17,
    "invalid_plans": 0,
    "network_types": ["NBN", "5G"]
  },
  "discovered_urls": [],
  "page_analyses": [],
  "plans": [],
  "invalid_plans": [],
  "errors": []
}
```

CSV exports use the field order defined by `PLAN_FIELDS` in `main_crawler.py`:

```text
provider, network_type, plan_name, download_speed, upload_speed, price, promo_price, promo_period, contract, typical_evening_dl, typical_evening_ul, source_url
```

## Web UI

Start the parent Flask application from the workspace root:

```bash
cd C:\xampp\htdocs\scrape
python app.py
```

Then open:

```text
http://localhost:5000/isp
```

The active UI at `templates/crawler_ui.html` provides:

- ISP URL input
- Optional provider name
- Crawl depth selector from 1 to 3
- Fixed network request list: `nbn`, `opticomm`, `redtrain`, `supa`
- Async crawl progress polling
- Elapsed timer
- Saved scrape table
- Latest scrape auto-load
- JSON download
- CSV download
- Copy API response
- Previous-run comparison for saved results
- Saved result deletion
- Provider confidence report from `page_analyses`

## Flask API

The blueprint in `routes.py` is registered as `isp_bp` with URL prefix `/isp`.

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/isp/` | GET | Render the crawler UI. |
| `/isp/health` | GET | Render the standalone scrape health report page. |
| `/isp/api/crawl` | POST | Start a background crawl. |
| `/isp/api/status` | GET | Return current crawl state, progress events, and result summary. |
| `/isp/api/results` | GET | List timestamped saved JSON results. |
| `/isp/api/results/<filename>` | GET | Return one saved result file. |
| `/isp/api/health` | GET | Return scrape health metrics from saved runs. |
| `/isp/api/results/<filename>/compare` | GET | Compare a saved result with the previous run for the same provider. |
| `/isp/api/results/<filename>` | DELETE | Delete a saved JSON result, matching CSV, and matching latest file when applicable. |

Example crawl request:

```json
{
  "url": "https://www.telstra.com.au/internet",
  "name": "Telstra",
  "networks": ["nbn", "opticomm", "redtrain", "supa"],
  "depth": 2
}
```

The route caps `depth` at `3`. If the URL does not start with `http`, it prefixes `https://`.

## Scrape Health Report

The standalone health page at `/isp/health` calls `/isp/api/health` to summarise saved timestamped crawler runs. The report is built from JSON files in `output/isp_crawler`, so it survives Flask restarts. The main crawler dashboard links to this page through the `Scrape Health Report` button.

The health report includes:

- Overall success rate, where a run is successful when it produced at least one valid plan.
- Average crawl duration.
- Average number of valid plans per run.
- Total failed pages, based on analysed pages that did not become confirmed plan pages or recorded an analysis error.
- Total saved-run errors.
- Latest run metadata.
- Latest-vs-previous change counts across providers: new plans, removed plans, price changes, and promo changes.
- Per-provider health rows with run counts, success rate, average duration, latest valid plan count, failed pages, and latest change counts.
- Recent failed runs for quick review.

Example response shape:

```json
{
  "success": true,
  "health": {
    "total_runs": 12,
    "successful_runs": 10,
    "failed_runs": 2,
    "success_rate": 83.3,
    "average_duration_seconds": 42.8,
    "average_valid_plans": 8.5,
    "total_failed_pages": 6,
    "total_errors": 3,
    "changes_since_last_run": {
      "new_plans": 1,
      "removed_plans": 0,
      "price_changed": 2,
      "promo_changed": 1
    },
    "providers": []
  }
}
```

## Command-Line Usage

From the parent workspace root:

```bash
cd C:\xampp\htdocs\scrape
python -m isp.main_crawler https://www.telstra.com.au/internet
```

With options:

```bash
python -m isp.main_crawler https://www.superloop.com/consumer/internet ^
  --name "Superloop" ^
  --networks nbn opticomm ^
  --depth 2 ^
  --max-urls 150
```

CLI arguments:

| Argument | Default | Description |
| --- | --- | --- |
| `url` | required | Base ISP URL to crawl. |
| `--name` | inferred from domain | Human-readable provider name. |
| `--depth` | `2` | Maximum crawl depth. |
| `--networks` | `nbn opticomm redtrain supa` | Network keywords to prioritise. |
| `--max-urls` | `150` | Maximum URLs to visit. |

## Python Usage

```python
from isp.main_crawler import ISPCrawler

crawler = ISPCrawler(
    base_url="https://www.telstra.com.au/internet",
    provider_name="Telstra",
    network_types=["nbn", "opticomm"],
    max_depth=2,
    max_urls=150,
)

result = crawler.run()
print(result.valid_plans)
print(result.plans)
```

For UI progress, pass a callback:

```python
def on_progress(event):
    print(event["stage"], event["status"], event["message"])

crawler = ISPCrawler(
    base_url="https://www.example.com/internet",
    progress_callback=on_progress,
)
result = crawler.run()
```

Progress stages currently include:

- `starting`
- `discovering_urls`
- `analyzing_pages`
- `scraping_plans`
- `validating`
- `saving`
- `completed`
- `error`

## Testing

Run all crawler scenarios:

```bash
cd C:\xampp\htdocs\scrape
python -m isp.test_crawler
```

Run a quick Telstra smoke test:

```bash
python -m isp.test_crawler --quick
```

Run one provider:

```bash
python -m isp.test_crawler --provider telstra
```

Configured test scenarios:

- `telstra`
- `superloop`
- `swoop`
- `occom`
- `exetel`
- `leaptel`

The tests are live website tests. They require browser automation, network access, and current provider pages that still match the expected minimums.

## Dependencies And Integration Points

The package imports:

- `playwright.sync_api`
- Flask objects in `routes.py`
- Parent workspace utilities: `utils.logger` and `utils.stealth`
- Parent workspace provider scraper bridge: `scraper_service.scrape_provider`

This means the module should normally be run from `C:\xampp\htdocs\scrape`, not from inside `isp`, so parent imports resolve correctly.

Expected parent integration:

```python
from isp.routes import isp_bp
app.register_blueprint(isp_bp)
```

## Extending The Crawler

To add a new network type:

1. Add URL keywords to `PLAN_KEYWORDS` in `url_discovery.py`.
2. Add text signatures to `NETWORK_SIGNATURES` in `plan_detector.py`.
3. Add output validation spelling to `KNOWN_NETWORK_TYPES` in `validator.py`.
4. Add UI checkbox/request support if the active UI should expose it.
5. Add or update a test scenario in `test_crawler.py`.

To improve extraction for unusual sites:

1. Add selector candidates in `plan_detector.py`.
2. Add JSON field aliases in `scraper_engine.py`.
3. Add regex patterns or nearby-block parsing improvements in `scraper_engine.py`.
4. Add provider-specific fallback support in the parent `scraper_service` when a generic strategy is not reliable enough.

## Operational Notes

- Live crawl speed depends on page load time, JavaScript rendering, crawl depth, and URL count.
- `URLDiscovery` waits around 3 seconds after page load; page analysis waits around 5 seconds.
- Generic extraction can fail on heavily interactive address-gated pages.
- Known-provider fallback can bypass generic analysis and may produce results without `page_analyses`.
- The active UI uses Bootstrap from CDN but includes lightweight CSS fallbacks for local/offline use.
- `routes.py` stores crawl state in process memory, so status is not shared across multiple Python processes.
- Only one crawl can run at a time through the `/isp/api/crawl` route.
- Saved result filenames are restricted by `_safe_result_path` to timestamped JSON files inside `output/isp_crawler`.

## Troubleshooting

If no plans are found:

- Try a more direct plan URL.
- Increase crawl depth to `2` or `3`.
- Check `page_analyses` in the JSON output for confidence, selectors, price signals, and speed signals.
- Confirm the provider page is publicly reachable without address entry, login, or bot blocking.
- For known providers, check whether `scraper_service.scrape_provider` supports the domain.

If extracted data looks wrong:

- Inspect the saved `page_analyses` selector fields.
- Check whether the page exposes plan data in embedded JSON.
- Add selector candidates or JSON aliases.
- Tighten regex parsing for that provider layout.

If the UI does not update:

- Check `/isp/api/status`.
- Confirm no other crawl is already running.
- Restart the Flask app to clear in-memory crawl state.

If tests fail:

- Remember the tests hit live provider websites.
- Re-run a single provider to isolate the issue.
- Check provider page changes, bot blocking, timeout errors, and minimum expected plan counts.

## Related Documentation

- `QUICKSTART.md`: Fast setup and basic usage.
- `EXAMPLES.md`: Example command and Python workflows.
- `IMPLEMENTATION_SUMMARY.md`: Architecture notes and rationale.
- `BEFORE_AFTER_COMPARISON.md`: Recent behavior/UI comparison notes.
- `VERIFICATION_CHECKLIST.md`: Manual QA checklist.

## Review Summary

This folder implements a practical hybrid crawler: generic discovery and extraction for unknown ISP sites, plus known-provider fallback for better accuracy where a custom scraper already exists. The most important current behavior to understand is that saved results may come from either the generic Playwright pipeline or the provider-specific fallback. When generic analysis is skipped or replaced, `page_analyses` may be empty, and the UI handles that as a provider-specific result.
