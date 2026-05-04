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
        'enabled': True
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
    }
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
