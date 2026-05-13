import json

with open('output/all_plans.json') as f:
    data = json.load(f)

iprimus_plans = [p for p in data['plans'] if p.get('provider') == 'iprimus']
print(f"Total plans in JSON: {data['total_plans']}")
print(f"iPrimus plans: {len(iprimus_plans)}")
print()
for p in iprimus_plans:
    if p.get('promo_price'):
        promo = f" (promo: ${p['promo_price']} for {p['promo_period']})"
    else:
        promo = ''
    print(f"  [{p['network_type']:15}] {p['plan_name']:30}  DL:{p['download_speed']:4} UL:{p['upload_speed']:3}  ${p['price']}/mth{promo}")

# Check by provider
print()
print("Plans per provider:")
from collections import Counter
counts = Counter(p.get('provider', 'unknown') for p in data['plans'])
for provider, count in sorted(counts.items()):
    print(f"  {provider:15}: {count}")
