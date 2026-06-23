# Australian ISP Plan Scraper — Project Description and Technical Summary

## 1. Executive Summary

This project is a Python-based data collection and analysis platform for Australian internet service provider plans. It combines provider-specific web scrapers, a generic ISP crawler, Flask dashboards and REST APIs, JSON/CSV persistence, optional MySQL storage, Google Sheets synchronization, competitive price benchmarking, change alerts, and an ROI/value calculator.

The system is designed to collect plan information such as provider, network type, plan name, download and upload speed, monthly price, promotional price, promotion period, contract terms, typical evening speeds, and the source URL. It supports both static websites and JavaScript-heavy sites through a mixture of `requests`, BeautifulSoup, Playwright, and browser stealth utilities.

There are two main scraping approaches:

1. **Provider-specific scraping** — modules in `providers/` contain selectors and parsing rules tailored to known ISP websites.
2. **Generic ISP crawling** — the `isp/` package discovers likely plan pages, analyzes them, extracts possible plans through several strategies, validates the results, and falls back to provider-specific scrapers when they are likely to produce better data.

The primary application is `app.py`, which serves the main dashboard, scraping endpoints, the generic crawler UI, Google Sheets integration, reports, downloads, screenshots, benchmark data, alerts, and ROI analysis.

The canonical combined data snapshot is:

```text
output/all_plans.json
output/all_plans.csv
```

At the time this document was generated, the saved snapshot reported:

- Snapshot timestamp: `2026-06-16_21-50-24`
- Snapshot source: `isp_crawler_latest_files`
- Saved provider runs: 32
- Total plans: 391

The snapshot includes providers beyond the main `config.py` registry because the generic crawler can retain saved runs for additional providers.

---

## 2. Project Goals

The project addresses several related business and engineering needs:

- Collect current broadband and telecommunications plan details from many provider websites.
- Normalize different website formats into a common plan schema.
- Support sites rendered dynamically by JavaScript.
- Preserve provider-specific knowledge for difficult or unusual websites.
- Discover plan pages automatically when a dedicated scraper is unavailable.
- Save individual provider exports and a combined market snapshot.
- Expose saved data through dashboards and REST APIs.
- Compare Occom pricing with competitors by speed tier.
- Detect price changes, new plans, removed plans, and competitor undercutting.
- Calculate plan value using speed-per-dollar and annual-cost metrics.
- Synchronize eligible NBN prices into a structured Google Sheet.
- Retain screenshots, logs, page analyses, and historical crawl results for troubleshooting.

---

## 3. Technology Stack

### Backend and application framework

- Python 3
- Flask
- Flask-CORS
- Flask-Limiter is listed as a dependency, although the current visible API code does not configure a limiter.

### Web scraping

- Playwright for browser rendering and interaction
- `playwright-stealth` for anti-detection behavior
- `requests` for direct HTTP fetching
- BeautifulSoup and `lxml` for HTML parsing
- Regex parsing for prices, speeds, promotions, and plan text

### Data and persistence

- JSON
- CSV
- Optional MySQL through `mysql-connector-python`
- Local generated HTML dashboards and reports

### External integration

- Google OAuth 2.0
- Google Sheets API

### Browser debugging and Linux support

- Visible Chromium debugging on Windows and macOS
- CDP-connected persistent Chromium sessions
- Optional Xvfb/`pyvirtualdisplay` support on headless Linux servers
- Automatic screenshots during page navigation

---

## 4. High-Level Architecture

```text
User / Browser / API Client
            |
            v
       Flask app.py
       /           \
      v             v
Provider APIs    /isp Blueprint
      |             |
      v             v
scraper_service  Generic ISPCrawler
      |             |
      v             +--> URL discovery
providers/*.py      +--> Page detection
      |             +--> Multi-strategy extraction
      |             +--> Validation/deduplication
      +-------------+--> Provider-specific fallback
                            |
                            v
                  JSON / CSV / screenshots / logs
                            |
              +-------------+----------------+
              v             v                v
         Public APIs    Benchmarking     Google Sheets
                       Alerts and ROI       Sync
```

The application uses local files as its primary operational data store. MySQL support exists, but it is mainly used by the older CLI pipeline in `main.py`; the Flask dashboards and APIs primarily read from JSON files.

---

## 5. Main Entry Points

### `app.py`

This is the main development application and the most complete runtime entry point.

It:

- Creates the Flask application.
- Enables CORS.
- Registers the `/isp` crawler blueprint.
- Serves the main dashboard.
- Runs individual or all configured provider scrapers.
- Reports live scraping progress.
- Serves saved JSON and CSV files.
- Serves screenshots.
- Exposes the combined plan snapshot.
- Provides Google OAuth and Google Sheets synchronization.
- Runs and serves benchmark, alert, and ROI reports.

Run it with:

```powershell
python app.py
```

Default address:

```text
http://localhost:5000
```

The app starts with Flask debug mode enabled and binds to `0.0.0.0`.

### `app_api.py`

This is a separate API-oriented Flask application. It provides:

- Standardized response envelopes.
- A public filterable plans endpoint.
- API-key-protected complete and provider-specific plan endpoints.
- A small five-minute in-memory response cache.
- API documentation and health endpoints.

It is not mounted inside `app.py`; it is an alternative server process and also defaults to port 5000. Therefore, `app.py` and `app_api.py` should not normally be run on the same port at the same time.

### `main.py`

This is an older CLI-style orchestration pipeline. It:

1. Runs a hard-coded subset of provider scrapers.
2. Uses a rendered HTML fallback if no provider scraper returns data.
3. Cleans and validates plans.
4. Attempts MySQL persistence.
5. Saves JSON output.
6. Generates benchmark reports.
7. Runs alerts.
8. Generates the ROI page.

This pipeline does not use the complete current provider registry and should be treated as a legacy or specialized batch entry point rather than the authoritative “scrape all” implementation.

### `python -m isp.main_crawler`

This starts the generic crawler from the command line:

```powershell
python -m isp.main_crawler https://www.telstra.com.au/internet --name Telstra
```

Options include crawl depth, requested network types, and maximum URLs.

---

## 6. Main Web Interfaces

| URL | Purpose |
| --- | --- |
| `/` | Main provider scraper dashboard |
| `/isp` | Generic ISP Mini Crawler dashboard |
| `/isp/health` | Historical crawler health report |
| `/sheets` | Google Sheets connection and synchronization page |
| `/benchmark` | Generated competitive benchmark dashboard |
| `/roi` | Generated speed/price ROI calculator |

The main dashboard supports provider selection, browser visibility options, progress polling, screenshots, saved data, and file downloads.

The ISP crawler dashboard supports a user-supplied URL, provider name, requested networks, crawl depth, asynchronous progress, saved run history, result comparison, health reporting, JSON/CSV access, and deletion of saved crawler runs.

---

## 7. Provider-Specific Scraping System

### Provider registry

`config.py` defines 25 provider entries:

1. Telstra
2. Optus
3. Aussie Broadband
4. Superloop
5. Occom
6. TPG
7. Exetel
8. Leaptel
9. iiNet
10. Swoop
11. iPrimus
12. Dodo
13. Kogan
14. More
15. Tangerine
16. MATE
17. Spintel
18. Origin Energy
19. Airtel
20. Alpha
21. City7Net
22. Epsinet
23. IQNet
24. New Aus Fiber
25. VOCPhone

All current registry entries are marked as enabled. Aussie Broadband is additionally marked as blocked for live access because of Cloudflare Turnstile, although its scraper can provide a maintained static catalogue.

`isp/routes.py` also contains a crawl URL for Activ8me, but Activ8me is not currently present in `config.py`. This means it can participate in the generic crawler’s URL registry but is not included in the main application’s `get_provider_list()` or provider-specific `/api/scrape/all` loop.

### Module convention

The shared service dynamically imports:

```text
providers.<provider_key>
```

It then looks for:

```python
scrape_<provider_key>_plans()
```

If that function does not exist, it falls back to:

```python
scrape_via_playwright()
```

Scrapers return either:

- A flat list of plan dictionaries; or
- A dictionary of page/network keys mapped to plan lists.

The service understands both shapes and writes per-page plus combined output where necessary.

### Scraping techniques

Provider modules use different techniques depending on the target website:

- Static HTML requests and BeautifulSoup parsing
- Rendered Playwright page parsing
- Plan-card selector extraction
- Whole-page visible-text parsing
- Embedded JSON or JSON-LD parsing
- Tab and modal interaction
- Multiple product-page traversal
- Static catalogues for blocked or unreliable sites
- Provider-specific price, promotion, speed, and contract parsing

### Provider output

Provider-specific exports are written under:

```text
output/scrape_isp_<provider>/json/
output/scrape_isp_<provider>/csv/
```

Examples:

```text
output/scrape_isp_telstra/json/telstra_all_plans.json
output/scrape_isp_telstra/csv/telstra_all_plans.csv
```

Multi-page providers can also produce files such as:

```text
<provider>_<network-or-page>_plans.json
<provider>_<network-or-page>_plans.csv
```

### Legacy and duplicate provider files

The provider folder includes historical or alternate implementations:

- `kogan1.py`
- `leaptel_old.py`
- `swoop1.py`
- `telll1.py`

The active dynamically imported modules use the canonical filenames such as `kogan.py`, `leaptel.py`, `swoop.py`, and `telstra.py`. The alternate files should be considered development history unless explicitly imported elsewhere.

---

## 8. Generic ISP Mini Crawler

The `isp/` package is a reusable crawler intended for providers without a dedicated scraper and for discovery/debugging work.

### Pipeline

The generic crawler performs the following sequence:

1. Accepts a base URL, optional provider name, network types, maximum depth, and maximum URL count.
2. Infers a provider name from the domain if one is not supplied.
3. Checks whether the domain maps to a known provider-specific scraper.
4. For known providers, tries the dedicated scraper first.
5. If needed, launches a stealth Playwright browser.
6. Discovers and ranks internal links likely to contain plan information.
7. Ensures the original submitted URL is also analyzed.
8. Renders candidate pages.
9. Scores pages for plan likelihood.
10. Extracts plan records using selector, JSON, and regex strategies.
11. Deduplicates plans across pages.
12. Validates records.
13. Re-evaluates provider-specific fallback data when it appears richer or more complete.
14. Saves timestamped and latest output files.
15. Rebuilds or contributes to the combined all-plans snapshot.

### URL discovery

`isp/url_discovery.py`:

- Follows internal links only.
- Normalizes URLs and removes fragments.
- Excludes assets and unrelated sections.
- Scores URLs using terms such as `nbn`, `plans`, `broadband`, `internet`, `opticomm`, `redtrain`, `supa`, `fibre`, `5g`, `fixed-wireless`, `satellite`, `pricing`, and business internet terms.
- Limits crawl depth and total visited URLs.

### Page detection

`isp/plan_detector.py` produces a `PageAnalysis` containing:

- URL and page title
- Plan detection boolean
- Confidence score
- Detected network types
- Candidate card selector and card count
- Candidate name, price, and speed selectors
- Price and speed signal counts
- Body text sample
- Error details

A page is considered a likely plan page when its confidence reaches the configured threshold used by the detector.

### Extraction strategies

`isp/scraper_engine.py` attempts:

1. **Selector extraction** from repeated plan cards.
2. **Embedded JSON extraction** from script content containing plan or product arrays.
3. **Regex text extraction** from rendered page text.

If selector extraction returns weak rows, the engine tries the fallback strategies before deciding whether to keep the selector result.

### Validation

`isp/validator.py` validates:

- Plan name presence and length
- Numeric and reasonable price
- Promotional price consistency
- Download speed availability or inference
- Recognized network type

The crawler stores invalid records separately instead of silently losing all diagnostic context.

### Generic crawler outputs

Files are saved in:

```text
output/isp_crawler/
```

Typical files:

```text
<provider>_<timestamp>.json
<provider>_<timestamp>.csv
<provider>_latest.json
```

The full JSON contains crawl metadata, discovered URLs, page analyses, valid plans, invalid plans, network types, duration, and errors.

---

## 9. Standard Plan Data Model

The central normalized schema contains these fields:

| Field | Description |
| --- | --- |
| `provider` | Provider display name or key |
| `network_type` | NBN, Opticomm, fibre, fixed wireless, mobile, 5G, satellite, and similar |
| `plan_name` | Provider’s plan name |
| `download_speed` | Download speed in Mbps |
| `upload_speed` | Upload speed in Mbps |
| `price` | Standard monthly price in AUD |
| `promo_price` | Promotional monthly price |
| `promo_period` | Promotion duration or conditions |
| `contract` | Contract term or contract description |
| `typical_evening_dl` | Typical evening download speed |
| `typical_evening_ul` | Typical evening upload speed |
| `source_url` | Page from which the plan was obtained |

Some older code and database functions also use:

- `provider_id`
- `speed`
- `speed_label`
- `monthly_price`
- `contract_term`
- `last_checked`

The validation and database layers contain compatibility logic for several of these older names.

---

## 10. Combined Snapshot and Current Saved Data

The canonical API-facing snapshot is `output/all_plans.json`.

Its top-level structure is:

```json
{
  "scraped_at": "2026-06-16_21-50-24",
  "source": "isp_crawler_latest_files",
  "total_providers": 32,
  "total_plans": 391,
  "providers": [],
  "plans": []
}
```

The `providers` array contains metadata such as provider name, base URL, latest filename, plan count, and run timestamp. The `plans` array contains normalized plan rows.

Current saved plan counts by provider label are:

| Provider label | Plans |
| --- | ---: |
| Telstra | 46 |
| Airtel | 37 |
| Occom | 31 |
| Superloop | 28 |
| More | 26 |
| IQNet | 25 |
| Aussie Broadband | 25 |
| Leaptel | 16 |
| Alpha | 14 |
| iprimus | 13 |
| swoop | 12 |
| Origin | 9 |
| activ8me | 9 |
| Unitiinternet | 9 |
| tangerine | 9 |
| iinet | 9 |
| VOCPhone | 8 |
| dodo | 8 |
| kogan | 7 |
| mate | 7 |
| Optus | 5 |
| City7Net | 4 |
| Blitznet | 4 |
| Zennet | 4 |
| Wavezone | 4 |
| Teletech | 4 |
| New Aus Fiber | 4 |
| Epsinet | 4 |
| spintel | 3 |
| Tpg | 3 |
| Clevernet | 2 |
| exetel | 2 |

Provider capitalization is not fully normalized in the saved data. For example, `Telstra`, `iprimus`, `Tpg`, and `exetel` use different casing styles. This matters for exact-match filters, reports, and Google Sheets aliases.

The combined snapshot may be created in more than one way:

- A complete `/isp` scrape-all run writes a batch snapshot with source `isp_crawler_scrape_all`.
- The crawler can rebuild the snapshot from available `*_latest.json` files, producing a source such as `isp_crawler_latest_files`.

This explains why the number of saved providers can exceed the current configured provider count.

---

## 11. REST APIs

### Main application APIs in `app.py`

#### Status and capability

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/status` | Application and provider-data status |
| GET | `/api/capabilities` | Visible browser, platform, display, and Xvfb capability |
| GET | `/api/providers` | Configured provider list and saved-data flags |
| GET | `/api/scrape/progress` | Current in-memory provider scrape progress |

#### Scraping

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/api/scrape/<provider>` | Run one provider-specific scraper |
| POST | `/api/scrape/all` | Sequentially scrape every enabled `config.py` provider |

The optional JSON body accepts:

```json
{
  "visible_browser": false,
  "slow_mo": 0
}
```

`slow_mo` is clamped to a maximum of 3000 milliseconds.

#### Data and downloads

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/plans/all` | Read the canonical combined snapshot |
| GET | `/api/results` | Read saved provider-specific combined files |
| GET | `/api/results/<provider>` | Read all saved files for one provider |
| GET | `/api/download/<provider>/<filename>.json` | Download provider JSON |
| GET | `/api/download/<provider>/<filename>.csv` | Download provider CSV |
| GET | `/screenshots/<path>` | Serve saved screenshots |

#### Benchmark, alerts, and ROI

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/benchmark` | Read the latest benchmark report |
| POST | `/api/benchmark/run` | Generate benchmark JSON, CSV, and HTML |
| GET | `/api/benchmark/advantages` | Speed tiers where Occom is cheapest |
| GET | `/api/benchmark/gaps` | Speed tiers where a competitor undercuts Occom |
| GET | `/api/alerts` | Read the latest alert run |
| POST | `/api/alerts/run` | Compare current plans with the prior snapshot |
| GET | `/api/roi` | Calculate ROI data |
| POST | `/api/roi/generate` | Generate the ROI HTML page |

#### Google Sheets

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/api/sheets/status` | OAuth, token, sheet, and snapshot status |
| GET | `/api/google/auth/start` | Start Google OAuth |
| GET | `/oauth2callback` | Complete Google OAuth |
| POST | `/api/sheets/sync` | Dry-run or execute sheet synchronization |

### Generic crawler APIs in `isp/routes.py`

| Method | Endpoint | Purpose |
| --- | --- | --- |
| POST | `/isp/api/crawl` | Start one background crawl |
| GET | `/isp/api/status` | Poll single-crawl progress and result |
| POST | `/isp/api/crawl-all` | Start a sequential crawl of all enabled targets |
| GET | `/isp/api/crawl-all/status` | Poll batch progress |
| GET | `/isp/api/all-plans` | Read the combined crawler snapshot |
| GET | `/isp/api/results` | List saved crawler results |
| GET | `/isp/api/results/<filename>` | Read a saved result |
| DELETE | `/isp/api/results/<filename>` | Delete a saved result |
| GET | `/isp/api/results/<filename>/compare` | Compare a run with the previous run |
| GET | `/isp/api/health` | Return aggregated historical health information |

### Alternative API in `app_api.py`

| Method | Endpoint | Access |
| --- | --- | --- |
| GET | `/api/status` | Public |
| GET | `/api/providers` | Public |
| GET | `/api/docs` | Public |
| GET | `/api/plans` | Public, filterable and cached |
| GET | `/api/plans/all` | Requires `X-API-Key` |
| GET | `/api/plans/<provider>` | Requires `X-API-Key` |
| GET | `/health` | Public |

Filters include provider, network type, minimum/maximum speed, minimum/maximum price, sorting field, and order.

---

## 12. Progress, Logging, Screenshots, and Debugging

### Progress

`utils/progress.py` stores process-local progress in a thread-safe dictionary. It records:

- Current provider and URL
- Status and message
- Plans found
- Current screenshot
- Provider totals
- Errors
- Recent events
- Start, update, and finish timestamps

Only the most recent 80 provider-scrape events are retained.

The generic crawler maintains separate in-memory single-crawl and batch-crawl states in `isp/routes.py`.

### Logging

`utils/logger.py` writes structured log entries and human-readable logs in the output area. Provider, status, message, timestamp, and optional data can be recorded.

### Screenshots

`utils/screenshots.py` saves screenshots under:

```text
output/screenshots/<provider>/
```

`utils/stealth.py` attaches a page-load event that captures screenshots as navigation occurs and reports them through the progress state.

### Investigation scripts

The repository includes many:

- `investigate_*.py`
- `probe_*.py`
- `debug_*.py`
- `check_*.py`
- `analyze_*.py`
- `inject_*.py`

These are exploratory tools used to inspect page structure, test selectors, discover APIs, compare render behavior, and debug individual providers. They are useful engineering evidence but are not part of the normal production runtime.

---

## 13. Browser and Anti-Bot Handling

The shared stealth layer:

- Uses a modern Chromium user agent.
- Sets Australian locale and Sydney timezone.
- Adds browser-like HTTP headers.
- Applies `playwright-stealth`.
- Disables the obvious `AutomationControlled` browser feature.
- Supports headless and visible browser modes.
- Can leave visible debug browsers open for manual inspection.
- Uses a persistent Chromium session connected through the Chrome DevTools Protocol on desktop platforms.
- Can launch a visible browser inside Xvfb on Linux.

This improves access reliability but does not guarantee bypass of anti-bot platforms. Aussie Broadband is explicitly marked as affected by Cloudflare Turnstile.

---

## 14. Validation and Deduplication

There are two validation layers:

### Shared/legacy validator

`utils/validator.py` requires:

- Non-empty plan name
- Numeric non-negative price
- Numeric non-negative speed

It also normalizes currency strings and speed strings.

### Generic crawler validator

`isp/validator.py` is richer and checks:

- Plan-name quality
- Price validity and reasonableness
- Promo/regular-price relationships
- Speed inference
- Network type recognition

Deduplication is performed in several places:

- Individual provider modules
- Generic extraction strategies
- Global crawler result processing
- Benchmark data loading

The generic crawler’s global key uses plan name, price, download speed, and network type. Benchmark loading uses provider, plan name, speed, and network type.

---

## 15. Competitive Benchmarking

`utils/benchmark.py` is focused on Occom’s competitive position.

It groups plans into these download-speed tiers:

| Tier | Speed range |
| --- | --- |
| Basic | 0–15 Mbps |
| Standard | 16–30 Mbps |
| Boost | 31–60 Mbps |
| Fast | 61–150 Mbps |
| Superfast | 151–300 Mbps |
| Ultrafast | 301–600 Mbps |
| Hyper | 601–1000 Mbps |
| Mega | 1001+ Mbps |

For each tier it calculates:

- Cheapest effective price
- Regular and promotional prices
- First-year annual cost
- Mbps-per-dollar value score
- Most expensive provider
- Best-value provider
- Occom savings when Occom is cheapest
- Occom pricing gap when a competitor is cheaper

Outputs include:

```text
output/benchmark_report.json
output/benchmark_report.csv
output/benchmark_dashboard.html
```

Benchmark loading prefers all per-provider `*_all_plans.json` files. It falls back to `output/all_plans.json` only when no per-provider combined files are found. Therefore, benchmark results can be based on a different effective source set than `/api/plans/all`.

---

## 16. Alerts

`utils/alerts.py` compares current plans against:

```text
output/plans_snapshot.json
```

It detects:

- Regular-price changes
- Promotional-price changes
- New plans
- Removed plans
- Speed tiers where a competitor undercuts Occom

Alert severities are high, medium, or low. Alert history is appended to:

```text
output/alerts.json
```

The last 100 alert runs are retained. Each alert run also updates the saved comparison snapshot for the next execution.

---

## 17. ROI and Value Calculator

`roi_calculator.py` computes:

- Effective price
- Regular price
- Download speed
- Mbps per dollar using effective price
- Mbps per dollar using regular price
- First-year annual cost
- Speed tier
- Best overall plan
- Best Occom plan
- Average and maximum ROI

It generates:

```text
output/roi_calculator.html
```

The HTML page provides interactive filtering and a ranked table of plans.

---

## 18. Google Sheets Synchronization

`google_sheets_sync.py` synchronizes selected broadband pricing into a preformatted Google Sheet.

### Authentication

It uses OAuth 2.0 with the Sheets scope:

```text
https://www.googleapis.com/auth/spreadsheets
```

Credentials are stored locally at:

```text
instance/google_token.json
```

### Configuration

Expected environment variables:

```text
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REDIRECT_URI
GOOGLE_SHEET_ID
GOOGLE_SHEET_TAB
FLASK_SECRET_KEY
```

### Eligibility and matching

The synchronization logic:

- Excludes mobile, SIM, travel, prepaid, postpaid, roaming, and phone-plan rows.
- Requires NBN-related plan data.
- Normalizes provider names through an alias map.
- Matches plans to speed tiers using explicit speeds, typical evening speeds, and plan-name parsing.
- Selects promotional price when available, otherwise regular price.
- Uses the lowest matching price per provider and speed tier.
- Detects missing provider headers and unmatched providers.
- Supports a dry-run mode before writing.

The target sheet is expected to contain recognized provider columns and fields such as speed, minimum price, and maximum price.

---

## 19. Optional MySQL Database

`database.sql` creates:

- `plans_current`
- `providers`
- `scrape_logs`
- `v_plan_summary`

The `plans_current` table uses a unique key on:

```text
provider_id + plan_name + speed_label
```

The database helper supports connection creation, table creation, individual upsert operations, and batch insertion.

Default development configuration:

```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "isp_plans",
    "port": 3306
}
```

The database schema’s seeded provider table contains only the original four providers. It does not represent the complete current `config.py` registry.

The main Flask application does not require MySQL for its normal JSON/CSV workflow.

---

## 20. Installation and Setup

From the project root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install
```

Create a local `.env` using `.env.example` as a guide. Do not commit real OAuth credentials, API keys, Flask secrets, or refresh tokens.

Optional MySQL setup:

```sql
CREATE DATABASE isp_plans;
```

Then import:

```powershell
mysql -u root isp_plans < database.sql
```

For Linux visible-browser debugging, install Xvfb and ensure the Python virtual-display dependency is present.

---

## 21. Common Operating Workflows

### Run the main dashboard

```powershell
python app.py
```

### Scrape one provider through the API

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:5000/api/scrape/telstra `
  -ContentType application/json `
  -Body '{"visible_browser":false,"slow_mo":0}'
```

### Read all saved plans

```powershell
Invoke-RestMethod http://localhost:5000/api/plans/all
```

### Start a generic crawler run

Open:

```text
http://localhost:5000/isp
```

Or run:

```powershell
python -m isp.main_crawler https://example-isp.com.au/internet --name ExampleISP --depth 2
```

### Generate market analysis

Use:

```text
POST /api/benchmark/run
POST /api/alerts/run
POST /api/roi/generate
```

### Synchronize Google Sheets

1. Open `/sheets`.
2. Connect the Google account.
3. Run a dry-run synchronization.
4. Review missing headers, provider matches, and warnings.
5. Run the live synchronization.

---

## 22. Repository Organization

| Path | Responsibility |
| --- | --- |
| `app.py` | Main Flask dashboard and API |
| `app_api.py` | Alternative API-key-oriented Flask server |
| `main.py` | Legacy CLI pipeline |
| `config.py` | Provider and runtime configuration |
| `scraper_service.py` | Shared provider execution and file persistence |
| `google_sheets_sync.py` | Google OAuth and Sheets price matrix synchronization |
| `providers/` | Dedicated provider scrapers |
| `isp/` | Generic crawler, routes, validation, and crawler UI |
| `utils/` | Shared browser, logging, progress, validation, DB, benchmark, alert, and parsing utilities |
| `scrapers/` | Older/shared rendered-page scraper implementation |
| `templates/` | Main dashboard and Sheets templates |
| `output/` | Generated plans, reports, screenshots, logs, HTML, and crawl history |
| `instance/` | Local OAuth token storage |
| `database.sql` | Optional MySQL schema |
| `requirements.txt` | Python dependencies |
| `.env.example` | Environment variable template |

Excluding `venv/`, generated `output/`, and bytecode directories, the repository currently contains approximately 188 source/documentation files, including roughly:

- 150 Python files
- 19 Markdown documents
- 8 HTML files
- 6 JSON configuration/reference files
- 1 SQL schema

The large number of Python files is partly due to provider investigations, probes, targeted tests, and historical scraper variants.

---

## 23. Testing and Verification Approach

Testing is primarily script-based rather than a unified automated test suite.

The repository contains:

- Provider-specific `test_*.py` files
- Rendering and stealth tests
- Total-cost and parser tests
- The generic crawler’s `isp/test_crawler.py`
- Verification scripts such as `verify_kogan.py`
- Manual check scripts
- Historical screenshots and downloaded HTML
- Health and previous-run comparison features in the crawler UI

`isp/test_crawler.py` includes end-to-end scenarios for several known providers and can produce a test report.

There is no evident centralized `pytest` configuration or continuous-integration workflow in the reviewed tree. Many root-level tests appear designed to be run individually during scraper development.

---

## 24. Current Strengths

- Broad provider coverage.
- Good separation between dedicated scrapers and generic crawling.
- Multiple extraction strategies for resilience.
- Browser stealth and screenshot capture are centralized.
- Both headless automation and visible debugging are supported.
- Output is normalized into a useful market-comparison schema.
- Every provider can retain independent JSON and CSV exports.
- Combined snapshot supports simple downstream API consumption.
- Generic crawl history provides useful operational evidence.
- Benchmarking, alerts, ROI, and Sheets synchronization add practical business value beyond raw scraping.
- Failures in one provider generally do not stop provider-specific scrape-all processing.
- The generic crawler preserves page analyses and invalid records for diagnostics.

---

## 25. Current Limitations and Maintenance Risks

### Registry drift

Provider definitions are duplicated across:

- `config.py`
- `isp/routes.py`
- Generic crawler domain mappings
- Google Sheets provider headers and aliases
- Database seed data
- Older `main.py` hard-coded imports

These lists are not fully synchronized. Activ8me is a clear example: it has a scraper and generic crawl URL but no `config.py` entry.

### Multiple meanings of “all plans”

Different subsystems load data differently:

- `/api/plans/all` reads `output/all_plans.json`.
- Benchmarking prefers per-provider `*_all_plans.json` files.
- Generic crawler batch mode creates a new combined snapshot.
- The current snapshot can be rebuilt from saved latest crawler files.

Reports and APIs may therefore operate on different plan sets unless the data refresh process is standardized.

### In-memory job state

Scrape progress and crawler job state are process-local:

- State is lost on restart.
- Multiple Flask workers would not share state.
- Only one crawler job is allowed at a time within one process.
- Background work uses daemon threads rather than a durable task queue.

### Sequential scraping

Both main scrape-all and generic crawl-all run providers sequentially. This is simple and reduces browser contention, but full market refreshes may take a long time.

### Development server defaults

Both Flask entry points run with:

```python
debug=True
host="0.0.0.0"
```

This is appropriate only for trusted development environments.

### API security defaults

`app_api.py` contains a default fallback API key. `app.py` enables unrestricted CORS. Authentication, rate limiting, HTTPS termination, and deployment-server configuration need strengthening before internet exposure.

### Data normalization

Provider casing, aliases, and network labels vary in saved output. Exact string filters can miss semantically identical providers. A canonical provider key should be stored alongside the display label.

### Legacy code and duplicate modules

Historical provider modules and old orchestration paths increase cognitive load. Their intended status is not always encoded in filenames or documentation.

### Encoding artifacts

Some source comments and generated messages contain mojibake characters caused by prior encoding mismatches. Logic is generally unaffected, but source readability and generated text quality suffer.

### Database schema drift

The SQL seed data covers only four providers, while current configuration covers many more. Field names also reflect an older model.

### Test organization

The project has many useful targeted scripts but no single repeatable regression command covering all parsers, APIs, and output contracts.

### Scraper fragility

Like all website scrapers, provider modules depend on external page structures and can break when:

- Selectors change
- Pages add address qualification
- Content moves behind APIs
- Anti-bot systems change
- Product cards are redesigned
- Promotions use new wording
- Region, cookie, or session state alters content

The screenshots, health reports, saved HTML, and investigation scripts help diagnose these failures but do not remove the maintenance requirement.

---

## 26. Recommended Technical Priorities

1. Create one canonical provider registry containing key, display name, URLs, enabled state, aliases, and scraper capability.
2. Make all dashboards, crawler batches, Sheets aliases, reports, and database seeds derive from that registry.
3. Define one authoritative refresh workflow for `output/all_plans.json`.
4. Add canonical `provider_key` and `network_key` fields while retaining display labels.
5. Move long-running scraping into a durable job queue if multi-user or production use is required.
6. Add structured run IDs and persist job status to a database or JSON state file.
7. Add a unified automated test command with fixture HTML for provider parsers.
8. Add API contract tests for all plan endpoints.
9. Remove or archive obsolete provider variants after confirming they are unused.
10. Replace development Flask serving with a production WSGI server for deployment.
11. Remove default secrets and require environment-supplied secure values.
12. Restrict CORS and add configured rate limiting.
13. Normalize source encoding to UTF-8.
14. Add snapshot provenance so every benchmark, alert, ROI report, and Sheets sync records the exact input snapshot.
15. Add freshness checks and per-provider failure thresholds before publishing a combined market snapshot.

---

## 27. Overall Assessment

This repository has evolved from a collection of provider experiments into a capable ISP market-data platform. Its strongest feature is the combination of handcrafted provider knowledge with a generic discovery-and-extraction crawler. The project does more than scrape: it maintains evidence, produces standardized exports, exposes APIs, compares competitors, tracks changes, calculates value, and updates a business-facing spreadsheet.

The project is highly useful in its present local/development form. The main work needed for a more robust production deployment is consolidation: one provider registry, one canonical data-refresh contract, durable job state, stronger security defaults, systematic regression tests, and cleanup of historical code paths.

In practical terms, the current system can:

- Scrape a large set of Australian providers.
- Discover and evaluate unfamiliar ISP sites.
- Produce reusable plan datasets.
- Show live progress and screenshots.
- Retain crawl history and compare runs.
- Benchmark Occom against competitors.
- Generate market-change alerts.
- Rank plans by speed-per-dollar value.
- Synchronize eligible NBN pricing to Google Sheets.

That makes it both a scraping framework and a lightweight competitive intelligence application.
