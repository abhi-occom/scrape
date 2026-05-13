"""
One-shot script: scrape Dodo plans and merge into output/all_plans.json.
Run once, then delete.
"""
import json, sys, os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from providers.dodo import scrape_dodo_plans

JSON_PATH = os.path.join(os.path.dirname(__file__), 'output', 'all_plans.json')

with open(JSON_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Drop any stale dodo entries
existing = [p for p in data['plans'] if p.get('provider') != 'dodo']

new_plans = scrape_dodo_plans()
print(f'Scraped {len(new_plans)} Dodo plans')

all_plans = existing + new_plans

output = {
    'scraped_at':   datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
    'total_plans':  len(all_plans),
    'plans':        all_plans,
}

with open(JSON_PATH, 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f'all_plans.json updated -> {len(all_plans)} total plans')
from collections import Counter
counts = Counter(p.get('provider', 'unknown') for p in all_plans)
for provider, count in sorted(counts.items()):
    print(f'  {provider:15}: {count}')
