import glob, json
files = sorted(glob.glob('output/scrape_isp_*/json/*_all_plans.json'))
for f in files:
    with open(f) as fp:
        data = json.load(fp)
    plans = data if isinstance(data, list) else data.get('plans', [])
    if not plans:
        print(f"{f}: 0 plans")
        continue
    sample = plans[0]
    prov = sample.get('provider', 'MISSING')
    pid = sample.get('provider_id', 'MISSING')
    print(f"{f}")
    print(f"  plans={len(plans)} | provider={prov} | provider_id={pid}")
