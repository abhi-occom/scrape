"""Quick test: trace _parse_total_cost against actual rRNco text."""
import re

def _parse_total_cost(note):
    m = re.search(
        r'(?:Total\s+(?:once-off|min\.?)\s+cost|Total\s+cost)\s*\$?([\d.]+)',
        note, re.IGNORECASE
    )
    if m:
        return round(float(m.group(1)), 2)
    m2 = re.search(r'\$(\d+(?:\.\d+)?)', note)
    return round(float(m2.group(1)), 2) if m2 else None

def _parse_price(raw):
    m = re.search(r'\$(\d+(?:\.\d+)?)', raw)
    return round(float(m.group(1)), 2) if m else None

notes = [
    'Total once-off cost $149.70.',
    '$70.90/month thereafter.\u207c\nTotal min. cost $58.90.',
    '$80.90/month thereafter.\u207c\nTotal min. cost $70.90.',
    '$85.90/month thereafter.\u207c\nTotal min. cost $71.90.',
    '$94.90/month thereafter.\u207c\nTotal min. cost $84.90.',
    '$108.90/month thereafter.\u207c\nTotal min. cost $94.90.',
]

for note in notes:
    result = _parse_total_cost(note)
    fallback = _parse_price(note)
    print(f"note={note!r}")
    print(f"  _parse_total_cost => {result}")
    print(f"  _parse_price fallback => {fallback}")
    print()
