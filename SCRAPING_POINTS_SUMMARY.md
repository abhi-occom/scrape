# ISP Scraper - Key Points Summary (Quick Reference)

## 🎯 Main Scraping Process (10 Points)

### **1️⃣ System Initialization**
- Flask server starts (`python app.py`)
- Dashboard accessible at `http://localhost:5000`
- Config loaded with provider list and settings
- Output folders created

---

### **2️⃣ User Opens Dashboard**
- Web interface shows list of ISP providers
- Each provider has "Scrape" button
- Bottom section has debug options
- Left panel for controls, right panel for results

---

### **3️⃣ Configure Browser with Checkbox** ⭐ **KEY FEATURE**

#### **Before Scraping - System Checks Capabilities**
```javascript
checkCapabilities() → GET /api/capabilities
```
**Results**:
- **Windows**: ✅ Checkbox ENABLED
- **Mac**: ✅ Checkbox ENABLED  
- **Linux + Xvfb**: ✅ Checkbox ENABLED
- **Linux (no Xvfb)**: ❌ Checkbox DISABLED + warning

#### **The Checkbox**
```
☑ Show browser while scraping
```
- **CHECKED ☑** = Visible Browser Mode
  - Flask receives: `visible_browser: true`
  - Chromium window opens on desktop
  - You watch it in real-time
  - Perfect for validation
  
- **UNCHECKED ☐** = Headless Mode (Default)
  - Flask receives: `visible_browser: false`
  - No visible window
  - Faster, less resource usage
  - Screenshots still captured

#### **Slow Motion Dropdown**
```
Slow motion: [0 / 100 / 250 / 500 / 1000] ms
```
- Each Playwright action pauses for selected time
- 500ms = good for debugging
- 1000ms = very slow (good for screenshots)

---

### **4️⃣ Send Scrape Request**

**When User Clicks "Scrape Telstra"**:

```
POST /api/scrape/telstra
Content-Type: application/json

{
  "visible_browser": true,     ← from checkbox
  "slow_mo": 500               ← from dropdown
}
```

**Backend Receives & Processes**:
```python
scraper_service.scrape_provider('telstra', options)
  ↓
configure_browser(
    headless=False,            # true = headless, false = visible
    slow_mo=500                # milliseconds per action
)
```

---

### **5️⃣ Initialize Playwright Browser**

**File**: `utils/stealth.py`

```python
def create_stealth_browser():
    
    if not headless:  # visible_browser=True
        _start_virtual_display()  # Linux/Xvfb support
    
    browser = chromium.launch(
        headless=False,  # ← Browser OPENS on screen!
        args=[
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            # Anti-detection measures
        ]
    )
    return browser
```

**What Happens**:
- ✅ Chromium window appears on desktop
- ✅ Stealth headers applied (avoid bot detection)
- ✅ Custom User-Agent set
- ✅ Ready to navigate websites

---

### **6️⃣ Navigate to Provider Website**

**Example: Telstra** (`providers/telstra.py`)

```python
PAGES_TO_SCRAPE = {
    'plans': 'https://www.telstra.com.au/internet/plans',
    '5g_home': 'https://www.telstra.com.au/internet/5g-home-internet',
    'starlink': 'https://www.telstra.com.au/internet/starlink',
    'opticomm': 'https://www.telstra.com.au/internet/opticomm-plans',
    'small_business': 'https://www.telstra.com.au/small-business/internet'
}

for page_name, url in PAGES_TO_SCRAPE.items():
    page = browser.new_page()
    
    # NAVIGATE
    page.goto(url, timeout=30000, wait_until="domcontentloaded")
    
    # YOU SEE IN VISIBLE BROWSER:
    #   ✓ Page loading (HTML, CSS, JavaScript)
    #   ✓ Plan cards rendering
    #   ✓ Prices showing up
    #   ✓ Network type visible
    #   ✓ All data appears
    
    # WAIT FOR FULL RENDER
    page.wait_for_timeout(6000)  # 6 seconds
    
    # EXTRACT DATA
    plans = extract_plans_from_page(page)
    
    # CLEANUP
    page.close()
```

**What You See in Browser** 👀:
```
┌──────────────────────────────────┐
│ www.telstra.com.au/internet/... │
├──────────────────────────────────┤
│                                  │
│  Telstra Internet Plans          │
│                                  │
│  ┌─────────┐  ┌─────────┐        │
│  │ Plan 1  │  │ Plan 2  │        │
│  │ $89/m   │  │ $99/m   │        │
│  │ 25 Mbps │  │ 50 Mbps │        │
│  └─────────┘  └─────────┘        │
│                                  │
│  (Each action: pauses 500ms)     │
│                                  │
└──────────────────────────────────┘
```

---

### **7️⃣ Extract Data Using CSS Selectors**

**How it Works**:

```python
# QUERY ELEMENTS using CSS selectors
headers = page.query_selector_all(
    'h3.tcom-fixed-plan-card-header__headline'
)

prices = page.query_selector_all(
    '[data-fixed-plan-card-price]'
)

downloads = page.query_selector_all(
    '[data-tcom-fixed-plancard-dsq-evening-download]'
)

uploads = page.query_selector_all(
    '[data-tcom-fixed-plancard-dsq-evening-upload]'
)

# EXTRACT VALUES
for i, header in enumerate(headers):
    plan_name = header.get_attribute('data-tcom-fixed-plan-card-header-label')
    price = float(prices[i].get_attribute('data-fixed-plan-card-price'))
    download_speed = int(downloads[i].get_attribute('...'))
    upload_speed = int(uploads[i].get_attribute('...'))
    
    plans.append({
        'plan_name': plan_name,
        'price': price,
        'download_speed': download_speed,
        'upload_speed': upload_speed,
        'network_type': 'NBN',
        'source_url': url
    })

return plans  # e.g., [20 plans]
```

**With Visible Browser**:
- ✅ Watch selectors execute
- ✅ See which elements match
- ✅ Verify data is correct
- ✅ Use DevTools to debug (F12)

---

### **8️⃣ Capture Screenshots**

**File**: `utils/screenshots.py`

```python
def take_screenshot(page, provider_name, page_name):
    timestamp = datetime.now().isoformat()
    filename = f"{provider_name}_{page_name}_{timestamp}.png"
    path = f"output/screenshots/{filename}"
    
    # Take screenshot of rendered page
    page.screenshot(path=path)
    
    return path
```

**What Gets Saved**:
- `output/screenshots/telstra_plans_2024-01-20T10:30:00.png`
- `output/screenshots/telstra_5g_home_2024-01-20T10:30:15.png`
- `output/screenshots/telstra_starlink_2024-01-20T10:30:30.png`
- etc...

**Screenshots Show**:
- ✅ Real page rendering
- ✅ All plan cards visible
- ✅ Prices clearly shown
- ✅ Network types labeled
- ✅ JavaScript-rendered content
- ✅ Proof data was available

**Validation**:
Compare screenshot with actual website → verify data matches ✓

---

### **9️⃣ Validate & Clean Data**

**File**: `utils/validator.py`

```python
def validate_plans(plans):
    valid_plans = []
    invalid_plans = []
    
    for plan in plans:
        # Check plan_name exists
        if not plan.get('plan_name'):
            invalid_plans.append(plan)
            continue
        
        # Check price is positive number
        try:
            price = float(plan.get('price', 0))
            if price <= 0:
                invalid_plans.append(plan)
                continue
        except (TypeError, ValueError):
            invalid_plans.append(plan)
            continue
        
        # Check speed is positive integer
        try:
            speed = int(plan.get('download_speed', 0))
            if speed < 0:
                invalid_plans.append(plan)
                continue
        except (TypeError, ValueError):
            invalid_plans.append(plan)
            continue
        
        # All checks passed
        valid_plans.append(plan)
    
    return valid_plans, invalid_plans
```

**Validation Rules**:
- ✅ plan_name: non-empty string
- ✅ price: positive number
- ✅ download_speed: positive integer
- ✅ network_type: valid value
- ✅ No duplicates

**Example Results**:
```
Total plans: 20
Valid plans: 20
Invalid plans: 0
→ Proceed to save
```

---

### **🔟 Save & Output Results**

**4 Different Formats**:

#### **A. JSON Files**
Path: `output/scrape_isp_telstra/json/telstra_all_plans.json`

```json
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
  { ... more plans ... }
]
```

#### **B. CSV Files**
Path: `output/scrape_isp_telstra/csv/telstra_all_plans.csv`

```csv
provider,plan_name,network_type,download_speed,upload_speed,price,promo_price,contract,source_url
Telstra,Telstra 25 NBN Plan,NBN,25,1,89.0,,No Lock-in,https://www.telstra.com.au/internet/plans
Telstra,Telstra 50 NBN Plan,NBN,50,2,99.0,,No Lock-in,https://www.telstra.com.au/internet/plans
Telstra,Telstra 100 NBN Plan,NBN,100,2,109.0,,No Lock-in,https://www.telstra.com.au/internet/plans
```

#### **C. MySQL Database**
Table: `plans_current`

```sql
INSERT INTO plans_current (
  provider_id, plan_name, network_type, download_speed, 
  upload_speed, monthly_price, source_url, last_checked
) VALUES 
  (1, 'Telstra 25 NBN Plan', 'NBN', 25, 1, 89.0, '...', NOW()),
  (1, 'Telstra 50 NBN Plan', 'NBN', 50, 2, 99.0, '...', NOW()),
  (1, 'Telstra 100 NBN Plan', 'NBN', 100, 2, 109.0, '...', NOW());
```

#### **D. Logs**
Path: `output/logs.json`

```json
{
  "timestamp": "2024-01-20T10:30:00",
  "status": "success",
  "message": "Retrieved 20 plans from telstra",
  "provider": "telstra",
  "data": {"plan_count": 20, "pages_scraped": 5}
}
```

---

## 📊 Complete Example: Scraping Telstra from Start to Finish

```
STEP-BY-STEP WALKTHROUGH
═════════════════════════════════════════════════════════════

START: User visits http://localhost:5000
│
├─ 1. Page loads
│  └─ JavaScript runs: checkCapabilities()
│     └─ Calls: GET /api/capabilities
│        └─ Result: {visible_browser: true, platform: "Windows", ...}
│        └─ CHECKBOX ENABLED ✅
│
├─ 2. User configuration
│  ├─ Checks: "Show browser while scraping" ☑
│  ├─ Selects: Slow motion = 500ms
│  └─ Clicks: "Scrape" (next to Telstra)
│
├─ 3. Frontend sends request
│  └─ POST /api/scrape/telstra
│     └─ Body: {visible_browser: true, slow_mo: 500}
│
├─ 4. Backend receives request
│  └─ scraper_service.scrape_provider('telstra', options)
│     ├─ Import: from providers import telstra
│     └─ Call: telstra.scrape_telstra_plans()
│
├─ 5. Configure browser
│  └─ configure_browser(headless=False, slow_mo=500)
│     ├─ Call: create_stealth_browser()
│     ├─ Browser launches: chromium.launch(headless=False)
│     └─ 👀 CHROMIUM WINDOW OPENS ON YOUR DESKTOP
│
├─ 6. Start timer
│  └─ Frontend shows: "⏱ Scraping in progress..."
│     └─ Timer: 00:00
│
├─ 7. Scrape multiple pages
│  │
│  ├─ PAGE 1: Plans
│  │  ├─ page.goto('https://www.telstra.com.au/internet/plans')
│  │  ├─ YOU SEE: Page loading with slow motion
│  │  ├─ YOU SEE: Plan cards, prices, speeds rendering
│  │  ├─ page.wait_for_timeout(6000)  # Wait 6 sec
│  │  ├─ query selectors → Match 5 plan cards
│  │  ├─ Extract: 5 plans
│  │  ├─ page.screenshot() → telstra_plans_2024-01-20T10:30:00.png
│  │  └─ page.close()
│  │
│  ├─ PAGE 2: 5G Home
│  │  ├─ page.goto('https://www.telstra.com.au/internet/5g-home-internet')
│  │  ├─ YOU SEE: 5G page loading
│  │  ├─ Extract: 1 plan
│  │  ├─ page.screenshot() → telstra_5g_home_2024-01-20T10:30:15.png
│  │  └─ page.close()
│  │
│  ├─ PAGE 3: Starlink
│  │  ├─ page.goto('https://www.telstra.com.au/internet/starlink')
│  │  ├─ Extract: 1 plan
│  │  ├─ page.screenshot() → telstra_starlink_2024-01-20T10:30:30.png
│  │  └─ page.close()
│  │
│  ├─ PAGE 4: Opticomm
│  │  ├─ page.goto('https://www.telstra.com.au/internet/opticomm-plans')
│  │  ├─ Extract: 8 plans
│  │  ├─ page.screenshot() → telstra_opticomm_2024-01-20T10:30:45.png
│  │  └─ page.close()
│  │
│  ├─ PAGE 5: Small Business
│  │  ├─ page.goto('https://www.telstra.com.au/small-business/internet')
│  │  ├─ Extract: 5 plans
│  │  ├─ page.screenshot() → telstra_business_2024-01-20T10:31:00.png
│  │  └─ page.close()
│  │
│  └─ TOTAL PLANS EXTRACTED: 5+1+1+8+5 = 20 plans
│
├─ 8. Browser closes
│  └─ browser.close()
│
├─ 9. Validate data
│  ├─ For each of 20 plans:
│  │  ├─ Check: plan_name exists? ✓
│  │  ├─ Check: price > 0? ✓
│  │  ├─ Check: download_speed valid? ✓
│  │  └─ If all checks pass → VALID ✓
│  │
│  └─ Result: 20 valid plans, 0 invalid
│
├─ 10. Save results
│  ├─ JSON: output/scrape_isp_telstra/json/telstra_all_plans.json
│  │        (20 plans as JSON array)
│  │
│  ├─ CSV: output/scrape_isp_telstra/csv/telstra_all_plans.csv
│  │       (20 plans in CSV format)
│  │
│  ├─ DATABASE: INSERT 20 rows into plans_current table
│  │            Each row: (provider_id, plan_name, price, speed, ...)
│  │
│  └─ LOG: output/logs.json
│         (Add entry: "SUCCESS - Telstra: 20 plans")
│
├─ 11. Stop timer
│  └─ Frontend: "✅ Completed in 45s"
│     └─ Timer shows: 00:45
│
└─ RESULT: Everything complete! ✓
   ├─ Dashboard shows stats:
   │  ├─ Providers: 1
   │  ├─ Total plans: 20
   │  ├─ Price range: $89-$199/month
   │  ├─ Speed range: 25-300 Mbps
   │  └─ Network: NBN, 5G, Satellite, Opticomm
   │
   ├─ Screenshots available:
   │  └─ 5 PNG files in output/screenshots/
   │     (Can compare with actual website)
   │
   ├─ Data available to download:
   │  ├─ telstra_all_plans.json
   │  └─ telstra_all_plans.csv
   │
   └─ In database & JSON files ready for analysis
```

---

## 🎬 What You See When "Show Browser" is CHECKED

### **Real-time Browser View**:
```
Chromium Window on Desktop
┌─────────────────────────────────────────┐
│ 🔙 ⟳ telstra.com.au/internet/plans ⋮   │
├─────────────────────────────────────────┤
│                                         │
│     TELSTRA INTERNET PLANS              │
│                                         │
│  ┌──────────┐  ┌──────────┐             │
│  │ PLAN 1   │  │ PLAN 2   │             │
│  │ 25 Mbps  │  │ 50 Mbps  │             │
│  │ $89/m    │  │ $99/m    │             │
│  │ NBN      │  │ NBN      │             │
│  │[Select]  │  │[Select]  │             │
│  └──────────┘  └──────────┘             │
│                                         │
│  ┌──────────┐  ┌──────────┐             │
│  │ PLAN 3   │  │ PLAN 4   │             │
│  │ 100 Mbps │  │ 300 Mbps │             │
│  │ $109/m   │  │ $199/m   │             │
│  │ NBN      │  │ NBN      │             │
│  │[Select]  │  │[Select]  │             │
│  └──────────┘  └──────────┘             │
│                                         │
│           (Slow motion: 500ms)          │
│           (Each action pauses 500ms)    │
│                                         │
└─────────────────────────────────────────┘
```

### **Browser DevTools (F12)**:
```
┌─────────────────────────────────────────┐
│ Elements | Console | Network | Sources │
├─────────────────────────────────────────┤
│                                         │
│ NETWORK TAB:                            │
│ ✓ GET telstra.com.au/...       200 OK  │
│ ✓ GET /api/plans               200 OK  │
│ ✓ GET /images/...              200 OK  │
│ ✓ GET /styles/...              200 OK  │
│                                         │
│ CONSOLE TAB:                            │
│ [No errors]                             │
│ [JavaScript executing]                  │
│                                         │
│ ELEMENTS TAB:                           │
│ <div class="plan-card">                 │
│   <h3>Plan Name</h3>                    │
│   <span data-price>89.00</span>         │
│   <span data-speed>25</span>            │
│ </div>                                  │
│                                         │
└─────────────────────────────────────────┘
```

### **Dashboard Progress Panel**:
```
┌─────────────────────────────────────────┐
│ Live scrape progress          Running    │
├─────────────────────────────────────────┤
│                                         │
│ Provider:  TELSTRA                      │
│ URL:       telstra.com.au/internet/plans│
│ Plans Found: 5                          │
│ Providers Done: 1 / 1                   │
│                                         │
│ Events:                                 │
│ ✓ TELSTRA started                       │
│ ✓ TELSTRA navigated to plans page       │
│ ✓ TELSTRA extracted 5 plans             │
│ ✓ TELSTRA took screenshot              │
│ ✓ TELSTRA navigated to 5g page         │
│ ... (more events)                       │
│                                         │
└─────────────────────────────────────────┘
```

---

## 📋 When NOT Checking "Show Browser" (Headless Mode)

- No visible window
- Browser runs in background
- Same data extracted
- Same screenshots captured
- Faster execution
- Lower CPU/memory usage
- Good for production/batch scraping

---

## 🎯 Key Advantages of Visible Browser with Screenshots

1. **Validation**
   - See exactly what page looks like
   - Screenshots prove data availability
   - Easy to spot if selectors are wrong

2. **Debugging**
   - Watch page loading in real-time
   - Monitor network requests
   - Check for JavaScript errors
   - Use DevTools (F12)

3. **Selector Verification**
   - See which elements match
   - Understand page structure
   - Quick updates if structure changes

4. **Quality Assurance**
   - Compare screenshot with actual site
   - Verify prices match
   - Confirm plan details are correct
   - Proof data is accurate

5. **Learning**
   - Understand how scraper works
   - Learn CSS selectors
   - See Playwright in action
   - Educational for debugging

---

## ✅ Success Indicators

**Scraping Completed Successfully When**:

```
✓ Timer shows: "✅ Completed in 45s"
✓ Dashboard shows plan count (e.g., "20 plans")
✓ Stats cards populated (price range, speed range)
✓ Results table shows all plans
✓ Screenshots visible in output/screenshots/
✓ JSON files created in output/scrape_isp_telstra/json/
✓ CSV files created in output/scrape_isp_telstra/csv/
✓ Log entry shows "success" in output/logs.json
✓ Data can be filtered, sorted, downloaded
✓ Compare screenshots with actual website → match ✓
```

---

## 🚨 Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Checkbox disabled | Platform not supported | Run on Windows/Mac or install Xvfb on Linux |
| No plans extracted | Selector mismatch | Check visible browser, inspect with DevTools |
| Page not loading | Network timeout | Increase wait time, check internet connection |
| Bad data quality | Page structure changed | Update CSS selectors in provider file |
| Screenshot blank | Page not rendered | Increase wait_for_timeout value |
| Price is $0 | Selector wrong | Open DevTools, find correct attribute |

---

## 📞 Quick Support

- **Docs**: Read `SYSTEM_ANALYSIS.md` (this file)
- **Code**: Check `providers/telstra.py` for examples
- **Logs**: See `output/logs.json` for errors
- **Screenshots**: `output/screenshots/` for validation

---

**System**: ISP Plan Scraper with Visible Browser Mode ✓
**Status**: ✅ Ready to Use
**Last Updated**: 2024
