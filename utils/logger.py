"""
Logger utility module.
Handles JSON-based logging (file-based, not database).
"""

import json
import os
import threading
from datetime import datetime
from typing import Dict, Any
import config

_LOG_LOCK = threading.Lock()


def _project_root() -> str:
    """Return the repository root, independent of the process cwd."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_output_path(path: str) -> str:
    """Resolve configured output paths against the repository root."""
    if os.path.isabs(path):
        return os.path.normpath(os.path.abspath(path))
    return os.path.normpath(os.path.abspath(os.path.join(_project_root(), path)))


def _logs_json_file() -> str:
    return _resolve_output_path(config.LOGS_JSON_FILE)


def ensure_output_dir():
    """Ensure the output directory exists."""
    output_dir = _resolve_output_path(config.OUTPUT_DIR)
    os.makedirs(output_dir, exist_ok=True)


def log_entry(status: str, message: str, provider: str = None, data: Dict[str, Any] = None):
    """
    Create and append a log entry to the JSON log file.
    
    Args:
        status: Log status ('success', 'error', 'warning', 'info')
        message: Log message
        provider: Provider name (optional)
        data: Additional data to log (optional)
    """
    log_data = {
        'timestamp': datetime.now().isoformat(),
        'status': status,
        'message': message,
        'provider': provider,
        'data': data or {}
    }

    try:
        ensure_output_dir()
        logs_file = _logs_json_file()

        with _LOG_LOCK:
            # Read existing logs
            logs = []
            if os.path.exists(logs_file):
                try:
                    with open(logs_file, 'r', encoding='utf-8') as f:
                        logs = json.load(f)
                    if not isinstance(logs, list):
                        logs = []
                except (json.JSONDecodeError, FileNotFoundError, OSError, ValueError):
                    logs = []

            # Append new log entry
            logs.append(log_data)

            # Write back atomically so concurrent readers never see a partial file.
            temp_file = f'{logs_file}.{os.getpid()}.{threading.get_ident()}.tmp'
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(logs, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, logs_file)
    except (OSError, ValueError) as exc:
        # Logging should never abort a scrape/crawl.
        print(f"Logger warning: could not write {_logs_json_file()}: {exc}")


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
    logs_file = _logs_json_file()
    with _LOG_LOCK:
        if os.path.exists(logs_file):
            os.remove(logs_file)
