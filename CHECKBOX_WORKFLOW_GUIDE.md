# 🎯 Checkbox Workflow: "Show Browser While Scraping"

## 📌 Overview

The **"Show browser while scraping" checkbox** is the key feature that enables **real-time visual validation** of the scraping process. This guide explains exactly how it works.

---

## 🔍 The Checkbox Feature

### **Location**
Bottom-left panel of dashboard → "Debug Options" section

```
┌─────────────────────────────────────────┐
│        DEBUG OPTIONS                    │
├─────────────────────────────────────────┤
│                                         │
│  ☑ Show browser while scraping         │ ← THIS CHECKBOX
│                                         │
│  Slow motion: [Dropdown]               │
│    ├─ Off (0ms)                        │
│    ├─ 100 ms                           │
│    ├─ 250 ms                           │
│    ├─ 500 ms          ← Recommended   │
│    └─ 1000 ms                          │
│                                         │
│  [Scrape All] [Load Data] [Benchmark]  │
│                                         │
└─────────────────────────────────────────┘
```

---

## 🔄 Complete Checkbox Workflow

### **PHASE 1: System Initialization (Page Load)**

**When user opens `http://localhost:5000`**:

```
Browser loads dashboard
    ↓
JavaScript executes: checkCapabilities()
    ↓
GET /api/capabilities
    ↓
Backend checks:
  - Platform: Windows? Linux? Mac?
  - Xvfb installed? (Linux only)
  - DISPLAY env var set? (Linux only)
    ↓
Response: {
  "visible_browser": true/false,
  "platform": "Windows",
  "has_display": false,
  "has_xvfb": false,
  "reason": null
}
    ↓
Frontend receives response
    ↓
IF visible_browser == false:
  ├─ checkbox.disabled = true
  ├─ slowMo.disabled = true
  ├─ Show warning message ⚠️
  └─ reason: "..."
ELSE:
  ├─ checkbox.enabled = true
  ├─ slowMo.enabled = true
  └─ User can configure
```

### **Capability Check Results**

| Platform | has_xvfb | Result | Checkbox |
|----------|----------|--------|----------|
| Windows | N/A | Browser opens natively | ✅ ENABLED |
| macOS | N/A | Browser opens natively | ✅ ENABLED |
| Linux + Xvfb | Yes | Browser in virtual display | ✅ ENABLED |
| Linux + no Xvfb | No | Headless only | ❌ DISABLED |

---

### **PHASE 2: User Configuration**

**User sees checkbox**:

```
IF checkbox is ENABLED ✅:
  └─ User can:
     ├─ CHECK ☑ to enable visible browser
     ├─ UNCHECK ☐ to use headless mode
     └─ Adjust slow motion slider

IF checkbox is DISABLED ❌:
  └─ User sees:
     ├─ Checkbox greyed out (can't click)
     ├─ Slow motion dropdown also disabled
     └─ Warning message with explanation
```

### **Option A: CHECKING THE BOX ☑**

```
User clicks checkbox: ☑ Show browser while scraping
    ↓
Checkbox state changes to: CHECKED
    ↓
User selects: Slow motion = 500ms
    ↓
User clicks: "Scrape" (next to provider, e.g., Telstra)
```

### **Option B: LEAVING UNCHECKED ☐**

```
User does NOT check the box (default)
    ↓
Checkbox stays: UNCHECKED
    ↓
(Slow motion dropdown ignored for headless)
    ↓
User clicks: "Scrape" (next to provider)
```

---

## 📤 PHASE 3: Scrape Request Sent

### **When User Clicks "Scrape Telstra"**

```
JavaScript in frontend collects options:

getScrapeOptions() {
  return {
    visible_browser: document.getElementById('visible-browser').checked,
    slow_mo: parseInt(document.getElementById('slow-mo').value || '0')
  }
}

Result (if checkbox is CHECKED ☑):
{
  visible_browser: true,      ← ☑ Checkbox is checked
  slow_mo: 500                ← 500ms slow motion
}

Result (if checkbox is UNCHECKED ☐):
{
  visible_browser: false,     ← ☐ Default (headless)
  slow_mo: 0                  ← No slow motion
}
```

### **HTTP Request**

```
POST /api/scrape/telstra
Content-Type: application/json

{
  "visible_browser": true,
  "slow_mo": 500
}
```

---

## 🖥️ PHASE 4: Backend Processing

### **File**: `app.py`

```python
@app.route('/api/scrape/<provider_name>', methods=['POST'])
def api_scrape_provider(provider_name):
    """Scrape a specific provider"""
    
    # 1. Get options from request body
    options = get_scrape_options()
    # → options = {
    #     'visible_browser': true,
    #     'slow_mo': 500
    #   }
    
    # 2. Call scraper service
    result = scrape_provider(provider_name, options=options)
    
    return jsonify(result)


def get_scrape_options():
    """Extract browser debug settings from request"""
    payload = request.get_json(silent=True) or {}
    
    visible_browser = bool(payload.get('visible_browser'))
    # → visible_browser = True (from checkbox)
    
    slow_mo = payload.get('slow_mo', 0)
    # → slow_mo = 500
    
    return {
        'visible_browser': visible_browser,
        'slow_mo': max(0, min(slow_mo, 3000))  # Cap at 3 seconds
    }
```

### **File**: `scraper_service.py`

```python
def scrape_provider(provider_name, options=None):
    """Scrape a single provider"""
    
    options = options or {}
    
    # 1. CONFIGURE BROWSER with options
    configure_browser(
        headless=not bool(options.get('visible_browser')),
        # → headless = not True = False
        # → False means VISIBLE (not headless)
        
        slow_mo=int(options.get('slow_mo') or 0)
        # → slow_mo = 500 milliseconds
    )
    
    # 2. Import provider dynamically
    provider_module = __import__(f'providers.{provider_name}')
    # → Import: from providers import telstra
    
    # 3. Call scraper function
    plans = provider_module.scrape_telstra_plans()
    # → Returns: [20 plans from Telstra]
    
    # 4. Return results
    return {
        'success': True,
        'plans': plans,
        'total_plans': len(plans)
    }
```

---

## 🎨 PHASE 5: Browser Initialization

### **File**: `utils/stealth.py`

```python
def configure_browser(headless=True, slow_mo=0):
    """
    Configure Playwright browser settings
    """
    global _browser_headless, _slow_mo
    
    _browser_headless = headless
    # → False (not headless = VISIBLE)
    
    _slow_mo = slow_mo
    # → 500 milliseconds


def create_stealth_browser(playwright_instance):
    """
    Create Playwright browser with stealth features
    """
    headless = _browser_headless  # False
    slow_mo = _slow_mo            # 500
    
    # If visible browser requested, try to start virtual display
    if not headless:
        # Try to start Xvfb (Linux) - fails silently on Windows/Mac
        _start_virtual_display()
    
    # Launch browser
    browser = playwright_instance.chromium.launch(
        headless=headless,      # False = VISIBLE WINDOW
        slow_mo=slow_mo,        # 500ms delay per action
        args=[
            '--disable-blink-features=AutomationControlled',
            # Remove --headless flag
            # Remove chrome flag indicating headless mode
            '--disable-dev-shm-usage',
            # Stealth measures to avoid bot detection
            # Custom user-agents
            # Custom headers
        ]
    )
    
    return browser
```

### **What Happens When headless=False**

```
1. Chromium is launched with visible UI
   └─ Browser window appears on desktop (you can see it!)

2. slow_mo=500 is applied
   └─ Each Playwright action (goto, click, type) waits 500ms
   └─ You can watch the page load slowly
   └─ Good for debugging and screenshots

3. Stealth features enabled
   └─ User-Agent spoofed
   └─ Automation indicators removed
   └─ Headers customized
   └─ Timing randomized

4. Ready to scrape
   └─ Browser waiting for first page.goto() call
```

---

## 🌐 PHASE 6: Navigating & Scraping Pages

### **File**: `providers/telstra.py`

```python
def scrape_telstra_plans() -> Dict[str, List[Dict]]:
    """Scrape all Telstra pages"""
    
    # Browser already created with visible=True, slow_mo=500
    # (from previous phases)
    
    pages = {
        'plans': 'https://www.telstra.com.au/internet/plans',
        '5g_home': 'https://www.telstra.com.au/internet/5g-home-internet',
        'starlink': 'https://www.telstra.com.au/internet/starlink',
        # ... more pages
    }
    
    for page_name, url in pages.items():
        
        page = browser.new_page()
        # → Creates new browser tab/page
        
        page.goto(url, timeout=30000)
        # → NAVIGATES TO URL
        # → WITH SLOW MOTION: This takes extra time
        # → YOU SEE: Browser window shows page loading
        
        page.wait_for_timeout(6000)
        # → Wait 6 seconds for full render
        # → JavaScript executes
        # → Dynamic content loads
        # → Images appear
        
        # YOU CAN SEE IN BROWSER WINDOW:
        # ✓ Page loading (CSS styles appearing)
        # ✓ Plan cards rendering
        # ✓ Prices showing
        # ✓ Network types visible
        # ✓ All content fully loaded
        
        page.screenshot(path=...)
        # → Screenshot of rendered page
        # → Saved to output/screenshots/
        
        plans = extract_plans_from_page(page)
        # → CSS selectors extract plan data
        # → Returns: list of plans
        
        page.close()
        # → Close page/tab
```

### **What User SEES in Visible Browser Window**

```
Time: 00:15 (15 seconds into scrape)

┌────────────────────────────────────────────────────┐
│ ↙ ↗ 🔄 telstra.com.au/internet/plans        × □ ⋮ │
├────────────────────────────────────────────────────┤
│                                                    │
│  TELSTRA INTERNET PLANS                           │
│                                                    │
│  [Card 1 slowly animating]  [Card 2 loading...]   │
│   Plan Name: Telstra 25                            │
│   Speed: 25 Mbps                                   │
│   Price: $89.00/month                              │
│   Network: NBN                                     │
│   [Loading button...]                              │
│                                                    │
│  [Card 3 rendering]  [Card 4 not yet visible]     │
│                                                    │
│  (Slow motion: 500ms per action)                  │
│  (You're watching real-time page rendering)        │
│                                                    │
└────────────────────────────────────────────────────┘

DevTools Console (F12):
  ✓ All requests shown
  ✓ No JavaScript errors
  ✓ Can inspect selectors
  ✓ Can see HTML structure
```

---

## 📸 PHASE 7: Screenshots Captured

```python
# In provider scraper
page.screenshot(path=f"output/screenshots/telstra_plans_2024-01-20T10:30:00.png")

# What gets saved:
# output/screenshots/
#   ├─ telstra_plans_2024-01-20T10:30:00.png (plans page)
#   ├─ telstra_5g_home_2024-01-20T10:30:15.png (5G page)
#   ├─ telstra_starlink_2024-01-20T10:30:30.png (Starlink page)
#   ├─ telstra_opticomm_2024-01-20T10:30:45.png (Opticomm page)
#   └─ telstra_business_2024-01-20T10:31:00.png (Business page)

# Screenshots show:
# ✓ Exact page layout
# ✓ All plan cards visible
# ✓ Prices clearly shown
# ✓ Network type labeled
# ✓ Proof data was available

# VALIDATION:
# User can compare screenshot with actual website
# → "Does this match telstra.com.au/internet/plans?"
# → If yes, data is accurate ✓
```

---

## 🎯 PHASE 8: Extract, Validate, Save

```python
# Data extraction using CSS selectors
plans = extract_plans_from_page(page)
# → Returns: [20 plans]

# Validation
valid_plans, invalid_plans = validate_plans(plans)
# → 20 valid, 0 invalid ✓

# Save output
save_output('telstra', plans)
# → output/scrape_isp_telstra/json/telstra_all_plans.json
# → output/scrape_isp_telstra/csv/telstra_all_plans.csv
# → Database: INSERT into plans_current
# → Log: output/logs.json
```

---

## ✅ PHASE 9: Complete & Display Results

### **Frontend Updates**

```
Timer stops:
✅ Completed in 45s

Stats updated:
  Providers: 1
  Total plans: 20
  Price range: $89-$199/month
  Speed range: 25-300 Mbps

Results table populated:
  | Plan Name              | Network | Speed    | Price   |
  |------------------------|---------|----------|---------|
  | Telstra 25 NBN Plan    | NBN     | 25/1 Mbps| $89.00 |
  | Telstra 50 NBN Plan    | NBN     | 50/2 Mbps| $99.00 |
  | Telstra 100 NBN Plan   | NBN     |100/2 Mbps|$109.00 |
  | ... more plans ...     |         |          |        |

Available actions:
  ✓ Filter by network, price, speed
  ✓ Sort by price or speed
  ✓ Download JSON file
  ✓ Download CSV file
  ✓ View screenshots in browser
```

---

## 🔄 Comparison: Checkbox CHECKED vs UNCHECKED

| Aspect | ☑ CHECKED (Visible) | ☐ UNCHECKED (Headless) |
|--------|------------------|------------------|
| **Browser Window** | 👀 Visible on desktop | Hidden (background) |
| **Slow Motion** | Applied (500ms) | Ignored |
| **DevTools** | Can use F12 to inspect | N/A |
| **Speed** | Slower (visible + slow_mo) | Faster |
| **Resource Usage** | Higher (GPU, display) | Lower |
| **Screenshots** | Captured | Captured |
| **Validation** | Visual real-time | Log-based only |
| **Debugging** | Easy (watch it) | Harder (read logs) |
| **Production Use** | Development/QA | Batch scraping |

---

## 📊 Complete Checkbox Workflow Diagram

```
USER OPENS DASHBOARD
│
├─ checkCapabilities()
│  ├─ Check: Windows? ✓
│  ├─ Check: Display available? ✓
│  ├─ Check: Xvfb installed? ✗
│  └─ Result: visible_browser = true
│     └─ Checkbox ENABLED ✅
│
├─ User sees checkbox options
│  ├─ ☑ Can CHECK for visible browser
│  └─ Slow motion slider available
│
├─ User configuration
│  ├─ CHECK ☑ "Show browser while scraping"
│  ├─ SELECT "500 ms" slow motion
│  └─ CLICK "Scrape" button
│
├─ Frontend sends request
│  └─ POST /api/scrape/telstra
│     └─ Body: {visible_browser: true, slow_mo: 500}
│
├─ Backend receives
│  ├─ configure_browser(headless=False, slow_mo=500)
│  └─ Provider scraper starts
│
├─ Playwright launches
│  ├─ create_stealth_browser(headless=False)
│  └─ Chromium window OPENS on desktop 👀
│
├─ Pages scraped (with slow motion)
│  ├─ page.goto(url) → YOU SEE page loading
│  ├─ page.wait_for_timeout(6000) → Page renders
│  ├─ page.screenshot() → Proof captured
│  ├─ extract_plans_from_page() → Data extracted
│  └─ page.close()
│
├─ Data processed
│  ├─ validate_plans()
│  ├─ save_output() → JSON, CSV, DB, Log
│  └─ browser.close()
│
├─ Frontend updates
│  ├─ Timer: ✅ Completed in 45s
│  ├─ Stats: 20 plans found
│  ├─ Results table populated
│  └─ Screenshots visible
│
└─ USER CAN NOW:
   ├─ View plan details
   ├─ Filter & sort results
   ├─ Download data files
   └─ Compare with screenshots
```

---

## 🎓 Why Use the Checkbox?

### **Development & Debugging**
```
✓ See exactly what's happening
✓ Verify selectors are correct
✓ Spot JavaScript errors
✓ Watch page loading in real-time
✓ Use DevTools for inspection
✓ Validate data immediately
```

### **Quality Assurance**
```
✓ Screenshot proof of scrape
✓ Compare with actual website
✓ Verify prices match
✓ Confirm plan details accurate
✓ Easy to spot parsing errors
```

### **Learning**
```
✓ Understand how Playwright works
✓ Learn about CSS selectors
✓ See browser automation in action
✓ Educational for developers
```

### **Testing New Sites**
```
✓ Quickly validate new selectors
✓ Identify page structure issues
✓ Debug timing/timeout problems
✓ Adjust slow_mo for screenshots
```

---

## 🚫 When NOT to Use Checkbox

### **Production Batch Scraping**
```
UNCHECK ☐ for:
✓ Faster execution
✓ Lower resource usage
✓ Running scheduled jobs
✓ Scraping many providers
✓ Server environments
```

---

## 📝 Summary

**The "Show browser while scraping" checkbox**:

1. **When checked ☑**: Browser opens visibly → you watch scraping happen → screenshots prove data
2. **When unchecked ☐**: Browser runs headless → faster, quieter, production-ready
3. **Slow motion dropdown**: Makes actions slower → easier to see what's happening
4. **Screenshots**: Always captured (regardless of checkbox) → validate accuracy
5. **Validation**: Compare screenshots with actual website → confirm data is correct

---

**This feature makes it easy to validate that:**
- ✅ Right pages are being scraped
- ✅ Right selectors are matching elements  
- ✅ Right data is being extracted
- ✅ Prices match the website
- ✅ Plan details are accurate
- ✅ All information is valid

---

**System Ready**: ✅ ISP Scraper with Visual Validation
