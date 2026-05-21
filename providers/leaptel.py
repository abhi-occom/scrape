"""Leaptel ISP provider scraper."""

import re
from typing import List, Dict, Any, Optional

from playwright.sync_api import sync_playwright

from utils.stealth import create_stealth_browser, create_stealth_page
from utils.logger import log_info, log_success, log_error, log_warning
import config


LEAPTEL_PAGES = {
    "nbn": {
        "url": "https://leaptel.com.au/plans/?provider=nbn",
        "network_type": "NBN",
    },
    "opticomm": {
        "url": "https://leaptel.com.au/plans/?provider=opt",
        "network_type": "Opticomm",
    },
    "redtrain": {
        "url": "https://leaptel.com.au/plans/?provider=red",
        "network_type": "Redtrain",
    },
    "fixed_wireless": {
        "url": "https://leaptel.com.au/fixed-wireless/",
        "network_type": "Fixed Wireless",
    },
}


PLAN_NAMES = [
    "Pronto",
    "Accelerated",
    "Full Throttle",
    "Fast",
    "Ultrafast",
    "Fixed Wireless +",
    "Fixed Wireless Fast",
    "Fixed Wireless Superfast",
]


def extract_number(text: str) -> int:
    """Extract first number from text."""
    match = re.search(r"\d+", str(text))
    return int(match.group()) if match else 0


def extract_price(text: str) -> float:
    """Extract price from text like '$49.95 / month'."""
    match = re.search(r"\$(\d+\.?\d*)", str(text))
    return float(match.group(1)) if match else 0.0


def extract_speed_range(text: str) -> tuple:
    """Extract speed range from text like '75-100Mbps' or '25Mbps'."""
    text = str(text).replace("Mbps", "").strip()
    if "-" in text:
        parts = text.split("-")
        try:
            return int(parts[0].strip()), int(parts[1].strip())
        except Exception:
            return 0, 0

    try:
        val = int(text)
        return val, val
    except Exception:
        return 0, 0


def extract_max_speed(text: str) -> int:
    """Extract the max speed from '25Mbps' or '75-100Mbps'."""
    nums = [int(num) for num in re.findall(r"\d+", str(text))]
    return max(nums) if nums else 0


def extract_plan_section(page_text: str) -> str:
    """Extract only the rendered internet plan section."""
    start = page_text.find("2. Build your perfect plan")
    if start == -1:
        start = 0

    end_markers = [
        "3. Now, customise your plan",
        "Would you like to include a home phone line?",
        "Your perfect plan",
        "Why choose Leaptel",
    ]

    end = len(page_text)
    for marker in end_markers:
        idx = page_text.find(marker, start + 1)
        if idx != -1:
            end = min(end, idx)

    return page_text[start:end]


def split_plan_blocks(section_text: str) -> List[List[str]]:
    """Split the plan section into one block per plan."""
    lines = [line.strip() for line in section_text.splitlines() if line.strip()]
    indexes = [i for i, line in enumerate(lines) if line in PLAN_NAMES]

    blocks = []
    for pos, start in enumerate(indexes):
        end = indexes[pos + 1] if pos + 1 < len(indexes) else len(lines)
        blocks.append(lines[start:end])

    return blocks


def extract_plan_from_block(
    block: List[str],
    network_type: str,
    source_url: str,
) -> Optional[Dict[str, Any]]:
    """Extract plan data from a rendered Leaptel plan text block."""
    try:
        if not block:
            return None

        plan_name = block[0]
        block_text = "\n".join(block)

        download_speed = 0
        upload_speed = 0

        for i, line in enumerate(block):
            if i + 1 < len(block) and block[i + 1].upper() == "DOWNLOAD":
                download_speed = extract_max_speed(line)

            if i + 1 < len(block) and block[i + 1].upper() == "UPLOAD":
                upload_speed = extract_max_speed(line)

        typical_evening_speed = None
        for i, line in enumerate(block):
            if line.lower().startswith("typical evening speed"):
                if i + 1 < len(block):
                    typical_evening_speed = block[i + 1]
                break

        price_match = re.search(r"\$(\d+(?:\.\d+)?)\s*/\s*month", block_text)
        if not price_match:
            return None

        displayed_price = float(price_match.group(1))
        ongoing_price = displayed_price
        promo_price = None
        promo_period = None
        promo_discount = None

        discount_match = re.search(
            r"\$(\d+(?:\.\d+)?)\s*discount\s*for\s*(\d+)\s*(months?|years?),\s*then\s*\$(\d+(?:\.\d+)?)\s*ongoing",
            block_text,
            flags=re.IGNORECASE,
        )

        if discount_match:
            promo_discount = float(discount_match.group(1))
            promo_period = f"{discount_match.group(2)} {discount_match.group(3)}"
            promo_price = displayed_price
            ongoing_price = float(discount_match.group(4))

        saving_match = re.search(r"Save\s*\$(\d+(?:\.\d+)?)", block_text, flags=re.IGNORECASE)
        total_saving = float(saving_match.group(1)) if saving_match else None

        notes = []
        if "Recommended" in block:
            notes.append("Recommended")
        if "Eligible locations only" in block_text or "eligible locations only" in block_text:
            notes.append("Eligible locations only")
        if "Available for FTTP technology at eligible locations only" in block_text:
            notes.append("Available for FTTP technology at eligible locations only")

        return {
            "provider_id": config.PROVIDERS.get("leaptel", {}).get("id", 8),
            "plan_name": plan_name,
            "network_type": network_type,
            "download_speed": download_speed,
            "upload_speed": upload_speed,
            "typical_evening_speed": typical_evening_speed,
            "data": "Unlimited" if "UNLIMITED DATA" in block else None,
            "price": ongoing_price,
            "promo_price": promo_price,
            "promo_period": promo_period,
            "promo_discount": promo_discount,
            "total_saving": total_saving,
            "contract": "No Contract",
            "source_url": source_url,
        }

    except Exception as e:
        log_error(f"Error extracting plan block: {str(e)}", provider="leaptel")
        return None


def scrape_page(browser, url: str, network_type: str) -> List[Dict[str, Any]]:
    """Scrape a single Leaptel page and extract plans."""
    plans = []
    page = None

    try:
        page = create_stealth_page(browser)
        page.goto(url, timeout=60000, wait_until="networkidle")
        page.wait_for_selector("text=Build your perfect plan", timeout=30000)
        page.wait_for_timeout(2500)

        page_text = page.inner_text("body")
        plan_section = extract_plan_section(page_text)
        plan_blocks = split_plan_blocks(plan_section)

        log_info(f"Found {len(plan_blocks)} plan blocks on {network_type} page", provider="leaptel")

        for block in plan_blocks:
            plan = extract_plan_from_block(block, network_type, url)
            if plan:
                plans.append(plan)

        seen = set()
        unique_plans = []
        for plan in plans:
            key = (
                plan["plan_name"],
                plan["network_type"],
                plan["price"],
                plan["promo_price"],
                plan["download_speed"],
                plan["upload_speed"],
            )
            if key not in seen:
                seen.add(key)
                unique_plans.append(plan)

        log_success(f"Extracted {len(unique_plans)} unique plans from {network_type} page", provider="leaptel")
        return unique_plans

    except Exception as e:
        log_error(f"Error scraping {network_type} page: {str(e)}", provider="leaptel")
        return plans

    finally:
        if page:
            page.close()


def scrape_leaptel_plans() -> List[Dict[str, Any]]:
    """Main scraper function - returns flat list of all Leaptel plans."""
    all_plans = []

    try:
        with sync_playwright() as p:
            browser = create_stealth_browser(p)

            try:
                for page_key, page_config in LEAPTEL_PAGES.items():
                    try:
                        log_info(f"Scraping {page_key} plans", provider="leaptel")
                        plans = scrape_page(
                            browser,
                            page_config["url"],
                            page_config["network_type"],
                        )
                        all_plans.extend(plans)

                    except Exception as e:
                        log_error(f"Failed to scrape {page_key}: {str(e)}", provider="leaptel")
                        continue

            finally:
                browser.close()

        log_success(f"Scraping complete. Total plans: {len(all_plans)}", provider="leaptel")
        return all_plans

    except Exception as e:
        log_error(f"Fatal error in scrape_leaptel_plans: {str(e)}", provider="leaptel")
        return all_plans