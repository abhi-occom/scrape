# ISP Scraper - Visual Diagrams & Flowcharts

## 🎯 System Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                          END-USER BROWSER                              │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │              Dashboard: http://localhost:5000                    │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │                                                                  │  │
│  │  LEFT PANEL              │         RIGHT PANEL                  │  │
│  │  ─────────────────────────────────────────────────────────────  │  │
│  │                          │                                       │  │
│  │  [Provider List]         │  [Results Table]                    │  │
│  │  ─────────────────────────────────────────────────────────────  │  │
│  │  ☑ Telstra [Scrape]      │  Plan Name | Network | Price        │  │
│  │  ☐ Optus   [Scrape]      │  ──────────┴────────┴────────────   │  │
│  │  ☐ Aussie  [Scrape]      │  Telstra 25 NBN   89.00             │  │
│  │  ☐ Superloop             │  Telstra 50 NBN   99.00             │  │
│  │                          │  Telstra 100 NBN  109.00            │  │
│  │  [Debug Options]         │                                       │  │
│  │  ─────────────────────   │  [Filter & Sort]                    │  │
│  │  ☑ Show browser while    │  Network: [All ▼]                   │  │
│  │    scraping              │  Price: $0 - $200                   │  │
│  │  Slow motion:            │  Speed: 0 - 300 Mbps                │  │
│  │  [500 ms ▼]              │  [Reset Filters]                    │  │
│  │                          │                                       │  │
│  │  [Scrape All]            │  [📥 Download JSON]                 │  │
│  │  [Load Data]             │  [📥 Download CSV]                  │  │
│  │  [🔧 Run Benchmark]      │                                       │  │
│  │                          │                                       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘

         ↓ POST /api/scrape/telstra {visible_browser: true, slow_mo: 500}

┌────────────────────────────────────────────────────────────────────────┐
│                      FLASK SERVER (Python)                             │
│                                                                         │
│  app.py                                                                │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ @app.route('/api/scrape/<provider_name>', methods=['POST'])      │  │
│  │                                                                  │  │
│  │ → get_scrape_options()                                          │  │
│  │   └─ Extract: visible_browser=true, slow_mo=500                 │  │
│  │                                                                  │  │
│  │ → scraper_service.scrape_provider('telstra', options)           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  scraper_service.py                                                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ configure_browser(headless=False, slow_mo=500)                  │  │
│  │   └─ Sets global browser config                                 │  │
│  │                                                                  │  │
│  │ import providers.telstra                                        │  │
│  │ plans = telstra.scrape_telstra_plans()                          │  │
│  │   └─ Returns: [20 plans]                                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘

         ↓ Browser Launch Signal

┌────────────────────────────────────────────────────────────────────────┐
│                  PLAYWRIGHT BROWSER (Python)                           │
│                                                                         │
│  utils/stealth.py                                                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ create_stealth_browser()                                         │  │
│  │   ├─ playwright.chromium.launch(headless=False)                  │  │
│  │   ├─ Apply stealth args (remove --headless, etc)                 │  │
│  │   ├─ Custom User-Agent                                          │  │
│  │   ├─ Custom headers                                             │  │
│  │   └─ 👀 CHROMIUM WINDOW OPENS ON DESKTOP                       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  providers/telstra.py                                                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ For page_key in ['plans', '5g_home', 'starlink', ...]:          │  │
│  │                                                                  │  │
│  │   page = browser.new_page()                                     │  │
│  │   page.goto(url)  ← slow_mo: 500ms per action                   │  │
│  │   page.wait_for_timeout(6000)  ← Wait for render                │  │
│  │   page.screenshot()  ← Capture proof                            │  │
│  │   extract_plans_from_page(page)  ← CSS selectors                │  │
│  │   page.close()                                                  │  │
│  │                                                                  │  │
│  │   Plans extracted: 20 total                                     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘

         ↓ Data & Screenshots

┌────────────────────────────────────────────────────────────────────────┐
│                    DATA PROCESSING (Python)                            │
│                                                                         │
│  utils/validator.py                                                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ validate_plans([20 plans])                                       │  │
│  │   ├─ Check: plan_name exists                                    │  │
│  │   ├─ Check: price > 0                                           │  │
│  │   ├─ Check: speed is integer                                    │  │
│  │   └─ Result: [20 valid, 0 invalid]                              │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  scraper_service.py - save_output()                                    │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Save to 4 formats:                                               │  │
│  │                                                                  │  │
│  │ A. JSON: output/scrape_isp_telstra/json/                        │  │
│  │    [{plan_name: "...", price: 89.0, ...}, ...]                  │  │
│  │                                                                  │  │
│  │ B. CSV: output/scrape_isp_telstra/csv/                          │  │
│  │    provider,plan_name,price,...                                 │  │
│  │    Telstra,Telstra 25 NBN,89.0,...                              │  │
│  │                                                                  │  │
│  │ C. MySQL: INSERT into plans_current                             │  │
│  │    (provider_id, plan_name, price, speed, ...)                  │  │
│  │                                                                  │  │
│  │ D. Log: output/logs.json                                        │  │
│  │    {status: "success", plans: 20, ...}                          │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘

         ↓ Response

┌────────────────────────────────────────────────────────────────────────┐
│                    FRONTEND UPDATES (JavaScript)                       │
│                                                                         │
│  ✅ Timer: "Completed in 45s"                                          │
│  ✅ Stats: 1 provider, 20 plans, $89-$199, 25-300 Mbps                │
│  ✅ Results: Table with all 20 plans                                   │
│  ✅ Filters: Network, price, speed options                             │
│  ✅ Downloads: JSON, CSV buttons active                                │
│  ✅ Screenshots: 5 PNG images in output/screenshots/                   │
│                                                                         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Checkbox Configuration Flow

```
┌─────────────────────────────────────────────────────┐
│  USER OPENS DASHBOARD: http://localhost:5000        │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│  JavaScript: checkCapabilities()                     │
│  Calls: GET /api/capabilities                       │
└─────────────────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────────────────┐
│  Backend: app.py                                     │
│  Checks:                                            │
│  ├─ Platform: Windows / Linux / Mac?               │
│  ├─ Xvfb installed? (Linux only)                   │
│  └─ DISPLAY env var? (Linux only)                  │
└─────────────────────────────────────────────────────┘
              ↓
      ┌──────┴──────┬───────────┐
      ↓             ↓           ↓
   WINDOWS       MAC          LINUX
     │            │              │
     ├─Yes   ├─Yes        ┌──Xvfb?──┐
     │       │            ├─Yes ├─No
     ↓       ↓            ↓     ↓
   ✅      ✅           ✅    ❌
  ENABLED  ENABLED      ENABLED DISABLED
   │        │           │        │
   └────┬───┘           │        │
        │               └────┬───┘
        └───────────┬────────┘
                    ↓
        ┌──────────────────────────────┐
        │   Checkbox Status Set         │
        ├──────────────────────────────┤
        │  ☑ ENABLED  (can be checked) │
        │  ☐ DISABLED (greyed out)     │
        └──────────────────────────────┘
                    ↓
        ┌──────────────────────────────┐
        │  User Configuration           │
        ├──────────────────────────────┤
        │  IF enabled:                  │
        │  ├─ Can CHECK ☑               │
        │  └─ Can select slow_mo        │
        │                              │
        │  IF disabled:                 │
        │  └─ Shows warning ⚠️          │
        └──────────────────────────────┘
                    ↓
        ┌──────────────────────────────┐
        │  User Clicks "Scrape"         │
        └──────────────────────────────┘
                    ↓
        ┌──────────────────────────────┐
        │  Frontend Collects Options    │
        ├──────────────────────────────┤
        │  visible_browser:             │
        │  ├─ true  (☑ checked)        │
        │  └─ false (☐ unchecked)      │
        │                              │
        │  slow_mo:                     │
        │  ├─ 0    (Off)               │
        │  ├─ 100  (100 ms)            │
        │  ├─ 250  (250 ms)            │
        │  ├─ 500  (500 ms) ← Recommended
        │  └─ 1000 (1000 ms)           │
        └──────────────────────────────┘
                    ↓
        ┌──────────────────────────────┐
        │  POST /api/scrape/telstra    │
        │  {                           │
        │    visible_browser: true,    │
        │    slow_mo: 500              │
        │  }                           │
        └──────────────────────────────┘
                    ↓
        ┌──────────────────────────────┐
        │  configure_browser()          │
        │  ├─ headless = False          │
        │  │  (visible, not headless)  │
        │  └─ slow_mo = 500             │
        │     (500ms per action)        │
        └──────────────────────────────┘
                    ↓
        ┌──────────────────────────────┐
        │  👀 BROWSER OPENS             │
        │  Chromium on Desktop         │
        └──────────────────────────────┘
```

---

## 🔄 Complete Scraping Loop (Telstra Example)

```
ITERATION 1: Plans Page
─────────────────────────────────────────
URL: https://www.telstra.com.au/internet/plans

page = browser.new_page()
    ↓
page.goto(url)  [slow_mo: 500ms per action]
    ↓
👀 YOU SEE IN BROWSER:
    Address bar shows: telstra.com.au/internet/plans
    HTML starts loading
    CSS applies
    JavaScript executes
    Plan cards appear one by one
    Prices render
    Network types show
    ↓
page.wait_for_timeout(6000)  [Wait 6 seconds]
    ↓
✅ PAGE FULLY LOADED
    ↓
page.query_selector_all('h3.tcom-fixed-plan-card-header__headline')
    ↓
    Match: [5 plan headers]
        ├─ "Telstra 25 NBN Plan"
        ├─ "Telstra 50 NBN Plan"
        ├─ "Telstra 100 NBN Plan"
        ├─ "Telstra 300 NBN Plan"
        └─ "Online Exclusive Plan"
    ↓
page.query_selector_all('[data-fixed-plan-card-price]')
    ↓
    Match: [5 prices]
        ├─ 89.00
        ├─ 99.00
        ├─ 109.00
        ├─ 199.00
        └─ (promotional)
    ↓
[Similar queries for download_speed, upload_speed]
    ↓
BUILD PLANS:
    [
        {plan_name: "Telstra 25 NBN Plan", price: 89.0, download_speed: 25, ...},
        {plan_name: "Telstra 50 NBN Plan", price: 99.0, download_speed: 50, ...},
        {plan_name: "Telstra 100 NBN Plan", price: 109.0, download_speed: 100, ...},
        {plan_name: "Telstra 300 NBN Plan", price: 199.0, download_speed: 300, ...},
        {plan_name: "Online Exclusive Plan", price: 79.0, download_speed: 25, ...}
    ]
    ↓
    PLANS EXTRACTED: 5
    ↓
page.screenshot(path='output/screenshots/telstra_plans_2024-01-20T10:30:00.png')
    ↓
    📸 SCREENSHOT SAVED (proof of page)
    ↓
page.close()


ITERATION 2: 5G Home Page
─────────────────────────────────────────
URL: https://www.telstra.com.au/internet/5g-home-internet

[Same process as above]
    → Extract: 1 plan
    → Screenshot: telstra_5g_home_2024-01-20T10:30:15.png


ITERATION 3: Starlink Page
─────────────────────────────────────────
[Same process]
    → Extract: 1 plan
    → Screenshot: telstra_starlink_2024-01-20T10:30:30.png


ITERATION 4: Opticomm Page
─────────────────────────────────────────
[Same process]
    → Extract: 8 plans
    → Screenshot: telstra_opticomm_2024-01-20T10:30:45.png


ITERATION 5: Small Business Page
─────────────────────────────────────────
[Same process]
    → Extract: 5 plans
    → Screenshot: telstra_business_2024-01-20T10:31:00.png


MERGE ALL PAGES:
─────────────────────────────────────────
total_plans = 5 + 1 + 1 + 8 + 5 = 20

[
    {from page 1}, {from page 1}, ... (5 total)
    {from page 2} (1 total)
    {from page 3} (1 total)
    {from page 4}, {from page 4}, ... (8 total)
    {from page 5}, {from page 5}, ... (5 total)
]

RETURN: all_plans = [20 plans]
```

---

## 💾 Data Storage Flow

```
VALIDATED PLANS
    [20 plans]
        ↓
    ┌───────────────────────────────────────┐
    │  SAVE TO 4 DIFFERENT FORMATS           │
    └───────────────────────────────────────┘
        ↓
    ┌──────────┬──────────┬──────────┬──────────┐
    ↓          ↓          ↓          ↓
   JSON      CSV      MySQL      LOG
    │          │          │          │
    ↓          ↓          ↓          ↓

A. JSON FILE
───────────────────────────────────────────
output/scrape_isp_telstra/json/telstra_all_plans.json

[
  {
    "plan_name": "Telstra 25 NBN Plan",
    "network_type": "NBN",
    "download_speed": 25,
    "upload_speed": 1,
    "price": 89.0,
    "promo_price": null,
    "contract": "No Lock-in",
    "source_url": "https://www.telstra.com.au/internet/plans",
    "provider_id": 1,
    "last_checked": "2024-01-20T10:30:00"
  },
  { ... 19 more plans ... }
]


B. CSV FILE
───────────────────────────────────────────
output/scrape_isp_telstra/csv/telstra_all_plans.csv

provider,plan_name,network_type,download_speed,upload_speed,price,promo_price,contract,source_url
Telstra,Telstra 25 NBN Plan,NBN,25,1,89.0,,No Lock-in,https://www.telstra.com.au/internet/plans
Telstra,Telstra 50 NBN Plan,NBN,50,2,99.0,,No Lock-in,https://www.telstra.com.au/internet/plans
Telstra,Telstra 100 NBN Plan,NBN,100,2,109.0,,No Lock-in,https://www.telstra.com.au/internet/plans
... (20 rows total)


C. MYSQL DATABASE
───────────────────────────────────────────
Table: plans_current

INSERT INTO plans_current 
  (provider_id, plan_name, network_type, download_speed, upload_speed, monthly_price, contract, source_url, last_checked)
VALUES
  (1, 'Telstra 25 NBN Plan', 'NBN', 25, 1, 89.0, 'No Lock-in', '...', NOW()),
  (1, 'Telstra 50 NBN Plan', 'NBN', 50, 2, 99.0, 'No Lock-in', '...', NOW()),
  (1, 'Telstra 100 NBN Plan', 'NBN', 100, 2, 109.0, 'No Lock-in', '...', NOW()),
  ... (20 rows total)


D. LOG FILE
───────────────────────────────────────────
output/logs.json

{
  "timestamp": "2024-01-20T10:31:15",
  "status": "success",
  "message": "Retrieved 20 plans from telstra",
  "provider": "telstra",
  "data": {
    "plan_count": 20,
    "pages_scraped": 5,
    "duration_seconds": 75,
    "screenshots": 5
  }
}
```

---

## 🎨 Dashboard State Changes

```
BEFORE SCRAPING:
┌──────────────────────────────────────┐
│ Results Panel                        │
├──────────────────────────────────────┤
│                                      │
│  Select a provider and click "Scrape"│
│  or "Load Saved Data"                │
│                                      │
│  [Stats Cards - Hidden]              │
│  [Filter Bar - Hidden]               │
│  [Results Table - Empty]             │
│                                      │
└──────────────────────────────────────┘


DURING SCRAPING (Progress):
┌──────────────────────────────────────┐
│ Results Panel                        │
├──────────────────────────────────────┤
│                                      │
│ ⏱ Scraping in progress…             │
│ [Timer: 00:25]                       │
│                                      │
│ Live scrape progress        Running  │
│ Provider:  TELSTRA                   │
│ URL:       telstra.com.../plans      │
│ Plans Found: 5                       │
│ Providers Done: 1 / 1                │
│                                      │
│ Events:                              │
│ ✓ TELSTRA started                   │
│ ✓ TELSTRA extracted 5 plans          │
│ ... (more events)                    │
│                                      │
│ [Loading Spinner]                    │
│ Scraping in progress…                │
│                                      │
└──────────────────────────────────────┘


AFTER SCRAPING (Success):
┌──────────────────────────────────────┐
│ Results Panel                        │
├──────────────────────────────────────┤
│                                      │
│ ✅ Completed in 45s                  │
│ [Timer: 00:45]                       │
│                                      │
│ [Stats Cards - Visible]              │
│ ┌─────────┐ ┌─────────┐              │
│ │Providers│ │  Plans  │              │
│ │   1     │ │   20    │              │
│ └─────────┘ └─────────┘              │
│ ┌─────────┐ ┌─────────┐              │
│ │  Price  │ │ Speed   │              │
│ │89-199/mo│ │25-300 M │              │
│ └─────────┘ └─────────┘              │
│                                      │
│ [Filter & Sort Bar - Visible]        │
│ Network: [All ▼]  Price: $__-$__     │
│ Speed: __-__ Mbps [Reset]            │
│                                      │
│ [Results Table - Visible]            │
│ | Plan Name     | Network | Price   │
│ |─────────────────────────────────|  │
│ | Telstra 25... |   NBN   |  $89   │
│ | Telstra 50... |   NBN   |  $99   │
│ | ... 18 more   |         |        │
│                                      │
│ [Download Buttons - Visible]         │
│ [📥 Download JSON] [📥 Download CSV]│
│                                      │
└──────────────────────────────────────┘
```

---

## 📈 Error Flow (If Something Goes Wrong)

```
SCRAPING STARTS
    ↓
IF page.goto() fails:
    ├─ Network error?
    ├─ URL invalid?
    ├─ Timeout (30 seconds)?
    └─ Exception caught
        ↓
        Log error: {"status": "error", "message": "...", ...}
        ↓
        Continue to next page
        ↓


IF selectors don't match:
    ├─ No elements found (0 plans)
    ├─ Website structure changed?
    ├─ CSS selector outdated?
    └─ Log warning: "No plans extracted from page"
        ↓
        Continue scraping


IF validation fails:
    ├─ plan_name missing
    ├─ price <= 0
    ├─ speed not numeric
    └─ Plan marked as invalid
        ↓
        Logged but not saved
        ↓


IF database insert fails:
    ├─ MySQL connection error?
    ├─ Duplicate unique key?
    ├─ Field too long?
    └─ Fallback: Save to JSON/CSV only
        ↓


RECOVERY:
    ├─ All errors logged to output/logs.json
    ├─ Errors don't stop entire pipeline
    ├─ Other providers continue scraping
    ├─ Partial results still valid
    └─ User can retry failed provider


FINAL RESULT:
    ├─ Some providers succeed
    ├─ Some providers fail
    ├─ Dashboard shows partial results
    ├─ Logs explain what failed
    └─ User can fix and re-run
```

---

## 🔄 Visible Browser vs Headless Comparison

```
VISIBLE BROWSER (☑ CHECKED)          |  HEADLESS (☐ UNCHECKED)
─────────────────────────────────    |  ─────────────────────────────────
visible_browser = true               |  visible_browser = false
headless = False                     |  headless = True
                                     |
👀 Browser window OPENS             |  🎯 No visible window
✓ You SEE page loading              |  ✓ Faster (no rendering overhead)
✓ Real-time HTML rendering          |  ✓ Lower CPU usage
✓ JavaScript execution visible      |  ✓ Lower memory usage
✓ Network requests visible (F12)    |  ✓ Good for batch scraping
✓ DevTools available (F12)          |  ✓ Good for servers
✓ Slow motion works (500ms)         |  ✓ Scheduled jobs work well
✓ Easy debugging                    |
✓ Screenshot validation             |  ❌ Can't watch (for debugging)
✓ Selector verification             |  ❌ No DevTools access
                                     |  ❌ Slower mo ignored (no display)
✓ Development & QA ideal            |  ✓ Production & batch ideal
✓ Data quality validation easy      |  ✓ Performance optimized
```

---

## 🎯 Success Flowchart

```
START SCRAPE
    ↓
Browser opens (if visible_browser=true)
    ↓
Navigate to https://www.telstra.com.au/internet/plans
    ↓
Page loads and renders
    ↓
Wait 6 seconds for full load
    ↓
Query CSS selectors
    ↓
Elements found? ─NO→ Log warning, continue
    ↓ YES
Extract plan data (5 plans)
    ↓
Take screenshot
    ↓
Close page, move to next
    ↓
[Repeat for 5 pages]
    ↓
TOTAL: 20 plans
    ↓
Validate each plan
    ├─ plan_name exists? YES
    ├─ price > 0? YES
    ├─ speed is integer? YES
    └─ All 20 valid ✓
    ↓
Save to JSON
    ↓
Save to CSV
    ↓
Save to MySQL
    ↓
Save log entry
    ↓
Close browser
    ↓
Return results to frontend
    ↓
Frontend updates dashboard
    ├─ Stats: 1 provider, 20 plans
    ├─ Timer: ✅ 45 seconds
    ├─ Results table: 20 rows
    ├─ Download: JSON, CSV active
    ├─ Screenshots: visible
    └─ Filters: enabled
    ↓
✅ SUCCESS - Data ready for analysis
```

---

**Visual Diagrams Complete!**

Use these diagrams to understand:
- System architecture
- Data flow
- Browser configuration
- Scraping loop
- Dashboard states
- Error handling
- Success path

