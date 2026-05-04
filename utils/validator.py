"""
Validator utility module.
Validates plan data and removes invalid records.
"""

from typing import List, Dict, Any, Optional
import re


def validate_plan(plan: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate a single plan record.
    
    Required fields:
    - plan_name: Must exist and be non-empty
    - price: Must exist and be a valid number
    - speed: Must exist and be a valid number
    
    Args:
        plan: Plan dictionary to validate
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check plan_name exists and is non-empty
    if not plan.get('plan_name'):
        return False, "Missing or empty plan_name"
    
    if not isinstance(plan.get('plan_name'), str) or not plan['plan_name'].strip():
        return False, "plan_name must be a non-empty string"
    
    # Check price exists and is valid
    price = plan.get('price') or plan.get('monthly_price')
    if price is None:
        return False, "Missing price or monthly_price"
    
    try:
        price_float = float(price)
        if price_float < 0:
            return False, "Price cannot be negative"
    except (ValueError, TypeError):
        return False, f"Invalid price format: {price}"
    
    # Check speed exists and is valid
    speed = plan.get('speed') or plan.get('speed_label') or plan.get('download_speed')
    if speed is None:
        return False, "Missing speed, speed_label, or download_speed"
    
    try:
        speed_int = int(speed)
        if speed_int < 0:
            return False, "Speed cannot be negative"
    except (ValueError, TypeError):
        return False, f"Invalid speed format: {speed}"
    
    # All validations passed
    return True, None


def validate_plans(plans: List[Dict[str, Any]]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Validate a list of plans and separate valid from invalid.
    
    Args:
        plans: List of plan dictionaries
    
    Returns:
        Tuple of (valid_plans, invalid_plans)
    """
    valid_plans = []
    invalid_plans = []
    
    for plan in plans:
        is_valid, error = validate_plan(plan)
        if is_valid:
            valid_plans.append(plan)
        else:
            invalid_plan = plan.copy()
            invalid_plan['validation_error'] = error
            invalid_plans.append(invalid_plan)
    
    return valid_plans, invalid_plans


def clean_plan_data(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean and normalize plan data.
    
    - Strip whitespace from strings
    - Convert numeric strings to proper types
    - Normalize price formats
    
    Args:
        plan: Plan dictionary to clean
    
    Returns:
        Cleaned plan dictionary
    """
    cleaned = plan.copy()
    
    # Clean string fields
    string_fields = ['plan_name', 'network_type', 'promo_period', 'contract', 'source_url']
    for field in string_fields:
        if field in cleaned and isinstance(cleaned[field], str):
            cleaned[field] = cleaned[field].strip()
    
    # Clean and normalize price
    price_fields = ['price', 'monthly_price', 'promo_price']
    for field in price_fields:
        if field in cleaned:
            cleaned[field] = normalize_price(cleaned[field])
    
    # Clean and normalize speed
    speed_fields = ['speed', 'speed_label', 'download_speed', 'upload_speed']
    for field in speed_fields:
        if field in cleaned and cleaned[field] is not None:
            cleaned[field] = normalize_speed(cleaned[field])
    
    return cleaned


def normalize_price(price_value) -> Optional[float]:
    """
    Normalize price value to float.
    Handles formats like: "$89", "$89/month", "89.00", etc.
    
    Args:
        price_value: Price value (string or number)
    
    Returns:
        Float value or None if invalid
    """
    if price_value is None:
        return None
    
    if isinstance(price_value, (int, float)):
        return float(price_value)
    
    if isinstance(price_value, str):
        # Remove currency symbols and text
        cleaned = re.sub(r'[^\d.]', '', price_value)
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None
    
    return None


def normalize_speed(speed_value) -> Optional[int]:
    """
    Normalize speed value to integer.
    Handles formats like: "100", "100 Mbps", "100Mbps", etc.
    
    Args:
        speed_value: Speed value (string or number)
    
    Returns:
        Integer value or None if invalid
    """
    if speed_value is None:
        return None
    
    if isinstance(speed_value, int):
        return speed_value
    
    if isinstance(speed_value, float):
        return int(speed_value)
    
    if isinstance(speed_value, str):
        # Extract numeric part
        match = re.search(r'(\d+)', speed_value)
        if match:
            return int(match.group(1))
        return None
    
    return None


def extract_speed_from_plan_name(plan_name: str) -> Optional[int]:
    """
    Extract speed value from plan name using regex.
    Useful when speed is embedded in the plan name.
    
    Examples:
        "Premium 100" -> 100
        "Fast 50 Mbps" -> 50
        "Ultra 250Mbps" -> 250
    
    Args:
        plan_name: Plan name string
    
    Returns:
        Extracted speed as integer or None
    """
    if not plan_name or not isinstance(plan_name, str):
        return None
    
    # Look for patterns like "100", "100 Mbps", "100Mbps"
    match = re.search(r'(\d+)\s*(?:mbps|mb)?', plan_name, re.IGNORECASE)
    if match:
        return int(match.group(1))
    
    return None
