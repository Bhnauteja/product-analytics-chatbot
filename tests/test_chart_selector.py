"""
Unit Tests for Chart Selector.
Tests deterministic mapping of query result shapes to chart specifications.
"""

from backend.chart_selector import select_chart

def test_single_value_kpi():
    columns = ["total_revenue"]
    rows = [[145200.50]]
    chart = select_chart(columns, rows)
    assert chart["type"] == "kpi"
    assert chart["spec"]["formatted"] == "145,200.50"

def test_date_and_number_line_chart():
    columns = ["signup_week", "signups"]
    rows = [
        ["2026-01-05", 120],
        ["2026-01-12", 150],
        ["2026-01-19", 180]
    ]
    chart = select_chart(columns, rows)
    assert chart["type"] == "line"
    assert len(chart["spec"]["data"]) == 1
    assert chart["spec"]["data"][0]["type"] == "scatter"

def test_category_and_number_bar_chart():
    columns = ["country", "users"]
    rows = [
        ["United States", 500],
        ["India", 450],
        ["Germany", 200]
    ]
    chart = select_chart(columns, rows)
    assert chart["type"] == "bar"

def test_few_categories_pie_chart():
    columns = ["platform", "users"]
    rows = [
        ["web", 600],
        ["ios", 300],
        ["android", 100]
    ]
    chart = select_chart(columns, rows, question_hint="Platform share breakdown")
    assert chart["type"] == "pie"

def test_two_categories_stacked_bar():
    columns = ["device", "plan", "user_count"]
    rows = [
        ["Desktop", "Free", 300],
        ["Desktop", "Pro", 120],
        ["Mobile", "Free", 400],
        ["Mobile", "Pro", 80]
    ]
    chart = select_chart(columns, rows)
    assert chart["type"] == "stacked_bar"

def test_large_dataset_table_fallback():
    columns = ["user_id", "email"]
    rows = [[f"usr_{i}", f"user{i}@test.com"] for i in range(60)]
    chart = select_chart(columns, rows)
    assert chart["type"] == "table"

