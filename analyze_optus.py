"""Analyze saved Optus HTML to find plan card selectors."""
import re
from bs4 import BeautifulSoup
import json

# Use the Firefox HTML (most complete at 558KB)
with open("output/optus_firefox.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "lxml")

# ── 1. Check JSON-LD ────────────────────────────────────────────
print("=" * 60)
print("1. JSON-LD scripts")
print("=" * 60)
for i, tag in enumerate(soup.find_all("script", type="application/ld+json")):
    data = tag.string
    if data:
        try:
            parsed = json.loads(data)
            print(f"  [{i}] type={parsed.get('@type', '?')} — {str(parsed)[:200]}")
        except:
            print(f"  [{i}] parse error — {data[:200]}")

# ── 2. Check __NEXT_DATA__ ──────────────────────────────────────
print("\n" + "=" * 60)
print("2. __NEXT_DATA__ / embedded JSON")
print("=" * 60)
next_data = soup.find("script", id="__NEXT_DATA__")
if next_data:
    print("Found __NEXT_DATA__")
    data = json.loads(next_data.string)
    print(json.dumps(data, indent=2)[:2000])
else:
    print("No __NEXT_DATA__")

# ── 3. Search for plan/price patterns in data attributes ────────
print("\n" + "=" * 60)
print("3. Elements with 'plan' in class or data-* attrs")
print("=" * 60)
plan_elements = soup.find_all(attrs={"class": re.compile(r"plan", re.I)})
print(f"Elements with 'plan' in class: {len(plan_elements)}")
seen_classes = set()
for el in plan_elements[:40]:
    cls = " ".join(el.get("class", []))
    if cls not in seen_classes:
        seen_classes.add(cls)
        txt = el.get_text(" ", strip=True)[:100]
        print(f"  <{el.name} class='{cls[:80]}'> {txt}")

# data-* attributes containing plan
print("\nElements with 'plan' in data-* attrs:")
for el in soup.find_all(True):
    for attr in el.attrs:
        if attr.startswith("data-") and "plan" in str(el[attr]).lower():
            val = str(el[attr])[:80]
            print(f"  <{el.name} {attr}='{val}'> {el.get_text(' ', strip=True)[:60]}")
            break

# ── 4. Search for price patterns ($XX) near speed info ──────────
print("\n" + "=" * 60)
print("4. Price elements")
print("=" * 60)
for el in soup.find_all(text=re.compile(r"\$\d+")):
    parent = el.parent
    txt = el.strip()[:100]
    cls = " ".join(parent.get("class", []))[:60] if parent else ""
    print(f"  <{parent.name if parent else '?'} class='{cls}'> {txt}")

# ── 5. Search for Mbps speed patterns ───────────────────────────
print("\n" + "=" * 60)
print("5. Speed elements (Mbps)")
print("=" * 60)
for el in soup.find_all(text=re.compile(r"\d+\s*Mbps", re.I)):
    parent = el.parent
    txt = el.strip()[:100]
    cls = " ".join(parent.get("class", []))[:60] if parent else ""
    print(f"  <{parent.name if parent else '?'} class='{cls}'> {txt}")

# ── 6. Check for embedded JS data (window.__data, etc.) ────────
print("\n" + "=" * 60)
print("6. Inline script data blobs")
print("=" * 60)
for script in soup.find_all("script"):
    if script.string:
        text = script.string
        # Look for JSON objects with plan data
        if any(kw in text.lower() for kw in ["planname", "plan_name", "monthlyPrice", "downloadSpeed", "nbn", "speed_tier"]):
            # Extract relevant snippet
            for kw in ["planname", "plan_name", "monthlyPrice", "downloadSpeed", "nbn", "speed_tier"]:
                idx = text.lower().find(kw)
                if idx != -1:
                    snippet = text[max(0, idx-50):idx+200]
                    print(f"  Found '{kw}' in script: ...{snippet}...")
                    break
