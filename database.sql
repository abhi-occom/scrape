-- ISP Plans Database Schema
-- This script creates the database and tables for the ISP plan scraping system

-- Create database
CREATE DATABASE IF NOT EXISTS isp_plans
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

-- Use the database
USE isp_plans;

-- Create plans_current table
CREATE TABLE IF NOT EXISTS plans_current (
    provider_id INT NOT NULL COMMENT 'Provider identifier (1=Telstra, 2=Optus, 3=Aussie, 4=Superloop)',
    plan_name VARCHAR(255) NOT NULL COMMENT 'Name of the ISP plan',
    network_type VARCHAR(50) COMMENT 'Network technology (NBN, FTTP, HFC, etc.)',
    speed_label INT COMMENT 'Speed tier label in Mbps',
    download_speed INT COMMENT 'Download speed in Mbps',
    upload_speed INT COMMENT 'Upload speed in Mbps',
    monthly_price DECIMAL(10, 2) COMMENT 'Regular monthly price in AUD',
    promo_price DECIMAL(10, 2) COMMENT 'Promotional price in AUD',
    promo_period VARCHAR(50) COMMENT 'Promotional period (e.g., "6 months")',
    contract_term VARCHAR(50) COMMENT 'Contract duration (e.g., "No Contract", "12 months")',
    source_url TEXT COMMENT 'Source URL where the plan was scraped from',
    last_checked DATETIME COMMENT 'Timestamp of last data verification',
    
    -- Unique constraint to prevent duplicate plans
    UNIQUE KEY unique_plan (provider_id, plan_name, speed_label),
    
    -- Indexes for better query performance
    INDEX idx_provider (provider_id),
    INDEX idx_price (monthly_price),
    INDEX idx_speed (speed_label),
    INDEX idx_last_checked (last_checked)
) ENGINE=InnoDB 
  DEFAULT CHARSET=utf8mb4 
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Current ISP plan data scraped from providers';

-- Create provider reference table (optional, for documentation)
CREATE TABLE IF NOT EXISTS providers (
    provider_id INT PRIMARY KEY,
    provider_name VARCHAR(100) NOT NULL,
    website_url VARCHAR(255),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB 
  DEFAULT CHARSET=utf8mb4 
  COLLATE=utf8mb4_unicode_ci
  COMMENT='ISP Provider reference table';

-- Insert provider data
INSERT INTO providers (provider_id, provider_name, website_url, active) VALUES
(1, 'Telstra', 'https://www.telstra.com.au/internet/home-nbn', TRUE),
(2, 'Optus', 'https://www.optus.com.au/broadband/nbn', TRUE),
(3, 'Aussie Broadband', 'https://www.aussiebroadband.com.au/broadband/nbn/', TRUE),
(4, 'Superloop', 'https://www.superloop.com/au/home-broadband/nbn', TRUE)
ON DUPLICATE KEY UPDATE 
    provider_name = VALUES(provider_name),
    website_url = VALUES(website_url),
    active = VALUES(active);

-- Create logs table (optional - for reference, actual logs are JSON-based)
CREATE TABLE IF NOT EXISTS scrape_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL,
    status VARCHAR(20) NOT NULL COMMENT 'success, error, warning, info',
    provider VARCHAR(50) COMMENT 'Provider name',
    message TEXT NOT NULL,
    data JSON COMMENT 'Additional log data in JSON format',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB 
  DEFAULT CHARSET=utf8mb4 
  COLLATE=utf8mb4_unicode_ci
  COMMENT='Scraping operation logs (optional - primary logging is JSON-based)';

-- Create view for easy plan summary (optional)
CREATE OR REPLACE VIEW v_plan_summary AS
SELECT 
    p.provider_name,
    pc.plan_name,
    pc.network_type,
    pc.speed_label as speed_mbps,
    pc.monthly_price,
    pc.promo_price,
    pc.last_checked,
    CASE 
        WHEN pc.promo_price IS NOT NULL THEN pc.promo_price
        ELSE pc.monthly_price
    END as effective_price
FROM plans_current pc
LEFT JOIN providers p ON pc.provider_id = p.provider_id
WHERE p.active = TRUE
ORDER BY pc.speed_label ASC, effective_price ASC;

-- Sample query: Get cheapest plans by speed tier
-- SELECT speed_label, MIN(monthly_price) as min_price
-- FROM plans_current
-- GROUP BY speed_label
-- ORDER BY speed_label;

-- Sample query: Get all plans with provider names
-- SELECT p.provider_name, pc.*
-- FROM plans_current pc
-- JOIN providers p ON pc.provider_id = p.provider_id
-- ORDER BY pc.speed_label, pc.monthly_price;
