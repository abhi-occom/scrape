"""Quick check of typical_evening_dl/ul fields in the scraped JSON."""
import json

data = json.load(open('output/scrape_isp_kogan/json/kogan_plans.json', 'r', encoding='utf-8'))
for p in data['plans']:
    name = p['name']
    ted = p.get('typical_evening_dl')
    teu = p.get('typical_evening_ul')
    sd = p.get('speed_down')
    su = p.get('speed_up')
    print(f"{name:12s}  speed_down={sd:>4}  speed_up={su}  typical_evening_dl={ted}  typical_evening_ul={teu}")
