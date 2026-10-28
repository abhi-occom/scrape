# ISP Scraper Tool — Brief Summary

## What it is
A Python/Flask/Playwright system that scrapes and normalizes internet plan
data (price, speed, network type, contract terms) from ~27 Australian ISPs,
and exposes it through dashboards, JSON/CSV exports, a read-only API, a
Google Sheets price-comparison sync, and benchmark/alert/ROI reports.

## Four execution paths (share provider code, produce different outputs)
| Path | Entry point | Output |
| --- | --- | --- |
| Main dashboard | `python app.py` (port 5000) | `output/scrape_isp_<provider>/{json,csv}/` |
| ISP Mini Crawler | `/isp` UI or `python -m isp.main_crawler <url>` | `output/isp_crawler/*_latest.json` → rebuilds `output/all_plans.json`/`.csv` |
| Legacy pipeline | `python main.py` | MySQL (`isp_plans` db) + `output/plans.json` + benchmark/alert/ROI files |
| **NL scraping agent** | `/agent/` chat UI, or the Chrome extension in `agent/chrome_extension/` | Same as main dashboard (`output/scrape_isp_<provider>/`) — it drives `scraper_service.py`, not a separate pipeline |

`output/all_plans.json` is the canonical combined snapshot used by
dashboards and the read API — note that `/api/scrape/all` does **not**
refresh it; only the `/isp` "Scrape All" workflow does.

## Key components
- **`config.py`** — provider registry (`PROVIDERS` dict: id, enabled flag,
  optional `supported_networks` allowlist), DB config, Playwright timeouts.
- **`providers/`** — one module per ISP (e.g. `telstra.py`, `optus.py`),
  each implementing `scrape_<key>_plans()` (or legacy `scrape_via_playwright()`),
  loaded dynamically by `scraper_service.py`.
- **`isp/`** — generic crawler engine: URL discovery → Playwright render →
  plan/network detection → selector/embedded-data/text extraction →
  validation/dedup → normalization → snapshot save. Has its own Flask
  blueprint (`isp/routes.py`) mounted at `/isp`.
- **`utils/`** — DB, logging, progress tracking, validator, network
  classifier, stealth (anti-bot), screenshots, benchmark, alerts.
- **`app.py`** — main dashboard + scrape/report/Sheets APIs; registers the
  `isp` blueprint.
- **`app_api.py`** — separate, API-key-protected, filterable read API
  (also binds port 5000 — don't run alongside `app.py`).
- **`google_sheets_sync.py`** — OAuth + writes NBN speed-tier price matrix
  to a Google Sheet from `output/all_plans.json`.
- **`main.py`** — legacy pipeline: explicit provider subset → validate →
  MySQL (`plans_current`, transactional) → JSON → benchmark/alerts/ROI.
- **`agent/`** — natural-language front end (chat box) over the existing
  scraper/benchmark code, no scraping logic duplicated. `translator.py`
  (English → structured job) is pluggable: rule-based by default
  (`agent/translators/rule_based.py`), or Claude/Gemini via `AI_PROVIDER` in
  `.env` (`agent/translators/`), always falling back to rule-based if a key
  is missing or the call fails. `executor.py` runs the job through
  `scraper_service.py` + `utils/benchmark.py`; `responder.py` renders a
  plain-English + HTML-table reply; `routes.py` is the `/agent` Flask
  blueprint (rate-limited via `flask-limiter`). `local_llm_extractor.py` is
  an optional, off-by-default local-LLM (Ollama) fallback for pages the
  deterministic engine can't parse — validated as **unreliable on small
  local models** in live testing (see `AI_AGENT_BROWSER_PLAN.md`).
  `chrome_extension/` is a Manifest V3 side-panel client for the same API.

## Data model (normalized fields)
`provider`, `network_type` (NBN/Opticomm/Supa/Redtrain/fixed wireless/
fibre/mobile/...), `plan_name`, `download_speed`, `upload_speed`, `price`,
`promo_price`, `promo_period`, `contract`, `typical_evening_dl/ul`,
`source_url`.

## Special handling
- **Aussie Broadband** is Cloudflare-Turnstile blocked, so it uses a
  maintained static fallback catalogue restricted to `NBN`/`Opticomm`
  networks only (never inferred from other carriers).
- Several small fibre-only ISPs (Epsinet, New Aus Fiber, WaveZone, Zennet)
  are locked to `supported_networks: ['Fibre']`.
- Provider websites change often — `investigate_*.py`, `probe_*.py`,
  `debug_*.py` scripts at repo root are ad-hoc selector-research tools, not
  part of the runtime pipeline.

## Running it
```powershell
python -m venv venv && .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
python app.py        # main dashboard on http://localhost:5000
```
Tests are focused `unittest` scripts (`test_*.py`, `isp/test_crawler.py`),
not one unified suite — provider selector drift should also be checked
against saved screenshots/logs, not just test pass/fail.

## Notable repo state
- `venv/` and `.venv/` (two separate virtualenvs) and `__pycache__/` are
  present in the working tree alongside source.
- Many generated `output/*.json`/`.csv` files show as modified in git —
  these are scrape artifacts, not source changes.
- Existing longer-form docs for deeper context: `README.md` (full
  reference), `Summary.md`, `SYSTEM_ANALYSIS.md`,
  `Non-Technical-Summary.md`, `how-the-project-runs.md`.
- `AI_AGENT_BROWSER_PLAN.md` covers the `agent/` natural-language feature in
  depth — design rationale, phase-by-phase build status, and real
  live-testing findings (including a confirmed local-LLM extraction
  reliability issue on this machine's hardware).
