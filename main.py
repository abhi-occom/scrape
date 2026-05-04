"""
Main pipeline for ISP plan scraping system.
Orchestrates all provider scrapers, validates data, and saves to database and JSON.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from typing import List, Dict, Any
from utils.logger import log_info, log_error, log_success, log_warning
from utils.db import create_connection, create_table_if_not_exists, insert_plans_batch
from utils.save_json import save_plans_to_json
from utils.validator import validate_plans, clean_plan_data
from utils.benchmark import run_benchmark, save_benchmark_report, save_benchmark_csv
from utils.alerts import run_alerts
from benchmark_report import generate_html_report
from roi_calculator import run_and_save_roi
from providers import telstra, optus, aussie, superloop
from scrapers.renderer import create_renderer_scraper, SiteConfig
import config


def run_rendered_scraper() -> List[Dict[str, Any]]:
    """
    Run the rendered HTML scraper for sites that require JavaScript rendering.
    This is used as a fallback when API scraping fails or for sites without APIs.
    
    Returns:
        List of scraped plans from rendered HTML
    """
    log_info("Starting rendered HTML scraper")
    
    # Define site configurations for ISP providers
    sites = [
        SiteConfig(
            name="telstra",
            base_url="https://www.telstra.com.au/internet/home-nbn",
            selectors={
                'plan_name': '.plan-name, h2.plan-title, [class*="plan-name"]',
                'price': '.price, .plan-price, [class*="price"]',
                'speed': '.speed, .plan-speed, [class*="speed"]'
            },
            wait_selector=".plan-card, .plan-container, article",
            wait_time=2000,
            max_pages=5
        ),
        SiteConfig(
            name="optus", 
            base_url="https://www.optus.com.au/internet/nbn-plans",
            selectors={
                'plan_name': '.plan-title, h3[class*="plan"]',
                'price': '.price-amount, [class*="price"]',
                'speed': '.speed-value, [class*="speed"]'
            },
            wait_selector=".plan-card, .product-card",
            wait_time=2000,
            max_pages=5
        )
    ]
    
    scraper = create_renderer_scraper(sites=sites, headless=True)
    
    try:
        results = scraper.scrape_all_sites()
        
        # Convert scraped data to plan format
        plans = []
        for site_name, pages in results.items():
            for page in pages:
                if page.success and page.parsed_data:
                    plan = {
                        'provider_id': config.PROVIDERS.get(site_name.lower(), {}).get('id', 0),
                        'source': 'rendered_html',
                        'url': page.url,
                        **page.parsed_data
                    }
                    plans.append(plan)
                    
        log_success(f"Rendered scraper collected {len(plans)} plans")
        
        # Save raw results for debugging
        scraper.save_results(f"{config.OUTPUT_DIR}/rendered_results.json")
        
        return plans
        
    except Exception as e:
        log_error(f"Rendered scraper failed: {str(e)}")
        return []


def run_all_scrapers() -> List[Dict[str, Any]]:
    """
    Run all provider scrapers and collect results.
    Each scraper is wrapped in try/catch to prevent system-wide failures.
    
    Returns:
        Combined list of all scraped plans
    """
    all_plans = []
    
    # Define scrapers to run
    scrapers = [
        ('telstra', telstra.scrape_telstra_plans),
        ('optus', optus.scrape_optus_plans),
        ('aussie', aussie.scrape_aussie_plans),
        ('superloop', superloop.scrape_superloop_plans)
    ]
    
    for provider_name, scraper_func in scrapers:
        try:
            log_info(f"Running {provider_name} scraper", provider=provider_name)
            plans = scraper_func()
            
            if plans:
                log_success(f"Retrieved {len(plans)} plans from {provider_name}", 
                           provider=provider_name, data={'plan_count': len(plans)})
                all_plans.extend(plans)
            else:
                log_warning(f"No plans retrieved from {provider_name}", provider=provider_name)
                
        except Exception as e:
            log_error(f"Scraper failed for {provider_name}: {str(e)}", 
                     provider=provider_name, data={'error': str(e)})
    
    return all_plans


def merge_and_clean_plans(plans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Merge results from all providers and clean the data.
    
    Args:
        plans: Raw list of plans from all providers
    
    Returns:
        Cleaned list of plans
    """
    log_info(f"Merging and cleaning {len(plans)} plans")
    
    # Clean each plan
    cleaned_plans = []
    for plan in plans:
        try:
            cleaned = clean_plan_data(plan)
            cleaned_plans.append(cleaned)
        except Exception as e:
            log_warning(f"Failed to clean plan: {str(e)}", data={'plan': plan})
    
    log_success(f"Cleaned {len(cleaned_plans)} plans")
    return cleaned_plans


def validate_all_plans(plans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate all plans and remove invalid records.
    
    Args:
        plans: List of plans to validate
    
    Returns:
        List of valid plans only
    """
    log_info(f"Validating {len(plans)} plans")
    
    valid_plans, invalid_plans = validate_plans(plans)
    
    if invalid_plans:
        log_warning(f"Found {len(invalid_plans)} invalid plans", 
                   data={'invalid_count': len(invalid_plans)})
        for invalid in invalid_plans:
            log_warning(f"Invalid plan: {invalid.get('plan_name', 'Unknown')} - {invalid.get('validation_error', 'Unknown error')}",
                       data={'plan': invalid})
    
    log_success(f"Validation complete: {len(valid_plans)} valid, {len(invalid_plans)} invalid")
    return valid_plans


def save_to_database(plans: List[Dict[str, Any]]):
    """
    Save plans to MySQL database.
    
    Args:
        plans: List of validated plans
    """
    log_info("Saving plans to database")
    
    connection = create_connection()
    if not connection:
        log_error("Failed to connect to database")
        return False
    
    try:
        # Create table if it doesn't exist
        create_table_if_not_exists(connection)
        
        # Insert plans in batch
        insert_plans_batch(connection, plans)
        
        log_success(f"Successfully saved {len(plans)} plans to database")
        return True
        
    except Exception as e:
        log_error(f"Database save failed: {str(e)}")
        return False
    finally:
        if connection.is_connected():
            connection.close()


def save_to_json(plans: List[Dict[str, Any]]):
    """
    Save plans to JSON file.
    
    Args:
        plans: List of validated plans
    """
    log_info("Saving plans to JSON file")
    
    success = save_plans_to_json(plans)
    
    if success:
        log_success(f"Successfully saved {len(plans)} plans to JSON")
    else:
        log_error("Failed to save plans to JSON")
    
    return success


def run_pipeline():
    """
    Main pipeline execution function.
    Orchestrates the entire scraping workflow.
    """
    log_info("=" * 50)
    log_info("Starting ISP Plan Scraping Pipeline")
    log_info("=" * 50)
    
    try:
        # Step 1: Run all scrapers
        raw_plans = run_all_scrapers()
        
        if not raw_plans:
            log_warning("No plans from API scrapers, attempting rendered HTML scraping")
            raw_plans = run_rendered_scraper()
        
        if not raw_plans:
            log_error("No plans scraped from any source")
            return False
        
        log_success(f"Total raw plans collected: {len(raw_plans)}")
        
        # Step 2: Merge and clean data
        cleaned_plans = merge_and_clean_plans(raw_plans)
        
        # Step 3: Validate plans
        valid_plans = validate_all_plans(cleaned_plans)
        
        if not valid_plans:
            log_error("No valid plans after validation")
            return False
        
        # Step 4: Save to database
        db_success = save_to_database(valid_plans)
        
        # Step 5: Save to JSON
        json_success = save_to_json(valid_plans)
        
        # Step 6: Run competitive benchmark
        log_info("Running competitive benchmark analysis")
        benchmark_report = run_benchmark(valid_plans)
        if 'error' not in benchmark_report:
            save_benchmark_report(benchmark_report)
            save_benchmark_csv(benchmark_report)
            generate_html_report(benchmark_report)
            log_success(
                f"Benchmark: Occom wins {benchmark_report['summary']['occom_cheapest_tiers']} of "
                f"{benchmark_report['summary']['total_speed_tiers']} tiers "
                f"({benchmark_report['summary']['occom_win_rate']}% win rate)"
            )
        else:
            log_warning(f"Benchmark skipped: {benchmark_report.get('error')}")

        # Step 7: Run alerts
        log_info("Running alert checks")
        alert_report = run_alerts(valid_plans, benchmark_report if 'error' not in benchmark_report else None)
        if alert_report['total_alerts'] > 0:
            log_warning(f"Alerts: {alert_report['total_alerts']} "
                        f"({alert_report['high']} high, {alert_report['medium']} medium)")
        else:
            log_success("No new alerts")

        # Step 8: Generate ROI Calculator
        log_info("Generating ROI Calculator page")
        roi_result = run_and_save_roi(valid_plans)
        if 'error' not in roi_result:
            log_success(f"ROI Calculator: {roi_result['data']['total_plans']} plans ranked")
        else:
            log_warning(f"ROI Calculator skipped: {roi_result.get('error')}")
        
        # Final summary
        log_info("=" * 50)
        log_info("Pipeline Execution Summary")
        log_info("=" * 50)
        log_success(f"Total plans processed: {len(valid_plans)}")
        log_success(f"Database save: {'Success' if db_success else 'Failed'}")
        log_success(f"JSON save: {'Success' if json_success else 'Failed'}")
        log_success(f"Benchmark: {'Generated' if 'error' not in benchmark_report else 'Skipped'}")
        log_success(f"Alerts: {alert_report['total_alerts']} generated")
        log_success(f"ROI Calculator: {'Generated' if 'error' not in roi_result else 'Skipped'}")
        log_info("=" * 50)
        
        return db_success and json_success
        
    except Exception as e:
        log_error(f"Pipeline failed with critical error: {str(e)}")
        return False


if __name__ == "__main__":
    success = run_pipeline()
    sys.exit(0 if success else 1)
