import requests
headers = {'X-API-Key': 'ispPlans2024SecureKey123'}
response = requests.get('http://localhost:5000/api/plans/all', headers=headers).json(); 
occom = response['data']['occom']['occom_all_plans']; 
print('OCCOM Plans:', len(occom)); 
[print(p['plan_name'], p['download_speed'], p['upload_speed'], p['price'], p.get('promo_price')) for p in occom]