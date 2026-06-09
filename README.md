# Australian ISP Plan Scraper

Python and Playwright based scraping system for collecting, validating, comparing, and exporting Australian ISP internet plan data. The project includes provider-specific scrapers, a generic ISP crawler, a Flask dashboard, benchmark reporting, ROI reporting, screenshots, and JSON/CSV output.

## Current Folder Summary

This workspace is located at `C:\xampp\htdocs\scrape` and contains a working scraper application with these main areas:

| Area | Purpose |
| --- | --- |
| `app.py` | Flask dashboard and API entry point. Serves the main UI, provider scraping APIs, benchmark APIs, screenshot files, and the ISP crawler blueprint. |
| `scraper_service.py` | Shared service layer used by the dashboard and CLI flows. Dynamically loads provider modules, runs scrapers, and saves JSON/CSV output. |
| `config.py` | Provider registry, database settings, Playwright settings, and retry constants. |
| `providers/` | Provider-specific scraping modules for Telstra, Optus, Superloop, Occom, TPG, Exetel, Leaptel, iiNet, Swoop, iPrimus, Dodo, Kogan, More, Tangerine, MATE, Spintel, Origin, Airtel, Alpha, City7Net, Epsinet, IQNet, New Aus Fiber, and VOCPhone. |
| `isp/` | Generic Playwright-powered ISP Mini Crawler for discovering plan pages from a provider URL and extracting plan data when a dedicated provider scraper is not enough. |
| `utils/` | Shared utilities for progress tracking, logging, browser stealth, screenshots, validation, benchmarking, alerts, and related helpers. |
| `templates/` | Main Flask dashboard templates. |
| `output/` | Generated scrape results, benchmark reports, screenshots, crawler output, logs, and provider JSON/CSV exports. |
| `database.sql` | Database schema for MySQL storage. |
| `requirements.txt` | Python dependencies for Flask, Playwright, MySQL, parsing, CORS, rate limiting, and virtual display support. |
| `investigate_*.py`, `probe_*.py`, `test_*.py` | Provider investigation, debugging, and test scripts used while developing scraper coverage. |

## Key Capabilities

- Scrapes internet plan data from many Australian providers.
- Supports both provider-specific extraction and generic rendered-page crawling.
- Uses Playwright for JavaScript-rendered pages.
- Supports visible browser debugging with slow motion for scraper validation.
- Uses stealth browser helpers for dynamic and bot-sensitive pages.
- Saves provider output as JSON and CSV.
- Aggregates all plans into combined output files.
- Captures screenshots for visual verification.
- Provides a Flask dashboard for running scrapes, viewing results, downloading files, and checking progress.
- Includes benchmark and ROI reporting utilities.
- Includes an `isp` crawler module that discovers likely broadband plan pages from a base URL, analyzes plan signals, extracts normalized plans, validates results, and writes timestamped output.

## Provider Coverage

Provider configuration is managed in `config.py`. Enabled providers currently include:

| Provider Key | Provider Name | Notes |
| --- | --- | --- |
| `telstra` | Telstra | Multi-page internet plan scraping. |
| `optus` | Optus | Provider-specific scraper. |
| `aussie` | Aussie Broadband | Enabled but marked as blocked by Cloudflare Turnstile. |
| `superloop` | Superloop | Provider-specific scraper. |
| `occom` | Occom | Multi-network scraper. |
| `tpg` | TPG | NBN, home wireless, 5G, FTTB, and fibre upgrade flows. |
| `exetel` | Exetel | NBN, fibre upgrade, and mobile-related pages. |
| `leaptel` | Leaptel | NBN and fixed wireless pages. |
| `iinet` | iiNet | Fibre, wireless, FTTH, and fibre upgrade output. |
| `swoop` | Swoop | NBN, fixed wireless, and Opticomm. |
| `iprimus` | iPrimus | NBN, fixed wireless, and fibre plans. |
| `dodo` | Dodo | NBN plans from Drupal-rendered pages. |
| `kogan` | Kogan | Rendered NBN plan extraction. |
| `more` | More | JavaScript-rendered NBN and mobile pages. |
| `tangerine` | Tangerine | Static HTML NBN plan extraction. |
| `mate` | MATE | NBN plan sub-pages. |
| `spintel` | Spintel | NBN, fixed wireless, and fibre. |
| `origin` | Origin Energy | JavaScript-rendered NBN plans. |
| `airtel` | Airtel | Mobile and travel SIM plans. |
| `alpha` | Alpha | Residential network plans. |
| `city7net` | City7Net | Fibre month-to-month plans. |
| `epsinet` | Epsinet | Fibre month-to-month plans. |
| `iqnet` | IQNet | ASN, Lynham, SUPA, NBN, and Vision network plans. |
| `newausfiber` | New Aus Fiber | Fibre month-to-month plans. |
| `vocphone` | VOCPhone | NBN and SUPA fibre internet plans. |

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
playwright install
```

Optional MySQL setup:

```sql
CREATE DATABASE isp_plans;
```

Then review `DB_CONFIG` in `config.py`:

```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "isp_plans",
    "port": 3306,
}
```

## Running The Application

Start the Flask dashboard:

```bash
python app.py
```

Open:

```text
http://localhost:5000
```

Useful routes:

| Route | Purpose |
| --- | --- |
| `/` | Main scraper dashboard. |
| `/api/providers` | Lists configured providers and saved-data status. |
| `/api/scrape/<provider>` | Scrapes one provider. |
| `/api/scrape/all` | Scrapes all enabled providers. |
| `/api/scrape/progress` | Returns live scrape progress. |
| `/api/capabilities` | Reports visible-browser support for debugging. |
| `/screenshots/<path>` | Serves captured scraper screenshots. |
| `/isp/` | ISP Mini Crawler dashboard. |

## Running From Python

Run a single provider through the shared service:

```python
from scraper_service import scrape_provider, save_output

result = scrape_provider("telstra")
if result["success"]:
    files = save_output("telstra", result["plans"])
    print(files)
```

Run the main pipeline:

```bash
python main.py
```

Run benchmark reporting:

```bash
python benchmark_report.py
```

## ISP Mini Crawler

The `isp/` folder contains a generic crawler for cases where the project needs to start from a provider URL rather than a dedicated provider module.

Pipeline summary:

1. Accept a base ISP URL and optional provider/network hints.
2. Discover internal links with broadband, internet, plan, pricing, fibre, wireless, NBN, Opticomm, RedTrain, SUPA, 5G, satellite, and business signals.
3. Render candidate pages with Playwright.
4. Score whether each page contains plan cards or plan data.
5. Extract plans using selectors, embedded JSON, and regex fallback parsing.
6. Normalize and validate plan records.
7. Deduplicate results.
8. Save timestamped JSON, latest JSON, and CSV files under `output/isp_crawler`.

More detailed crawler documentation is available in `isp/README.md`, `isp/QUICKSTART.md`, and `isp/EXAMPLES.md`.

## Output Files

Generated output is written under `output/`.

| Output Path | Description |
| --- | --- |
| `output/all_plans.json` | Combined plan data across providers. |
| `output/all_plans.csv` | Combined CSV export. |
| `output/scrape_isp_<provider>/json/` | Provider-specific JSON exports. |
| `output/scrape_isp_<provider>/csv/` | Provider-specific CSV exports. |
| `output/isp_crawler/` | Generic ISP Mini Crawler timestamped and latest outputs. |
| `output/screenshots/` | Rendered page screenshots captured during scraper runs. |
| `output/logs.json` | Structured scrape logs. |
| `output/benchmark_report.json` | Benchmark report data. |
| `output/benchmark_report.csv` | Benchmark CSV data. |
| `output/benchmark_dashboard.html` | HTML benchmark dashboard. |

Standard plan rows are normalized toward:

| Field | Meaning |
| --- | --- |
| `provider` | Provider name or key. |
| `network_type` | NBN, Opticomm, fibre, fixed wireless, 5G, satellite, mobile, or related network category. |
| `plan_name` | Name of the internet or mobile plan. |
| `download_speed` | Download speed where available. |
| `upload_speed` | Upload speed where available. |
| `price` | Standard monthly price. |
| `promo_price` | Promotional price where available. |
| `promo_period` | Promotional period where available. |
| `contract` | Contract information where available. |
| `typical_evening_dl` | Typical evening download speed where available. |
| `typical_evening_ul` | Typical evening upload speed where available. |
| `source_url` | Page used to extract the plan. |

## AI Initiative Evaluation

| Department | Employee Name | AI Initiative / Project | Original Objective | Planned Deliverables | Current Status (%) | Actual Deliverables Achieved | Business Impact / Outcome | Quality Rating (1-5) | Ownership & Engagement (1-5) | Innovation / Initiative (1-5) | Challenges Encountered | Mitigation Actions Taken | Key Learnings | Next Steps | Manager Comments | Overall Score (%) | Recognition Recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Data Engineering / Automation | TBD | AI-assisted Australian ISP plan scraping, validation, benchmarking, and crawler dashboard | Automate collection of Australian ISP plan pricing, speed, and network data across many providers for comparison and analysis | Provider-specific scrapers; generic ISP crawler; Flask dashboard; visible browser debugging; JSON/CSV exports; screenshots; benchmark reports; ROI reporting; validation and logs | 90% | Multi-provider scraper coverage; `isp` mini crawler; dashboard APIs and UI; progress tracking; screenshot capture; combined output files; provider JSON/CSV exports; benchmark dashboard; documentation and test/investigation scripts | Reduces manual price monitoring effort, improves visibility into ISP plan changes, supports competitive benchmarking, and creates reusable data exports for reporting | 4 | 5 | 5 | Dynamic JavaScript pages; anti-bot protection; provider layout changes; inconsistent plan schemas; large generated output volume; providers with Cloudflare or qualification-gated flows | Used Playwright rendering, stealth helpers, screenshots, provider-specific fallback logic, validation, output normalization, and investigation scripts | Provider websites require mixed extraction strategies; screenshots are important for trust; generic crawling helps broaden coverage but provider-specific scrapers produce richer data | Finalize automated regression tests, improve blocked-provider handling, add scheduled runs, strengthen schema validation, prune generated artifacts from version control, and document deployment steps | Strong initiative with clear automation value; focus next on operational hardening and repeatable QA | 88% | Recommended for recognition, with continued support for production hardening |

## Maintenance Notes

- Keep generated files under `output/` separate from source changes when reviewing commits.
- Avoid committing `__pycache__` files or local runtime artifacts.
- When adding a provider, update `config.py`, add a `providers/<key>.py` scraper, and ensure `scraper_service.py` can resolve `scrape_<key>_plans()`.
- Use screenshots and CSV/JSON output together to validate scraper accuracy.
- For providers with unstable markup, prefer small provider-specific extraction helpers over fragile broad selectors.
- Re-run targeted provider tests after changing extraction selectors or normalization rules.
