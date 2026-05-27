# 🚀 ISP Mini Crawler - Quick Start Guide

## ⚡ 5-Minute Setup

### **Step 1: Start the Server**

```bash
cd C:\xampp\htdocs\scrape
python app.py
```

You should see:
```
Starting ISP Scraper API Server...
Access dashboard at: http://localhost:5000
```

### **Step 2: Open the Crawler**

Navigate to: **http://localhost:5000/isp**

### **Step 3: Enter a URL**

Try one of these examples:

**Telstra:**
```
https://www.telstra.com.au/internet
```

**Superloop:**
```
https://www.superloop.com/consumer/internet
```

**Your own ISP:**
```
https://www.example.com.au/plans
```

### **Step 4: Configure Options**

- ✅ **Network Types**: Select which types to search for (NBN, Opticomm, etc.)
- 📏 **Crawl Depth**: 
  - `1 level` = Fast, base URL only
  - `2 levels` = Recommended, follows 1 link deep
  - `3 levels` = Thorough, slower

### **Step 5: Click "Start Crawling"**

Watch the status panel for real-time updates:
- ⏱ **Running**: Crawler is discovering and scraping
- ✅ **Success**: Plans found and saved
- ❌ **Error**: Check error messages

### **Step 6: Review Results**

Results include:
- 📊 **Summary Cards**: Plans found, pages scraped, duration
- 📋 **Plans Table**: All discovered plans with prices, speeds, networks
- 🔗 **Discovered URLs**: Internal plan pages that were found
- ⚠️ **Errors**: Any issues encountered

---

## 🖥️ Command Line Usage

### **Basic Crawl**
```bash
python -m isp.main_crawler https://www.telstra.com.au/internet
```

### **With Options**
```bash
python -m isp.main_crawler https://www.superloop.com \
    --name "Superloop" \
    --networks nbn opticomm \
    --depth 2
```

### **Help**
```bash
python -m isp.main_crawler --help
```

---

## 📂 Where Are Results Saved?

All results saved to: **`output/isp_crawler/`**

**Files created:**
- `<provider>_<timestamp>.json` — Full crawl result with metadata
- `<provider>_latest.json` — Latest result (always current)
- `<provider>_<timestamp>.csv` — Plans only in CSV format

**Example:**
```
output/isp_crawler/
├── telstra_20260525_213045.json
├── telstra_latest.json
├── telstra_20260525_213045.csv
├── superloop_20260525_214512.json
└── superloop_latest.json
```

---

## 🧪 Run Tests

### **Full Test Suite**
```bash
python -m isp.test_crawler
```

### **Quick Test** (Telstra only)
```bash
python -m isp.test_crawler --quick
```

### **Specific Provider**
```bash
python -m isp.test_crawler --provider superloop
```

---

## 🎯 Common Use Cases

### **1. Compare Competitor Prices**
```bash
# Crawl multiple competitors
python -m isp.main_crawler https://www.telstra.com.au/internet --name Telstra
python -m isp.main_crawler https://www.superloop.com --name Superloop
python -m isp.main_crawler https://www.swoop.com.au --name Swoop

# Compare results
cat output/isp_crawler/telstra_latest.json | grep "price"
cat output/isp_crawler/superloop_latest.json | grep "price"
```

### **2. Find Opticomm Providers**
```bash
python -m isp.main_crawler https://www.example.com \
    --networks opticomm \
    --depth 2
```

### **3. Quick Plan Check**
```bash
# Fast crawl, depth 1
python -m isp.main_crawler https://www.telstra.com.au/internet/plans --depth 1
```

### **4. Discover New Plans**
```bash
# Deep crawl to find all plan pages
python -m isp.main_crawler https://www.provider.com --depth 3 --max-urls 200
```

---

## ⚙️ Adjust Crawling Behavior

### **Faster Crawling**
- Set `depth=1`
- Reduce `max_urls`
- Target specific plan URLs directly

### **More Thorough**
- Set `depth=3`
- Increase `max_urls=300`
- Add more `network_types`

### **Target Specific Networks**
```bash
python -m isp.main_crawler https://www.example.com --networks nbn
```

---

## 🐛 Troubleshooting

### **"No plans found"**
1. Check if URL loads in browser
2. Try increasing depth: `--depth 3`
3. Check `page_analyses` in JSON output
4. Verify network types are correct

### **"Crawler is slow"**
1. Reduce depth: `--depth 1`
2. Target specific URLs instead of homepage
3. Reduce max URLs: `--max-urls 50`

### **"Invalid/missing data"**
1. Check `invalid_plans` in JSON output
2. Review validation errors
3. Page may use unusual HTML structure

### **"Server won't start"**
```bash
# Check if port 5000 is in use
netstat -ano | findstr :5000

# Kill process if needed
taskkill /PID <PID> /F

# Try different port
set FLASK_RUN_PORT=5001
python app.py
```

---

## 📖 Next Steps

- Read [README.md](README.md) for full documentation
- Check [test_crawler.py](test_crawler.py) for test examples
- Explore [scraper_engine.py](scraper_engine.py) to understand extraction strategies
- Customize [url_discovery.py](url_discovery.py) keyword scoring

---

## 🎉 You're Ready!

Start discovering and scraping ISP plans automatically! 🚀

**Need help?** Check the full README or review the JSON output for detailed results.
