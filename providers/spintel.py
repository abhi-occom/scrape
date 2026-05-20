import re
import sys
import os
from typing import List, Dict, Any, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import log_info, log_error, log_success, log_warning
from utils.stealth import create_stealth_browser, create_stealth_page
from playwright.sync_api import sync_playwright

PROVIDER_ID = 17  # Fixed ID for Spintel
URL = 'https://www.spintel.net.au/home-internet/nbn'

# Valid plan names to filter - we only want NBN, Fixed Wireless, and Fibre plans
VALID_PLAN_KEYWORDS = [
    'home starter', 'home turbo', 'home ultrafast', 'home superfast', 'home fast',
    'fixed wireless', 'wireless plus', 'wireless homefast', 'wireless superfast',
    'fibre upgrade', 'fibre standard', 'fibre plus', 'fibre premium'
]

# Network type derived from plan name prefix
NETWORK_TYPE_MAP = {
    'home starter': 'NBN',
    'home turbo': 'NBN',
    'home ultrafast': 'NBN',
    'home superfast': 'NBN',
    'home fast': 'NBN',
    'nbn': 'NBN',
    'fixed wireless': 'Fixed Wireless',
    'wireless plus': 'Fixed Wireless',
    'wireless homefast': 'Fixed Wireless',
    'wireless superfast': 'Fixed Wireless',
    'fibre upgrade': 'Fibre',
    'fibre': 'Fibre',
}


def _normalise_text(text: str) -> str:
    """Lowercase, strip special chars and collapse spaces."""
    text = text.lower()
    for ch in ('®', '™', '\xa0', '\u00ae', '\u2019'):
        text = text.replace(ch, '')
    return re.sub(r'\s+', ' ', text).strip()


def _network_type_from_name(name_normalised: str) -> str:
    """Determine network type from normalised plan heading."""
    for prefix, ntype in NETWORK_TYPE_MAP.items():
        if prefix in name_normalised:
            return ntype
    return 'NBN'  # safe fallback


def _parse_price(raw: str) -> Optional[float]:
    """Extract dollar amount - first price in the text (promo price)."""
    price_match = re.search(r'^\$(\d+\.?\d*)', raw.strip(), re.MULTILINE)
    if price_match:
        return float(price_match.group(1))
    price_match = re.search(r'\$(\d+\.?\d*)', raw)
    if price_match:
        return float(price_match.group(1))
    return None


def _parse_ongoing_price(raw: str) -> Optional[float]:
    """Extract the ongoing price from text like 'For 6 months, then $64.95 ongoing*'."""
    match = re.search(r'then\s+\$(\d+\.?\d*)\s+ongoing', raw, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def _parse_speed(text: str) -> Tuple[int, int]:
    """Extract download/upload speeds from text like '500/50 Mbps' or '25/8 Mbps'."""
    match = re.search(r'(\d+)/(\d+)\s*Mbps', text, re.IGNORECASE)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.search(r'(\d+)/(\d+)', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def _parse_promo_period(text: str) -> Optional[str]:
    """Extract promo period from text like 'For 6 months, then $64.95 ongoing*'."""
    match = re.search(r'For\s+(?:the\s+)?(?:first\s+)?(\d+)\s*months?', text, re.IGNORECASE)
    if match:
        return f"{match.group(1)} months"
    return None


def _is_valid_plan(full_text: str, plan_name: str) -> bool:
    """Check if this is a valid NBN/Fixed Wireless/Fibre plan (not mobile/VOIP)."""
    text_lower = full_text.lower()
    name_lower = plan_name.lower()
    
    # Skip if it contains mobile-specific keywords
    if any(kw in text_lower for kw in ['unlimited calls', 'esim', 'mobile broadband', '4g/5g']):
        if 'mbps' not in text_lower:
            return False
    
    # Skip if it's the 200GB wireless plan
    if '200gb' in text_lower and 'capped' in text_lower:
        return False
    
    # Skip VOIP plans
    if 'free incoming' in name_lower or 'unlimited national' in name_lower:
        return False
    
    # Must have Mbps in the text for internet plans
    if 'mbps' not in text_lower:
        return False
        
    # Must contain valid plan keywords
    text_for_check = text_lower + name_lower
    if not any(kw in text_for_check for kw in VALID_PLAN_KEYWORDS):
        # But allow if it has typical speed pattern
        if not re.search(r'\d+/\d+\s*mbps', text_lower):
            return False
    
    return True


def _extract_plan_name(block) -> str:
    """Extract clean plan name from the block element."""
    # Try .heading-6 first
    heading_el = block.query_selector('.heading-6')
    if heading_el:
        name = heading_el.inner_text().strip()
        if name and not name.startswith('$') and len(name) < 50:
            return name
    
    # Try .plan-heading
    heading_el = block.query_selector('.plan-heading')
    if heading_el:
        name = heading_el.inner_text().strip()
        if name and not name.startswith('$') and len(name) < 50:
            return name
    
    # Try to get from full text - look for first line with valid plan name
    full_text = block.inner_text()
    lines = full_text.split('\n')
    for line in lines:
        line = line.strip()
        if line and not line.startswith('$') and 'mbps' not in line.lower() and 'per month' not in line.lower():
            # Check if this looks like a plan name
            if any(kw in line.lower() for kw in ['home ', 'wireless', 'fibre', 'nbn']) or re.search(r'\d+/\d+', line):
                if len(line) < 50:
                    return line
    
    return ""


def _extract_plan(block, cls: str) -> Optional[Dict[str, Any]]:
    """
    Extract a single plan dict from a .plan-block.product-option element.
    """
    try:
        full_text = block.inner_text()
        
        # Get plan name
        plan_name = _extract_plan_name(block)
        if not plan_name:
            return None
        
        # Validate this is a real plan we want
        if not _is_valid_plan(full_text, plan_name):
            return None
        
        plan_name_norm = _normalise_text(plan_name)
        
        # --- Network Type ---
        network_type = _network_type_from_name(plan_name_norm)
        
        # --- Price ---
        price_el = block.query_selector('.plan-price')
        if not price_el:
            return None
        
        price_text = price_el.inner_text().strip()
        current_price = _parse_price(price_text)
        ongoing_price = _parse_ongoing_price(price_text)
        
        if current_price is None:
            return None
        
        # Use ongoing price as the regular price
        regular_price = ongoing_price if ongoing_price else current_price
        
        # --- Speed ---
        desc_el = block.query_selector('.plan-description')
        desc_text = desc_el.inner_text() if desc_el else full_text
        
        download_speed, upload_speed = _parse_speed(desc_text)
        
        # Fallback: infer speed from plan name if not found
        if download_speed == 0:
            if 'starter' in plan_name_norm or '25' in plan_name:
                download_speed, upload_speed = 25, 8
            elif 'turbo' in plan_name_norm or '500' in plan_name:
                download_speed, upload_speed = 500, 50
            elif 'ultrafast' in plan_name_norm or '1000' in plan_name:
                download_speed, upload_speed = 1000, 100
            elif 'homefast' in plan_name_norm or '250' in plan_name:
                download_speed, upload_speed = 250, 20
            elif 'superfast' in plan_name_norm or '400' in plan_name:
                download_speed, upload_speed = 400, 40
            elif 'plus' in plan_name_norm or '100' in plan_name:
                download_speed, upload_speed = 100, 20
        
        # --- Promo Period ---
        promo_period = _parse_promo_period(price_text)
        
        return {
            'provider_id': PROVIDER_ID,
            'provider': 'spintel',
            'plan_name': plan_name,
            'network_type': network_type,
            'download_speed': download_speed,
            'upload_speed': upload_speed,
            'speed': download_speed,
            'price': regular_price,
            'promo_price': current_price if ongoing_price else None,
            'promo_period': promo_period,
            'data_allowance': 'Unlimited',
            'contract': 'No Contract',
            'source_url': URL,
        }

    except Exception as e:
        log_error(f'Error extracting spintel plan: {e}', provider='spintel')
        return None


def scrape_spintel_plans() -> List[Dict[str, Any]]:
    """
    Scrape all Spintel internet plans from /home-internet/nbn.
    """
    log_info('Starting Spintel scraper', provider='spintel')
    all_plans: List[Dict[str, Any]] = []

    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)
            page = create_stealth_page(browser)

            page.goto(URL, timeout=30000, wait_until='domcontentloaded')
            page.wait_for_timeout(8000)

            # Get all plan-block.product-option elements
            plan_blocks = page.query_selector_all('.plan-block.product-option')
            log_info(f'Found {len(plan_blocks)} plan-block.product-option elements', provider='spintel')

            seen: set = set()

            for block in plan_blocks:
                cls = block.get_attribute('class') or ''
                
                # Skip options elements (Yes/No selectors)
                if 'options-content-box' in cls:
                    continue
                
                plan = _extract_plan(block, cls)
                if plan:
                    key = f"{plan['plan_name']}|{plan['network_type']}"
                    if key not in seen:
                        seen.add(key)
                        all_plans.append(plan)
                        log_info(f"  Found: {plan['plan_name']} ({plan['network_type']}) ${plan['price']}", provider='spintel')

            browser.close()

    except Exception as e:
        log_error(f'Spintel scraper failed: {e}', provider='spintel')

    # Sort: NBN first, then Fixed Wireless, then Fibre; within each by download speed
    ORDER = {'NBN': 0, 'Fixed Wireless': 1, 'Fibre': 2}
    all_plans.sort(key=lambda x: (ORDER.get(x['network_type'], 9), x['download_speed']))

    log_success(
        f'Spintel scraper complete: {len(all_plans)} plans '
        f'({sum(1 for p in all_plans if p["network_type"]=="NBN")} NBN, '
        f'{sum(1 for p in all_plans if p["network_type"]=="Fixed Wireless")} Fixed Wireless, '
        f'{sum(1 for p in all_plans if p["network_type"]=="Fibre")} Fibre)',
        provider='spintel',
    )
    return all_plans


if __name__ == '__main__':
    plans = scrape_spintel_plans()
    print(f'\nTotal plans: {len(plans)}')
    for plan in plans:
        promo = f" (promo: ${plan['promo_price']}/mth for {plan['promo_period']})" if plan.get('promo_price') else ''
        print(
            f"  [{plan['network_type']:15}] {plan['plan_name']:35}  "
            f"{plan['download_speed']:4}/{plan['upload_speed']:3} Mbps  "
            f"${plan['price']}/mth{promo}"
        )
