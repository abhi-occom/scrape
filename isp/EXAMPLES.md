# 💡 ISP Mini Crawler - Usage Examples

## 📚 Table of Contents

1. [Basic Web UI Usage](#basic-web-ui-usage)
2. [CLI Examples](#cli-examples)
3. [Python API Usage](#python-api-usage)
4. [Testing Examples](#testing-examples)
5. [Advanced Scenarios](#advanced-scenarios)
6. [Integration Examples](#integration-examples)

---

## 1. Basic Web UI Usage

### **Example 1: Crawl Telstra**

1. Open browser: `http://localhost:5000/isp`
2. Enter URL: `https://www.telstra.com.au/internet`
3. Keep all defaults:
   - Network types: NBN, Opticomm, RedTrain, Supa ✓
   - Depth: 2 levels
4. Click **"Start Crawling"**
5. Wait 45-60 seconds
6. See results: 10-17 plans with NBN and 5G types

**Expected Output:**
```
Plans Found: 17
Pages Scraped: 5
URLs Visited: 42
Duration: 58.3s
Networks: NBN, 5G
```

### **Example 2: Quick NBN-Only Check**

1. Enter URL: `https://www.superloop.com/consumer/internet`
2. **Uncheck** Opticomm, RedTrain, Supa (leave only NBN checked)
3. Set depth: **1 level** (faster)
4. Click **"Start Crawling"**
5. Get results in ~20 seconds

---

## 2. CLI Examples

### **Example 1: Simple Crawl**

```bash
python -m isp.main_crawler https://www.telstra.com.au/internet
```

**Output:**
```
============================================================
  ISP Crawler starting for: https://www.telstra.com.au/internet
  Provider: Telstra
  Network types: ['nbn', 'opticomm', 'redtrain', 'supa']
  Max depth: 2
============================================================
[INFO] Starting URL discovery from https://www.telstra.com.au/internet
[INFO] [depth=0] Crawling: https://www.telstra.com.au/internet
[SUCCESS] Discovered 42 candidate plan pages
[INFO] Step 2: Analysing pages for plan data...
[SUCCESS] Plan page confirmed: .../plans (confidence=0.85, cards=8)
[SUCCESS] Extracted 8 plans from .../plans
...
[SUCCESS] Crawl complete for Telstra: 17 valid plans, 0 invalid, 5 pages scraped in 58.3s
```

### **Example 2: Targeted Opticomm Search**

```bash
python -m isp.main_crawler https://www.swoop.com.au \
    --name "Swoop" \
    --networks opticomm \
    --depth 2
```

Searches only for Opticomm plans, ignoring NBN.

### **Example 3: Deep Thorough Crawl**

```bash
python -m isp.main_crawler https://www.provider.com \
    --name "My ISP" \
    --depth 3 \
    --max-urls 200
```

Crawls 3 levels deep, visits up to 200 URLs (thorough but slow).

### **Example 4: Fast Shallow Crawl**

```bash
python -m isp.main_crawler https://www.telstra.com.au/internet/plans \
    --depth 1
```

Only scrapes the exact URL provided, no following links (fast).

---

## 3. Python API Usage

### **Example 1: Programmatic Crawl**

```python
from isp.main_crawler import ISPCrawler

crawler = ISPCrawler(
    base_url="https://www.telstra.com.au/internet",
    network_types=['nbn', 'opticomm'],
    max_depth=2,
    provider_name="Telstra",
)

result = crawler.run()

print(f"Found {result.valid_plans} plans")
print(f"Network types: {result.network_types_found}")

for plan in result.plans:
    print(f"  {plan['plan_name']}: ${plan['price']}/mth")
```

### **Example 2: Batch Multiple Providers**

```python
from isp.main_crawler import ISPCrawler

providers = [
    ("https://www.telstra.com.au/internet", "Telstra"),
    ("https://www.superloop.com", "Superloop"),
    ("https://www.swoop.com.au", "Swoop"),
]

all_plans = []

for url, name in providers:
    crawler = ISPCrawler(url, provider_name=name, max_depth=2)
    result = crawler.run()
    all_plans.extend(result.plans)
    print(f"{name}: {result.valid_plans} plans")

print(f"\nTotal: {len(all_plans)} plans from {len(providers)} providers")
```

### **Example 3: Custom Validation**

```python
from isp.main_crawler import ISPCrawler
from isp.validator import ISPValidator

crawler = ISPCrawler("https://www.example.com")
result = crawler.run()

validator = ISPValidator()
valid, invalid, details = validator.validate_batch(result.plans)

print(f"Valid: {len(valid)}, Invalid: {len(invalid)}")

for inv in invalid:
    print(f"  Invalid: {inv['plan_name']} - {inv['_validation_errors']}")
```

### **Example 4: Save to Database**

```python
from isp.main_crawler import ISPCrawler
from utils.db import create_connection, insert_plans_batch

crawler = ISPCrawler("https://www.telstra.com.au/internet")
result = crawler.run()

if result.success:
    connection = create_connection()
    insert_plans_batch(connection, result.plans)
    print(f"Saved {len(result.plans)} plans to database")
    connection.close()
```

---

## 4. Testing Examples

### **Example 1: Run Full Test Suite**

```bash
python -m isp.test_crawler
```

**Output:**
```
============================================================
  ISP CRAWLER TEST SUITE
  2026-05-25 21:30:00
============================================================

────────────────────────────────────────────────────────
  Testing: Telstra (https://www.telstra.com.au/internet)
  Type: dynamic
  Networks: ['nbn', 'opticomm']
────────────────────────────────────────────────────────

  Plans found (17):
    - NBN Basic Home                     $85/mth  25/5 Mbps  [NBN]
    - NBN Standard Plus                  $95/mth  50/20 Mbps  [NBN]
    ...

  [PASSED] telstra: 12 passed, 0 failed, 2 warnings

============================================================
  TEST SUITE SUMMARY
============================================================
  Providers tested:  6
  Passed:            5
  Failed:            1
  Total checks:      45/48
  Total time:        345.2s
============================================================
```

### **Example 2: Quick Smoke Test**

```bash
python -m isp.test_crawler --quick
```

Only tests Telstra (fastest single test).

### **Example 3: Test Specific Provider**

```bash
python -m isp.test_crawler --provider superloop
```

### **Example 4: Custom Test Scenario**

```python
from isp.test_crawler import run_test, TestResult

scenario = {
    'url': 'https://www.myisp.com/plans',
    'name': 'MyISP',
    'type': 'static',
    'networks': ['nbn'],
    'depth': 2,
    'expected': {
        'min_plan_pages': 1,
        'min_plans': 5,
        'expected_networks': ['NBN'],
        'sample_plans': [
            {'plan_name_contains': 'Basic', 'min_price': 50, 'max_price': 80},
        ],
    },
}

result = run_test('myisp', scenario)
print(result.summary())
```

---

## 5. Advanced Scenarios

### **Example 1: Price Comparison Pipeline**

```bash
#!/bin/bash
# compare_prices.sh

# Crawl 3 competitors
python -m isp.main_crawler https://www.telstra.com.au/internet --name Telstra
python -m isp.main_crawler https://www.superloop.com --name Superloop
python -m isp.main_crawler https://www.swoop.com.au --name Swoop

# Extract prices
echo "=== NBN 50 Plans ==="
jq '.plans[] | select(.download_speed == 50) | {provider, price}' output/isp_crawler/*_latest.json

echo "=== NBN 100 Plans ==="
jq '.plans[] | select(.download_speed == 100) | {provider, price}' output/isp_crawler/*_latest.json
```

### **Example 2: Scheduled Daily Crawl** (Windows Task Scheduler)

**Action:**
```
Program: python
Arguments: C:\xampp\htdocs\scrape\isp\main_crawler.py https://www.telstra.com.au/internet
Start in: C:\xampp\htdocs\scrape
```

**Trigger:** Daily at 2:00 AM

### **Example 3: Comparison Logging**

```python
from isp.main_crawler import ISPCrawler
from isp.validator import ComparisonLogger

# Run crawl
crawler = ISPCrawler("https://www.telstra.com.au/internet")
result = crawler.run()

# Compare against known expected data
logger = ComparisonLogger()
logger.add_scenario(
    url=result.base_url,
    scenario="static_menu",
    expected_plans=17,
    expected_data=[
        {"plan_name": "NBN Basic Home", "price": 85, "download_speed": 25},
        {"plan_name": "NBN Standard Plus", "price": 95, "download_speed": 50},
    ],
    actual_plans=result.plans,
)

report = logger.generate_report()
print(f"Match rate: {report['overall_match_rate']:.1f}%")

# Save report
import json
with open('comparison_report.json', 'w') as f:
    json.dump(report, f, indent=2)
```

### **Example 4: Monitor Price Changes**

```python
import json
import os
from datetime import datetime
from isp.main_crawler import ISPCrawler

HISTORY_FILE = "price_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {}

def save_history(history):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

# Run crawl
crawler = ISPCrawler("https://www.telstra.com.au/internet")
result = crawler.run()

# Load history
history = load_history()

# Check for changes
today = datetime.now().strftime("%Y-%m-%d")
changes = []

for plan in result.plans:
    key = f"{plan['provider']}_{plan['plan_name']}"
    current_price = plan['price']
    
    if key in history:
        old_price = history[key]['price']
        if abs(current_price - old_price) > 0.01:
            changes.append({
                'plan': plan['plan_name'],
                'old_price': old_price,
                'new_price': current_price,
                'change': current_price - old_price,
            })
    
    history[key] = {
        'price': current_price,
        'last_checked': today,
    }

# Report changes
if changes:
    print(f"\n⚠️  PRICE CHANGES DETECTED ({len(changes)}):\n")
    for c in changes:
        direction = "↑" if c['change'] > 0 else "↓"
        print(f"  {direction} {c['plan']}: ${c['old_price']} → ${c['new_price']} ({c['change']:+.2f})")
else:
    print("\n✓ No price changes detected")

save_history(history)
```

---

## 6. Integration Examples

### **Example 1: Flask API Integration**

```python
from flask import Flask, jsonify
from isp.main_crawler import ISPCrawler

app = Flask(__name__)

@app.route('/crawl/<provider>')
def crawl_provider(provider):
    urls = {
        'telstra': 'https://www.telstra.com.au/internet',
        'superloop': 'https://www.superloop.com',
        'swoop': 'https://www.swoop.com.au',
    }
    
    if provider not in urls:
        return jsonify({'error': 'Unknown provider'}), 404
    
    crawler = ISPCrawler(urls[provider], provider_name=provider.capitalize())
    result = crawler.run()
    
    return jsonify({
        'provider': result.provider_name,
        'plans_found': result.valid_plans,
        'duration': result.duration_seconds,
        'plans': result.plans,
    })

app.run(port=5001)
```

### **Example 2: Export to Excel**

```python
from isp.main_crawler import ISPCrawler
import pandas as pd

crawler = ISPCrawler("https://www.telstra.com.au/internet")
result = crawler.run()

# Convert to DataFrame
df = pd.DataFrame(result.plans)

# Export to Excel
df.to_excel("telstra_plans.xlsx", index=False)
print(f"Exported {len(df)} plans to telstra_plans.xlsx")
```

### **Example 3: Send Email Alert**

```python
import smtplib
from email.mime.text import MIMEText
from isp.main_crawler import ISPCrawler

crawler = ISPCrawler("https://www.telstra.com.au/internet")
result = crawler.run()

if result.success:
    msg = MIMEText(
        f"Successfully crawled {result.provider_name}\n"
        f"Found {result.valid_plans} plans\n"
        f"Duration: {result.duration_seconds}s"
    )
    msg['Subject'] = f"Crawl Complete: {result.provider_name}"
    msg['From'] = 'scraper@example.com'
    msg['To'] = 'admin@example.com'
    
    smtp = smtplib.SMTP('localhost')
    smtp.send_message(msg)
    smtp.quit()
```

### **Example 4: Webhook Notification**

```python
import requests
from isp.main_crawler import ISPCrawler

crawler = ISPCrawler("https://www.telstra.com.au/internet")
result = crawler.run()

# Post to webhook
webhook_url = "https://your-webhook.com/notify"
payload = {
    'provider': result.provider_name,
    'plans_found': result.valid_plans,
    'status': 'success' if result.success else 'failure',
    'duration': result.duration_seconds,
}

response = requests.post(webhook_url, json=payload)
print(f"Webhook response: {response.status_code}")
```

---

## 🎯 Real-World Use Cases

### **Use Case 1: Daily Competitive Analysis**

**Goal:** Track competitor plan changes daily

**Solution:**
```bash
# cron: 0 2 * * * (daily at 2 AM)
cd /path/to/scrape
python -m isp.main_crawler https://www.competitor.com
python compare_with_yesterday.py
```

### **Use Case 2: New Provider Onboarding**

**Goal:** Quickly assess if a new ISP offers Opticomm

**Solution:**
```bash
python -m isp.main_crawler https://www.newisp.com --networks opticomm --depth 2
```

Check results for Opticomm plans.

### **Use Case 3: Market Research**

**Goal:** Collect plan data from 10 ISPs for analysis

**Solution:**
```python
providers = [url_list_of_10_isps]
for url in providers:
    crawler = ISPCrawler(url)
    result = crawler.run()
    # Aggregate results
```

### **Use Case 4: Price Alert System**

**Goal:** Get notified when competitor drops price

**Solution:** Run `price_change_monitor.py` (Example 4 above) daily and send email/Slack alert on changes.

---

## 📖 Tips & Tricks

### **Tip 1: Speed Up Crawling**
Set `depth=1` and target specific plan URLs:
```bash
python -m isp.main_crawler https://www.provider.com/nbn-plans --depth 1
```

### **Tip 2: Debug Failed Crawls**
Check the JSON output for `page_analyses`:
```bash
jq '.page_analyses' output/isp_crawler/provider_latest.json
```

Look at confidence scores and detected selectors.

### **Tip 3: Extract Only NBN Plans**
Post-filter results:
```bash
jq '.plans[] | select(.network_type == "NBN")' output/isp_crawler/provider_latest.json
```

### **Tip 4: Find Cheapest Plan Per Speed**
```bash
jq '.plans | group_by(.download_speed) | map({speed: .[0].download_speed, cheapest: map(.price) | min})' output/isp_crawler/provider_latest.json
```

### **Tip 5: Combine Multiple Results**
```bash
jq -s 'map(.plans) | flatten' output/isp_crawler/*_latest.json > all_plans.json
```

---

## 🎉 You're Now an ISP Crawler Expert!

Try these examples and customize them for your needs. The crawler is flexible and can adapt to most use cases.

**Need more help?** Check [README.md](README.md) or [QUICKSTART.md](QUICKSTART.md)
