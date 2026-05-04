"""
Database utility module.
Handles MySQL connections and data operations.
"""

import mysql.connector
from mysql.connector import Error
from typing import List, Dict, Any
from datetime import datetime
import config


def create_connection():
    """
    Create a MySQL database connection.
    
    Returns:
        mysql.connector.connection: Database connection object or None
    """
    try:
        connection = mysql.connector.connect(**config.DB_CONFIG)
        if connection.is_connected():
            return connection
    except Error as e:
        print(f"Error connecting to MySQL: {e}")
        return None
    return None


def create_table_if_not_exists(connection):
    """
    Create the plans_current table if it doesn't exist.
    
    Args:
        connection: MySQL connection object
    """
    create_table_query = """
    CREATE TABLE IF NOT EXISTS plans_current (
        provider_id INT NOT NULL,
        plan_name VARCHAR(255) NOT NULL,
        network_type VARCHAR(50),
        speed_label INT,
        download_speed INT,
        upload_speed INT,
        monthly_price DECIMAL(10, 2),
        promo_price DECIMAL(10, 2),
        promo_period VARCHAR(50),
        contract_term VARCHAR(50),
        source_url TEXT,
        last_checked DATETIME,
        UNIQUE KEY unique_plan (provider_id, plan_name, speed_label)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    
    try:
        cursor = connection.cursor()
        cursor.execute(create_table_query)
        connection.commit()
        cursor.close()
    except Error as e:
        print(f"Error creating table: {e}")


def insert_or_update_plan(connection, plan_data: Dict[str, Any]):
    """
    Insert a plan or update if it already exists.
    Uses INSERT ... ON DUPLICATE KEY UPDATE.
    
    Args:
        connection: MySQL connection object
        plan_data: Dictionary containing plan information
    """
    insert_query = """
    INSERT INTO plans_current 
    (provider_id, plan_name, network_type, speed_label, download_speed, 
     upload_speed, monthly_price, promo_price, promo_period, contract_term, 
     source_url, last_checked)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        network_type = VALUES(network_type),
        download_speed = VALUES(download_speed),
        upload_speed = VALUES(upload_speed),
        monthly_price = VALUES(monthly_price),
        promo_price = VALUES(promo_price),
        promo_period = VALUES(promo_period),
        contract_term = VALUES(contract_term),
        source_url = VALUES(source_url),
        last_checked = VALUES(last_checked)
    """
    
    try:
        cursor = connection.cursor()
        
        # Extract values with proper defaults
        values = (
            plan_data.get('provider_id'),
            plan_data.get('plan_name'),
            plan_data.get('network_type', 'N/A'),
            plan_data.get('speed_label', plan_data.get('speed')),
            plan_data.get('download_speed', plan_data.get('speed')),
            plan_data.get('upload_speed'),
            plan_data.get('price', plan_data.get('monthly_price')),
            plan_data.get('promo_price'),
            plan_data.get('promo_period'),
            plan_data.get('contract'),
            plan_data.get('source_url'),
            datetime.now()
        )
        
        cursor.execute(insert_query, values)
        connection.commit()
        cursor.close()
        return True
        
    except Error as e:
        print(f"Error inserting/updating plan: {e}")
        return False


def insert_plans_batch(connection, plans: List[Dict[str, Any]]):
    """
    Insert multiple plans in batch.
    
    Args:
        connection: MySQL connection object
        plans: List of plan dictionaries
    """
    for plan in plans:
        insert_or_update_plan(connection, plan)
