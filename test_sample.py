"""
Test script with sample data to demonstrate the scraping system.
This creates mock data to test the database and JSON saving functionality.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import log_info, log_success
from utils.db import create_connection, create_table_if_not_exists, insert_plans_batch
from utils.save_json import save_plans_to_json
from utils.validator import validate_plans, clean_plan_data
import config


# Sample ISP plan data (mock data for testing)
SAMPLE_PLANS = [
    {
        'provider_id': 1,
        'plan_name': 'Telstra Premium 100',
        'network_type': 'FTTP',
        'speed': 100,
        'download_speed': 100,
        'upload_speed': 20,
        'price': 90.00,
        'promo_price': 70.00,
        'promo_period': '6 months',
        'contract': 'No Contract',
        'source_url': 'https://www.telstra.com.au/internet/home-nbn'
    },
    {
        'provider_id': 1,
        'plan_name': 'Telstra Fast 50',
        'network_type': 'HFC',
        'speed': 50,
        'download_speed': 50,
        'upload_speed': 10,
        'price': 75.00,
        'promo_price': None,
        'promo_period': None,
        'contract': 'No Contract',
        'source_url': 'https://www.telstra.com.au/internet/home-nbn'
    },
    {
        'provider_id': 2,
        'plan_name': 'Optus Superfast 100',
        'network_type': 'FTTP',
        'speed': 100,
        'download_speed': 100,
        'upload_speed': 20,
        'price': 85.00,
        'promo_price': 65.00,
        'promo_period': '12 months',
        'contract': '12 months',
        'source_url': 'https://www.optus.com.au/broadband/nbn'
    },
    {
        'provider_id': 2,
        'plan_name': 'Optus Value 25',
        'network_type': 'FTTN',
        'speed': 25,
        'download_speed': 25,
        'upload_speed': 5,
        'price': 60.00,
        'promo_price': None,
        'promo_period': None,
        'contract': 'No Contract',
        'source_url': 'https://www.optus.com.au/broadband/nbn'
    },
    {
        'provider_id': 3,
        'plan_name': 'Aussie Broadband Premium 100',
        'network_type': 'FTTP',
        'speed': 100,
        'download_speed': 100,
        'upload_speed': 40,
        'price': 89.00,
        'promo_price': None,
        'promo_period': None,
        'contract': 'No Contract',
        'source_url': 'https://www.aussiebroadband.com.au/broadband/nbn/'
    },
    {
        'provider_id': 3,
        'plan_name': 'Aussie Broadband Fast 50',
        'network_type': 'FTTC',
        'speed': 50,
        'download_speed': 50,
        'upload_speed': 20,
        'price': 74.00,
        'promo_price': 64.00,
        'promo_period': '3 months',
        'contract': 'No Contract',
        'source_url': 'https://www.aussiebroadband.com.au/broadband/nbn/'
    },
    {
        'provider_id': 4,
        'plan_name': 'Superloop Premium 100',
        'network_type': 'FTTP',
        'speed': 100,
        'download_speed': 100,
        'upload_speed': 20,
        'price': 80.00,
        'promo_price': 70.00,
        'promo_period': '6 months',
        'contract': 'No Contract',
        'source_url': 'https://www.superloop.com/au/home-broadband/nbn'
    },
    {
        'provider_id': 4,
        'plan_name': 'Superloop Value 50',
        'network_type': 'FTTN',
        'speed': 50,
        'download_speed': 50,
        'upload_speed': 10,
        'price': 65.00,
        'promo_price': None,
        'promo_period': None,
        'contract': 'No Contract',
        'source_url': 'https://www.superloop.com/au/home-broadband/nbn'
    }
]


def run_test_pipeline():
    """
    Run test pipeline with sample data.
    """
    log_info("=" * 50)
    log_info("Running Test Pipeline with Sample Data")
    log_info("=" * 50)
    
    try:
        # Step 1: Clean and validate data
        log_info("Cleaning and validating sample data")
        cleaned_plans = [clean_plan_data(plan) for plan in SAMPLE_PLANS]
        valid_plans, invalid_plans = validate_plans(cleaned_plans)
        
        log_success(f"Validated {len(valid_plans)} plans, {len(invalid_plans)} invalid")
        
        if not valid_plans:
            log_error("No valid plans to save")
            return False
        
        # Step 2: Save to database
        log_info("Saving to MySQL database")
        connection = create_connection()
        
        if not connection:
            log_error("Failed to connect to database")
            return False
        
        try:
            create_table_if_not_exists(connection)
            insert_plans_batch(connection, valid_plans)
            log_success(f"Successfully saved {len(valid_plans)} plans to database")
        except Exception as e:
            log_error(f"Database error: {str(e)}")
            return False
        finally:
            if connection.is_connected():
                connection.close()
        
        # Step 3: Save to JSON
        log_info("Saving to JSON file")
        save_success = save_plans_to_json(valid_plans)
        
        if save_success:
            log_success(f"Successfully saved {len(valid_plans)} plans to JSON")
        else:
            log_error("Failed to save to JSON")
        
        # Summary
        log_info("=" * 50)
        log_success("Test Pipeline Completed Successfully!")
        log_info(f"Total plans processed: {len(valid_plans)}")
        log_info(f"Output files:")
        log_info(f"  - {config.PLANS_JSON_FILE}")
        log_info(f"  - {config.LOGS_JSON_FILE}")
        log_info("=" * 50)
        
        return True
        
    except Exception as e:
        log_error(f"Pipeline failed: {str(e)}")
        return False


if __name__ == "__main__":
    success = run_test_pipeline()
    sys.exit(0 if success else 1)
