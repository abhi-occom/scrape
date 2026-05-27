"""Shared in-memory scrape progress state for the Flask dashboard."""

from copy import deepcopy
from datetime import datetime
from threading import Lock
from typing import Any, Dict, Optional


_lock = Lock()
_active_provider: Optional[str] = None
_state: Dict[str, Any] = {
    "running": False,
    "mode": "idle",
    "current_provider": None,
    "current_url": None,
    "status": "idle",
    "message": "No scrape running",
    "plans_found": 0,
    "current_screenshot": None,
    "providers_total": 0,
    "providers_done": 0,
    "errors": [],
    "events": [],
    "started_at": None,
    "updated_at": datetime.now().isoformat(),
    "finished_at": None,
}


def _now() -> str:
    return datetime.now().isoformat()


def reset_progress(mode: str = "single", providers_total: int = 1) -> None:
    """Reset progress for a new scrape run."""
    global _active_provider
    with _lock:
        _active_provider = None
        _state.update({
            "running": True,
            "mode": mode,
            "current_provider": None,
            "current_url": None,
            "status": "starting",
            "message": "Starting scrape",
            "plans_found": 0,
            "current_screenshot": None,
            "providers_total": providers_total,
            "providers_done": 0,
            "errors": [],
            "events": [],
            "started_at": _now(),
            "updated_at": _now(),
            "finished_at": None,
        })


def set_active_provider(provider: str, message: Optional[str] = None) -> None:
    """Mark the provider currently being scraped."""
    global _active_provider
    _active_provider = provider
    update_progress(
        provider=provider,
        status="running",
        message=message or f"Scraping {provider}",
        current_url=None,
    )


def update_progress(
    provider: Optional[str] = None,
    status: Optional[str] = None,
    message: Optional[str] = None,
    current_url: Optional[str] = None,
    plans_found: Optional[int] = None,
    error: Optional[str] = None,
    screenshot: Optional[Dict[str, str]] = None,
) -> None:
    """Update progress and append a compact event for the UI."""
    event = {
        "time": _now(),
        "provider": provider or _active_provider,
        "status": status,
        "message": message,
        "url": current_url,
        "plans_found": plans_found,
        "error": error,
        "screenshot": screenshot,
    }

    with _lock:
        if provider is not None:
            _state["current_provider"] = provider
        if status is not None:
            _state["status"] = status
        if message is not None:
            _state["message"] = message
        if current_url is not None:
            _state["current_url"] = current_url
        if plans_found is not None:
            _state["plans_found"] = plans_found
        if screenshot is not None:
            _state["current_screenshot"] = screenshot
        if error:
            _state["errors"].append({
                "provider": provider or _active_provider,
                "message": error,
                "time": event["time"],
            })
        _state["updated_at"] = event["time"]
        _state["events"].append(event)
        _state["events"] = _state["events"][-80:]


def finish_provider(provider: str, plans_found: int, success: bool, error: Optional[str] = None) -> None:
    """Record completion for a provider."""
    status = "success" if success else "error"
    message = f"{provider} completed with {plans_found} plans" if success else f"{provider} failed"
    with _lock:
        _state["providers_done"] += 1
    update_progress(
        provider=provider,
        status=status,
        message=message,
        plans_found=plans_found,
        error=error,
    )


def finish_progress(success: bool = True, message: Optional[str] = None) -> None:
    """Mark the current scrape run as finished."""
    with _lock:
        _state["running"] = False
        _state["status"] = "success" if success else "error"
        _state["message"] = message or ("Scrape complete" if success else "Scrape failed")
        _state["updated_at"] = _now()
        _state["finished_at"] = _state["updated_at"]


def get_progress() -> Dict[str, Any]:
    """Return a snapshot of the current progress state."""
    with _lock:
        return deepcopy(_state)
