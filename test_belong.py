"""Belong scraper tests (parsers run offline against captured page text)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from providers.belong import parse_internet_plans, parse_sim_plans
from utils.network_classifier import normalise_plans

INTERNET_TEXT = """Select a plan
Show all
High speed

$26/month off for 6 months

Starter plan
$26/month off for 6 months

nbn®25

$49/month

for 6 months, then $75/month. Offer ends 04 Nov 2026.
T&Cs apply
.

Typical evening speeds (7pm - 11pm)

25Mbps download
8Mbps upload

Check your address

$36/month off for 6 months

Fast plan
$36/month off for 6 months

nbn®500

$59/month

for 6 months, then $95/month. Offer ends 04 Nov 2026.

Typical evening speeds (7pm - 11pm)

500Mbps download
40Mbps upload
"""

MOBILE_TEXT = """Our mobile plans
60GB Bonus Offer
25GB SIM only plan
85 gigabytes
85GB
34 dollars per month
$34/mth
For 12 months, then 25GB/mth

4G and 5G download speeds capped at 150 Mbps.
Select 25GB SIM plan
60GB Bonus Offer
160GB SIM only plan
220 gigabytes
220GB
59 dollars per month
$59/mth
For 12 months, then 160GB/mth

4G and 5G download speeds capped at 250 Mbps.
Select 160GB SIM plan
"""

DATA_TEXT = """20GB Mobile Broadband
20 gigabytes
20GB
20 dollars per month
$20/mth

4G and 5G download speeds capped at 150 Mbps
Select 20GB data plan
Recommended
100GB Mobile Broadband
100 gigabytes
100GB
40 dollars per month
$40/mth

4G and 5G download speeds capped at 150 Mbps
"""


def test_internet_plans_use_promo_and_standard_price():
    plans = parse_internet_plans(INTERNET_TEXT)
    assert [p['download_speed'] for p in plans] == [25, 500]
    starter = plans[0]
    assert starter['plan_name'] == 'Starter plan - nbn 25'
    assert starter['promo_price'] == 49.0       # not the "$26 off" banner
    assert starter['price'] == 75.0
    assert starter['promo_period'] == '6 months'
    assert (starter['typical_evening_dl'], starter['typical_evening_ul']) == (25, 8)
    assert starter['network_type'] == 'NBN'


def test_mobile_plans():
    plans = parse_sim_plans(MOBILE_TEXT, 'Mobile', 'https://www.belong.com.au/go/mobile')
    assert [(p['plan_name'], p['price'], p['download_speed']) for p in plans] == [
        ('25GB SIM only plan', 34.0, 150),
        ('160GB SIM only plan', 59.0, 250),
    ]


def test_data_plans():
    plans = parse_sim_plans(DATA_TEXT, 'Mobile Broadband', 'https://www.belong.com.au/go/data-plans')
    assert [(p['plan_name'], p['price']) for p in plans] == [
        ('20GB Mobile Broadband', 20.0),
        ('100GB Mobile Broadband', 40.0),
    ]


def test_mobile_network_types_survive_normalisation():
    plans = normalise_plans(
        parse_sim_plans(MOBILE_TEXT, 'Mobile', 'u') + parse_sim_plans(DATA_TEXT, 'Mobile Broadband', 'u')
    )
    types = {p['network_type'] for p in plans}
    assert types == {'Mobile', 'Mobile Broadband'}
