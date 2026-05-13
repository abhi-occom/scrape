# ISP Plan Scraping System - Skill Reference

**Fast-track guide for LLMs to understand and work with the Australian ISP plan scraper.**

---

## Quick Facts

| Attribute | Value |
|-----------|-------|
| **Project Type** | Web Scraping System |
| **Language** | Python 3 |
| **Primary Purpose** | Scrape ISP broadband plans from 9 Australian providers |
| **Storage** | MySQL database + JSON files |
| **Core Methods** | REST APIs + Browser automation (Playwright) |
| **Main Entry** | `python main.py` (runs full pipeline) |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    MAIN ORCHESTRATOR                        │
│                      (main.py)                              │
└────────────────┬────────────────────────────────────────────┘
                 │
         ┌───────┴────────┐
         │                │
    ┌────▼─────┐    ┌─────▼───────┐
    │ API MODE │    │ RENDERER    │
    │ Scrapers │    │ (Playwright)│
    └────┬─────┘    └─────┬───────┘
         │                │
    ┌────▼────────────────▼─────┐
    │  VALIDATION & CLEANING    │
    │  (utils/validator.py)     │
    └────┬──────────────────────┘
         │
    ┌────▼─────────────────────┐
    │  DUAL STORAGE            │
    ├──────────────────────────┤
    │ MySQL (plans_current)    │
    │ JSON (output/plans.json) │
    │ LOGS (output/logs.json)  │
    └──────────────────────────┘
```

---

## ISP Providers (10 Total)

| Provider | ID | API Available | Status | Notes |
|----------|----|----|--------|-------|
| Telstra | 1 | ✓ | Enabled | Primary provider |
| Optus | 2 | ✓ | Enabled | API-first approach |
| Aussie Broadband | 3 | ✗ | Enabled | Cloudflare Turnstile blocks scraping |
| Superloop | 4 | ✓ | Enabled | Renderer fallback |
| Occom | 5 | ✓ | Enabled | Renders HTML for dynamic content |
| TPG | 6 | ✗ | Enabled | Renderer only |
| Exetel | 7 | ✗ | Enabled | Renderer only |
| Leaptel | 8 | ✗ | Enabled | Renderer only |
| iiNet | 9 | ✗ | Enabled | Renderer only |
| Swoop | 10 | ✗ | Enabled | 3 service types: NBN, Fixed Wireless, Opticomm |
| Swoop | 10 | ✗ | Enabled | 3 service types: NBN, Fixed Wireless, Opticomm |

---

## Key Modules & Entry Points

### Core Entry Points

| Module | Location | Key Functions | Purpose |
|--------|----------|----------------|---------|
| **Main Pipeline** | `main.py` | `run_all_scrapers()`, `main()` | Orchestrates all scrapers, validates, stores to DB/JSON |
| **Individual Providers** | `providers/*.py` | `scrape_[provider]_plans()` | API/renderer scraping for specific provider (10 total) |
| **Renderer Engine** | `scrapers/renderer.py` | `create_renderer_scraper()`, `scrape_all_sites()` | Playwright-based HTML rendering for JS-heavy sites |
| **Web Interface** | `app.py` | Flask routes | REST API and web dashboard |

### Utility Modules

| Module | Location | Key Functions | Purpose |
|--------|----------|----------------|---------|
| **Database** | `utils/db.py` | `create_connection()`, `insert_plans_batch()`, `create_table_if_not_exists()` | MySQL connection and data persistence |
| **Validation** | `utils/validator.py` | `validate_plans()`, `clean_plan_data()` | Plan data validation and cleaning |
| **Logging** | `utils/logger.py` | `log_info()`, `log_error()`, `log_success()`, `log_warning()` | JSON-based logging system |
| **HTML Parsing** | `utils/html_parser.py` | `parse_html()`, `extract_plans()` | HTML parsing utilities |
| **Stealth Mode** | `utils/stealth.py` | Anti-bot detection bypass | Playwright stealth plugin for bot detection evasion |
| **Benchmarking** | `utils/benchmark.py` | `run_benchmark()`, `save_benchmark_report()` | Performance metrics collection |

---

## Usage Scenarios

### 1. Run Complete Pipeline (All Providers)

```bash
cd c:\xampp\htdocs\scrape
python main.py
```

**Output**: 
- **API Providers** (Telstra, Optus, Superloop, Occom): Uses API endpoints first
- **Renderer-Only Providers** (TPG, Exetel, Leaptel, iiNet): Uses Playwright browser automation
- **Fallback Strategy**: If any provider API fails, automatically uses renderer as backup
- Validates and cleans data
- Stores to MySQL: `isp_plans.plans_current`
- Exports JSON: `output/plans.json`
- Logs all operations: `output/logs.json`

### 2. Scrape Individual Provider

```python
# Example: Scrape Telstra plans
from providers import telstra
plans = telstra.scrape_telstra_plans()
print(f"Found {len(plans)} plans")

# Example: Scrape Swoop plans (all 3 service types)
from providers import swoop
swoop_plans = swoop.scrape_swoop_plans()
print(f"Found {len(swoop_plans)} Swoop plans")

# Example: Scrape only Swoop NBN plans
nbn_only = swoop.scrape_swoop_nbn_plans()
print(f"NBN plans: {len(nbn_only)}")
```

Available providers: `telstra`, `optus`, `aussie`, `superloop`, `occom`, `tpg`, `exetel`, `leaptel`, `iinet`, `swoop`

### 3. Access Scraped Data from Database

```python
from utils.db import create_connection

conn = create_connection()
cursor = conn.cursor()
cursor.execute("SELECT plan_name, monthly_price FROM plans_current WHERE provider_id = 1 LIMIT 5")
results = cursor.fetchall()
for plan_name, price in results:
    print(f"{plan_name}: ${price}")
```

### 4. Add New Provider

```python
# Create file: providers/newprovider.py
def scrape_newprovider_plans():
    """
    Scrape plans from new provider.
    Returns: List of plan dicts with keys: plan_name, price, speed, network_type, source_url
    """
    plans = []
    # Implementation here
    return plans

# Add to config.py PROVIDERS dict:
'newprovider': {
    'id': 10,
    'name': 'New Provider',
    'enabled': True
}

# Import in main.py and call scraper
```

### 5. Run Web Interface

```bash
python app.py
# Visit http://localhost:5000
```

---

## Configuration Quick Reference

**File**: `config.py`

### Database Configuration
```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # Set your MySQL password
    'database': 'isp_plans',
    'port': 3306
}
```

### Key Settings
```python
OUTPUT_DIR = 'output'                    # Output directory for JSON files
PLANS_JSON_FILE = f'{OUTPUT_DIR}/plans.json'
LOGS_JSON_FILE = f'{OUTPUT_DIR}/logs.json'

PLAYWRIGHT_TIMEOUT = 30000               # 30 seconds
PLAYWRIGHT_WAIT_TIME = 2000              # 2 seconds

MAX_RETRIES = 3                          # Network retry attempts
RETRY_DELAY = 2                          # Seconds between retries
```

---

## Database Schema Summary

**Main Table**: `plans_current`

| Column | Type | Purpose |
|--------|------|---------|
| `provider_id` | INT | Foreign key to provider (1-10) |
| `plan_name` | VARCHAR(255) | Name of the plan |
| `network_type` | VARCHAR(50) | NBN/FTTP/HFC/etc. |
| `speed_label` | INT | Speed tier in Mbps (e.g., 50, 100, 250) |
| `download_speed` | INT | Actual download speed (Mbps) |
| `upload_speed` | INT | Actual upload speed (Mbps) |
| `monthly_price` | DECIMAL(10,2) | Regular price in AUD |
| `promo_price` | DECIMAL(10,2) | Promotional price (if applicable) |
| `contract_term` | VARCHAR(50) | e.g., "No Contract", "12 months" |
| `source_url` | TEXT | Where plan was scraped from |
| `last_checked` | DATETIME | Last verification timestamp |

**Unique Constraint**: `(provider_id, plan_name, speed_label)` prevents duplicates

**Indexes**: provider_id, monthly_price, speed_label, last_checked (for query optimization)

---

## Dependencies & Installation

### Install Python Packages
```bash
pip install -r requirements.txt
```

### Key Dependencies
```
requests>=2.31.0                    # HTTP requests
mysql-connector-python>=8.2.0       # MySQL database
playwright>=1.40.0                  # Headless browser automation
playwright-stealth>=2.0.0           # Anti-bot detection bypass
beautifulsoup4>=4.12.0              # HTML parsing
lxml>=4.9.0                         # XML/HTML processing
flask>=3.0.0                        # Web framework
```

### Install Playwright Browsers (Required)
```bash
playwright install
```

---

## Data Flow Summary

1. **Initiation**: `main.py` calls `run_all_scrapers()`
2. **API Scraping**: Each provider module (e.g., `telstra.scrape_telstra_plans()`) queries APIs
3. **Fallback Rendering**: Renderer uses Playwright for non-API providers or on API failure
4. **Data Validation**: `utils/validator.validate_plans()` cleans and validates all data
5. **Storage**: 
   - MySQL: `utils/db.insert_plans_batch()` 
   - JSON: `utils/save_json.save_plans_to_json()`
6. **Logging**: `utils/logger` writes all operations to `output/logs.json`
7. **Exports**: Plans available via database queries, REST API, or JSON file

---

## Common Tasks

| Task | Command/Code |
|------|---------|
| **View all logs** | `cat output/logs.json` or read JSON programmatically |
| **Query latest plans** | `SELECT * FROM plans_current ORDER BY last_checked DESC LIMIT 20` |
| **Check provider status** | Review `PROVIDERS` dict in `config.py` |
| **Run benchmarks** | `python benchmark_report.py` |
| **Export to CSV** | Use pandas on `output/plans.json` or database export |
| **Debug provider** | Run `python providers/[provider].py` directly (if has main block) |
| **Check renderer logs** | View `output/rendered_results.json` after renderer runs |

---

## Directory Structure

```
scrape/
├── main.py                    # Main orchestrator
├── app.py                     # Flask web interface
├── config.py                  # Configuration and constants
├── requirements.txt           # Python dependencies
├── database.sql              # Database schema
├── providers/                # Provider-specific scrapers (10 modules)
│   ├── telstra.py
│   ├── optus.py
│   ├── aussie.py
│   ├── superloop.py
│   ├── occom.py
│   ├── tpg.py
│   ├── exetel.py
│   ├── leaptel.py
│   ├── iinet.py
│   └── swoop.py              # Swoop: NBN, Fixed Wireless, Opticomm
├── scrapers/                 # Rendering engines
│   ├── renderer.py           # Playwright renderer
│   └── render_engine.py
├── utils/                    # Utility modules
│   ├── db.py                 # Database operations
│   ├── logger.py             # JSON logging
│   ├── validator.py          # Data validation
│   ├── html_parser.py        # HTML parsing
│   ├── stealth.py            # Bot detection bypass
│   ├── benchmark.py          # Performance metrics
│   └── save_json.py          # JSON export
├── output/                   # Generated files
│   ├── plans.json            # Scraped plans
│   ├── logs.json             # Operation logs
│   └── rendered_results.json  # Renderer debug output
└── templates/                # Flask templates (if used)
```

---

## Troubleshooting Quick Links

| Issue | Solution |
|-------|----------|
| **Database connection error** | Check DB_CONFIG in config.py, ensure MySQL is running |
| **Playwright not installed** | Run `playwright install` |
| **Provider blocked (Cloudflare)** | Use renderer fallback; Aussie Broadband known blocker |
| **Memory issues** | Reduce PLAYWRIGHT_TIMEOUT, use batch processing |
| **Slow scraping** | Check PLAYWRIGHT_WAIT_TIME, increase MAX_RETRIES |
| **No data output** | Check logs in `output/logs.json` for errors |

---

## Integration Points

- **REST API**: Exposed via `app.py` (Flask)
- **Database**: Direct MySQL connection via `utils/db.py`
- **JSON Export**: Plain JSON files in `output/`
- **Logging**: JSON structured logs for easy parsing
- **Extensions**: Add providers under `providers/`, utilities under `utils/`

---

**Last Updated**: May 2026 | **Scope**: Token-optimized reference guide | **Target**: LLM-friendly documentation
