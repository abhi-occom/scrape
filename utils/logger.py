"""
Logger utility module.
Handles JSON-based logging (file-based, not database).
"""

import json
import os
from datetime import datetime
from typing import Dict, Any
import config


def ensure_output_dir():
    """Ensure the output directory exists."""
    if not os.path.exists(config.OUTPUT_DIR):
        os.makedirs(config.OUTPUT_DIR)


def log_entry(status: str, message: str, provider: str = None, data: Dict[str, Any] = None):
    """
    Create and append a log entry to the JSON log file.
    
    Args:
        status: Log status ('success', 'error', 'warning', 'info')
        message: Log message
        provider: Provider name (optional)
        data: Additional data to log (optional)
    """
    ensure_output_dir()
    
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'status': status,
        'message': message,
        'provider': provider,
        'data': data or {}
    }
    
    # Read existing logs
    logs = []
    if os.path.exists(config.LOGS_JSON_FILE):
        try:
            with open(config.LOGS_JSON_FILE, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            logs = []
    
    # Append new log entry
    logs.append(log_data)
    
    # Write back to file
    with open(config.LOGS_JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=2, ensure_ascii=False)


def log_success(message: str, provider: str = None, data: Dict[str, Any] = None):
    """Log a success message."""
    log_entry('success', message, provider, data)


def log_error(message: str, provider: str = None, data: Dict[str, Any] = None):
    """Log an error message."""
    log_entry('error', message, provider, data)


def log_warning(message: str, provider: str = None, data: Dict[str, Any] = None):
    """Log a warning message."""
    log_entry('warning', message, provider, data)


def log_info(message: str, provider: str = None, data: Dict[str, Any] = None):
    """Log an informational message."""
    log_entry('info', message, provider, data)


def clear_logs():
    """Clear all logs (use with caution)."""
    if os.path.exists(config.LOGS_JSON_FILE):
        os.remove(config.LOGS_JSON_FILE)
