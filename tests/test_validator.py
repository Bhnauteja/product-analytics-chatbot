"""
Unit Tests for SQL Validator & Security Guardrails.
Tests that dangerous operations, injections, and unauthorized table accesses are blocked.
"""

import pytest
from backend.sql_validator import validate_and_sanitize_sql, ALLOWED_SCHEMA

def test_valid_select_query():
    sql = "SELECT country, COUNT(*) AS count FROM users GROUP BY country ORDER BY count DESC LIMIT 5;"
    result = validate_and_sanitize_sql(sql)
    assert result.is_valid is True
    assert "LIMIT 5" in result.sanitized_sql
    assert "users" in result.tables_used

def test_auto_limit_injection():
    sql = "SELECT user_id, signup_date FROM users"
    result = validate_and_sanitize_sql(sql, max_limit=500)
    assert result.is_valid is True
    assert "LIMIT 500" in result.sanitized_sql

def test_block_drop_table():
    sql = "DROP TABLE users;"
    result = validate_and_sanitize_sql(sql)
    assert result.is_valid is False
    assert "Prohibited" in result.error_message or "Only SELECT" in result.error_message

def test_block_delete_from():
    sql = "DELETE FROM orders WHERE amount > 0;"
    result = validate_and_sanitize_sql(sql)
    assert result.is_valid is False
    assert "Security violation" in result.error_message

def test_block_insert_into():
    sql = "INSERT INTO users (user_id) VALUES ('hacked');"
    result = validate_and_sanitize_sql(sql)
    assert result.is_valid is False

def test_block_update():
    sql = "UPDATE products SET price = 0;"
    result = validate_and_sanitize_sql(sql)
    assert result.is_valid is False

def test_block_multiple_statements_stacked_injection():
    sql = "SELECT * FROM users; DROP TABLE orders;"
    result = validate_and_sanitize_sql(sql)
    assert result.is_valid is False
    assert "Multiple SQL statements" in result.error_message

def test_block_unauthorized_tables():
    sql = "SELECT * FROM secret_passwords;"
    result = validate_and_sanitize_sql(sql)
    assert result.is_valid is False
    assert "secret_passwords" in result.error_message

def test_block_system_catalogs():
    sql = "SELECT * FROM information_schema.tables;"
    result = validate_and_sanitize_sql(sql)
    assert result.is_valid is False

def test_block_filesystem_access_read_csv():
    sql = "SELECT * FROM read_csv('/etc/passwd');"
    result = validate_and_sanitize_sql(sql)
    assert result.is_valid is False
    assert "read_csv" in result.error_message or "Prohibited" in result.error_message

def test_block_filesystem_access_read_parquet():
    sql = "SELECT * FROM read_parquet('s3://my-secret-bucket/data.parquet');"
    result = validate_and_sanitize_sql(sql)
    assert result.is_valid is False

def test_allow_cte_with_valid_tables():
    sql = """
    WITH cohort AS (
        SELECT user_id FROM users WHERE signup_date >= '2026-01-01'
    )
    SELECT COUNT(*) FROM cohort;
    """
    result = validate_and_sanitize_sql(sql)
    assert result.is_valid is True
    assert "users" in result.tables_used

def test_allow_complex_joins():
    sql = """
    SELECT p.name, SUM(o.amount) AS rev
    FROM orders o
    JOIN products p ON o.product_id = p.product_id
    WHERE o.status = 'completed'
    GROUP BY p.name
    LIMIT 10;
    """
    result = validate_and_sanitize_sql(sql)
    assert result.is_valid is True
    assert "orders" in result.tables_used
    assert "products" in result.tables_used

def test_dynamic_custom_table_registration():
    from backend.sql_validator import register_custom_table
    register_custom_table("kaggle_superstore", {"order_id", "category", "sales", "profit"})
    
    sql = "SELECT category, SUM(sales) AS total_sales FROM kaggle_superstore GROUP BY category LIMIT 5;"
    result = validate_and_sanitize_sql(sql)
    assert result.is_valid is True
    assert "kaggle_superstore" in result.tables_used

