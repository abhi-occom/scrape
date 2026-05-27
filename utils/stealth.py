"""
Stealth browser utilities.
Shared helpers for creating stealth Playwright browser instances.
Uses playwright-stealth v2 API.
Supports virtual display (Xvfb) for visible browser debugging on headless servers.
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
from threading import Lock

from playwright.sync_api import Browser, BrowserContext, Page
from playwright_stealth import Stealth
from utils.progress import update_progress
from utils.screenshots import capture_page_screenshot

# Try importing pyvirtualdisplay (for Linux servers with Xvfb)
try:
    from pyvirtualdisplay import Display
    HAS_VIRTUAL_DISPLAY = True
except ImportError:
    HAS_VIRTUAL_DISPLAY = False
    Display = None

_stealth = Stealth()
_settings_lock = Lock()
_browser_settings = {
    "headless": True,
    "slow_mo": 0,
}
_debug_refs = []
_debug_contexts = {}
_virtual_display = None  # Global virtual display instance (Xvfb)


def configure_browser(headless: bool = True, slow_mo: int = 0) -> None:
    """Configure browser launch settings used by provider scrapers."""
    with _settings_lock:
        _browser_settings["headless"] = bool(headless)
        _browser_settings["slow_mo"] = max(0, int(slow_mo or 0))


def get_browser_settings() -> dict:
    """Return the current browser launch settings."""
    with _settings_lock:
        return dict(_browser_settings)


def keep_open_for_debug(*objects) -> None:
    """Prevent explicit close calls from shutting visible debug objects."""
    if get_browser_settings()["headless"]:
        return
    for obj in objects:
        if obj is not None:
            _patch_close(obj, "Browser left open for manual inspection")


def create_stealth_browser(playwright, headless: bool = None, slow_mo: int = None) -> Browser:
    """Create a Chromium browser with anti-detection flags."""
    settings = get_browser_settings()
    if headless is None:
        headless = settings["headless"]
    if slow_mo is None:
        slow_mo = settings["slow_mo"]

    if not headless:
        # Start virtual display if on Linux without GUI
        _start_virtual_display()
        return create_persistent_debug_chromium(playwright, slow_mo=slow_mo)

    return playwright.chromium.launch(
        headless=headless,
        slow_mo=slow_mo,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )


def create_persistent_debug_chromium(playwright, slow_mo: int = 0) -> Browser:
    """
    Launch Chromium outside Playwright's ownership and connect over CDP.

    This keeps visible debug windows open after the scraper finishes. Users can
    close the browser manually after inspecting the loaded pages.
    """
    port = _free_port()
    user_data_dir = tempfile.mkdtemp(prefix="isp_scraper_chromium_")
    executable = playwright.chromium.executable_path
    args = [
        executable,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--new-window",
        "about:blank",
    ]

    process = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=os.name != "nt",
    )

    endpoint = f"http://127.0.0.1:{port}"
    browser = None
    last_error = None
    for _ in range(50):
        try:
            browser = playwright.chromium.connect_over_cdp(endpoint, slow_mo=slow_mo)
            break
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)

    if browser is None:
        process.terminate()
        raise RuntimeError(f"Unable to connect to visible Chromium: {last_error}")

    _debug_refs.append((process, browser, user_data_dir))
    _patch_close(browser, "Browser left open for manual inspection")
    return browser


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _patch_close(obj, message: str) -> None:
    try:
        original_close = getattr(obj, "close", None)
        setattr(obj, "_scraper_original_close", original_close)
        setattr(obj, "close", lambda *args, **kwargs: update_progress(message=message))
    except Exception:
        pass


def create_stealth_context(browser: Browser) -> BrowserContext:
    """Create a browser context with realistic fingerprints."""
    settings = get_browser_settings()
    if not settings["headless"]:
        key = id(browser)
        if key not in _debug_contexts:
            _debug_contexts[key] = browser.contexts[0] if browser.contexts else browser.new_context()
            try:
                _debug_contexts[key].set_extra_http_headers({
                    "Accept-Language": "en-AU,en;q=0.9",
                    "Upgrade-Insecure-Requests": "1",
                })
            except Exception:
                pass
            _patch_close(_debug_contexts[key], "Browser context left open for manual inspection")
        return _debug_contexts[key]

    return browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720},
        locale="en-AU",
        timezone_id="Australia/Sydney",
        color_scheme="light",
        extra_http_headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-AU,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        },
    )


def create_stealth_page(browser: Browser) -> Page:
    """Create a stealth page with full anti-detection applied."""
    context = create_stealth_context(browser)
    page = context.new_page()
    try:
        page.set_viewport_size({"width": 1280, "height": 720})
    except Exception:
        pass
    page.on(
        "framenavigated",
        lambda frame: frame == page.main_frame and update_progress(
            status="loading",
            message="Page loaded",
            current_url=page.url,
        ),
    )
    page.on("load", lambda: capture_loaded_page(page))
    if not get_browser_settings()["headless"]:
        _patch_close(page, "Tab left open for manual inspection")
    _stealth.apply_stealth_sync(page)
    return page


def capture_loaded_page(page: Page) -> None:
    """Capture a screenshot once a page finishes loading."""
    try:
        # Check if page is still alive before taking screenshot
        if page.is_closed():
            return
        
        url = page.url
        if not url or url == getattr(page, "_last_screenshot_url", None):
            return
        setattr(page, "_last_screenshot_url", url)
        
        # Double-check before screenshot (async event may have closed page)
        if page.is_closed():
            return
            
        screenshot = capture_page_screenshot(page, label="loaded")
        if screenshot:
            update_progress(
                message="Screenshot captured",
                current_url=url,
                screenshot=screenshot,
            )
    except Exception as exc:
        # Silently ignore if page closed during screenshot
        if "closed" not in str(exc).lower():
            update_progress(message=f"Screenshot failed: {exc}")


def _start_virtual_display() -> None:
    """Start Xvfb virtual display if needed (Linux servers without GUI)."""
    global _virtual_display
    
    # Skip if already running
    if _virtual_display is not None:
        return
    
    # Skip if not Linux or pyvirtualdisplay not available
    if not HAS_VIRTUAL_DISPLAY or sys.platform not in ('linux', 'linux2'):
        return
    
    # Skip if DISPLAY is already set (native GUI available)
    if os.environ.get('DISPLAY'):
        return
    
    # Try to start virtual display
    try:
        _virtual_display = Display(visible=True, size=(1280, 900))
        _virtual_display.start()
        update_progress(
            status="info",
            message="Virtual display (Xvfb) started for visible browser debugging"
        )
    except Exception as exc:
        # Fallback silently - native browser will open on Windows/Mac
        update_progress(
            status="warning",
            message=f"Virtual display unavailable, using native browser: {exc}"
        )
        _virtual_display = None


def _stop_virtual_display() -> None:
    """Stop the virtual display if running."""
    global _virtual_display
    if _virtual_display is not None:
        try:
            _virtual_display.stop()
        except Exception:
            pass
        _virtual_display = None


def has_virtual_display_support() -> bool:
    """Check if virtual display (Xvfb) is available on this system."""
    if not HAS_VIRTUAL_DISPLAY:
        return False
    if sys.platform not in ('linux', 'linux2'):
        return False
    # Check if Xvfb is installed
    try:
        import shutil
        return shutil.which('Xvfb') is not None
    except Exception:
        return False
