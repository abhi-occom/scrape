# Australian ISP Plan Scraper

A Python, Flask, and Playwright system for collecting Australian internet plan
data. It contains provider-specific scrapers, a generic ISP crawler, JSON/CSV
exports, comparison tools, a Google Sheets price synchronizer, and optional
MySQL storage.

The canonical combined snapshot used by the dashboards and read APIs is:

```text
output/all_plans.json
output/all_plans.csv
```

## What the project provides

- Provider-specific scrapers for known Australian ISPs.
- A generic crawler that discovers plan pages and extracts plans from a URL.
- Main and crawler web dashboards.
- Per-provider and combined JSON/CSV exports.
- Benchmark, pricing alert, and ROI reports.
- Google Sheets synchronization for NBN price comparison tables.
- A separate filterable read API.
- Optional MySQL persistence through the legacy pipeline.

## Architecture

There are three distinct execution paths. They share provider code and output
utilities, but they should not be treated as identical.

| Path | Entry point | Provider coverage | Primary output |
| --- | --- | --- | --- |
| Main dashboard | `python app.py` | All enabled providers in `config.py` | Per-provider files under `output/scrape_isp_<provider>/` |
| ISP Mini Crawler | `/isp` or `python -m isp.main_crawler` | A supplied URL, or enabled providers that also have an entry in `PROVIDER_CRAWL_URLS` | Timestamped/latest crawler files and `output/all_plans.*` |
| Legacy pipeline | `python main.py` | Explicit subset imported in `main.py` | MySQL, `output/plans.json`, benchmark, alerts, and ROI output |

Important: `POST /api/scrape/all` saves provider-specific files, but it does not
rebuild `output/all_plans.json`. Use the `/isp` Scrape All workflow when the
combined snapshot needs to be refreshed.

## Project layout

| Path | Purpose |
| --- | --- |
| `app.py` | Main Flask dashboard, scrape APIs, reports, Google Sheets, and `/isp` blueprint registration. |
| `app_api.py` | Separate read-oriented API with filters, caching, and API-key-protected endpoints. |
| `config.py` | Provider registry, database connection, output paths, and Playwright settings. |
| `scraper_service.py` | Dynamically loads provider modules and saves provider JSON/CSV files. |
| `main.py` | Legacy scrape/validate/database/report pipeline. |
| `providers/` | Provider-specific scraper implementations. |
| `isp/` | Generic crawler, extraction engine, validation, Flask routes, health page, and crawler UI. |
| `utils/` | Database, logging, progress, validation, browser, screenshot, benchmark, and alert helpers. |
| `google_sheets_sync.py` | Google OAuth and NBN price matrix synchronization. |
| `templates/` | Main dashboard and Google Sheets UI. |
| `output/` | Generated plans, crawler snapshots, screenshots, logs, reports, and HTML pages. |
| `database.sql` | Optional MySQL schema. |
| `test_*.py` | Focused regression and provider tests. |
| `investigate_*.py`, `probe_*.py`, `debug_*.py` | Site research and selector diagnostics. |

## Data model

Plan exports are normalized toward the following fields:

| Field | Description |
| --- | --- |
| `provider` | Display name of the ISP. |
| `network_type` | NBN, Opticomm, Supa, Redtrain, fixed wireless, fibre, mobile, or another service type. |
| `plan_name` | Provider plan name. |
| `download_speed` | Advertised download speed in Mbps. |
| `upload_speed` | Advertised upload speed in Mbps. |
| `price` | Standard monthly price in AUD. |
| `promo_price` | Promotional monthly price, when available. |
| `promo_period` | Promotion duration or explanatory text. |
| `contract` | Contract or cancellation terms. |
| `typical_evening_dl` | Typical evening download speed. |
| `typical_evening_ul` | Typical evening upload speed. |
| `source_url` | Page used as the plan source. |

The combined crawler snapshot wraps plans with metadata:

```json
{
  "scraped_at": "2026-06-22_08-51-59",
  "source": "isp_crawler_latest_files",
  "total_providers": 32,
  "total_plans": 379,
  "providers": [],
  "plans": []
}
```

Counts vary as providers and saved latest files change.

## Provider support

`config.py` is the source of truth for providers exposed by the main dashboard.
Every configured provider currently has a compatible function in `providers/`.

| Provider key | Provider | Main coverage notes |
| --- | --- | --- |
| `telstra` | Telstra | NBN, internet, Opticomm, 5G, Starlink, and related pages. |
| `optus` | Optus | Playwright-based plan extraction. |
| `aussie` | Aussie Broadband | Maintained fallback because of Cloudflare; only NBN and Opticomm are supported. |
| `superloop` | Superloop | NBN, fibre, fixed wireless, and upgrade pages. |
| `occom` | Occom | NBN, Opticomm, Supa, Redtrain, FTTP, and community fibre. |
| `tpg` | TPG | NBN, fibre upgrade, FTTB, home wireless, and 5G. |
| `exetel` | Exetel | NBN, fibre upgrade, and mobile. |
| `leaptel` | Leaptel | NBN and private-network plans. |
| `iinet` | iiNet | Fibre and wireless plans. |
| `swoop` | Swoop | NBN, fixed wireless, and Opticomm. |
| `iprimus` | iPrimus | NBN, fixed wireless, and fibre. |
| `dodo` | Dodo | NBN plans. |
| `kogan` | Kogan | NBN plans. |
| `more` | More | Personal/business NBN, fixed wireless, and mobile. |
| `tangerine` | Tangerine | NBN and fixed wireless. |
| `mate` | MATE | Individual NBN plan pages. |
| `spintel` | Spintel | NBN, fixed wireless, and fibre. |
| `origin` | Origin Energy | Internet plan pages. |
| `airtel` | Airtel | Mobile and travel SIM plans. |
| `alpha` | Alpha | Supanetworks, Lynham, Opticomm, and NBN. |
| `city7net` | City7Net | Fibre plans. |
| `epsinet` | Epsinet | Fibre plans. |
| `iqnet` | IQNet | ASN, Lynham, Supa, NBN, and Vision networks. |
| `newausfiber` | New Aus Fiber | Fibre plans. |
| `vocphone` | VOCPhone | NBN and Supa fibre plans. |

The `/isp` Scrape All workflow only runs configured, enabled providers that also
have a URL in `isp/routes.py::PROVIDER_CRAWL_URLS`.

Saved `*_latest.json` files can include older or manually crawled providers that
are no longer in `config.py`. A single crawler run rebuilds the combined
snapshot from every latest file in `output/isp_crawler/`; the batch Scrape All
workflow instead writes a snapshot from that batch's successful results.

### Aussie Broadband safeguard

Aussie Broadband is protected by Cloudflare Turnstile in automated sessions.
Its provider module therefore uses a maintained fallback catalogue.

- Supported networks are explicitly restricted to `NBN` and `Opticomm`.
- The provider returns 13 plans: 7 NBN and 6 Opticomm.
- Supa and Redtrain plans are not inferred from Opticomm prices.
- The generic crawler intersects fallback data with the provider's
  `supported_networks` allowlist from `config.py`.

## Requirements

- Python 3.10 or newer.
- Playwright-supported Chromium.
- Internet access to provider websites.
- MySQL only if `main.py` database persistence is required.
- Google Cloud OAuth credentials only if Google Sheets sync is required.

Install dependencies:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

On Linux, install browser dependencies as needed:

```bash
python -m playwright install --with-deps chromium
```

Visible browser debugging on a headless Linux host may also require Xvfb. See
`XVFB_SETUP_GUIDE.md`.

## Environment configuration

Copy `.env.example` to `.env` and replace placeholders:

```powershell
Copy-Item .env.example .env
```

Supported environment variables:

| Variable | Purpose |
| --- | --- |
| `FLASK_SECRET_KEY` | Flask session signing key. Required for secure OAuth sessions. |
| `GOOGLE_CLIENT_ID` | Google OAuth desktop/web application client ID. |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret. |
| `GOOGLE_REDIRECT_URI` | OAuth callback; defaults to `http://localhost:5000/oauth2callback`. |
| `GOOGLE_SHEET_ID` | Target spreadsheet ID. |
| `GOOGLE_SHEET_TAB` | Target tab name; defaults to `Sheet1`. |
| `API_KEY` | API key used by protected endpoints in `app_api.py`. |

Never commit `.env` or `instance/google_token.json`.

Database settings are currently configured directly in `config.py` through
`DB_CONFIG`.

## Run the main web application

```powershell
python app.py
```

Open:

| URL | Page |
| --- | --- |
| `http://localhost:5000/` | Provider scraping dashboard. |
| `http://localhost:5000/isp/` | ISP Mini Crawler dashboard. |
| `http://localhost:5000/isp/health` | Saved crawler health report. |
| `http://localhost:5000/sheets` | Google Sheets synchronization dashboard. |
| `http://localhost:5000/benchmark` | Generated benchmark page. |
| `http://localhost:5000/roi` | Generated ROI page. |

The Flask development server binds to `0.0.0.0:5000` with debug mode enabled.
Use a production WSGI server and a strong `FLASK_SECRET_KEY` outside local
development.

## Main dashboard APIs

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/status` | Application and provider status. |
| `GET` | `/api/capabilities` | Browser/display capabilities. |
| `GET` | `/api/providers` | Configured providers and saved-data status. |
| `POST` | `/api/scrape/<provider>` | Run one provider scraper and save its output. |
| `POST` | `/api/scrape/all` | Run all enabled provider-specific scrapers. |
| `GET` | `/api/scrape/progress` | Current in-memory scrape progress. |
| `GET` | `/api/plans/all` | Read the canonical `output/all_plans.json` snapshot. |
| `GET` | `/api/results` | List saved provider-specific results. |
| `GET` | `/api/results/<provider>` | Read saved results for one provider. |
| `GET` | `/api/download/<provider>/<filename>.json` | Download provider JSON. |
| `GET` | `/api/download/<provider>/<filename>.csv` | Download provider CSV. |
| `GET` | `/screenshots/<path>` | Serve a captured scraper screenshot. |

Single-provider example:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:5000/api/scrape/aussie `
  -ContentType application/json `
  -Body '{"visible_browser":false,"slow_mo":0}'
```

Read the combined snapshot:

```powershell
Invoke-RestMethod http://localhost:5000/api/plans/all
```

## ISP Mini Crawler

The generic crawler performs:

1. Known-provider detection and provider-specific fallback.
2. Internal URL discovery for unknown or incomplete providers.
3. Playwright rendering.
4. Plan-page and network detection.
5. Selector, embedded-data, and text extraction.
6. Validation and global deduplication.
7. Field normalization and snapshot persistence.

For known providers, the provider-specific scraper is attempted first. Fallback
plans are filtered to the requested network types. Providers with an explicit
`supported_networks` list are filtered to both the request and that allowlist.

### Crawler CLI

```powershell
python -m isp.main_crawler `
  https://www.aussiebroadband.com.au/internet/nbn-plans/ `
  --name "Aussie Broadband" `
  --networks nbn opticomm `
  --depth 2 `
  --max-urls 150
```

Available arguments:

| Argument | Default | Description |
| --- | --- | --- |
| `url` | Required | Provider base URL. |
| `--name` | Domain-derived | Provider display name. |
| `--depth` | `2` | Maximum crawl depth. |
| `--networks` | `nbn opticomm redtrain supa` | Requested network types. |
| `--max-urls` | `150` | Maximum URLs to visit. |

### Crawler APIs

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/isp/api/crawl` | Start a single crawl in a background thread. |
| `GET` | `/isp/api/status` | Poll single-crawl state. |
| `POST` | `/isp/api/crawl-all` | Start the configured provider batch. |
| `GET` | `/isp/api/crawl-all/status` | Poll batch state and results. |
| `GET` | `/isp/api/all-plans` | Read the combined crawler snapshot. |
| `GET` | `/isp/api/results` | List timestamped crawler files. |
| `GET` | `/isp/api/results/<filename>` | Read a crawler result. |
| `GET` | `/isp/api/results/<filename>/compare` | Compare with the previous provider run. |
| `DELETE` | `/isp/api/results/<filename>` | Delete a result and related files. |
| `GET` | `/isp/api/health` | Return crawler health JSON. |

Start and poll a batch:

```powershell
Invoke-RestMethod -Method Post http://localhost:5000/isp/api/crawl-all
Invoke-RestMethod http://localhost:5000/isp/api/crawl-all/status
```

## Google Sheets NBN price sync

The `/sheets` page reads `output/all_plans.json` and updates a price comparison
spreadsheet through Google OAuth.

Sync behavior:

- Only plans identified as NBN are eligible.
- Mobile, SIM, travel, prepaid, postpaid, roaming, and phone plans are excluded.
- The promotional price is preferred when present; otherwise regular price is
  used.
- Plans are matched to speed tiers such as `50M`, `100/20M`, and `100/40M`.
- Configured provider columns are updated.
- `Min Price` and `Max Price` formulas are written when those columns exist.
- A dry run can be executed without writing to the spreadsheet.

Required sheet structure:

- Row 1 must contain `SPEED MBPS`.
- Row 1 must contain at least one recognized provider column.
- Speed tier rows must use labels understood by `parse_speed_label()`.

Endpoints:

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/sheets/status` | OAuth, spreadsheet, tab, and snapshot status. |
| `GET` | `/api/google/auth/start` | Start Google OAuth. |
| `GET` | `/oauth2callback` | OAuth callback. |
| `POST` | `/api/sheets/sync` | Preview or execute synchronization. |

Dry-run example:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://localhost:5000/api/sheets/sync `
  -ContentType application/json `
  -Body '{"dry_run":true}'
```

OAuth tokens are saved locally to:

```text
instance/google_token.json
```

## Benchmark, alerts, and ROI

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/api/benchmark` | Read the latest benchmark report. |
| `POST` | `/api/benchmark/run` | Rebuild benchmark JSON, CSV, and HTML. |
| `GET` | `/api/benchmark/advantages` | Tiers where Occom is cheapest. |
| `GET` | `/api/benchmark/gaps` | Tiers where Occom is not cheapest. |
| `GET` | `/api/alerts` | Read saved alert history. |
| `POST` | `/api/alerts/run` | Run alert checks. |
| `GET` | `/api/roi` | Return ROI data. |
| `POST` | `/api/roi/generate` | Generate the ROI calculator page. |

Generated files include:

```text
output/benchmark_report.json
output/benchmark_report.csv
output/benchmark_dashboard.html
output/alerts.json
output/roi_calculator.html
```

## Separate read API

Run the alternative API application:

```powershell
$env:API_KEY = "replace-with-a-strong-key"
python app_api.py
```

It also binds to port 5000, so do not run it alongside `app.py` on the same
port.

| Method | Endpoint | Authentication |
| --- | --- | --- |
| `GET` | `/api/docs` | Public. |
| `GET` | `/api/status` | Public. |
| `GET` | `/api/providers` | Public. |
| `GET` | `/api/plans` | Public, filterable, cached for five minutes. |
| `GET` | `/api/plans/all` | `X-API-Key` header required. |
| `GET` | `/api/plans/<provider>` | `X-API-Key` header required. |
| `GET` | `/health` | Public. |

Supported `/api/plans` query parameters:

```text
provider
network_type
min_speed
max_speed
min_price
max_price
sort_by=price|speed
order=asc|desc
```

Example:

```powershell
Invoke-RestMethod `
  "http://localhost:5000/api/plans?network_type=NBN&min_speed=100&max_price=100&sort_by=price"
```

`app_api.py` contains a development fallback API key. Always set `API_KEY` in a
real deployment.

## Optional MySQL pipeline

Create the schema:

```powershell
mysql -u root < database.sql
```

Review `DB_CONFIG` in `config.py`, then run:

```powershell
python main.py
```

The legacy pipeline:

1. Runs the explicit provider subset declared in `main.py`.
2. Cleans and validates plans.
3. Writes plans to `plans_current`.
4. Saves `output/plans.json`.
5. Generates benchmark, alert, and ROI output.

Database batches run in one transaction. When Aussie plans are present, existing
Aussie rows are deleted and replaced in the same transaction so removed network
plans cannot remain stale. A failed insert rolls the deletion back.

The pipeline currently considers database and JSON success when choosing its
exit code. If MySQL is not required, prefer the Flask/provider or ISP crawler
workflows.

## Output files

| Path | Description |
| --- | --- |
| `output/all_plans.json` | Canonical combined crawler snapshot. |
| `output/all_plans.csv` | CSV form of the combined snapshot. |
| `output/plans.json` | Validated output from `main.py`. |
| `output/scrape_isp_<provider>/json/` | Provider-specific JSON files. |
| `output/scrape_isp_<provider>/csv/` | Provider-specific CSV files. |
| `output/isp_crawler/<provider>_<timestamp>.json` | Historical crawler result. |
| `output/isp_crawler/<provider>_latest.json` | Latest crawler result used in snapshot rebuilds. |
| `output/screenshots/` | Browser screenshots captured during scraping. |
| `output/logs.json` | Structured application logs. |

Historical timestamped crawler files are retained unless deleted through the
crawler result API or manually removed.

## Run from Python

Provider-specific scraper:

```python
from scraper_service import save_output, scrape_provider

result = scrape_provider(
    "aussie",
    options={"visible_browser": False, "slow_mo": 0},
)

if result["success"]:
    print(save_output("aussie", result["plans"]))
else:
    print(result["error"])
```

Generic crawler:

```python
from isp.main_crawler import ISPCrawler

crawler = ISPCrawler(
    base_url="https://www.aussiebroadband.com.au/internet/nbn-plans/",
    provider_name="Aussie Broadband",
    network_types=["nbn", "opticomm"],
)
result = crawler.run()

print(result.valid_plans)
print(result.network_types_found)
```

Read the combined snapshot:

```python
from scraper_service import load_all_plans_snapshot

snapshot = load_all_plans_snapshot()
print(snapshot["total_providers"], snapshot["total_plans"])
```

## Testing

The repository uses focused `unittest` scripts rather than one comprehensive
test package.

Core regression checks:

```powershell
python -m unittest -v test_aussie_networks.py
python test_tangerine_catalog.py
python -m isp.test_crawler
```

Syntax check:

```powershell
python -m py_compile `
  app.py `
  app_api.py `
  scraper_service.py `
  google_sheets_sync.py `
  isp\main_crawler.py `
  isp\routes.py
```

Endpoint smoke checks while `app.py` is running:

```powershell
Invoke-RestMethod http://localhost:5000/api/status
Invoke-RestMethod http://localhost:5000/api/providers
Invoke-RestMethod http://localhost:5000/api/plans/all
Invoke-RestMethod http://localhost:5000/isp/api/health
Invoke-RestMethod http://localhost:5000/api/sheets/status
```

Provider websites change frequently. A passing unit test does not replace
checking current screenshots, extracted text, and saved output after selector
changes.

## Adding a provider

1. Add provider metadata and a unique ID to `PROVIDERS` in `config.py`.
2. Create `providers/<key>.py`.
3. Implement `scrape_<key>_plans()` or the legacy
   `scrape_via_playwright()` entry point.
4. Return normalized plan dictionaries.
5. Add a base URL to `PROVIDER_CRAWL_URLS` in `isp/routes.py` if Scrape All
   should include it.
6. Add a focused regression test.
7. Run the provider directly and inspect JSON, CSV, logs, and screenshots.
8. Add Google Sheets aliases/header support if the provider should appear in
   that comparison sheet.

`scraper_service.scrape_provider()` imports `providers.<key>` dynamically. It
prefers `scrape_<key>_plans()` and falls back to
`scrape_via_playwright()`.

For a provider whose supported networks are known and restricted, add a
`supported_networks` list in `config.py`. The generic crawler will enforce it
when provider fallback data is used.

## Troubleshooting

| Problem | Check |
| --- | --- |
| `ModuleNotFoundError` | Activate the virtual environment and reinstall `requirements.txt`. |
| Playwright executable missing | Run `python -m playwright install chromium`. |
| Empty or incomplete plans | Inspect `output/screenshots`, `output/logs.json`, and the provider probe scripts. |
| Cloudflare or bot challenge | Use a maintained provider fallback or manual verification; do not treat challenge HTML as plan data. |
| `/api/plans/all` is stale | Run `/isp` Scrape All or a crawler job that rebuilds the combined snapshot. |
| Provider-specific scrape succeeded but combined data did not change | Provider dashboard output and crawler combined output are separate workflows. |
| Google Sheets sync cannot connect | Check OAuth variables, redirect URI, token file, spreadsheet access, and tab name. |
| Google Sheets rows remain blank | Confirm plans are NBN, provider headers match, and speed labels are supported. |
| MySQL error 1813 | An orphaned InnoDB tablespace exists; repair/drop the orphaned table files before recreating the table. |
| MySQL table missing | Import `database.sql` and verify the selected database in `DB_CONFIG`. |
| Old provider appears in combined output | Remove its stale `output/isp_crawler/*_latest.json` or run a clean batch snapshot. |
| Generated files dominate `git status` | Review source and generated `output/` changes separately. |
| **OAuth connection error (PermissionError)** | **See detailed fix below** |

### Google OAuth Connection Error Fix

If you encounter:
```
OAuth failed: ('Connection aborted.', PermissionError(13, 'Permission denied'))
```

This is a **Windows network permission issue**. Quick fixes:

1. **Run diagnostic tool first:**
   ```powershell
   python diagnose_oauth.py
   ```

2. **Most common solution - Add Python to Windows Firewall:**
   - Press `Win + R`, type `wf.msc`, press Enter
   - Add Python to both Inbound and Outbound rules
   - See `OAUTH_QUICK_FIX.md` for step-by-step instructions

3. **Alternative: Run as Administrator**

4. **See comprehensive guide:**
   - Quick reference: `OAUTH_QUICK_FIX.md`
   - Detailed solutions: `OAUTH_TROUBLESHOOTING.md`
   - Technical details: `OAUTH_FIX_SUMMARY.md`

## Security and maintenance

- Keep `.env`, OAuth tokens, and production API keys out of version control.
- Replace development Flask secrets and the fallback API key before deployment.
- Do not expose the Flask debug server publicly.
- Treat provider HTML and extracted values as untrusted input.
- Keep provider-specific extraction as the preferred path for known sites.
- Use the generic crawler for discovery, fallback, and new-provider research.
- Do not infer a provider's network availability from another carrier's plans.
- Update provider allowlists when authoritative network support changes.
- Keep source changes separate from generated snapshots where practical.
- Re-run focused tests after changing selectors, normalization, persistence, or
  fallback logic.
