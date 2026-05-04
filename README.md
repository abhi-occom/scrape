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
├── providers/                    # Provider-specific scrapers
│   ├── __init__.py
│   ├── aussie.py                # Aussie Broadband scraper
│   ├── occom.py                 # Occom scraper
│   ├── optus.py                 # Optus scraper
│   ├── superloop.py             # Superloop scraper
│   ├── telstra.py               # Telstra scraper
│   └── tpg.py                   # TPG scraper
├── scrapers/                     # Generic scraping utilities
│   ├── __init__.py
│   └── renderer.py              # Rendered HTML scraper orchestrator
├── utils/                        # Utility modules
│   ├── __init__.py
│   ├── alerts.py                # Automated price change & gap alert system
│   ├── benchmark.py             # Competitive price benchmarking engine
│   ├── db.py                    # Database operations (MySQL)
│   ├── discover_apis.py         # API endpoint discovery
│   ├── html_parser.py           # HTML parsing utilities
│   ├── logger.py                # JSON-based logging
│   ├── render_engine.py         # Playwright rendering engine
│   ├── save_json.py             # JSON file operations
│   ├── stealth.py               # Anti-detection utilities
│   └── validator.py             # Data validation and cleaning
├── templates/                    # Flask HTML templates
│   └── index.html               # Main scraper dashboard UI
├── output/                       # Output directory
│   ├── .gitkeep
│   ├── all_plans.json           # Combined plans from all providers
│   ├── all_plans.csv            # Combined plans CSV export
│   ├── benchmark_report.json    # Competitive benchmark report (JSON)
│   ├── benchmark_report.csv     # Benchmark report (CSV for marketing)
│   ├── benchmark_dashboard.html # Interactive benchmark dashboard
│   ├── logs.json                # JSON log file
│   ├── alerts.json              # Price change & gap alert history
│   ├── plans_snapshot.json      # Snapshot for diff-based alerts
│   ├── investigation/           # Investigation outputs
│   ├── stealth_test/            # Stealth test outputs
│   └── scrape_isp_<provider>/   # Per-provider scraped data (json/csv)
├── config.py                     # Configuration settings
├── database.sql                  # Database schema
├── main.py                       # Main pipeline orchestrator
├── app.py                        # Flask API server & dashboard backend
├── scraper_service.py            # Shared scraper service (CLI + API)
├── benchmark_report.py           # Benchmark report generator (JSON/CSV/HTML)
├── requirements.txt              # Python dependencies
├── README.md                     # This file
│
├── *_apis.json                   # API endpoint configs per provider
│   ├── all_provider_apis.json
│   ├── aussie_apis.json
│   ├── optus_apis.json
│   ├── superloop_apis.json
│   └── telstra_apis.json
│
├── investigate_*.py              # Investigation scripts per provider
│   ├── investigate_deep.py
│   ├── investigate_occom.py
│   ├── investigate_optus.py
│   ├── investigate_optus2.py
│   ├── investigate_sites.py
│   ├── investigate_superloop.py
│   ├── investigate_superloop_cards.py
│   ├── investigate_superloop_pages.py
│   ├── investigate_telstra_detail.py
│   ├── investigate_telstra_pages.py
│   ├── investigate_tpg.py
│   ├── investigate_tpg_deep.py
│   ├── investigate_vodafone.py
│   └── investigate_vodafone_deep.py
│
├── test_*.py                     # Test scripts
│   ├── test_optus.py
│   ├── test_render.py
│   ├── test_sample.py
│   ├── test_stealth.py
│   ├── test_superloop.py
│   ├── test_telstra.py
│   └── test_tpg.py
│
├── analyze_optus.py              # Optus analysis script
├── debug_telstra.py              # Telstra debug script
├── show_output.py                # Output display utility
└── update_output.py              # Output update utility
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
