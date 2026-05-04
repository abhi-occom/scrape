"""
JSON save utility module.
Handles saving plans to JSON file.
"""

import json
import os
from typing import List, Dict, Any
import config


def ensure_output_dir():
    """Ensure the output directory exists."""
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR)


def save_plans_to_json(plans: List[Dict[str, Any]], file_path: str = None):
    """
    Save all plans to a JSON file.
    
    Args:
        plans: List of plan dictionaries
        file_path: Output file path (optional, defaults to config.PLANS_JSON_FILE)
    """
    ensure_output_dir()
    
    if file_path is None:
        file_path = config.PLANS_JSON_FILE
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(plans, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving plans to JSON: {e}")
        return False


def load_plans_from_json(file_path: str = None) -> List[Dict[str, Any]]:
    """
    Load plans from a JSON file.
    
    Args:
        file_path: Input file path (optional, defaults to config.PLANS_JSON_FILE)
    
    Returns:
        List of plan dictionaries
    """
    if file_path is None:
        file_path = config.PLANS_JSON_FILE
    
    if not os.path.exists(file_path):
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def append_plans_to_json(new_plans: List[Dict[str, Any]], file_path: str = None):
    """
    Append new plans to existing JSON file.
    
    Args:
        new_plans: List of new plan dictionaries to append
        file_path: Output file path (optional, defaults to config.PLANS_JSON_FILE)
    """
    ensure_output_dir()
    
    if file_path is None:
        file_path = config.PLANS_JSON_FILE
    
    # Load existing plans
    existing_plans = load_plans_from_json(file_path)
    
    # Merge plans
    all_plans = existing_plans + new_plans
    
    # Save back
    return save_plans_to_json(all_plans, file_path)
