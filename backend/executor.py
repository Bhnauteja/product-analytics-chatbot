"""
Read-Only DuckDB Query Executor with Timeouts and Row Limits.
Guarantees database-level read-only access (least privilege).
"""

import os
import time
from typing import Any, Dict, List, Optional
import duckdb

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "analytics.duckdb")
DEFAULT_TIMEOUT_SEC = 10
MAX_ROW_CAP = 10000

class QueryExecutionError(Exception):
    pass

def execute_query(
    sql_query: str,
    db_path: str = DEFAULT_DB_PATH,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    row_cap: int = MAX_ROW_CAP
) -> Dict[str, Any]:
    """
    Executes an approved, sanitized SQL query against DuckDB in strictly read-only mode.
    Returns:
        {
            "columns": List[str],
            "rows": List[List[Any]],
            "row_count": int,
            "execution_time_ms": float
        }
    """
    if not os.path.exists(db_path):
        raise QueryExecutionError(f"Database file not found at '{db_path}'. Please run the data generator first.")

    start_time = time.perf_counter()
    con = None
    try:
        # Strictly enforce read_only=True at the database connection layer
        con = duckdb.connect(database=db_path, read_only=True)
        
        # Configure resource limits
        con.execute(f"SET max_memory = '512MB';")
        
        # Execute the query
        rel = con.sql(sql_query)
        if rel is None:
            return {
                "columns": [],
                "rows": [],
                "row_count": 0,
                "execution_time_ms": round((time.perf_counter() - start_time) * 1000, 2)
            }
            
        columns = rel.columns
        raw_rows = rel.fetchall()
        
        # Clamp row limit for security and memory protection
        if len(raw_rows) > row_cap:
            raw_rows = raw_rows[:row_cap]

        # Convert DuckDB objects/dates/timestamps to JSON-safe representations
        safe_rows: List[List[Any]] = []
        for row in raw_rows:
            safe_row = []
            for val in row:
                if val is None:
                    safe_row.append(None)
                elif hasattr(val, "isoformat"):
                    safe_row.append(val.isoformat())
                elif isinstance(val, (int, float, str, bool)):
                    safe_row.append(val)
                else:
                    safe_row.append(str(val))
            safe_rows.append(safe_row)

        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        
        return {
            "columns": columns,
            "rows": safe_rows,
            "row_count": len(safe_rows),
            "execution_time_ms": execution_time_ms
        }
    except duckdb.Error as e:
        raise QueryExecutionError(f"Database execution error: {str(e)}")
    except Exception as e:
        raise QueryExecutionError(f"Unexpected query error: {str(e)}")
    finally:
        if con:
            con.close()

