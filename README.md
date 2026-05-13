# ISP Plan Scraping System

A production-ready ISP plan scraping system that extracts plan data from multiple Australian internet service providers using both API-based and rendered HTML scraping approaches.

## Features

- **Multi-Provider Support**: Scrapes from Telstra, Optus, Aussie Broadband, Superloop, and Occom
- **Hybrid Scraping Approach**: 
  - API-first scraping for providers with available APIs
  - Playwright-based rendered HTML scraping for dynamic JavaScript-heavy websites
  - Automatic fallback mechanisms when API access fails
- **Advanced Rendering Engine**: 
  - Headless browser automation with Playwright
  - JavaScript execution and dynamic content rendering
  - Pagination support for multi-page scraping
  - Configurable wait times and selectors
- **Dual Storage System**: 
  - MySQL database for structured storage
  - JSON file export for easy data access and backup
- **Comprehensive Data Validation**: 
  - Automatic validation of plan names, prices, and speeds
  - Data cleaning and normalization
  - Invalid record detection and logging
- **JSON-Based Logging**: 
  - All operations logged to JSON format (not database)
  - Detailed timestamps, status codes, and error messages
  - Easy log analysis and debugging
- **Modular Architecture**: 
  - Clean separation of concerns (providers, scrapers, utils)
  - Reusable components and utilities
  - Easy to extend with new providers
- **Robust Error Handling**: 
  - Isolated provider scrapers (failures don't crash entire system)
  - Retry logic for network requests
  - Graceful degradation and fallback strategies
  - Comprehensive error logging and reporting

## Installation

### 1. Install Python Dependencies

```bash
cd scrape
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install
```

### 3. Configure Database

Update the database configuration in `config.py`:

```python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your_password',
    'database': 'isp_plans',
    'port': 3306
}
```

### 4. Create Database

```sql
CREATE DATABASE isp_plans;
```

## Usage

### Run the Complete Pipeline

```bash
python main.py
```

This will:
1. Initialize the database connection and create tables if needed
2. Scrape all enabled providers (API-based scraping)
3. Run rendered HTML scraper for JavaScript-heavy sites
4. Validate and clean all scraped data
5. Save validated plans to MySQL database
6. Export plans to JSON file (`output/plans.json`)
7. Log all operations to JSON log file (`output/logs.json`)

### Run Individual Provider Scrapers

```python
from providers import telstra

plans = telstra.scrape_telstra_plans()
```

### Run Rendered HTML Scraper

```python
from scrapers.renderer import RendererScraper, SiteConfig

scraper = RendererScraper(headless=True)
site_config = SiteConfig(
    name="telstra",
    base_url="https://www.telstra.com.au/internet/home-nbn",
    selectors={
        'plan_name': '.plan-name',
        'price': '.price',
        'speed': '.speed'
    },
    wait_selector=".plan-card",
    wait_time=2000,
    max_pages=5
)

plans = scraper.scrape_site(site_config)
```

### Test Stealth Mode

```bash
python test_stealth.py
```

### View Output

```bash
python show_output.py
```

## Project Structure

```
scrape/
│
├── providers/                         # Provider-specific scraper modules
│   ├── __init__.py
│   ├── aussie.py                      # Aussie Broadband scraper
│   ├── exetel.py                      # Exetel scraper
│   ├── iinet.py                       # iiNet scraper
│   ├── leaptel.py                     # Leaptel scraper
│   ├── occom.py                       # Occom scraper
│   ├── optus.py                       # Optus scraper
│   ├── superloop.py                   # Superloop scraper
│   ├── telstra.py                     # Telstra scraper
│   └── tpg.py                         # TPG scraper
│
├── scrapers/                          # Generic scraping engine
│   ├── __init__.py
│   └── renderer.py                    # Playwright-based rendered HTML scraper
│
├── utils/                             # Shared utility modules
│   ├── __init__.py
│   ├── alerts.py                      # Automated price change & gap alert system
│   ├── benchmark.py                   # Competitive price benchmarking engine
│   ├── db.py                          # MySQL database operations
│   ├── discover_apis.py               # API endpoint discovery helper
│   ├── html_parser.py                 # HTML parsing utilities
│   ├── logger.py                      # JSON-based structured logging
│   ├── render_engine.py               # Playwright rendering engine wrapper
│   ├── save_json.py                   # JSON file read/write operations
│   ├── stealth.py                     # Anti-bot-detection & stealth utilities
│   └── validator.py                   # Plan data validation and cleaning
│
├── templates/                         # Flask HTML templates
│   └── index.html                     # Main scraper dashboard UI
│
├── output/                            # All generated output files
│   ├── .gitkeep
│   ├── all_plans.json                 # Combined plans from all providers
│   ├── all_plans.csv                  # Combined plans CSV export
│   ├── benchmark_dashboard.html       # Interactive benchmark dashboard (HTML)
│   ├── benchmark_report.json          # Competitive benchmark report (JSON)
│   ├── benchmark_report.csv           # Benchmark report (CSV)
│   ├── roi_calculator.html            # ROI calculator output (HTML)
│   ├── logs.json                      # Aggregated JSON log file
│   │
│   ├── investigation/                 # Per-provider investigation HTML snapshots
│   │   ├── aussie.html / aussie.png
│   │   ├── aussie_5g_cffi.html
│   │   ├── aussie_nbn_cffi.html
│   │   ├── aussie_nbn_headed.html
│   │   ├── aussie_wireless_cffi.html
│   │   ├── exetel_fibre_upgrade.html / _selectors.json
│   │   ├── exetel_mobile.html / _selectors.json
│   │   ├── exetel_nbn.html / _selectors.json
│   │   ├── occom.html / occom.png
│   │   ├── superloop.html / superloop.png
│   │   ├── superloop_nbn.html / superloop_nbn.png
│   │   ├── telstra.html / telstra.png
│   │   ├── tpg_5g_home.html
│   │   ├── tpg_fibre_upgrade.html
│   │   ├── tpg_fttb.html
│   │   ├── tpg_home_wireless.html
│   │   ├── tpg_nbn.html
│   │   ├── vodafone_4g_5g.html
│   │   ├── vodafone_nbn.html
│   │   ├── vodafone_opticomm.html
│   │   └── vodafone_super_wifi.html
│   │
│   ├── stealth_test/                  # Stealth mode test screenshots & HTML
│   │   ├── aussie.html / aussie.png
│   │   ├── superloop.html / superloop.png
│   │   └── telstra.html / telstra.png
│   │
│   ├── scrape_isp_aussie/             # Aussie Broadband scraped data
│   │   ├── json/
│   │   └── csv/
│   ├── scrape_isp_exetel/             # Exetel scraped data
│   │   ├── json/
│   │   └── csv/
│   ├── scrape_isp_iinet/              # iiNet scraped data
│   │   ├── json/
│   │   └── csv/
│   ├── scrape_isp_leaptel/            # Leaptel scraped data
│   │   ├── json/
│   │   └── csv/
│   ├── scrape_isp_occom/              # Occom scraped data
│   │   ├── json/
│   │   └── csv/
│   ├── scrape_isp_optus/              # Optus scraped data
│   │   ├── json/
│   │   └── csv/
│   ├── scrape_isp_superloop/          # Superloop scraped data
│   │   ├── json/
│   │   └── csv/
│   ├── scrape_isp_telstra/            # Telstra scraped data
│   │   ├── json/
│   │   └── csv/
│   └── scrape_isp_tpg/               # TPG scraped data
│       ├── json/
│       └── csv/
│
├── *_apis.json                        # Discovered API endpoint configs per provider
│   ├── all_provider_apis.json         # Consolidated API endpoints (all providers)
│   ├── aussie_apis.json               # Aussie Broadband API endpoints
│   ├── optus_apis.json                # Optus API endpoints
│   ├── superloop_apis.json            # Superloop API endpoints
│   └── telstra_apis.json              # Telstra API endpoints
│
├── investigate_*.py                   # Provider website investigation scripts
│   ├── investigate_deep.py            # Deep site structure analysis
│   ├── investigate_exetel.py          # Exetel investigation (v1)
│   ├── investigate_exetel2.py         # Exetel investigation (v2)
│   ├── investigate_exetel3.py         # Exetel investigation (v3)
│   ├── investigate_iinet.py           # iiNet investigation
│   ├── investigate_leaptel.py         # Leaptel investigation
│   ├── investigate_occom.py           # Occom investigation
│   ├── investigate_optus.py           # Optus investigation (v1)
│   ├── investigate_optus2.py          # Optus investigation (v2)
│   ├── investigate_sites.py           # Multi-site structure analysis
│   ├── investigate_superloop.py       # Superloop investigation
│   ├── investigate_superloop_cards.py # Superloop plan cards investigation
│   ├── investigate_superloop_pages.py # Superloop pagination investigation
│   ├── investigate_telstra_detail.py  # Telstra plan detail investigation
│   ├── investigate_telstra_pages.py   # Telstra pagination investigation
│   ├── investigate_tpg.py             # TPG investigation (v1)
│   ├── investigate_tpg_deep.py        # TPG deep investigation
│   ├── investigate_vodafone.py        # Vodafone investigation
│   └── investigate_vodafone_deep.py   # Vodafone deep investigation
│
├── probe_iinet*.py                    # iiNet connection/endpoint probe scripts
│   ├── probe_iinet.py                 # iiNet probe (v1)
│   ├── probe_iinet2.py                # iiNet probe (v2)
│   ├── probe_iinet3.py                # iiNet probe (v3)
│   ├── probe_iinet4.py                # iiNet probe (v4)
│   ├── probe_iinet5.py                # iiNet probe (v5)
│   ├── probe_iinet6.py                # iiNet probe (v6)
│   ├── probe_iinet7.py                # iiNet probe (v7)
│   └── probe_iinet8.py                # iiNet probe (v8)
│
├── test_*.py                          # Provider-specific test scripts
│   ├── test_exetel.py                 # Exetel scraper test
│   ├── test_iinet.py                  # iiNet scraper test
│   ├── test_optus.py                  # Optus scraper test
│   ├── test_render.py                 # Rendering engine test
│   ├── test_sample.py                 # Sample/generic scraper test
│   ├── test_stealth.py                # Stealth mode test
│   ├── test_superloop.py              # Superloop scraper test
│   ├── test_telstra.py                # Telstra scraper test
│   └── test_tpg.py                    # TPG scraper test
│
├── app.py                             # Flask API server & dashboard backend
├── main.py                            # Main pipeline orchestrator
├── scraper_service.py                 # Shared scraper service (CLI + API)
├── config.py                          # Global configuration settings
├── database.sql                       # MySQL database schema
├── requirements.txt                   # Python package dependencies
├── benchmark_report.py                # Benchmark report generator (JSON/CSV/HTML)
├── roi_calculator.py                  # ROI calculator script
├── check_providers.py                 # Provider availability checker
├── analyze_optus.py                   # Optus-specific analysis script
├── debug_telstra.py                   # Telstra scraper debug script
├── fix_iinet_indent.py                # iiNet data indentation fixer utility
├── show_output.py                     # CLI output display utility
├── update_output.py                   # Output files update utility
├── problems_faced.md                  # Known issues & problems log
└── README.md                          # This file
```

## Database Schema

### Table: `plans_current`

| Column | Type | Description |
|--------|------|-------------|
| provider_id | INT | Provider identifier (1=Telstra, 2=Optus, 3=Aussie, 4=Superloop, 5=Occom) |
| plan_name | VARCHAR(255) | Name of the ISP plan |
| network_type | VARCHAR(50) | Network technology (NBN, FTTP, HFC, etc.) |
| speed_label | INT | Speed tier label in Mbps |
| download_speed | INT | Download speed in Mbps |
| upload_speed | INT | Upload speed in Mbps |
| monthly_price | DECIMAL(10,2) | Regular monthly price in AUD |
| promo_price | DECIMAL(10,2) | Promotional price in AUD |
| promo_period | VARCHAR(50) | Promotional period (e.g., "6 months") |
| contract_term | VARCHAR(50) | Contract duration (e.g., "No Contract", "12 months") |
| source_url | TEXT | Source URL where the plan was scraped from |
| last_checked | DATETIME | Timestamp of last data verification |

**Unique Key**: (provider_id, plan_name, speed_label)

**Indexes**: provider_id, monthly_price, speed_label, last_checked

### Table: `providers`

| Column | Type | Description |
|--------|------|-------------|
| provider_id | INT | Primary key |
| provider_name | VARCHAR(100) | Provider name |
| website_url | VARCHAR(255) | Provider website URL |
| active | BOOLEAN | Whether provider is active |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

## Provider IDs

- **Telstra**: 1
- **Optus**: 2
- **Aussie Broadband**: 3
- **Superloop**: 4
- **Occom**: 5

## Data Validation Rules

All plans must pass the following validation checks:

- ✅ **plan_name**: Must exist and be a non-empty string
- ✅ **price**: Must exist and be a valid positive number (checks `price`, `monthly_price` fields)
- ✅ **speed**: Must exist and be a valid positive integer (checks `speed`, `speed_label`, `download_speed` fields)

**Validation Process**:
1. Check required fields exist
2. Validate data types and formats
3. Check for negative values
4. Clean and normalize data
5. Invalid records are logged with error messages and excluded from output

## Logging System

All logs are stored in `output/logs.json` with the following structure:

```json
{
  "timestamp": "2026-04-20T10:30:00",
  "status": "success|error|warning|info",
  "message": "Description of the event",
  "provider": "provider_name",
  "data": {}
}
```

**Log Levels**:
- **success**: Successful operations (e.g., "Scraped 15 plans from Telstra")
- **error**: Errors and exceptions (e.g., "Failed to connect to database")
- **warning**: Warnings and non-critical issues (e.g., "Invalid plan data skipped")
- **info**: Informational messages (e.g., "Starting pipeline execution")

## Error Handling

The system implements multiple layers of error handling:

- **Provider Isolation**: Each provider scraper runs independently (failures don't crash the entire pipeline)
- **Retry Logic**: Automatic retries for network requests with exponential backoff
- **Graceful Fallbacks**: 
  - API → Playwright scraping fallback
  - Rendered HTML → Static HTML parsing fallback
- **Validation Errors**: Invalid data is logged and skipped, not crashed
- **Database Errors**: Connection pooling and automatic reconnection
- **Browser Errors**: Playwright timeout handling and browser restart
- **Comprehensive Logging**: All errors logged with stack traces and context

## Customization

### Adding a New Provider

1. **Create Provider Scraper**: Create a new file in `providers/` directory (e.g., `newprovider.py`)
2. **Implement Scraper Function**: Implement the `scrape_<provider>_plans()` function
3. **Add Configuration**: Add provider configuration to `config.py` in the `PROVIDERS` dictionary
4. **Update Main Pipeline**: Import and add to the scrapers list in `main.py`
5. **Add API JSON** (optional): Add `<provider>_apis.json` if API-based scraping is available
6. **Test**: Create debug script (e.g., `debug_<provider>.py`) for testing

### Modifying Selectors for Rendered Scraping

Update the CSS selectors in the `SiteConfig` for each site in `main.py` or your custom scraper:

```python
SiteConfig(
    name="provider_name",
    base_url="https://provider.com/plans",
    selectors={
        'plan_name': '.plan-title, h2[class*="plan"]',
        'price': '.price, [class*="price"]',
        'speed': '.speed, [class*="speed"]'
    },
    wait_selector=".plan-card",
    wait_time=2000,
    max_pages=5
)
```

### Adding Custom Utilities

1. Create new module in `utils/` directory
2. Import in your scrapers as needed
3. Follow existing utility patterns (logging, error handling, etc.)

### Configuring Stealth Mode

Update stealth settings in `utils/stealth.py` to avoid detection:

- User-Agent rotation
- Browser fingerprinting
- Request timing randomization
- Header customization

## Notes

- **API Endpoints**: API URLs in `<provider>_apis.json` files are discovered through investigation scripts. Update them with actual endpoints as needed.
- **Website Changes**: Provider websites may change their structure. Update Playwright selectors and CSS selectors accordingly.
- **Rate Limiting**: The system includes basic delays, but consider adding more sophisticated rate limiting to avoid being blocked.
- **Browser Resources**: Playwright requires browser binaries. Install with `playwright install` command.
- **Memory Usage**: Rendering multiple pages can be memory-intensive. Adjust `max_pages` and run in headless mode for production.
- **Database Maintenance**: Regularly archive old data and maintain database indexes for optimal performance.
- **Investigation Scripts**: Use the `investigate_*.py` scripts to analyze new provider websites and discover APIs.

## Troubleshooting

### Common Issues

**Playwright Browser Not Found**:
```bash
playwright install
```

**Database Connection Failed**:
- Check MySQL credentials in `config.py`
- Ensure MySQL server is running
- Verify database `isp_plans` exists

**No Plans Scraped**:
- Check website structure has changed
- Update CSS selectors in provider scrapers
- Increase `wait_time` in SiteConfig
- Check browser console for JavaScript errors

**Stealth Mode Issues**:
- Run `test_stealth.py` to verify stealth settings
- Update User-Agent strings
- Adjust request timing

### Debug Scripts

Use the debug scripts to test individual providers:
- `debug_telstra.py` - Test Telstra scraping
- `investigate_sites.py` - Analyze website structure
- `show_output.py` - View scraped output
- `test_render.py` - Test rendering engine

## License

MIT License
