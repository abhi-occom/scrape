# Xvfb + VNC Setup Guide for Visible Browser Debugging

## 📋 Overview

This guide helps you set up virtual display (Xvfb) for visible browser debugging on headless servers and Windows localhost.

**Strategy**: Same code works on both platforms with graceful fallback.

```
Windows Localhost                    Ubuntu Server
┌─────────────────────┐             ┌─────────────────────┐
│ pyvirtualdisplay    │──deploy──►  │ pyvirtualdisplay    │
│ ↓ (no Xvfb)         │   same      │ ↓ (has Xvfb)        │
│ Fallback to native  │   code      │ Uses Xvfb           │
│ browser opening ✅   │             │ + VNC access ✅      │
└─────────────────────┘             └─────────────────────┘
```

---

## Phase 1: Windows Localhost Testing

### Step 1: Install Python Dependencies

```bash
# Install pyvirtualdisplay (will be used on server)
pip install -r requirements.txt
```

### Step 2: Start the Server

```bash
# Start Flask server
python app.py
```

Server runs at: `http://localhost:5000`

### Step 3: Test Visible Browser Mode

1. Open dashboard: `http://localhost:5000`
2. Check the "Show browser while scraping" checkbox
3. Select a provider (e.g., Optus, Telstra)
4. Click **Scrape**

**Expected Behavior on Windows**:
- ✅ Browser window opens natively (no Xvfb needed)
- ✅ You can watch the scraping live
- ✅ Slow motion slider works
- ✅ Browser stays open after scraping completes

### Step 4: Verify Fallback Logic

The code will:
1. Try to import `pyvirtualdisplay` ✅
2. Try to start Xvfb ❌ (fails on Windows - no Xvfb installed)
3. Fall back to native browser ✅ (opens normally)

Check console for message:
```
Virtual display unavailable, using native browser: ...
```

This confirms the fallback works correctly!

---

## Phase 2: Ubuntu Server Deployment

### Step 1: Install System Dependencies

```bash
# On Ubuntu server
sudo apt-get update
sudo apt-get install -y xvfb x11vnc xfwm4
```

### Step 2: Install Python Dependencies

```bash
# Upload code to server, then:
pip install -r requirements.txt
```

### Step 3: Start Virtual Display + VNC Server

**Option A: Manual Start (for testing)**

```bash
# Start virtual display on screen :99
Xvfb :99 -screen 0 1280x900x24 &

# Export display
export DISPLAY=:99

# Start VNC server (no password for testing)
x11vnc -display :99 -nopw -listen 0.0.0.0 -xkb &
```

**Option B: Systemd Service (production)**

Create `/etc/systemd/system/xvfb.service`:

```ini
[Unit]
Description=Virtual Frame Buffer X Server
After=network.target

[Service]
ExecStart=/usr/bin/Xvfb :99 -screen 0 1280x900x24
Restart=always
User=your-username
Environment="DISPLAY=:99"

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/x11vnc.service`:

```ini
[Unit]
Description=VNC Server for Xvfb
After=xvfb.service
Requires=xvfb.service

[Service]
ExecStart=/usr/bin/x11vnc -display :99 -nopw -xkb -forever -shared
Restart=always
User=your-username

[Install]
WantedBy=multi-user.target
```

Enable services:
```bash
sudo systemctl enable xvfb x11vnc
sudo systemctl start xvfb x11vnc
```

### Step 4: Start Flask Server

```bash
export DISPLAY=:99  # Important!
python app.py
```

### Step 5: Connect via VNC (Secure Tunnel)

**On your local machine**:

```bash
# Create SSH tunnel (forwards VNC port 5900)
ssh -L 5900:localhost:5900 user@your-server-ip
```

**Connect VNC client to**: `localhost:5900`

**VNC Clients**:
- Windows: [RealVNC Viewer](https://www.realvnc.com/en/connect/download/viewer/)
- Mac: Built-in Screen Sharing or RealVNC
- Linux: Remmina or TigerVNC

### Step 6: Test Remote Debugging

1. Keep VNC client connected
2. Open browser: `http://your-server-ip:5000`
3. Check "Show browser while scraping"
4. Click **Scrape**
5. **Watch the browser in VNC window** 🎉

---

## 🔧 Troubleshooting

### Problem: "Capability check failed" in browser console

**Solution**: Backend `/api/capabilities` endpoint is not responding.

Check server logs:
```bash
# In app.py terminal
# Should see: GET /api/capabilities 200
```

### Problem: Browser doesn't open on Windows

**Solution**: Check if `headless=False` is being passed correctly.

1. Open browser DevTools (F12)
2. Click Scrape
3. Check Network tab → POST to `/api/scrape/provider`
4. Request payload should have: `{"visible_browser": true, "slow_mo": 0}`

### Problem: VNC shows black screen

**Solution**: Xvfb not running or DISPLAY not set.

```bash
# Check if Xvfb is running
ps aux | grep Xvfb

# Restart Xvfb
sudo systemctl restart xvfb

# Export DISPLAY before starting Flask
export DISPLAY=:99
python app.py
```

### Problem: Can't connect to VNC from local machine

**Solution**: Check SSH tunnel and firewall.

```bash
# Verify SSH tunnel is active (local machine)
netstat -an | grep 5900

# On server, check if x11vnc is listening
sudo netstat -tlnp | grep 5900
```

---

## 🎯 Production Recommendations

| Usage | Recommendation |
|---|---|
| **Normal scraping** | Keep `headless=True` (fast, no GUI overhead) |
| **Debugging scrapers** | Use `headless=False` + VNC (temporary) |
| **Security** | Always use SSH tunnel for VNC (never expose port 5900) |
| **Server resources** | 2 CPU cores is tight - use visible mode sparingly |
| **Development** | Test on localhost first, deploy to server when confirmed working |

---

## 📊 Resource Usage Comparison

| Mode | CPU | RAM | Notes |
|---|---|---|---|
| `headless=True` | 1 core | ~500MB | Production default |
| `headless=False` (local) | 1 core | ~600MB | Native browser |
| `headless=False` (Xvfb) | 1.5 cores | ~800MB | Virtual display overhead |
| `headless=False` + VNC | 1.8 cores | ~900MB | With VNC streaming |

**Recommendation**: On your 2-core server, use visible mode **only when debugging**, not for production scrapes.

---

## ✅ Success Checklist

### Windows Localhost
- [ ] `pip install -r requirements.txt` completed
- [ ] Server starts: `python app.py`
- [ ] Dashboard loads: `http://localhost:5000`
- [ ] "Show browser" checkbox works
- [ ] Browser opens when scraping
- [ ] Slow motion slider affects browser speed
- [ ] No errors in console

### Ubuntu Server
- [ ] Xvfb installed: `which Xvfb`
- [ ] x11vnc installed: `which x11vnc`
- [ ] Services running: `systemctl status xvfb x11vnc`
- [ ] DISPLAY set: `echo $DISPLAY` → `:99`
- [ ] Flask server running with DISPLAY exported
- [ ] SSH tunnel active on local machine
- [ ] VNC client connects to `localhost:5900`
- [ ] Can see browser window in VNC
- [ ] Scraper works with visible browser

---

## 🚀 Quick Start Commands

### Windows (Localhost)
```bash
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

### Ubuntu (Server)
```bash
# One-time setup
sudo apt-get install -y xvfb x11vnc
pip install -r requirements.txt

# Start services
Xvfb :99 -screen 0 1280x900x24 &
export DISPLAY=:99
x11vnc -display :99 -nopw -xkb &

# Run server
python app.py
```

### Local Machine (VNC Access)
```bash
ssh -L 5900:localhost:5900 user@your-server-ip
# Then connect VNC to: localhost:5900
```

---

## 📞 Support

If you encounter issues:

1. Check server logs: `tail -f app.log` (if logging enabled)
2. Check Xvfb logs: `journalctl -u xvfb -f`
3. Check x11vnc logs: `journalctl -u x11vnc -f`
4. Verify Python packages: `pip list | grep virtual`
5. Test manually: `DISPLAY=:99 chromium-browser --version`

---

## 🎓 How It Works

### Code Flow

```python
# utils/stealth.py

def create_stealth_browser(playwright, headless=None, slow_mo=None):
    if not headless:
        _start_virtual_display()  # Try Xvfb, fall back if unavailable
        return create_persistent_debug_chromium(playwright, slow_mo)
    # Normal headless mode
    return playwright.chromium.launch(headless=True, ...)

def _start_virtual_display():
    if HAS_VIRTUAL_DISPLAY and sys.platform == 'linux':
        try:
            display = Display(visible=True, size=(1280, 900))
            display.start()
        except:
            # Fallback - native browser will open (Windows/Mac)
            pass
```

**Windows**: Xvfb not available → fallback → native browser opens  
**Linux**: Xvfb available → virtual display → browser in Xvfb → VNC shows it

---

## 📝 Next Steps

After confirming everything works:

1. ✅ Disable visible browser for production scrapes
2. ✅ Use it only when a scraper breaks and needs visual debugging
3. ✅ Consider adding password to VNC in production: `x11vnc -usepw`
4. ✅ Monitor server resources during visible browser sessions

**You're all set!** 🎉
