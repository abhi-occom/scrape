# Australian ISP Plan Scraper

A Flask and Playwright based scraping system for collecting Australian ISP plan
data, validating it, saving JSON/CSV exports, and presenting the results in web
dashboards. The project supports two scraping styles:

- Provider-specific scrapers in `providers/` for known ISP sites.
- A generic ISP Mini Crawler in `isp/` that can start from a provider URL,
  discover likely plan pages, scrape plan data, validate it, and save snapshots.

The main combined dataset is written to:

```text
output/all_plans.json
output/all_plans.csv
```

The public all-plans API reads that same file:

```text
http://localhost:5000/api/plans/all
```

## Project Layout

| Path | Purpose |
| --- | --- |
| `app.py` | Main Flask application. Serves the dashboard, provider scrape APIs, benchmark APIs, ROI APIs, screenshots, and the `/isp` blueprint. |
| `app_api.py` | Separate production-style API app with public/filterable plan endpoints and API-key protected endpoints. |
| `config.py` | Provider registry, database settings, Playwright timeout settings, and retry constants. |
| `scraper_service.py` | Shared service layer for running provider modules, saving per-provider output, loading `output/all_plans.json`, and listing providers. |
| `main.py` | CLI-oriented scraping pipeline entry point. |
| `providers/` | Provider-specific scraper modules. Each module usually exposes `scrape_<provider>_plans()` or `scrape_via_playwright()`. |
| `isp/` | Generic ISP Mini Crawler, Flask routes, crawler UI templates, saved-run comparison, and health reporting. |
| `scrapers/` | Shared rendering helpers. |
| `utils/` | Logging, progress state, browser stealth helpers, screenshots, validation, database utilities, benchmarking, alerts, API discovery, and render helpers. |
| `templates/` | Main dashboard HTML template. |
| `output/` | Generated data, screenshots, logs, benchmark reports, ROI pages, and crawler snapshots. |
| `database.sql` | MySQL schema for optional database storage. |
| `investigate_*.py`, `probe_*.py`, `debug_*.py`, `check_*.py` | Research and debugging scripts used to discover selectors and site behavior. |
| `test_*.py`, `verify_*.py` | Targeted scraper checks and validation scripts. |

## Core Data Flow

1. A user starts a scrape from the main dashboard, the `/isp` dashboard, or a
   Python script.
2. Provider-specific scrapers or the generic crawler load provider pages with
   Playwright or `requests`.
3. Raw page data is parsed into normalized plan dictionaries.
4. Plan rows are validated, deduplicated where applicable, and enriched with
   provider/network/source metadata.
5. Per-provider output is saved under `output/scrape_isp_<provider>/`.
6. The combined snapshot is saved as `output/all_plans.json` and
   `output/all_plans.csv`.
7. Dashboards and APIs read the saved output and render tables, benchmark
   reports, ROI data, or health summaries.

## Standard Plan Fields

Most exports are normalized toward this schema:

| Field | Meaning |
| --- | --- |
| `provider` | Provider name or provider key. |
| `network_type` | Network category such as NBN, Opticomm, Redtrain, Supa, fibre, fixed wireless, mobile, 5G, or satellite. |
| `plan_name` | Plan name shown by the provider. |
| `download_speed` | Download speed in Mbps when available. |
| `upload_speed` | Upload speed in Mbps when available. |
| `price` | Standard monthly price. |
| `promo_price` | Promotional monthly price when available. |
| `promo_period` | Promotion duration or notes. |
| `contract` | Contract term or contract notes. |
| `typical_evening_dl` | Typical evening download speed when available. |
| `typical_evening_ul` | Typical evening upload speed when available. |
| `source_url` | URL used to extract the plan. |

## Provider Coverage

Configured providers live in `config.py`. Current enabled provider keys are:

| Key | Provider | Notes |
| --- | --- | --- |
| `telstra` | Telstra | Multi-page internet, 5G, Starlink, Opticomm, and small business pages. |
| `optus` | Optus | NBN page scraper. |
| `aussie` | Aussie Broadband | Static catalogue output; config notes Cloudflare Turnstile for live access. |
| `superloop` | Superloop | NBN, fibre, flip-to-fibre, and fixed wireless pages. |
| `occom` | Occom | NBN, Opticomm, FTTP upgrade, Supa, Redtrain, and community fibre. |
| `tpg` | TPG | NBN, fibre upgrade, home wireless, 5G, and FTTB pages. |
| `exetel` | Exetel | NBN, fibre upgrade, and mobile page coverage. |
| `leaptel` | Leaptel | NBN, Opticomm, Redtrain, and fixed wireless. |
| `iinet` | iiNet | Fibre and wireless plan pages. |
| `swoop` | Swoop | NBN, fixed wireless, and Opticomm. |
| `iprimus` | iPrimus | NBN, fixed wireless, and fibre plans. |
| `dodo` | Dodo | NBN plans. |
| `kogan` | Kogan | NBN plans. |
| `more` | More | Personal and business NBN, fixed wireless, and mobile pages. |
| `tangerine` | Tangerine | NBN and fixed wireless catalogues. |
| `mate` | MATE | Individual NBN plan pages. |
| `spintel` | Spintel | NBN internet page. |
| `origin` | Origin Energy | Internet plans page. |
| `airtel` | Airtel | Mobile and travel SIM plans. |
| `alpha` | Alpha | Supanetworks, Lynham, Opticomm, and NBN pages. |
| `city7net` | City7Net | Static fibre internet plans. |
| `epsinet` | Epsinet | Static fibre internet plans. |
| `iqnet` | IQNet | ASN, Lynham, broadband, NBN, and Vision pages. |
| `newausfiber` | New Aus Fiber | Static fibre internet plans. |
| `vocphone` | VOCPhone | NBN and internet pricing pages. |

The `/isp` Scrape All workflow has a crawl URL registry in `isp/routes.py`.
When adding a new provider, update both `config.py` and that registry if the
provider should be included in the `/isp` batch button.

## Setup

Create or activate a Python environment, then install dependencies:

```bash
pip install -r requirements.txt
playwright install
```

On Linux servers, visible browser debugging may require Xvfb:

```bash
sudo apt-get install xvfb
```

The main development path in this workspace is:

```text
C:\xampp\htdocs\scrape
```

## Optional MySQL Setup

The scraper can run without MySQL for JSON/CSV output. If database storage is
needed, create the database and review `DB_CONFIG` in `config.py`.

```sql
CREATE DATABASE isp_plans;
```

Then import the schema:

```bash
mysql -u root isp_plans < database.sql
```

Default config:

```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "isp_plans",
    "port": 3306,
}
```

## Running The Main App

Start the Flask dashboard:

```bash
python app.py
```

Open:

```text
http://localhost:5000
```

Important pages:

| URL | Purpose |
| --- | --- |
| `http://localhost:5000/` | Main provider dashboard. |
| `http://localhost:5000/isp` | ISP Mini Crawler dashboard. |
| `http://localhost:5000/isp/health` | Health report built from saved crawler runs. |
| `http://localhost:5000/benchmark` | Saved benchmark dashboard, after a benchmark run. |
| `http://localhost:5000/roi` | Saved ROI calculator page, after ROI generation. |

## Main Dashboard APIs

These endpoints are served by `app.py`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/status` | Basic app status and provider counts. |
| `GET` | `/api/capabilities` | Reports platform and visible-browser capability. |
| `GET` | `/api/providers` | Lists configured providers and saved-data status. |
| `POST` | `/api/scrape/<provider_name>` | Scrapes one provider by key, such as `telstra`. |
| `POST` | `/api/scrape/all` | Scrapes all enabled providers through provider-specific scrapers. |
| `GET` | `/api/scrape/progress` | Returns live progress for provider-specific scrapes. |
| `GET` | `/api/plans/all` | Returns `output/all_plans.json`. This is the canonical all-plans API in the main app. |
| `GET` | `/api/results` | Returns saved provider results. |
| `GET` | `/api/results/<provider_name>` | Returns saved results for one provider. |
| `GET` | `/api/download/<provider>/<filename>.json` | Downloads a saved JSON provider export. |
| `GET` | `/api/download/<provider>/<filename>.csv` | Downloads a saved CSV provider export. |
| `GET` | `/screenshots/<path>` | Serves screenshots from `output/screenshots`. |

Example single-provider scrape:

```bash
curl -X POST http://localhost:5000/api/scrape/telstra ^
  -H "Content-Type: application/json" ^
  -d "{\"visible_browser\": false, \"slow_mo\": 0}"
```

Example all-plans read:

```bash
curl http://localhost:5000/api/plans/all
```

## Benchmark, Alert, And ROI APIs

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/benchmark` | Reads the latest benchmark report. |
| `POST` | `/api/benchmark/run` | Generates benchmark JSON, CSV, and HTML output. |
| `GET` | `/api/benchmark/advantages` | Lists tiers where Occom is cheapest. |
| `GET` | `/api/benchmark/gaps` | Lists tiers where Occom is not cheapest. |
| `GET` | `/api/alerts` | Reads saved alert history. |
| `POST` | `/api/alerts/run` | Runs alert checks against current plan data. |
| `GET` | `/api/roi` | Returns computed ROI data. |
| `POST` | `/api/roi/generate` | Generates the ROI calculator page. |

## ISP Mini Crawler

The `isp/` folder contains a generic crawler for provider URLs. It is useful
when a site does not have a dedicated scraper yet, or when a provider-specific
scraper needs fallback discovery.

Crawler pipeline:

1. Accept a base URL, provider name, network list, and crawl depth.
2. Discover internal links using broadband and network keywords.
3. Render candidate pages with Playwright.
4. Analyze pages for plan-card, price, and speed signals.
5. Extract plan data with selector, embedded JSON, and regex strategies.
6. Validate plans with `isp/validator.py`.
7. Deduplicate and normalize plan fields.
8. Save timestamped JSON, latest JSON, CSV, and the combined snapshot.

The single-crawl UI is available at:

```text
http://localhost:5000/isp
```

The CLI entry point is:

```bash
python -m isp.main_crawler https://www.telstra.com.au/internet --name Telstra
```

## ISP Scrape All Workflow

The `/isp` page includes a `Scrape All Providers` button.

Behavior:

1. Calls `POST /isp/api/crawl-all`.
2. Starts a background batch job.
3. Runs every enabled provider in the `/isp` provider URL registry.
4. Updates live progress with provider, URL, plans found, providers done, timer,
   and event log.
5. Continues if one provider fails.
6. Writes the final combined output to `output/all_plans.json` and
   `output/all_plans.csv`.
7. Displays all scraped plans in a frontend table.
8. Makes the same data available through `GET /api/plans/all`.

The `/isp` Scrape All feature uses these endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/isp/api/crawl-all` | Starts the all-provider crawler job. |
| `GET` | `/isp/api/crawl-all/status` | Polls batch progress and final result. |
| `GET` | `/isp/api/all-plans` | Reads the saved all-plans snapshot for the `/isp` UI. |

Important note:

```text
/api/plans/all reads output/all_plans.json.
```

So after `/isp` Scrape All finishes, the main API automatically returns the new
data without needing a separate database save.

## ISP Mini Crawler APIs

These endpoints are mounted by `isp/routes.py` under `/isp`.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/isp/` | Crawler UI. |
| `GET` | `/isp/health` | Saved-run health report UI. |
| `POST` | `/isp/api/crawl` | Starts a single URL crawl in the background. |
| `GET` | `/isp/api/status` | Polls single-crawl status. |
| `POST` | `/isp/api/crawl-all` | Starts all-provider crawl in the background. |
| `GET` | `/isp/api/crawl-all/status` | Polls all-provider crawl status. |
| `GET` | `/isp/api/all-plans` | Reads `output/all_plans.json`. |
| `GET` | `/isp/api/results` | Lists timestamped crawler result files. |
| `GET` | `/isp/api/results/<filename>` | Reads one saved crawler result. |
| `DELETE` | `/isp/api/results/<filename>` | Deletes one saved crawler result and related files. |
| `GET` | `/isp/api/results/<filename>/compare` | Compares a saved run with the previous run for the same provider. |
| `GET` | `/isp/api/health` | Returns scrape health summary JSON. |

Example single crawl:

```bash
curl -X POST http://localhost:5000/isp/api/crawl ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"https://www.telstra.com.au/internet\",\"name\":\"Telstra\",\"depth\":2}"
```

Example scrape all:

```bash
curl -X POST http://localhost:5000/isp/api/crawl-all
curl http://localhost:5000/isp/api/crawl-all/status
```

## Production API App

`app_api.py` is a separate Flask API app for read-oriented plan access. It
includes public filtered plan reads and API-key protected all-provider/provider
detail endpoints.

Common endpoints:

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/api/docs` | API documentation response. |
| `GET` | `/api/plans` | Public filtered plans endpoint. |
| `GET` | `/api/plans/all` | API-key protected all-plans endpoint in `app_api.py`. |
| `GET` | `/api/plans/<provider_name>` | API-key protected provider detail endpoint. |
| `GET` | `/health` | Health check. |

The default API key is read from `API_KEY`, with a fallback value in
`app_api.py`. For real deployment, set `API_KEY` in the environment.

## Output Files

Generated files are written under `output/`.

| Path | Description |
| --- | --- |
| `output/all_plans.json` | Combined plan snapshot used by `/api/plans/all`. |
| `output/all_plans.csv` | Combined CSV export for the all-plans snapshot. |
| `output/scrape_isp_<provider>/json/` | Provider-specific JSON output from provider scrapers. |
| `output/scrape_isp_<provider>/csv/` | Provider-specific CSV output from provider scrapers. |
| `output/isp_crawler/` | Generic crawler timestamped JSON, latest JSON, and CSV files. |
| `output/screenshots/` | Screenshots captured during Playwright scraper runs. |
| `output/logs.json` | Structured logs. |
| `output/benchmark_report.json` | Benchmark report data. |
| `output/benchmark_report.csv` | Benchmark report CSV. |
| `output/benchmark_dashboard.html` | Benchmark dashboard HTML. |
| `output/alerts.json` | Alert run history when alerts are generated. |
| `output/roi_calculator.html` | ROI page when generated. |

Generated output can become large. Review source changes separately from
generated `output/` changes when preparing commits.

## Running From Python

Run one provider through the shared service:

```python
from scraper_service import scrape_provider, save_output

result = scrape_provider("telstra", options={"visible_browser": False, "slow_mo": 0})
if result["success"]:
    files = save_output("telstra", result["plans"])
    print(files)
else:
    print(result["error"])
```

Read the combined snapshot:

```python
from scraper_service import load_all_plans_snapshot

snapshot = load_all_plans_snapshot()
print(snapshot["total_plans"])
```

Run the generic crawler directly:

```python
from isp.main_crawler import ISPCrawler

crawler = ISPCrawler(
    base_url="https://www.telstra.com.au/internet",
    provider_name="Telstra",
    max_depth=2,
)
result = crawler.run()
print(result.valid_plans)
```

## Testing And Verification

There is no single unified test suite yet. The repo contains targeted scripts for
provider and crawler checks.

Useful commands:

```bash
python -m py_compile app.py app_api.py scraper_service.py isp\routes.py isp\main_crawler.py
python test_telstra.py
python test_tpg.py
python test_more.py
python test_tangerine_catalog.py
python -m isp.test_crawler
```

For endpoint smoke checks while the Flask app is running:

```bash
curl http://localhost:5000/api/status
curl http://localhost:5000/api/providers
curl http://localhost:5000/isp/api/crawl-all/status
curl http://localhost:5000/api/plans/all
```

For visual verification:

1. Open `http://localhost:5000`.
2. Run a single provider scrape with visible browser disabled.
3. Check the progress panel, output JSON/CSV, and screenshots.
4. Open `http://localhost:5000/isp`.
5. Run one URL crawl or Scrape All Providers.
6. Confirm `output/all_plans.json` and `/api/plans/all` both show fresh data.

## Adding A New Provider

1. Add provider metadata to `PROVIDERS` in `config.py`.
2. Create `providers/<key>.py`.
3. Expose `scrape_<key>_plans()` or `scrape_via_playwright()`.
4. Return rows using the standard plan fields.
5. Add provider URL coverage to `/isp` batch registry in `isp/routes.py` if it
   should be included in Scrape All.
6. Add a focused `test_<key>.py` or probe script.
7. Run the scraper standalone before using it from the dashboard.
8. Validate JSON/CSV output and screenshots.

Recommended provider module shape:

```python
def scrape_example_plans():
    plans = []
    # Load pages, extract cards, normalize fields.
    return plans
```

`scraper_service.scrape_provider()` dynamically imports `providers.<key>` and
looks for `scrape_<key>_plans()` first. If that function is missing, it falls
back to `scrape_via_playwright()`.

## Scraper Research Workflow

The many `investigate_*.py` and `probe_*.py` files are intentional. They record
how selectors, page timing, and data structures were discovered.

Recommended workflow:

1. Start with a broad `investigate_<provider>.py` script that prints common card
   selectors and raw text.
2. Classify the site as static HTML, JavaScript rendered, embedded JSON, or
   API/SPA driven.
3. Write focused `probe_<provider>.py` scripts for exact DOM structure.
4. Test regex patterns against real captured text.
5. Build the production provider scraper only after the page structure is known.
6. Preserve the probes, because they explain why selectors and fallbacks exist.

## Troubleshooting

| Symptom | Likely Cause | What To Check |
| --- | --- | --- |
| `ModuleNotFoundError` | Environment not activated or dependencies missing. | Run `pip install -r requirements.txt`. |
| Playwright browser missing | Browsers were not installed. | Run `playwright install`. |
| Empty plans from a JS site | Page did not finish rendering or selector changed. | Increase wait, inspect screenshots, rerun probe scripts. |
| Visible browser does not open on Linux | No display server. | Install/configure Xvfb and check `/api/capabilities`. |
| `/api/plans/all` is empty | `output/all_plans.json` missing or no successful combined run. | Run `/isp` Scrape All or rebuild the snapshot. |
| A provider fails during Scrape All | Site layout changed, network issue, anti-bot page, or gated flow. | Check batch events, `output/logs.json`, screenshots, and provider-specific tests. |
| Generated files dominate `git status` | Scrapes update `output/` artifacts. | Review source files separately from generated output. |

## Maintenance Notes

- Keep source changes separate from generated `output/` changes.
- Do not commit virtual environments, `__pycache__`, or local secrets.
- Keep `.env` out of version control.
- Prefer provider-specific extraction when it produces richer data than generic
  crawling.
- Use the generic crawler for discovery, fallback, and new-provider exploration.
- Update documentation when adding endpoints, output formats, providers, or UI
  workflows.
- Re-run targeted provider checks after changing selectors or normalization.
- Check screenshots whenever a scraper depends on rendered DOM content.

