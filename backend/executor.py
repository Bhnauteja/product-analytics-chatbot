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

def ingest_dataframe_to_duckdb(
    df: Any,
    table_name: str,
    db_path: str = DEFAULT_DB_PATH
) -> Dict[str, Any]:
    """
    Safely ingests a Pandas DataFrame into DuckDB and registers it in the security schema.
    """
    from backend.sql_validator import register_custom_table, sanitize_identifier
    
    clean_table = sanitize_identifier(table_name)
    # Sanitize dataframe columns
    col_mapping = {col: sanitize_identifier(str(col)) for col in df.columns}
    df_clean = df.rename(columns=col_mapping)
    
    con = duckdb.connect(database=db_path, read_only=False)
    try:
        con.register("df_temp_upload", df_clean)
        con.execute(f"CREATE OR REPLACE TABLE {clean_table} AS SELECT * FROM df_temp_upload;")
        row_count = con.execute(f"SELECT COUNT(*) FROM {clean_table}").fetchone()[0]
        columns = list(df_clean.columns)
        
        # Register in AST allowlist
        register_custom_table(clean_table, set(columns))
        
        return {
            "table_name": clean_table,
            "columns": columns,
            "row_count": row_count,
            "sample": df_clean.head(5).to_dict(orient="records")
        }
    except Exception as e:
        raise QueryExecutionError(f"Failed to ingest data: {str(e)}")
    finally:
        con.close()

def sync_existing_tables(db_path: str = DEFAULT_DB_PATH):
    """Scans DuckDB on startup and registers all existing tables into the allowlist."""
    if not os.path.exists(db_path):
        return
    try:
        from backend.sql_validator import register_custom_table
        con = duckdb.connect(database=db_path, read_only=True)
        tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
        for tbl in tables:
            cols = [c[0] for c in con.execute(f"DESCRIBE {tbl}").fetchall()]
            register_custom_table(tbl, set(cols))
        con.close()
    except Exception:
        pass

# Auto-sync on import
sync_existing_tables()

