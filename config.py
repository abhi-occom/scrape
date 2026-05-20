"""
Configuration file for ISP scraper system.
Contains database settings, provider configurations, and constants.
"""

# Database Configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # Update with your MySQL password
    'database': 'isp_plans',
    'port': 3306
}

# Provider Configuration
PROVIDERS = {
    'telstra': {
        'id': 1,
        'name': 'Telstra',
        'enabled': True
    },
    'optus': {
        'id': 2,
        'name': 'Optus',
        'enabled': True
    },
    'aussie': {
        'id': 3,
        'name': 'Aussie Broadband',
        'enabled': True,
        'blocked': True,
        'blocked_reason': 'Cloudflare Turnstile'
    },
    'superloop': {
        'id': 4,
        'name': 'Superloop',
        'enabled': True
    },
    'occom': {
        'id': 5,
        'name': 'Occom',
        'enabled': True
    },
    'tpg': {
        'id': 6,
        'name': 'TPG',
        'enabled': True
    },
    'exetel': {
        'id': 7,
        'name': 'Exetel',
        'enabled': True
    },
    'leaptel': {
        'id': 8,
        'name': 'Leaptel',
        'enabled': True
    },
    'iinet': {
        'id': 9,
        'name': 'iiNet',
        'enabled': True
    },
    'swoop': {
        'id': 10,
        'name': 'Swoop',
        'enabled': True,
        'note': 'Scrapes 3 service types: NBN, Fixed Wireless, Opticomm'
    },
    'iprimus': {
        'id': 11,
        'name': 'iPrimus',
        'enabled': True,
        'note': 'Scrapes NBN, Fixed Wireless and Fibre plans from /nbn-plans'
    },
    'dodo': {
        'id': 12,
        'name': 'Dodo',
        'enabled': True,
        'note': 'Scrapes NBN plans (all tiers) from /nbn -- Drupal-rendered, no JS wait needed'
    },
    'kogan': {
        'id': 13,
        'name': 'Kogan',
        'enabled': True,
        'note': 'Scrapes NBN plans (all tiers) from /nbn -- rendered, no JS wait needed'
    },
    'more': {
        'id': 14,
        'name': 'More',
        'enabled': True,
        'note': 'Scrapes NBN plans (4 tiers) from /personal/nbn-plans -- JavaScript rendered'
    },
    'tangerine': {
        'id': 15,
        'name': 'Tangerine',
        'enabled': True,
        'note': 'Scrapes NBN plans (4 tiers) from /nbn/nbn-broadband -- static HTML'
    },
    'mate': {
        'id': 16,
        'name': 'MATE',
        'enabled': True,
        'note': 'Scrapes 7 NBN plans from individual sub-pages under /mate/ -- JS-rendered, uses networkidle'
    },
    'spintel': {
        'id': 17,
        'name': 'Spintel',
        'enabled': True,
        'note': 'Scrapes NBN, Fixed Wireless and Fibre plans from /home-internet/nbn -- JavaScript rendered'
    },
    'origin': {
        'id': 18,
        'name': 'Origin Energy',
        'enabled': True,
        'note': 'Scrapes NBN plans (4 tiers) from /internet/plans/ -- JavaScript rendered'
    },
}

# Output paths
OUTPUT_DIR = 'output'
PLANS_JSON_FILE = f'{OUTPUT_DIR}/plans.json'
LOGS_JSON_FILE = f'{OUTPUT_DIR}/logs.json'

# Playwright settings
PLAYWRIGHT_TIMEOUT = 30000  # 30 seconds
PLAYWRIGHT_WAIT_TIME = 2000  # 2 seconds default wait

# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
