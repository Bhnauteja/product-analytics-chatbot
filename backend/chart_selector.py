"""
Deterministic Chart Selector.
Applies Section 7.4 rules to pick the ideal chart type and generate a Plotly JSON spec:
- 1 row, 1 number -> Big number card (KPI)
- 1 date column + 1 or more numbers -> Line chart
- 1 category column + 1 number -> Bar chart (horizontal if category labels are long)
- Category + number (<= 5 categories) -> Pie / Donut chart
- 2 categories + 1 number -> Stacked / Grouped bar chart
- Anything else, or > 50 rows -> Table
"""

from typing import Any, Dict, List, Optional
import re

DATE_COLUMN_PATTERNS = [r"date", r"day", r"week", r"month", r"quarter", r"year", r"time", r"timestamp"]
ID_COLUMN_PATTERNS = [r"_id$", r"^id$"]

def is_date_column(col_name: str, sample_val: Any) -> bool:
    col_lower = col_name.lower()
    for pat in DATE_COLUMN_PATTERNS:
        if re.search(pat, col_lower):
            return True
    if sample_val is not None:
        val_str = str(sample_val)
        # Check standard date formats like YYYY-MM-DD or ISO
        if re.match(r"^\d{4}-\d{2}-\d{2}", val_str):
            return True
    return False

def is_numeric_value(val: Any) -> bool:
    if val is None:
        return False
    return isinstance(val, (int, float))

def select_chart(columns: List[str], rows: List[List[Any]], question_hint: str = "") -> Dict[str, Any]:
    """
    Selects the best chart type and builds a Plotly-compatible JSON spec.
    Returns:
        {
            "type": "kpi" | "line" | "bar" | "pie" | "stacked_bar" | "table",
            "title": str,
            "spec": Dict[str, Any]
        }
    """
    if not columns or not rows:
        return {
            "type": "table",
            "title": "Query Results",
            "spec": {"columns": columns or [], "rows": rows or []}
        }

    num_cols = len(columns)
    num_rows = len(rows)

    # If too many rows, default to Table for performance and readability
    if num_rows > 50:
        return {
            "type": "table",
            "title": "Detailed Data Table",
            "spec": {"columns": columns, "rows": rows}
        }

    # Inspect first row types
    sample_row = rows[0]
    
    # 1. Single value (1 row, 1 column, or 1 row with 1 numeric value)
    if num_rows == 1:
        # Find numeric column
        num_indices = [i for i, v in enumerate(sample_row) if is_numeric_value(v)]
        if len(num_indices) == 1:
            val = sample_row[num_indices[0]]
            col_name = columns[num_indices[0]].replace("_", " ").title()
            return {
                "type": "kpi",
                "title": col_name,
                "spec": {
                    "value": val,
                    "label": col_name,
                    "formatted": f"{val:,.2f}" if isinstance(val, float) else f"{val:,}"
                }
            }

    # Identify column classifications
    date_cols = []
    numeric_cols = []
    category_cols = []

    for i, col in enumerate(columns):
        first_non_null = next((r[i] for r in rows if r[i] is not None), None)
        if is_date_column(col, first_non_null):
            date_cols.append(i)
        elif is_numeric_value(first_non_null):
            numeric_cols.append(i)
        else:
            category_cols.append(i)

    # 2. Date column + 1 or more numeric columns -> Line Chart
    if len(date_cols) == 1 and len(numeric_cols) >= 1:
        date_idx = date_cols[0]
        x_values = [r[date_idx] for r in rows]
        
        traces = []
        for num_idx in numeric_cols:
            y_values = [r[num_idx] for r in rows]
            series_name = columns[num_idx].replace("_", " ").title()
            traces.append({
                "x": x_values,
                "y": y_values,
                "type": "scatter",
                "mode": "lines+markers",
                "name": series_name,
                "line": {"width": 3, "shape": "spline"}
            })
            
        chart_title = f"{columns[numeric_cols[0]].replace('_', ' ').title()} Over Time"
        return {
            "type": "line",
            "title": chart_title,
            "spec": {
                "data": traces,
                "layout": {
                    "xaxis": {"title": columns[date_idx].replace('_', ' ').title()},
                    "yaxis": {"title": "Count / Value"},
                    "hovermode": "x unified",
                    "template": "plotly_white"
                }
            }
        }

    # 3. 1 Category column + 1 Numeric column -> Bar or Pie
    if len(category_cols) == 1 and len(numeric_cols) == 1:
        cat_idx = category_cols[0]
        num_idx = numeric_cols[0]
        categories = [str(r[cat_idx]) if r[cat_idx] is not None else "(Unknown)" for r in rows]
        values = [r[num_idx] for r in rows]
        
        # Check if category labels are long (> 15 chars) -> Horizontal Bar Chart
        avg_label_len = sum(len(c) for c in categories) / max(len(categories), 1)
        is_horizontal = avg_label_len > 14
        
        # Check if few categories (<= 5) and represents parts of a whole (or pie requested)
        if 2 <= num_rows <= 5 and any(word in question_hint.lower() for word in ["share", "split", "ratio", "proportion", "breakdown", "platform"]):
            return {
                "type": "pie",
                "title": f"Distribution by {columns[cat_idx].replace('_', ' ').title()}",
                "spec": {
                    "data": [{
                        "labels": categories,
                        "values": values,
                        "type": "pie",
                        "hole": 0.4,
                        "textinfo": "label+percent"
                    }],
                    "layout": {"template": "plotly_white"}
                }
            }

        # Otherwise Bar Chart
        if is_horizontal:
            bar_trace = {
                "y": categories,
                "x": values,
                "type": "bar",
                "orientation": "h",
                "marker": {"color": "#3B82F6"}
            }
            layout = {
                "yaxis": {"autorange": "reversed"},
                "xaxis": {"title": columns[num_idx].replace('_', ' ').title()},
                "template": "plotly_white"
            }
        else:
            bar_trace = {
                "x": categories,
                "y": values,
                "type": "bar",
                "marker": {"color": "#3B82F6"}
            }
            layout = {
                "xaxis": {"title": columns[cat_idx].replace('_', ' ').title()},
                "yaxis": {"title": columns[num_idx].replace('_', ' ').title()},
                "template": "plotly_white"
            }

        return {
            "type": "bar",
            "title": f"{columns[num_idx].replace('_', ' ').title()} by {columns[cat_idx].replace('_', ' ').title()}",
            "spec": {
                "data": [bar_trace],
                "layout": layout
            }
        }

    # 4. 2 Categories + 1 Numeric Column -> Grouped / Stacked Bar
    if len(category_cols) == 2 and len(numeric_cols) == 1:
        cat1_idx = category_cols[0]
        cat2_idx = category_cols[1]
        num_idx = numeric_cols[0]
        
        # Pivot the data for stacked bar
        unique_groups = sorted(list({str(r[cat2_idx]) for r in rows}))
        x_vals = sorted(list({str(r[cat1_idx]) for r in rows}))
        
        data_map: Dict[str, Dict[str, Any]] = {g: {x: 0 for x in x_vals} for g in unique_groups}
        for r in rows:
            g = str(r[cat2_idx])
            x = str(r[cat1_idx])
            data_map[g][x] = r[num_idx]

        traces = []
        for g in unique_groups:
            traces.append({
                "name": g,
                "x": x_vals,
                "y": [data_map[g][x] for x in x_vals],
                "type": "bar"
            })

        return {
            "type": "stacked_bar",
            "title": f"{columns[num_idx].replace('_', ' ').title()} by {columns[cat1_idx].replace('_', ' ').title()} and {columns[cat2_idx].replace('_', ' ').title()}",
            "spec": {
                "data": traces,
                "layout": {
                    "barmode": "group",
                    "template": "plotly_white"
                }
            }
        }

    # Fallback to Table
    return {
        "type": "table",
        "title": "Data Table",
        "spec": {"columns": columns, "rows": rows}
    }

