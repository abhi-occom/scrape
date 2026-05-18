from providers.more import scrape_more_plans
plans = scrape_more_plans()
print('Total:', len(plans))
for p in plans:
    print(p)