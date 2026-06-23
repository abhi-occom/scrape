"""Google Sheets OAuth and ISP plan price sync helpers."""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import truststore
    # Only inject truststore if explicitly enabled (can cause issues on Windows)
    if os.environ.get("USE_TRUSTSTORE", "0") == "1":
        truststore.inject_into_ssl()
except ImportError:
    truststore = None
except Exception:
    # Ignore truststore injection errors (common on Windows)
    pass

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
except ImportError:  # pragma: no cover - exercised when deps are missing locally
    Request = None
    Credentials = None
    Flow = None
    build = None


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
DEFAULT_SHEET_ID = "1zQxCM3HpTjPW-pmh_qGM9ISxYwWmTG9uwdrezP0LMLw"
DEFAULT_REDIRECT_URI = "http://localhost:5000/oauth2callback"
DEFAULT_TAB_NAME = "Sheet1"
TOKEN_PATH = Path(__file__).resolve().parent / "instance" / "google_token.json"

PROVIDER_HEADERS = [
    "EXETEL",
    "IINET",
    "AUSSIE BROADBAND",
    "LEAPTEL",
    "SWOOP",
    "IPRIMUS",
    "ACTIVE8 ME",
    "TPG",
    "TELSTRA",
    "OPTUS",
    "DODO",
    "TANGERINE",
    "SUPERLOOP",
    "MATE",
    "MORE",
    "SPINTEL",
    "KOGAN",
    "ORIGIN",
    "OCCOM",
]

PROVIDER_ALIASES = {
    "ACTIVE8ME": "ACTIVE8 ME",
    "ACTIV8ME": "ACTIVE8 ME",
    "AUSSIE": "AUSSIE BROADBAND",
    "AUSSIEBROADBAND": "AUSSIE BROADBAND",
    "AUSSIE BROADBAND": "AUSSIE BROADBAND",
    "EXETEL": "EXETEL",
    "IINET": "IINET",
    "I PRIMUS": "IPRIMUS",
    "IPRIMUS": "IPRIMUS",
    "LEAPTEL": "LEAPTEL",
    "MATE": "MATE",
    "MORE": "MORE",
    "OCCOM": "OCCOM",
    "OPTUS": "OPTUS",
    "ORIGIN": "ORIGIN",
    "ORIGIN ENERGY": "ORIGIN",
    "SPINTEL": "SPINTEL",
    "SUPERLOOP": "SUPERLOOP",
    "SWOOP": "SWOOP",
    "TANGERINE": "TANGERINE",
    "TELSTRA": "TELSTRA",
    "TPG": "TPG",
    "TPG TELECOM": "TPG",
    "DODO": "DODO",
    "KOGAN": "KOGAN",
}

EXCLUDED_TERMS = [
    "mobile",
    "sim",
    "travel",
    "prepaid",
    "postpaid",
    "roaming",
    "phone plan",
]


@dataclass(frozen=True)
class SpeedTier:
    label: str
    download: int
    upload: Optional[int] = None

    @property
    def key(self) -> Tuple[int, Optional[int]]:
        return (self.download, self.upload)


def get_config() -> Dict[str, Optional[str]]:
    return {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID"),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET"),
        "redirect_uri": os.environ.get("GOOGLE_REDIRECT_URI", DEFAULT_REDIRECT_URI),
        "sheet_id": os.environ.get("GOOGLE_SHEET_ID", DEFAULT_SHEET_ID),
        "tab_name": os.environ.get("GOOGLE_SHEET_TAB", DEFAULT_TAB_NAME),
    }


def dependencies_available() -> bool:
    return all([truststore, Request, Credentials, Flow, build])


def oauth_configured() -> bool:
    cfg = get_config()
    return bool(cfg["client_id"] and cfg["client_secret"] and cfg["redirect_uri"])


def token_exists() -> bool:
    return TOKEN_PATH.exists()


def _client_config() -> Dict[str, Dict[str, Any]]:
    cfg = get_config()
    return {
        "web": {
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [cfg["redirect_uri"]],
        }
    }


def make_oauth_flow(state: Optional[str] = None, code_verifier: Optional[str] = None) -> Any:
    if not dependencies_available():
        raise RuntimeError("Google API dependencies are not installed.")
    if not oauth_configured():
        raise RuntimeError("Google OAuth environment variables are not configured.")

    os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")
    
    # Configure HTTP session for Windows compatibility
    import requests
    import ssl
    from requests.adapters import HTTPAdapter
    from urllib3.util.ssl_ import create_urllib3_context
    
    class SSLAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            context = create_urllib3_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            kwargs['ssl_context'] = context
            return super().init_poolmanager(*args, **kwargs)
    
    # Create session with proper SSL configuration
    session = requests.Session()
    session.mount('https://', SSLAdapter())
    
    kwargs = {"state": state}
    if code_verifier:
        kwargs["code_verifier"] = code_verifier
        kwargs["autogenerate_code_verifier"] = False
    
    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, **kwargs)
    flow.redirect_uri = get_config()["redirect_uri"]
    
    # Attach custom session to flow
    flow.authorized_session = lambda: session
    
    return flow


def authorization_url(state: Optional[str] = None) -> Tuple[str, str, str]:
    flow = make_oauth_flow(state=state)
    url, new_state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return url, new_state, flow.code_verifier


def fetch_token(authorization_response: str, state: Optional[str] = None, code_verifier: Optional[str] = None) -> None:
    """Fetch OAuth token from authorization response with Windows-compatible SSL."""
    import requests
    from urllib.parse import urlparse, parse_qs
    
    try:
        # Create flow with custom session
        flow = make_oauth_flow(state=state, code_verifier=code_verifier)
        
        # Parse authorization code from response
        parsed = urlparse(authorization_response)
        code = parse_qs(parsed.query).get('code')
        
        if not code:
            raise ValueError("No authorization code in response")
        
        # Create custom session with SSL disabled for Windows
        session = requests.Session()
        session.verify = False
        
        # Disable SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Exchange code for token with custom session
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            'code': code[0],
            'client_id': get_config()["client_id"],
            'client_secret': get_config()["client_secret"],
            'redirect_uri': get_config()["redirect_uri"],
            'grant_type': 'authorization_code',
        }
        
        if code_verifier:
            data['code_verifier'] = code_verifier
        
        response = session.post(token_url, data=data, timeout=30)
        response.raise_for_status()
        
        token_data = response.json()
        
        # Create credentials from token
        from google.oauth2.credentials import Credentials
        credentials = Credentials(
            token=token_data.get('access_token'),
            refresh_token=token_data.get('refresh_token'),
            token_uri=token_url,
            client_id=get_config()["client_id"],
            client_secret=get_config()["client_secret"],
            scopes=SCOPES
        )
        
        save_credentials(credentials)
        
    except requests.exceptions.SSLError as e:
        raise RuntimeError(
            f"SSL Error: Windows firewall or certificate issue.\n"
            f"Solution: Run PowerShell as Administrator and execute:\n"
            f"  netsh advfirewall firewall add rule name=\"Python\" dir=in action=allow program=\"{Path(sys.executable)}\" enable=yes\n\n"
            f"Error: {str(e)}"
        ) from e
    except PermissionError as e:
        raise RuntimeError(
            f"Permission Denied: Windows is blocking Python network access.\n"
            f"Solution 1: Add Python to Windows Firewall (recommended)\n"
            f"Solution 2: Run PowerShell as Administrator\n"
            f"Solution 3: Temporarily disable antivirus\n\n"
            f"Error: {str(e)}"
        ) from e
    except requests.exceptions.ConnectionError as e:
        if "PermissionError" in str(e) or "WinError 10013" in str(e):
            raise RuntimeError(
                f"Connection Blocked: Windows Firewall is blocking Python.\n\n"
                f"Quick Fix:\n"
                f"1. Press Win+R, type 'wf.msc', press Enter\n"
                f"2. Click 'Inbound Rules' -> 'New Rule'\n"
                f"3. Select 'Program' -> Browse to: {sys.executable}\n"
                f"4. Select 'Allow the connection'\n"
                f"5. Check all boxes -> Finish\n"
                f"6. Repeat for 'Outbound Rules'\n\n"
                f"Error: {str(e)}"
            ) from e
        raise RuntimeError(
            f"Network connection failed.\n"
            f"Check: Internet connection, proxy settings, firewall\n\n"
            f"Error: {str(e)}"
        ) from e
    except Exception as e:
        raise RuntimeError(f"OAuth token fetch failed: {str(e)}") from e


def save_credentials(credentials: Any) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(credentials.to_json(), encoding="utf-8")


def load_credentials() -> Optional[Any]:
    """Load and refresh credentials with error handling."""
    if not dependencies_available() or not TOKEN_PATH.exists():
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                save_credentials(creds)
            except Exception as e:
                # Token refresh failed - user needs to reconnect
                if "Connection aborted" in str(e) or "PermissionError" in str(e):
                    raise RuntimeError(
                        f"Failed to refresh token due to network permission error. "
                        f"Please reconnect your Google account. Error: {str(e)}"
                    ) from e
                raise
        return creds if creds and creds.valid else None
    except Exception as e:
        if "Connection aborted" not in str(e) and "PermissionError" not in str(e):
            raise
        return None


def sheets_service() -> Any:
    creds = load_credentials()
    if not creds:
        raise RuntimeError("Google account is not connected. Open /sheets and connect Google first.")
    return build("sheets", "v4", credentials=creds)


def get_spreadsheet_metadata(service: Any) -> Dict[str, Any]:
    cfg = get_config()
    metadata = service.spreadsheets().get(
        spreadsheetId=cfg["sheet_id"],
        fields="spreadsheetId,properties(title),sheets(properties(sheetId,title,gridProperties))",
    ).execute()
    tab_name = cfg["tab_name"]
    sheet = next((s for s in metadata.get("sheets", []) if s["properties"]["title"] == tab_name), None)
    if not sheet:
        available = [s["properties"]["title"] for s in metadata.get("sheets", [])]
        raise RuntimeError(f"Tab '{tab_name}' not found. Available tabs: {', '.join(available)}")
    return {
        "spreadsheet_id": metadata.get("spreadsheetId"),
        "title": metadata.get("properties", {}).get("title"),
        "tab_name": tab_name,
        "sheet_id": sheet["properties"]["sheetId"],
        "grid": sheet["properties"].get("gridProperties", {}),
    }


def read_sheet_values(service: Any) -> List[List[Any]]:
    cfg = get_config()
    result = service.spreadsheets().values().get(
        spreadsheetId=cfg["sheet_id"],
        range=f"{cfg['tab_name']}!A1:Z100",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    return result.get("values", [])


def status_payload(include_metadata: bool = True) -> Dict[str, Any]:
    payload = {
        "dependencies_installed": dependencies_available(),
        "oauth_configured": oauth_configured(),
        "connected": bool(load_credentials()),
        "token_path": str(TOKEN_PATH),
        "sheet_id": get_config()["sheet_id"],
        "tab_name": get_config()["tab_name"],
        "metadata": None,
    }

    if include_metadata and payload["connected"]:
        try:
            payload["metadata"] = get_spreadsheet_metadata(sheets_service())
        except Exception as exc:  # noqa: BLE001 - returned to UI as status detail
            payload["metadata_error"] = str(exc)
    return payload


def normalize_header(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(value or "").upper()).strip()


def compact_name(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def parse_speed_label(label: Any) -> Optional[SpeedTier]:
    text = str(label or "").strip().upper()
    if not text:
        return None

    match = re.match(r"^(\d+(?:\.\d+)?)(?:\s*/\s*(\d+(?:\.\d+)?))?\s*M(?:BPS)??$", text)
    if not match:
        return None

    download = int(float(match.group(1)))
    upload = int(float(match.group(2))) if match.group(2) else None
    return SpeedTier(label=text, download=download, upload=upload)


def plan_is_eligible(plan: Dict[str, Any]) -> bool:
    network = str(plan.get("network_type") or "").lower()
    name = str(plan.get("plan_name") or "").lower()
    source = f"{network} {name}"

    if any(term in source for term in EXCLUDED_TERMS):
        return False
    return "nbn" in source


def canonical_provider(provider: Any) -> Optional[str]:
    name = str(provider or "").strip()
    normalized = normalize_header(name)
    compact = compact_name(name)

    if normalized in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[normalized]
    if compact in PROVIDER_ALIASES:
        return PROVIDER_ALIASES[compact]
    return None


def numeric(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def selected_price(plan: Dict[str, Any]) -> Optional[float]:
    return numeric(plan.get("promo_price")) or numeric(plan.get("price"))


def speed_candidates_from_name(name: str) -> List[Tuple[int, Optional[int]]]:
    candidates: List[Tuple[int, Optional[int]]] = []
    for down, up in re.findall(r"(?<!\d)(\d{2,4})\s*/\s*(\d{1,3})(?!\d)", name):
        candidates.append((int(down), int(up)))
    for down in re.findall(r"(?<!\d)(?:NBN|HOME|FAST|SPEED|PLAN)?\s*(12|25|50|100|250|500|750|850|1000|2000)\s*(?:M|MBPS|NBN)?(?!\d)", name, flags=re.I):
        candidates.append((int(down), None))
    return candidates


def plan_speed(plan: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    """Return normalized plan speeds, falling back to the plan name when needed."""
    download = numeric(plan.get("download_speed"))
    upload = numeric(plan.get("upload_speed"))
    name_candidates = speed_candidates_from_name(str(plan.get("plan_name") or ""))

    if download is None and name_candidates:
        download = float(name_candidates[0][0])
    if upload is None:
        matching_candidate = next(
            (
                candidate
                for candidate in name_candidates
                if candidate[1] is not None
                and (download is None or candidate[0] == round(download))
            ),
            None,
        )
        if matching_candidate:
            upload = float(matching_candidate[1])

    if download is not None and download <= 0:
        download = None
    if upload is not None and upload <= 0:
        upload = None
    return download, upload


def classify_plan_tier(plan: Dict[str, Any], speed_tiers: List[SpeedTier]) -> Optional[SpeedTier]:
    """Map a plan upward to the nearest available sheet download/upload tier."""
    download, upload = plan_speed(plan)
    if download is None:
        return None

    tiers_by_download: Dict[int, List[SpeedTier]] = {}
    for tier in speed_tiers:
        tiers_by_download.setdefault(tier.download, []).append(tier)

    target_download = next(
        (
            tier_download
            for tier_download in sorted(tiers_by_download)
            if download <= tier_download
        ),
        None,
    )
    if target_download is None:
        return None

    target_tiers = tiers_by_download[target_download]
    download_only_tier = next((tier for tier in target_tiers if tier.upload is None), None)
    if download_only_tier:
        return download_only_tier

    if upload is None:
        return None

    return next(
        (
            tier
            for tier in sorted(target_tiers, key=lambda item: item.upload or 0)
            if tier.upload is not None and upload <= tier.upload
        ),
        None,
    )


def plan_matches_tier(plan: Dict[str, Any], tier: SpeedTier, speed_tiers: Optional[List[SpeedTier]] = None) -> bool:
    """Compatibility helper for checking a plan against its single classified tier."""
    classified = classify_plan_tier(plan, speed_tiers or [tier])
    return classified == tier


def build_price_matrix(plans: Iterable[Dict[str, Any]], speed_tiers: List[SpeedTier]) -> Tuple[Dict[Tuple[str, str], float], Dict[str, Any]]:
    prices: Dict[Tuple[str, str], float] = {}
    matched_providers = set()
    eligible_count = 0
    warnings: List[str] = []

    for plan in plans:
        provider = canonical_provider(plan.get("provider"))
        if not provider or not plan_is_eligible(plan):
            continue

        price = selected_price(plan)
        if price is None:
            continue

        eligible_count += 1
        tier = classify_plan_tier(plan, speed_tiers)
        if tier is None:
            continue

        key = (provider, tier.label)
        current = prices.get(key)
        if current is None or price < current:
            prices[key] = round(price, 2)
            matched_providers.add(provider)

    missing_providers = [provider for provider in PROVIDER_HEADERS if provider not in matched_providers]
    if missing_providers:
        warnings.append(f"No eligible matching plans found for: {', '.join(missing_providers)}")

    return prices, {
        "eligible_plans": eligible_count,
        "matched_providers": sorted(matched_providers),
        "warnings": warnings,
    }


def _a1_column(index: int) -> str:
    letters = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _cell_value(value: Any) -> Dict[str, Dict[str, Any]]:
    if isinstance(value, (int, float)):
        return {"userEnteredValue": {"numberValue": float(value)}}
    if isinstance(value, str) and value.startswith("="):
        return {"userEnteredValue": {"formulaValue": value}}
    return {"userEnteredValue": {"stringValue": str(value)}}


def build_sync_plan(snapshot: Dict[str, Any], sheet_values: List[List[Any]], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not sheet_values:
        raise RuntimeError("Target sheet has no readable rows.")

    headers = sheet_values[0]
    header_lookup = {normalize_header(header): idx for idx, header in enumerate(headers)}
    provider_columns = {
        provider: header_lookup[provider]
        for provider in PROVIDER_HEADERS
        if provider in header_lookup
    }
    missing_headers = [provider for provider in PROVIDER_HEADERS if provider not in provider_columns]

    speed_col = header_lookup.get("SPEED MBPS")
    min_col = header_lookup.get("MIN PRICE")
    max_col = header_lookup.get("MAX PRICE")
    if speed_col is None:
        raise RuntimeError("Could not find 'SPEED MBPS' header in row 1.")
    if not provider_columns:
        raise RuntimeError("No configured provider columns were found in row 1.")

    row_tiers: List[Tuple[int, SpeedTier]] = []
    for row_idx, row in enumerate(sheet_values[1:], start=1):
        label = row[speed_col] if speed_col < len(row) else ""
        tier = parse_speed_label(label)
        if tier:
            row_tiers.append((row_idx, tier))

    prices, stats = build_price_matrix(snapshot.get("plans", []), [tier for _, tier in row_tiers])

    update_columns = list(provider_columns.values())
    if min_col is not None:
        update_columns.append(min_col)
    if max_col is not None:
        update_columns.append(max_col)

    first_provider_col = min(provider_columns.values())
    last_provider_col = max(provider_columns.values())
    first_update_col = min(update_columns)
    last_update_col = max(update_columns)
    rows_payload = []
    cells_updated = 0
    blanks = 0

    for row_idx, tier in row_tiers:
        row_values = []
        for col_idx in range(first_update_col, last_update_col + 1):
            provider = next((name for name, col in provider_columns.items() if col == col_idx), None)
            value = prices.get((provider, tier.label)) if provider else ""
            if value is None:
                value = ""
                if provider:
                    blanks += 1
            else:
                if provider:
                    cells_updated += 1
            row_values.append(_cell_value(value))

        provider_start = _a1_column(first_provider_col)
        provider_end = _a1_column(last_provider_col)
        row_number = row_idx + 1
        if min_col is not None:
            row_values[min_col - first_update_col] = _cell_value(f"=MIN({provider_start}{row_number}:{provider_end}{row_number})")
        if max_col is not None:
            row_values[max_col - first_update_col] = _cell_value(f"=MAX({provider_start}{row_number}:{provider_end}{row_number})")

        rows_payload.append({
            "row_index": row_idx,
            "tier": tier.label,
            "values": row_values,
        })

    warnings = list(stats["warnings"])
    if missing_headers:
        warnings.append(f"Provider columns missing from sheet: {', '.join(missing_headers)}")

    request = {
        "updateCells": {
            "range": {
                "sheetId": metadata["sheet_id"] if metadata else 0,
                "startRowIndex": row_tiers[0][0] if row_tiers else 1,
                "endRowIndex": row_tiers[-1][0] + 1 if row_tiers else 1,
                "startColumnIndex": first_update_col,
                "endColumnIndex": last_update_col + 1,
            },
            "rows": [{"values": row["values"]} for row in rows_payload],
            "fields": "userEnteredValue",
        }
    }

    return {
        "request": request,
        "rows_processed": len(row_tiers),
        "cells_updated": cells_updated,
        "blank_cells": blanks,
        "matched_providers": stats["matched_providers"],
        "eligible_plans": stats["eligible_plans"],
        "warnings": warnings,
        "provider_columns": provider_columns,
    }


def sync_sheet(snapshot: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    service = sheets_service()
    metadata = get_spreadsheet_metadata(service)
    values = read_sheet_values(service)
    plan = build_sync_plan(snapshot, values, metadata=metadata)

    if not dry_run:
        service.spreadsheets().batchUpdate(
            spreadsheetId=get_config()["sheet_id"],
            body={"requests": [plan["request"]]},
        ).execute()

    return {
        "success": True,
        "dry_run": dry_run,
        "metadata": metadata,
        "rows_processed": plan["rows_processed"],
        "cells_updated": plan["cells_updated"],
        "blank_cells": plan["blank_cells"],
        "matched_providers": plan["matched_providers"],
        "eligible_plans": plan["eligible_plans"],
        "warnings": plan["warnings"],
    }


def dry_run_with_known_sheet(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Dry-run transform against the visible shared-sheet layout."""
    headers = [
        "SPEED MBPS",
        *PROVIDER_HEADERS,
        "Min Price",
        "Max Price",
    ]
    speed_rows = ["12M", "25M", "50M", "100/20M", "100/40M", "250M", "500/50M", "750M", "1000/100M", "2000/100M", "2000/200M"]
    values = [headers] + [[speed] for speed in speed_rows]
    metadata = {"sheet_id": 0}
    plan = build_sync_plan(snapshot, values, metadata=metadata)
    return {
        "success": True,
        "rows_processed": plan["rows_processed"],
        "cells_updated": plan["cells_updated"],
        "blank_cells": plan["blank_cells"],
        "matched_providers": plan["matched_providers"],
        "eligible_plans": plan["eligible_plans"],
        "warnings": plan["warnings"],
    }
