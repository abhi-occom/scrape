"""Centralised network-type classification.

Single source of truth for canonicalizing a plan's raw `network_type` value.
Intended to be imported by both scraper_service.py and isp/main_crawler.py,
replacing the duplicated, narrower logic that today only exists in the latter.
"""
import re
from typing import Any, Dict, List, Union

BROADBAND_NETWORK_TYPES = frozenset({
    "NBN", "OPTICOMM", "REDTRAIN", "SUPA", "FIBRE", "FTTP", "FTTB", "FTTN",
    "FTTC", "FIXED WIRELESS", "5G", "4G", "SATELLITE", "BUSINESS NBN",
    "ASN TELECOM", "LYNHAM NETWORKS", "SUPA NETWORKS", "SUPA FIBRE",
    "VISION NETWORKS", "COMMUNITY FIBRE",
})

# compact-form -> nicely-cased canonical label, used only for EXACT matches so
# compound strings like "NBN FTTP" fall through to the pass-through branch
# below instead of being collapsed to a single token.
_EXACT_TOKEN_LABELS = {
    'nbn': 'NBN',
    'fibre': 'Fibre',
    'fttp': 'FTTP',
    'fttb': 'FTTB',
    'fttn': 'FTTN',
    'fttc': 'FTTC',
    'fixed wireless': 'Fixed Wireless',
    '5g': '5G',
    '4g': '4G',
    'satellite': 'Satellite',
    'business nbn': 'Business NBN',
    'asn telecom': 'ASN Telecom',
    'lynham networks': 'Lynham Networks',
    'vision networks': 'Vision Networks',
    'community fibre': 'Community Fibre',
}

# Cellular SIM plans some ISPs sell alongside broadband (e.g. Belong). Exact
# matches only: they are deliberately not in _EXACT_TOKEN_LABELS, so labels
# like "Business Mobile" still resolve to 'Unknown' and are not mistaken for
# broadband.
_MOBILE_LABELS = {
    'mobile': 'Mobile',
    'mobile broadband': 'Mobile Broadband',
}

_KNOWN_TOKENS = tuple(_EXACT_TOKEN_LABELS.keys())

# Private fibre-only overbuild networks — these are FTTP by definition, so a
# plan on one of them is FTTP-capable even when the raw string never spells
# out the technology (e.g. a plan named just "Redtrain 100/20").
_PRIVATE_FIBRE_OPERATORS = frozenset({
    'Opticomm', 'Redtrain', 'Supa', 'Lynham Networks', 'ASN Telecom',
    'Vision Networks', 'Community Fibre',
})

# Realistic max download speed per access technology, keyed on
# classify_access_technology()'s return value. Used to flag plans whose
# advertised speed is physically implausible for the technology they're
# delivered over (e.g. an FTTN plan claiming 1000 Mbps).
SPEED_CEILING_MBPS = {
    'FTTN': 100,
    'FTTC': 250,
    'FTTB': 250,
    'HFC': 1000,
    'FTTP': 2000,
    'Fixed Wireless': 100,
    '4G': 100,
    '5G': 300,
    'Satellite': 100,
}


def _compact(raw: str) -> str:
    return re.sub(r'[\s_-]+', ' ', raw).lower().strip()


def canonicalize_network_type(raw: Any) -> str:
    text = str(raw or '').strip()
    if not text:
        return ''

    compact = _compact(text)

    # Alias-collapsing for branded private networks — same rule
    # isp/main_crawler.py::_canonical_network_type uses today.
    if 'opticomm' in compact:
        return 'Opticomm'
    if 'redtrain' in compact or 'red train' in compact:
        return 'Redtrain'
    if 'supa' in compact:
        return 'Supa'

    if compact in _MOBILE_LABELS:
        return _MOBILE_LABELS[compact]
    if compact in _EXACT_TOKEN_LABELS:
        return _EXACT_TOKEN_LABELS[compact]
    if any(token in compact for token in _KNOWN_TOKENS):
        # Already contains a recognisable token as part of a longer, real
        # label (e.g. "NBN FTTP Upgrade") — leave it intact rather than
        # collapsing it down to a single generic token and losing information.
        return text

    # Fallback keyword-priority scan, adapted from
    # isp/scraper_engine.py::_detect_network_from_text, for strings that
    # used different wording than the known-token list above (e.g. "Starlink").
    if '5g' in compact:
        return '5G'
    if 'fixed wireless' in compact:
        return 'Fixed Wireless'
    if 'satellite' in compact or 'starlink' in compact:
        return 'Satellite'
    if 'nbn' in compact:
        return 'NBN'
    if 'fibre' in compact or 'fttp' in compact:
        return 'Fibre'

    return 'Unknown'


def classify_upstream_network(raw: Any) -> str:
    """
    Identify the upstream network *operator* only (NBN, Opticomm, Redtrain,
    Supa, ...), independent of the access technology used to deliver it.

    Complements classify_access_technology() — together they replace the
    single blended `network_type` label with two queryable fields.
    """
    text = str(raw or '').strip()
    if not text:
        return ''

    compact = _compact(text)

    if 'opticomm' in compact:
        return 'Opticomm'
    if 'redtrain' in compact or 'red train' in compact:
        return 'Redtrain'
    if 'supa' in compact:
        return 'Supa'
    if 'lynham' in compact:
        return 'Lynham Networks'
    if 'asn telecom' in compact:
        return 'ASN Telecom'
    if 'vision networks' in compact:
        return 'Vision Networks'
    if 'community fibre' in compact:
        return 'Community Fibre'
    if 'nbn' in compact:
        return 'NBN'

    return 'Unknown'


def classify_access_technology(raw: Any) -> str:
    """
    Identify the access technology only (FTTP, FTTN, FTTC, FTTB, HFC, Fixed
    Wireless, 5G, 4G, Satellite), independent of the upstream operator.
    """
    text = str(raw or '').strip()
    if not text:
        return ''

    compact = _compact(text)

    if 'fttp' in compact:
        return 'FTTP'
    if 'fttb' in compact:
        return 'FTTB'
    if 'fttn' in compact:
        return 'FTTN'
    if 'fttc' in compact:
        return 'FTTC'
    if 'hfc' in compact:
        return 'HFC'
    if 'fixed wireless' in compact:
        return 'Fixed Wireless'
    if '5g' in compact:
        return '5G'
    if '4g' in compact:
        return '4G'
    if 'satellite' in compact or 'starlink' in compact:
        return 'Satellite'
    if compact in _MOBILE_LABELS:
        return 'Mobile'
    if 'fibre' in compact:
        return 'FTTP'

    if classify_upstream_network(raw) in _PRIVATE_FIBRE_OPERATORS:
        return 'FTTP'

    return 'Unknown'


def is_broadband_network_type(raw_or_canonical: Any) -> bool:
    """True if the canonicalized value is a recognized real broadband type."""
    canonical = canonicalize_network_type(raw_or_canonical)
    if not canonical or canonical == 'Unknown':
        return False
    canon_upper = canonical.upper()
    return any(token in canon_upper for token in BROADBAND_NETWORK_TYPES)


def normalise_plans(
    plans: Union[List[Dict], Dict[str, List[Dict]]],
) -> Union[List[Dict], Dict[str, List[Dict]]]:
    """Run every plan's network_type through canonicalize_network_type(), and
    add `access_technology` / `upstream_network` derived from the same raw
    value — these split what `network_type` blends together (see
    classify_access_technology() / classify_upstream_network()).

    Accepts the same two shapes scraper_service.py::_plan_count already
    handles: a flat list of plan dicts, or a dict of lists keyed by page/tab.
    Defensive: skips non-dict items, never raises.
    """
    if isinstance(plans, dict):
        return {key: normalise_plans(value) for key, value in plans.items()}

    if isinstance(plans, list):
        normalised = []
        for plan in plans:
            if not isinstance(plan, dict):
                normalised.append(plan)
                continue
            plan = dict(plan)
            raw_network_type = plan.get('network_type')
            plan['network_type'] = canonicalize_network_type(raw_network_type)
            plan['access_technology'] = classify_access_technology(raw_network_type)
            plan['upstream_network'] = classify_upstream_network(raw_network_type)
            normalised.append(plan)
        return normalised

    return plans
