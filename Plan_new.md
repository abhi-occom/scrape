# ISP Scraper — Classification, Accuracy & Validation Plan

Source: email thread with Rishabh (Occom), 2026-09-22. Rishabh asked to prioritize
two things: (1) reliable **access technology** classification (FTTP/FTTN/FTTC/Fixed
Wireless) and (2) reliable **upstream network operator** classification (NBN,
Opticomm, Supa, RedTrain). Abhishek agreed to prioritize classification + accuracy/
validation. This document verifies each roadmap item against the actual code in
this repo (not the email's description of it) and lays out an implementation plan
for anything not done or only partially done.

Verified against commit `777fcc8` (HEAD = `origin/main`, 2026-09-17).

---

## Status summary

| # | Roadmap item (from email) | Status | Priority |
|---|---|---|---|
| 1 | Fix Google Sheets sync "nbn" filter | **DONE in code** — verify hosted deploy | Low (ops only) |
| 2 | Centralized network classifier | **PARTIALLY DONE** — single flat field, tech/operator still conflated | **Highest (Rishabh's #1 ask)** |
| 3 | OCR-based price verification | **NOT DONE** — no OCR code exists anywhere in repo | **High (Rishabh's #2 ask)** |
| 4 | Network-specific validation rules | **PARTIALLY DONE** — generic bounds only, not network-aware | High |
| 5 | Provider confidence scoring | **NOT DONE** | Medium |
| 6 | Fuzzy plan-rename matching | **NOT DONE** — exact-key match only | Medium |
| 7 | Scheduled crawls | **NOT DONE** — blocked on AWS decision | Low (infra/ops) |
| 8 | Slack/email notifications | **NOT DONE** | Low |

---

## Task 1 — Google Sheets "nbn" filter — DONE, verify deployment only

**What the email claimed:** sync "expects the word 'nbn'... can cause legitimate
Opticomm, Supa or RedTrain plans to be excluded."

**What the code actually does:** `google_sheets_sync.py:429` — `plan_is_eligible()`
already calls the centralized `is_broadband_network_type()` (imported at line 12
from `utils/network_classifier.py`), not a raw `'nbn' in text` substring check.
This fix landed in commit `8a8d7d6` (2026-09-16) and is present in the current
`HEAD`/`origin/main` — already pushed, `git diff HEAD -- google_sheets_sync.py`
is empty.

**Action:** No code change needed. Confirm the **hosted server** has pulled
`8a8d7d6` or later and restarted the sync process — this is a deploy/ops check,
not a development task. Flag this explicitly back to Rishabh since the email
described it as unresolved when the repo shows it already fixed locally.

---

## Task 2 — Split network classification: access technology vs. upstream operator

**Status: PARTIALLY DONE.** This is the highest-priority item — it's the exact
gap Rishabh called out as business-critical.

**Current state:** `utils/network_classifier.py::canonicalize_network_type()`
(lines 45–83) is a real centralized classifier and it **is** wired into every
scrape via `scraper_service.py:15,120` (`normalise_plans()` runs on every
provider's output) and into `isp/main_crawler.py:568,592-595`. So centralization
of *a* classifier is done. But it returns **one flat string** that still mixes
two different concepts:
- Access technology: FTTP, FTTN, FTTC, FTTB, Fixed Wireless, 5G, 4G, Satellite
- Upstream operator: NBN, Opticomm, Redtrain, Supa, Lynham Networks, ASN Telecom,
  Vision Networks, Community Fibre

E.g. a plan on the RedTrain network delivered over FTTP has no way to record
both facts — it collapses to `"Redtrain"` (line 56-57) and the FTTP technology
information is lost, or vice versa for `"NBN FTTP"` which is kept as one literal
string only because it happens to already contain both tokens (line 63-67).

Separately, `isp/validator.py:28-34` maintains its **own independent**
`KNOWN_NETWORK_TYPES` set that duplicates (and can drift from)
`utils/network_classifier.py`'s `BROADBAND_NETWORK_TYPES` (lines 10-15) — this
is the "not consistently across all scripts" problem in miniature, still present
today.

**Implementation plan:**

1. `utils/network_classifier.py` — add two new pure functions alongside the
   existing `canonicalize_network_type()`:
   ```python
   ACCESS_TECHNOLOGIES = frozenset({
       "FTTP", "FTTN", "FTTC", "FTTB", "HFC",
       "FIXED WIRELESS", "5G", "4G", "SATELLITE",
   })
   UPSTREAM_OPERATORS = frozenset({
       "NBN", "OPTICOMM", "REDTRAIN", "SUPA", "LYNHAM NETWORKS",
       "ASN TELECOM", "VISION NETWORKS", "COMMUNITY FIBRE",
   })

   def classify_access_technology(raw: Any) -> str: ...
   def classify_upstream_network(raw: Any) -> str: ...
   ```
   Reuse the existing `_compact()` helper (line 41-42) and the same
   keyword-priority scan already used inside `canonicalize_network_type()`
   (lines 72-81) — split that logic into the two new functions rather than
   duplicating the token lists a third time.

2. `utils/network_classifier.py::normalise_plans()` (lines 95-118) — in the
   per-plan branch (lines 109-115), in addition to overwriting
   `plan['network_type']` (line 114), **add** two new fields without removing
   the existing one (avoids breaking every downstream consumer that reads
   `network_type` today — CSV export, dashboard templates, Google Sheets sync):
   ```python
   plan['access_technology']  = classify_access_technology(plan.get('network_type'))
   plan['upstream_network']   = classify_upstream_network(plan.get('network_type'))
   ```

3. `isp/main_crawler.py` — `_canonical_network_type()` (lines 592-595) is a
   staticmethod called from line 568 when building `normalised`. Add the same
   two fields there so the newer crawler pipeline populates them too (it
   doesn't route through `scraper_service.normalise_plans()`):
   ```python
   normalised['access_technology'] = classify_access_technology(network_type)
   normalised['upstream_network']  = classify_upstream_network(network_type)
   ```

4. `isp/validator.py:28-34` — delete the local `KNOWN_NETWORK_TYPES` set and
   import `BROADBAND_NETWORK_TYPES` from `utils/network_classifier.py` instead,
   so there is truly one source of truth (line 137's `upper not in
   KNOWN_NETWORK_TYPES` check becomes `not is_broadband_network_type(net)`).

5. `scraper_service.py:22-26` (`CSV_COLUMNS`) — add `'access_technology'` and
   `'upstream_network'` so they land in the exported CSVs, not just JSON.

6. Update dashboard/report templates that render network type
   (`templates/sheets.html`, `isp/templates/crawler_ui.html`,
   `isp/templates/health_report.html`) to show the two new columns instead of
   (or alongside) the single blended `network_type` label.

7. `test_network_classifier.py` — add a new test class mirroring
   `CanonicalizeNetworkTypeTests` for both new functions, including the
   compound case that motivates this whole task: a RedTrain-FTTP plan should
   report `upstream_network == "Redtrain"` **and** `access_technology ==
   "FTTP"` simultaneously.

**What this resolves:** Directly answers Rishabh's ask — "reliable
identification of access technologies" and "accurate classification of
upstream network providers" as two independent, queryable fields instead of one
conflated string.

---

## Task 3 — OCR-based price verification

**Status: NOT DONE.** The first email describes this as a working feature
("uses a free OCR library to read and verify... currently working ok"), but
there is no OCR code anywhere in this repo: no `pytesseract`/`easyocr`/
`tesseract` reference in any `.py` file, and no such package in
`requirements.txt`. `utils/screenshots.py` only captures screenshots for visual
audit — nothing reads them back or compares them to scraped values. This gap
should be flagged back to Rishabh, since the email's description doesn't match
what's actually deployed in this codebase (unless it lives in a system outside
this repo).

**Implementation plan (build from scratch):**

1. `requirements.txt` — add `pytesseract` and `Pillow`; document that the
   Tesseract OCR binary itself must be installed on the host (not pip-
   installable) — this is the actual infra dependency, lighter than AWS.

2. New file `utils/ocr_verify.py`:
   ```python
   import re
   from typing import Dict, List, Optional
   import pytesseract
   from PIL import Image

   _PRICE_RE = re.compile(r'\$\s?(\d{1,4}(?:\.\d{2})?)')

   def extract_prices_from_image(image_path: str) -> List[float]:
       text = pytesseract.image_to_string(Image.open(image_path))
       return [float(m) for m in _PRICE_RE.findall(text)]

   def verify_plan_price(plan: Dict, screenshot_path: str, tolerance: float = 0.01) -> Dict:
       """Non-blocking: always returns a result, never raises past this boundary."""
       try:
           found = extract_prices_from_image(screenshot_path)
       except Exception:
           return {'ocr_checked': False}
       targets = [p for p in (plan.get('price'), plan.get('promo_price')) if p]
       matched = any(abs(t - f) <= tolerance for t in targets for f in found)
       return {
           'ocr_checked': True,
           'ocr_verified': matched,
           'ocr_prices_found': found,
           'ocr_warning': None if matched else
               f"Scraped price {targets} not found in screenshot OCR text {found}",
       }
   ```

3. Wire-in point: `scraper_service.py::scrape_provider()`, right after line 120
   (`plans = normalise_plans(plans)`). Providers that call
   `utils/screenshots.py` during their scrape already save a screenshot path —
   thread that path through the provider's returned plan dict (or match by
   provider+timestamp) and call `verify_plan_price()` per plan, attaching the
   result dict's keys onto the plan. This preserves the email's stated design
   principle explicitly: **mismatch → tag with `ocr_warning`, never drop the
   plan.**

4. Surface `ocr_warning` in the dashboard as a visible badge — this is also the
   direct input for Task 5 (confidence scoring) below, so build them together.

**What this resolves:** Turns the OCR claim in the email from aspirational into
real, and gives Rishabh's "accuracy & validation" ask an actual mechanism:
independent cross-check of scraped price against what the page visually shows.

---

## Task 4 — Network-specific validation rules

**Status: PARTIALLY DONE.** `isp/validator.py::ISPValidator.validate_plan()`
(lines 76-131) already does *generic* bounds checking — price must be
$1–$500 (line 87), speed must be 0–10,000 Mbps (line 126) — flagged as a
warning, never an error, matching the email's non-blocking philosophy. But
none of these bounds are aware of *which* network/technology the plan is on,
so a "Fixed Wireless" plan claiming 2000 Mbps or an "FTTN" plan claiming
1000 Mbps passes silently today — exactly the kind of "unusual speed/price
combination" item 4 in the roadmap calls for.

**Implementation plan:**

1. New dict in `utils/network_classifier.py` (co-locate with the technology
   classifier from Task 2, since the rule is keyed on `access_technology`):
   ```python
   SPEED_CEILING_MBPS = {
       'FTTN': 100, 'FTTC': 250, 'FTTB': 250, 'HFC': 1000,
       'FTTP': 2000, 'FIXED WIRELESS': 100, '4G': 100, '5G': 300,
       'SATELLITE': 100,
   }
   ```

2. `isp/validator.py::validate_plan()` — after the existing speed check block
   (lines 110-131), add a network-aware check using the `access_technology`
   field introduced in Task 2:
   ```python
   tech = classify_access_technology(plan.get('network_type'))
   ceiling = SPEED_CEILING_MBPS.get(tech)
   if ceiling and plan.get('download_speed', 0) > ceiling:
       result.warnings.append(
           f'{tech} plan advertises {plan["download_speed"]} Mbps, '
           f'above expected ceiling of {ceiling} Mbps for this technology — verify'
       )
   ```

3. Add a batch-level outlier check (needs the full set, so it's a separate
   function, not per-plan): `flag_price_outliers(plans: List[Dict]) -> List[Dict]`
   in `isp/validator.py` — group by `access_technology`, compute median
   price-per-Mbps, and warn on any plan more than 3x off the median for its
   group. Call this from `validate_batch()` (line 144) after the per-plan loop.

**What this resolves:** Gives the validation layer real network-context
awareness instead of one-size-fits-all bounds — catches scraping errors that
produce physically implausible plans (e.g. a mis-parsed "1000" instead of "100"
for an FTTN plan).

---

## Task 5 — Provider confidence scoring ("Strong" / "Needs Review")

**Status: NOT DONE.** No confidence field exists anywhere in the data model.

**Implementation plan:** This is naturally downstream of Tasks 3 and 4 — don't
build a separate scoring input, derive it from warnings already being
collected. In `isp/validator.py::validate_plan()`, after all checks run, add:
```python
result.plan['confidence'] = 'Strong' if not result.warnings else 'Needs Review'
```
Surface `confidence` in `CSV_COLUMNS` (`scraper_service.py:22-26`) and in the
dashboard so users can filter/sort by it directly.

**What this resolves:** Roadmap item 5 — makes data reliability visible at a
glance without needing to read every warning.

---

## Task 6 — Fuzzy plan-rename matching

**Status: NOT DONE.** `utils/alerts.py::_plan_key()` (lines 44-49) builds an
exact string key `f"{provider}|{name}|{speed}"`. If a provider renames a plan
(e.g. "Value" → "Value Plus"), `detect_new_plans()` (line 103) and
`detect_removed_plans()` (line 127) will report it as two unrelated events
instead of one rename — exactly the limitation the email describes.

**Implementation plan:**

1. In `utils/alerts.py::run_alerts()` (line 174), after the three existing
   exact-match diff calls (lines 189-191), add a fuzzy reconciliation pass over
   whatever `detect_new_plans`/`detect_removed_plans` returned:
   ```python
   from difflib import SequenceMatcher

   def reconcile_renames(new_alerts, removed_alerts, threshold=0.75):
       renamed, still_new, still_removed = [], list(new_alerts), []
       for removed in removed_alerts:
           best, best_score = None, 0.0
           for new in still_new:
               if new['provider'] != removed['provider'] or new['speed'] != removed['speed']:
                   continue
               score = SequenceMatcher(None, new['plan_name'], removed['plan_name']).ratio()
               if score > best_score:
                   best, best_score = new, score
           if best and best_score >= threshold:
               renamed.append({'type': 'plan_renamed', 'severity': 'low',
                                'provider': removed['provider'],
                                'old_name': removed['plan_name'], 'new_name': best['plan_name'],
                                'message': f"{removed['provider'].title()} renamed "
                                           f"'{removed['plan_name']}' to '{best['plan_name']}'"})
               still_new.remove(best)
           else:
               still_removed.append(removed)
       return renamed, still_new, still_removed
   ```
2. Wire it in right after line 191, replacing the raw new/removed lists that
   get appended to `all_alerts` with the reconciled versions.

**What this resolves:** Roadmap item 6 — stops plan renames from generating
false "removed" + "new" noise in alerts.

---

## Task 7 — Scheduled crawls

**Status: NOT DONE**, and per the email this is explicitly blocked on an AWS
infrastructure decision, not a code gap. No cron/APScheduler/boto3 usage found
anywhere in the repo.

**Recommendation (addresses Rishabh's ask for an AWS-independent prototype):**
Add `APScheduler` as a lightweight in-process scheduler on the existing host —
no AWS needed to prototype. A `BackgroundScheduler` calling the existing
`scraper_service.scrape_provider()` loop on a cron trigger would validate
frequency/monitoring/failure-handling questions cheaply before committing to
AWS infra. This is an infra/ops decision to confirm with Rishabh, not something
to implement unilaterally — flag it, don't build it silently.

---

## Task 8 — Slack/email notifications

**Status: NOT DONE.** `utils/alerts.py::run_alerts()` already produces a fully
structured `alert_report` dict (lines 208-215) with severity buckets — it just
stops at writing to `alerts.json` (`_save_alerts()`, line 228) and never
delivers it anywhere.

**Implementation plan:**
1. New file `utils/notify.py` with `send_slack_alert(webhook_url: str,
   alert_report: Dict)` (a plain `requests.post` to a Slack incoming webhook)
   and `send_email_alert(smtp_config: Dict, alert_report: Dict)` (stdlib
   `smtplib`).
2. In `utils/alerts.py::run_alerts()`, after line 217 (`_save_alerts(...)`),
   call `send_slack_alert(...)` when `alert_report['high'] > 0`, config-gated
   via `config.py` so it's a no-op until credentials are supplied.

**What this resolves:** Roadmap item 8 — removes the need to manually check
the dashboard for high-severity changes.

---

## Suggested execution order

1. **Task 2** (technology/operator split) — unblocks Task 4's network-aware
   rules and gives Rishabh's top-priority ask a concrete deliverable.
2. **Task 4** (network-specific validation) — builds directly on Task 2's new
   fields.
3. **Task 3** (OCR verification) — independent of 2/4, can run in parallel.
4. **Task 5** (confidence scoring) — trivial once 3 and 4 exist.
5. **Task 6** (fuzzy rename matching) — independent, low effort.
6. **Task 1** — just confirm hosted deploy, no dev work.
7. **Tasks 7 & 8** — infra/ops decisions to raise with Rishabh, not to build
   ahead of a decision.
