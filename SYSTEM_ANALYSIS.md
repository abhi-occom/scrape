# ISP Plan Scraper System - Process Analysis

## 📋 System Overview

The ISP Plan Scraper is a **production-ready web-based system** that extracts internet plan data from Australian ISPs (Telstra, Optus, Aussie, Superloop, Occom, TPG, etc.). It combines API-based scraping with Playwright-driven browser automation for websites that require JavaScript rendering.

---

## 🔄 Main Scraping Process Flow (10 Steps)

### **STEP 1: Initialize System**
- **What happens**: Flask server starts and loads configuration
- **File**: `app.py` (Flask API server)
- **Output**: Server running on `http://localhost:5000`
- **Key Actions**:
  - Load provider list from `config.py`
  - Initialize output directories
  - Load saved results from previous scrapes

---

### **STEP 2: User Selects Action (Frontend)**
- **What happens**: Dashboard displays all available ISP providers
- **Interface**: `templates/index.html` (Responsive web dashboard)
- **Available Options**:
  - **Scrape Single Provider** - Click "Scrape" button next to provider name
  - **Scrape All Providers** - Click "Scrape All" button
  - **Load Saved Data** - Load previously scraped results
  - **Run Benchmark** - Compare prices across providers

---

### **STEP 3: Configure Browser Options (With Checkbox)**
**This is the key feature for scraping with visual validation:**

#### **Debug Options Section** (Bottom left of dashboard)
```
┌─────────────────────────────────────┐
│   DEBUG OPTIONS                      │
├─────────────────────────────────────┤
│ ☑ Show browser while scraping       │  ← CHECKBOX TO ENABLE VISIBLE BROWSER
│ Slow motion: [Dropdown: 0-1000ms]   │  ← DROPDOWN FOR SLOWER PLAYBACK
├─────────────────────────────────────┤
│ [Scrape All] [Load Data] [Benchmark]│
└─────────────────────────────────────┘
```

#### **How the Checkbox Works**:

**A. BEFORE SCRAPING - Capability Check**
- JavaScript function: `checkCapabilities()`
- Calls: `GET /api/capabilities`
- Checks: Platform (Windows/Linux/Mac), Xvfb availability, Display server
- **If supported**: Checkbox ENABLED ✅
- **If NOT supported**: Checkbox DISABLED ❌ + Warning message

**B. CHECKBOX STATES**:

| Scenario | Checkbox | Browser Behavior |
|----------|----------|------------------|
| **Windows (Localhost)** | ✅ Enabled | Browser opens natively on desktop |
| **Linux + Xvfb installed** | ✅ Enabled | Browser opens in virtual display (VNC access) |
| **Linux headless (no Xvfb)** | ❌ Disabled | Headless mode only (no visible browser) |
| **Mac (Native)** | ✅ Enabled | Browser opens natively |

**C. WHEN CHECKED ☑ (Visible Browser Mode)**:
- Flask receives: `visible_browser: true`
- Browser launches in **non-headless mode** (you can see it!)
- Playwright opens Chromium window
- Window shows real-time page loading
- Perfect for validating CSS selectors and page structure

**D. WHEN UNCHECKED ☐ (Headless Mode - Default)**:
- Flask receives: `visible_browser: false`
- Browser runs in **background** (headless)
- No visible window (faster, uses less resources)
- Screenshots still captured automatically

**E. SLOW MOTION DROPDOWN** (0 - 1000ms)
- Off (0ms) - Normal speed
- 100ms - Visible slow motion
- 250ms - Slower
- 500ms - Very slow (good for debugging)
- 1000ms - Slowest (1 second per action)

**When selected**: Each Playwright action (click, type, navigate) pauses for the specified time

---

### **STEP 4: Send Scrape Request (Flask API)**
**Endpoint**: `POST /api/scrape/<provider_name>`

**Example for Telstra**:
```bash
POST /api/scrape/telstra
Headers:
  Content-Type: application/json
Body:
{
  "visible_browser": true,      # ← User checked the box
  "slow_mo": 500                # ← User selected 500ms
}
```

**Backend Processing** (`scraper_service.py`):
```python
def scrape_provider(provider_name, options):
    # 1. Configure browser
    configure_browser(
        headless=not options['visible_browser'],  # False = visible
        slow_mo=options['slow_mo']                # 500ms delay
    )
    
    # 2. Dynamically import provider module
    provider_module = __import__(f'providers.{provider_name}')
    
    # 3. Call scrape function
    plans = provider_module.scrape_telstra_plans()
    
    # 4. Return results
    return {
        'success': True,
        'plans': plans,
        'total_plans': len(plans)
    }
```

---

### **STEP 5: Initialize Playwright Browser with Stealth**
**File**: `utils/stealth.py`

**Flow**:
```python
def create_stealth_browser(playwright_instance):
    # 1. Check if visible browser requested
    if not headless:
        # 2. Try to start virtual display (Linux + Xvfb)
        _start_virtual_display()
    
    # 3. Launch browser with anti-detection
    browser = playwright_instance.chromium.launch(
        headless=headless,           # True = no window, False = visible
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            # ... other stealth args
        ]
    )
    
    return browser
```

**Stealth Features**:
- User-Agent rotation
- Removes automation indicators
- Disables headless detection
- Custom headers
- Request timing randomization

---

### **STEP 6: Navigate to Provider Website & Render HTML**
**Example: Telstra** (`providers/telstra.py`)

```python
def scrape_telstra_plans():
    pages_to_scrape = {
        'plans': 'https://www.telstra.com.au/internet/plans',
        '5g_home': 'https://www.telstra.com.au/internet/5g-home-internet',
        'starlink': 'https://www.telstra.com.au/internet/starlink',
        'opticomm': 'https://www.telstra.com.au/internet/opticomm-plans',
        'small_business': 'https://www.telstra.com.au/small-business/internet'
    }
    
    for page_name, url in pages_to_scrape.items():
        # 1. Create page instance
        page = browser.new_page()
        
        # 2. Navigate to URL
        page.goto(url, timeout=30000, wait_until="domcontentloaded")
        
        # 3. VISIBLE BROWSER SHOWS:
        #    ✓ Page loading in real time
        #    ✓ HTML rendering
        #    ✓ JavaScript execution
        #    ✓ Exact CSS selectors being used
        
        # 4. Wait for page to fully render
        page.wait_for_timeout(6000)  # 6 seconds
        
        # 5. Extract data using CSS selectors
        plans = extract_plans_from_page(page)
        
        # 6. Close page
        page.close()
```

**What You SEE in Visible Browser**:
```
┌──────────────────────────────────────────┐
│ telstra.com.au/internet/plans            │
├──────────────────────────────────────────┤
│                                          │
│  Telstra Internet Plans                  │
│                                          │
│  [Plan 1]  [Plan 2]  [Plan 3]  [Plan 4]  │ ← Real cards loading
│   $89/m    $99/m     $109/m    $119/m    │
│   25 Mbps  50 Mbps   100 Mbps  300 Mbps  │
│                                          │
│  (Slow motion: Each action pauses 500ms) │
│                                          │
└──────────────────────────────────────────┘
```

---

### **STEP 7: Extract Plan Data Using CSS Selectors**
**Location**: `extract_plans_from_page()` in provider files

**For Telstra**:
```python
def extract_plans_from_page(page, page_cfg):
    # 1. Query plan headers
    headers = page.query_selector_all('h3.tcom-fixed-plan-card-header__headline')
    
    # 2. Query prices (data attribute)
    prices = page.query_selector_all('[data-fixed-plan-card-price]')
    
    # 3. Query download speeds
    downloads = page.query_selector_all(
        '[data-tcom-fixed-plancard-dsq-evening-download]'
    )
    
    # 4. Query upload speeds
    uploads = page.query_selector_all(
        '[data-tcom-fixed-plancard-dsq-evening-upload]'
    )
    
    # 5. Extract text and attributes from matching elements
    for i, header in enumerate(headers):
        plan_name = header.get_attribute('data-tcom-fixed-plan-card-header-label')
        price = float(prices[i].get_attribute('data-fixed-plan-card-price'))
        download_speed = int(downloads[i].get_attribute(...))
        upload_speed = int(uploads[i].get_attribute(...))
        
        plans.append({
            'plan_name': plan_name,
            'price': price,
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'network_type': 'NBN',
            'source_url': page_cfg['url']
        })
    
    return plans
```

**With Visible Browser You Can**:
- Watch each selector query execute
- See which elements are matched
- Verify if selector is correct
- Check if page has all data visible
- Inspect in real-time using browser DevTools

---

### **STEP 8: Capture Screenshots (For Validation)**
**File**: `utils/screenshots.py`

```python
def take_screenshot(page, provider_name, page_name):
    """
    Take screenshot of rendered page for validation
    """
    filename = f"{provider_name}_{page_name}_{timestamp}.png"
    screenshot_path = f"output/screenshots/{filename}"
    
    # Playwright takes screenshot
    page.screenshot(path=screenshot_path)
    
    # Screenshot saved to disk
    return screenshot_path
```

**Screenshots Saved To**: `output/screenshots/`

**Example Screenshots**:
- `telstra_plans_2024-01-20T10:30:00.png`
- `optus_5g_2024-01-20T10:30:15.png`
- `aussie_nbn_2024-01-20T10:30:30.png`

**What Screenshots Show**:
- ✓ Actual page rendering
- ✓ All plan cards visible
- ✓ Pricing clearly shown
- ✓ Network type labeled
- ✓ Any JavaScript-rendered content
- ✓ Proof data was available at scrape time

**Viewing Screenshots**:
1. After scrape completes, check `output/screenshots/`
2. Or access via web dashboard: `/screenshots/<filename>`
3. Compare with source website to validate accuracy

---

### **STEP 9: Validate & Clean Data**
**File**: `utils/validator.py`

```python
def validate_plans(plans):
    """
    Validate each plan has required fields with valid data
    """
    valid_plans = []
    invalid_plans = []
    
    for plan in plans:
        errors = []
        
        # Check plan_name exists
        if not plan.get('plan_name'):
            errors.append('Missing plan_name')
        
        # Check price is positive number
        try:
            price = float(plan.get('price', 0))
            if price <= 0:
                errors.append('Invalid price')
        except (TypeError, ValueError):
            errors.append('Price not numeric')
        
        # Check speed is positive integer
        try:
            speed = int(plan.get('download_speed', 0))
            if speed < 0:
                errors.append('Invalid speed')
        except (TypeError, ValueError):
            errors.append('Speed not numeric')
        
        if errors:
            invalid_plans.append({
                'plan': plan,
                'validation_errors': errors
            })
        else:
            valid_plans.append(plan)
    
    return valid_plans, invalid_plans
```

**Validation Checks**:
- ✅ Plan name exists and is non-empty
- ✅ Price exists and is positive
- ✅ Download speed is valid integer
- ✅ Network type is valid
- ✅ No duplicate entries

---

### **STEP 10: Save & Output Results**
**Files Saved**:

**A. JSON Format** - `output/scrape_isp_<provider>/json/`
```json
{
  "provider_id": 1,
  "plan_name": "Telstra 25 NBN Plan",
  "network_type": "NBN",
  "download_speed": 25,
  "upload_speed": 1,
  "price": 89.0,
  "promo_price": null,
  "contract": "No Lock-in",
  "source_url": "https://www.telstra.com.au/internet/plans",
  "last_checked": "2024-01-20T10:30:00"
}
```

**B. CSV Format** - `output/scrape_isp_<provider>/csv/`
```csv
provider,plan_name,network_type,download_speed,upload_speed,price,promo_price,contract,source_url
Telstra,Telstra 25 NBN Plan,NBN,25,1,89.0,,No Lock-in,https://www.telstra.com.au/internet/plans
Telstra,Telstra 50 NBN Plan,NBN,50,2,99.0,,No Lock-in,https://www.telstra.com.au/internet/plans
```

**C. Database** - MySQL `plans_current` table
```sql
INSERT INTO plans_current (
  provider_id, plan_name, network_type, download_speed, 
  upload_speed, monthly_price, source_url, last_checked
) VALUES (1, 'Telstra 25 NBN Plan', 'NBN', 25, 1, 89.0, '...', NOW());
```

**D. Progress Log** - `output/logs.json`
```json
{
  "timestamp": "2024-01-20T10:30:00",
  "status": "success",
  "message": "Telstra: Scraped 5 plans from /internet/plans",
  "provider": "telstra",
  "data": {"plan_count": 5}
}
```

---

## 🎯 EXAMPLE: Scraping Telstra with Visible Browser

### **Complete Workflow**:

```
USER INTERFACE (Dashboard)
│
├─ Step 1: Load page → checkCapabilities()
│         Result: Checkbox ENABLED (Windows)
│
├─ Step 2: Check "Show browser while scraping" ✅
│
├─ Step 3: Select slow motion: 500ms
│
├─ Step 4: Click "Scrape" next to "Telstra"
│         Request: POST /api/scrape/telstra
│                  Body: {visible_browser: true, slow_mo: 500}
│
├─ Step 5: Timer starts (00:00)
│
└─ Step 6: Progress updates in real-time
          Status: "Starting Telstra..."

BACKEND (Flask Server)
│
├─ Step 7: scraper_service.scrape_provider('telstra')
│
├─ Step 8: configure_browser(headless=False, slow_mo=500)
│         (Browser WILL BE VISIBLE now!)
│
├─ Step 9: Chromium window OPENS on your desktop! 👀
│         (You can watch it in real-time)
│
├─ Step 10: For each page (plans, 5g_home, starlink, ...):
│
│    └─ page.goto('https://www.telstra.com.au/internet/plans')
│       ✓ Page loads with slow motion (500ms delay per action)
│       ✓ You see HTML rendering in browser
│       ✓ You can see what selectors are targeting
│       ✓ Network tab shows all requests
│       ✓ DevTools available (F12)
│
├─ Step 11: Extract plans using CSS selectors
│          Result: 17 plans from plans page
│                  1 plan from 5g_home page
│                  1 plan from starlink page
│                  Total: ~20 plans
│
├─ Step 12: Take screenshot of each page
│          Saved: output/screenshots/telstra_plans_*.png
│
├─ Step 13: Validate all plans
│          Result: 20 valid, 0 invalid
│
├─ Step 14: Save results
│          Files:
│          - output/scrape_isp_telstra/json/telstra_all_plans.json
│          - output/scrape_isp_telstra/csv/telstra_all_plans.csv
│          - Database: INSERT INTO plans_current
│          - Log: output/logs.json
│
└─ Step 15: Browser closes after scrape completes
           Timer shows: ✅ Completed in 45s
           Total plans: 20

FRONTEND (Dashboard Updates)
│
└─ Display results:
   ✓ Stats: 1 provider, 20 plans, $89-$199/month, 25-300 Mbps
   ✓ Filter & sort options
   ✓ Plans table with all details
   ✓ Download buttons for JSON/CSV
   ✓ Screenshots available for validation
```

---

## 🔍 Key Observations for Visible Browser Mode

### **When Checking the Box ☑ & Scraping Telstra**:

1. **Browser Opens** - Chromium window appears on desktop
2. **You See**:
   - Page loading with slow motion (each action pauses 500ms)
   - Navigation to multiple Telstra pages
   - Plan cards rendering
   - Prices, speeds loading
   - JavaScript execution
   
3. **In DevTools (F12)**:
   - Network tab shows all API calls
   - Console logs (warnings, errors)
   - Element inspector shows exact selectors
   - Sources tab for debugging
   
4. **Screenshots Captured**:
   - Each page's final rendered state
   - Available in `output/screenshots/`
   - Can compare with actual website
   
5. **Validation**:
   - Verify all plans are visible
   - Check prices are correct
   - Confirm speed tiers match website
   - Ensure network type is accurate

---

## 📊 Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ FRONTEND: Browser Dashboard (index.html)                    │
│                                                             │
│ [Provider List]  [Results Table]                           │
│ ☑ Show browser   [Filter & Sort]                           │
│ Slow: [500ms]    [Stats Cards]                             │
│ [Scrape] [Bench] [Download JSON/CSV]                       │
└─────────────────────────────────────────────────────────────┘
                            ↓
                 POST /api/scrape/telstra
              {visible_browser: true, slow_mo: 500}
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ BACKEND: Flask API (app.py)                                 │
│                                                             │
│ @app.route('/api/scrape/<provider_name>', methods=['POST']) │
│   ↓                                                         │
│ scraper_service.scrape_provider(provider_name, options)     │
│   ↓                                                         │
│ configure_browser(headless=False, slow_mo=500)              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ PLAYWRIGHT: Browser Automation (utils/stealth.py)          │
│                                                             │
│ create_stealth_browser(playwright_instance)                 │
│   ↓                                                         │
│ browser.chromium.launch(headless=False)                     │
│   ↓                                                         │
│ [CHROMIUM WINDOW OPENS - YOU CAN SEE IT!] 👀              │
│   ↓                                                         │
│ page.goto('https://www.telstra.com.au/internet/plans')     │
│   ↓                                                         │
│ [Wait 6 seconds for page to load]                          │
│   ↓                                                         │
│ page.screenshot()                                          │
│   → output/screenshots/telstra_plans_*.png                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ DATA EXTRACTION (providers/telstra.py)                      │
│                                                             │
│ extract_plans_from_page(page)                              │
│   ↓                                                         │
│ headers = page.query_selector_all(...)                      │
│ prices = page.query_selector_all(...)                       │
│ speeds = page.query_selector_all(...)                       │
│   ↓                                                         │
│ FOR each element:                                          │
│   plan_name, price, speed = extract_values()               │
│   plans.append({...})                                      │
│   ↓                                                         │
│ RESULT: List of 20 plans                                   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ VALIDATION & CLEANUP (utils/validator.py)                  │
│                                                             │
│ validate_plans(plans)                                      │
│   ↓                                                         │
│ Check: name, price, speed valid?                           │
│   ↓                                                         │
│ Remove invalid entries                                     │
│   ↓                                                         │
│ RESULT: 20 valid plans                                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ SAVE OUTPUT (scraper_service.py)                           │
│                                                             │
│ save_output('telstra', plans)                              │
│   ├─ JSON: output/scrape_isp_telstra/json/*.json           │
│   ├─ CSV:  output/scrape_isp_telstra/csv/*.csv             │
│   ├─ DB:   INSERT INTO plans_current                       │
│   └─ Log:  output/logs.json (success)                      │
│                                                             │
│ RESULT: Data persisted in 3 formats                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ FRONTEND: Display Results                                   │
│                                                             │
│ {                                                          │
│   "success": true,                                         │
│   "total_plans": 20,                                       │
│   "plans": [{...}, {...}, ...]                             │
│ }                                                          │
│   ↓                                                         │
│ Update stats, table, filters                               │
│ Timer: ✅ Completed in 45s                                 │
│ Show screenshots in progress panel                         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technical Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | HTML5, CSS3, JavaScript (Vanilla) | Web dashboard UI |
| **Backend** | Python 3.x, Flask | REST API server |
| **Browser Automation** | Playwright (sync_api) | Navigate & render pages |
| **Data Storage** | MySQL + JSON + CSV | Persistent storage |
| **Logging** | JSON-based custom logger | Operation tracking |
| **Anti-Detection** | Stealth headers, User-Agent | Bypass bot detection |
| **Virtual Display** | Xvfb (Linux), pyvirtualdisplay | Headless server support |

---

## 📁 Key Files Reference

```
scrape/
│
├── app.py                          # Flask API server (main entry point)
├── main.py                         # CLI pipeline orchestrator
├── scraper_service.py              # Core scraping service
├── config.py                       # Configuration & provider list
│
├── templates/
│   └── index.html                  # Dashboard UI with checkbox & filters
│
├── providers/
│   ├── __init__.py
│   ├── telstra.py                  # Telstra scraper (5 pages)
│   ├── optus.py                    # Optus scraper
│   ├── aussie.py                   # Aussie Broadband scraper
│   └── ... (other ISPs)
│
├── utils/
│   ├── stealth.py                  # Browser stealth + Xvfb support
│   ├── screenshots.py              # Screenshot capture
│   ├── validator.py                # Data validation
│   ├── db.py                       # MySQL operations
│   ├── save_json.py                # JSON file handling
│   ├── logger.py                   # JSON-based logging
│   ├── benchmark.py                # Competitive analysis
│   └── progress.py                 # Progress tracking
│
├── output/
│   ├── scrape_isp_telstra/
│   │   ├── json/                   # ← Telstra JSON files
│   │   └── csv/                    # ← Telstra CSV files
│   ├── scrape_isp_optus/           # ← Optus data
│   ├── scrape_isp_aussie/          # ← Aussie data
│   ├── screenshots/                # ← Page screenshots
│   ├── benchmark_report.json       # ← Price comparison
│   ├── logs.json                   # ← Operation logs
│   └── all_plans.json              # ← Combined data
│
├── requirements.txt                # Python dependencies
├── database.sql                    # MySQL schema
└── README.md                       # Full documentation
```

---

## 🚀 How to Use the Scraper

### **1. Start the Server**
```bash
python app.py
```
Output: `Running on http://localhost:5000`

### **2. Open Dashboard**
```
http://localhost:5000
```

### **3. Configure & Scrape**
1. **Check "Show browser while scraping"** ☑
2. **Select slow motion: 500ms** (optional)
3. **Click "Scrape"** next to Telstra

### **4. Watch Browser Open**
- Chromium window launches
- Pages load with slow motion
- You see exact plan data
- Screenshots captured automatically

### **5. View Results**
- Stats update in dashboard
- Plans table shows all details
- Filter by network, price, speed
- Download JSON or CSV

### **6. Validate with Screenshots**
- Check `output/screenshots/`
- Compare with actual website
- Verify pricing plans match
- Confirm plan details are accurate

---

## ✅ Advantages of Visible Browser Mode

1. **Real-time Debugging**
   - Watch selectors being executed
   - See what's actually visible
   - Spot selector issues immediately

2. **Data Validation**
   - Screenshots prove data was on page
   - Can compare with source website
   - Easy to spot parsing errors

3. **Issue Detection**
   - See if page loads correctly
   - Spot JavaScript errors in console
   - Check if CAPTCHA/anti-bot triggered

4. **CSS Selector Verification**
   - Watch elements being targeted
   - Use browser DevTools alongside
   - Quickly update selectors if wrong

5. **Network Analysis**
   - Monitor all API calls
   - Check for redirects
   - Identify rate limiting

---

## 🔐 Anti-Detection Features

The system includes sophisticated anti-bot detection:

- **User-Agent Rotation** - Rotates browser identities
- **Headless Detection Removal** - Removes `--headless` indicators
- **Request Header Spoofing** - Custom headers to appear normal
- **Timing Randomization** - Variable delays between actions
- **Navigation via CDP** - Chrome DevTools Protocol for stealthiness

See `utils/stealth.py` for implementation details.

---

## 📈 Output Summary

**After scraping Telstra with visible browser**:

```
✓ 20 plans scraped
✓ 5 pages visited (plans, 5g_home, starlink, opticomm, business)
✓ 5 screenshots captured
✓ Data validated (20 valid, 0 invalid)
✓ Saved to: JSON, CSV, MySQL, logs
✓ Time: ~45 seconds
✓ Files:
  - output/scrape_isp_telstra/json/telstra_all_plans.json
  - output/scrape_isp_telstra/csv/telstra_all_plans.csv
  - output/screenshots/telstra_plans_*.png (5 images)
  - output/logs.json (success entry)
```

---

## 🎓 Learning Path

1. **Start**: Read this document
2. **Understand**: Review `app.py` and `scraper_service.py`
3. **Explore**: Look at `providers/telstra.py` for actual scraping logic
4. **Run**: Start server and test with visible browser
5. **Validate**: Check screenshots and data output
6. **Customize**: Add new providers or update selectors
7. **Scale**: Use CLI mode (`main.py`) for production

---

## 📞 Support

- **Documentation**: README.md, IMPLEMENTATION_SUMMARY.md
- **Setup Guide**: XVFB_SETUP_GUIDE.md (for Linux servers)
- **Troubleshooting**: problems_faced.md
- **Debug Scripts**: investigate_*.py, test_*.py

---

**Last Updated**: 2024
**System**: ISP Plan Scraper v2.0
**Status**: ✅ Production Ready
