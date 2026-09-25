"""OCR-based price verification: cross-checks scraped plan prices against the
text Tesseract reads off the provider's own page screenshot.

Non-blocking by design: a missing screenshot, a missing Tesseract install, or
a price mismatch only tags the plan with `ocr_*` fields. It never drops a
plan or fails a scrape.
"""
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.screenshots import SCREENSHOT_ROOT

_PRICE_RE = re.compile(r'\$\s?(\d{1,4}(?:\.\d{2})?)')


def extract_prices_from_image(image_path: str) -> List[float]:
    """Run Tesseract OCR on a screenshot and pull out every dollar amount found."""
    import pytesseract
    from PIL import Image

    text = pytesseract.image_to_string(Image.open(image_path))
    return [float(m) for m in _PRICE_RE.findall(text)]


def verify_plan_price(plan: Dict[str, Any], screenshot_path: str, tolerance: float = 0.01) -> Dict[str, Any]:
    """Check whether the plan's scraped price(s) appear in the screenshot's OCR text.

    Always returns a result dict; never raises past this boundary.
    """
    try:
        found = extract_prices_from_image(screenshot_path)
    except Exception as exc:
        return {'ocr_checked': False, 'ocr_warning': f'OCR failed: {exc}'}

    targets = [p for p in (plan.get('price'), plan.get('promo_price')) if isinstance(p, (int, float))]
    if not targets:
        return {'ocr_checked': True, 'ocr_verified': None, 'ocr_prices_found': found, 'ocr_warning': None}

    matched = any(abs(t - f) <= tolerance for t in targets for f in found)
    return {
        'ocr_checked': True,
        'ocr_verified': matched,
        'ocr_prices_found': found,
        'ocr_warning': None if matched else
            f"Scraped price {targets} not found in screenshot OCR text {found}",
    }


def find_latest_screenshot(provider_name: str, since: Optional[datetime] = None) -> Optional[str]:
    """Find the most recent screenshot saved for a provider.

    When `since` is given, only screenshots taken at/after that time are
    considered, so verification only uses screenshots from the current run.
    """
    provider_dir = os.path.join(SCREENSHOT_ROOT, provider_name)
    if not os.path.isdir(provider_dir):
        return None

    candidates = []
    for name in os.listdir(provider_dir):
        path = os.path.join(provider_dir, name)
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            continue
        if since and datetime.fromtimestamp(mtime) < since:
            continue
        candidates.append((mtime, path))

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _tag_all(plans: List[Dict[str, Any]], fields: Dict[str, Any]) -> None:
    for plan in plans:
        if isinstance(plan, dict):
            plan.update(fields)


def _verify_all(plans: List[Dict[str, Any]], screenshot_path: str) -> None:
    for plan in plans:
        if isinstance(plan, dict):
            plan.update(verify_plan_price(plan, screenshot_path))


def apply_ocr_verification(plans: Any, provider_name: str, since: Optional[datetime] = None) -> Any:
    """Attach `ocr_*` fields to every plan for a provider, using the most recent
    screenshot captured during this scrape run.

    Handles both simple providers (`plans` is a list) and multi-page providers
    (`plans` is a dict of sub_key -> list). Mutates and returns `plans`.
    """
    screenshot_path = find_latest_screenshot(provider_name, since)
    if not screenshot_path:
        no_screenshot = {'ocr_checked': False, 'ocr_warning': 'No screenshot captured for this run'}
        if isinstance(plans, list):
            _tag_all(plans, no_screenshot)
        elif isinstance(plans, dict):
            for sub_plans in plans.values():
                if isinstance(sub_plans, list):
                    _tag_all(sub_plans, no_screenshot)
        return plans

    if isinstance(plans, list):
        _verify_all(plans, screenshot_path)
    elif isinstance(plans, dict):
        for sub_plans in plans.values():
            if isinstance(sub_plans, list):
                _verify_all(sub_plans, screenshot_path)

    return plans
