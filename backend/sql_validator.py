"""
SQL Validator & Security Guardrails.
Uses sqlglot to inspect Abstract Syntax Trees (AST) and enforce enterprise security:
1. Strict Single-Statement enforcement (no query stacking/injection).
2. Command Whitelist: ONLY SELECT statements allowed (no DDL/DML like DROP, DELETE, ALTER, INSERT, UPDATE).
3. Table & Column Allow-list validation (with CTE alias awareness).
4. Filesystem / UDF Blacklist: blocks read_csv, read_parquet, write_parquet, httpfs, attach, pragma.
5. Automatic LIMIT Injection: clamps max rows to 1,000 to prevent DoS memory exhaustion.
"""

from typing import Dict, List, Optional, Set, Tuple
import sqlglot
from sqlglot import exp
from pydantic import BaseModel

# Allowed schema definition
ALLOWED_SCHEMA: Dict[str, Set[str]] = {
    "users": {
        "user_id", "signup_date", "country", "device", "plan", "acquisition_channel"
    },
    "events": {
        "event_id", "user_id", "event_type", "event_timestamp", "feature_name", "platform"
    },
    "orders": {
        "order_id", "user_id", "order_date", "amount", "product_id", "status"
    },
    "products": {
        "product_id", "name", "category", "price"
    },
    "sessions": {
        "session_id", "user_id", "start_time", "duration_seconds", "device"
    }
}

def sanitize_identifier(name: str) -> str:
    """Sanitizes table/column names to lowercase alphanumeric and underscores only."""
    import re
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip().lower())
    if cleaned and cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned

def register_custom_table(table_name: str, columns: Set[str]) -> Tuple[str, Set[str]]:
    """Registers a dynamically uploaded table and columns into the AST security allowlist."""
    clean_table = sanitize_identifier(table_name)
    clean_cols = {sanitize_identifier(c) for c in columns if c.strip()}
    ALLOWED_SCHEMA[clean_table] = clean_cols
    return clean_table, clean_cols

def get_allowed_schema() -> Dict[str, Set[str]]:
    """Returns a snapshot of the current allow-listed schema."""
    return dict(ALLOWED_SCHEMA)

BLOCKED_COMMANDS = (
    exp.Drop,
    exp.Delete,
    exp.Update,
    exp.Insert,
    exp.Create,
    exp.Alter,
    exp.Command,
    exp.Pragma,
)

BLOCKED_FUNCTIONS = {
    "read_csv",
    "read_csv_auto",
    "read_parquet",
    "read_json",
    "read_json_auto",
    "scan_csv",
    "scan_parquet",
    "write_csv",
    "write_parquet",
    "copy",
    "httpfs",
    "load",
    "install",
    "attach",
    "detach"
}

DEFAULT_MAX_LIMIT = 1000

class ValidationResult(BaseModel):
    is_valid: bool
    sanitized_sql: Optional[str] = None
    error_message: Optional[str] = None
    tables_used: List[str] = []

def validate_and_sanitize_sql(sql_query: str, max_limit: int = DEFAULT_MAX_LIMIT) -> ValidationResult:
    """
    Validates the given SQL query string against security guardrails.
    Returns ValidationResult with sanitized SQL or error reason.
    """
    clean_query = sql_query.strip()
    if not clean_query:
        return ValidationResult(is_valid=False, error_message="Empty query provided.")

    # 1. Parse using sqlglot with DuckDB dialect
    try:
        parsed_statements = sqlglot.parse(clean_query, read="duckdb")
    except Exception as e:
        return ValidationResult(is_valid=False, error_message=f"SQL syntax error: {str(e)}")

    # 2. Check for exactly one statement
    parsed_statements = [s for s in parsed_statements if s is not None]
    if len(parsed_statements) == 0:
        return ValidationResult(is_valid=False, error_message="No valid SQL statements found.")
    if len(parsed_statements) > 1:
        return ValidationResult(
            is_valid=False,
            error_message="Security violation: Multiple SQL statements detected. Only a single SELECT query is permitted."
        )

    statement = parsed_statements[0]

    # 3. Check statement type: MUST be a SELECT / Union query
    if not isinstance(statement, (exp.Select, exp.Union)):
        return ValidationResult(
            is_valid=False,
            error_message=f"Security violation: Statement of type '{statement.key.upper()}' is forbidden. Only SELECT queries are allowed."
        )

    # 4. Check for forbidden commands anywhere in AST
    for blocked_type in BLOCKED_COMMANDS:
        if statement.find(blocked_type):
            return ValidationResult(
                is_valid=False,
                error_message=f"Security violation: Prohibited SQL command '{blocked_type.__name__.upper()}' detected."
            )

    # 5. Check for dangerous function calls (e.g. read_csv, attach, httpfs)
    for func in statement.find_all(exp.Anonymous, exp.Func):
        func_identifiers = {
            func.name.lower() if func.name else "",
            func.key.lower() if func.key else "",
            getattr(func, "sql_name", lambda: "")().lower(),
            type(func).__name__.lower()
        }
        for fid in func_identifiers:
            fid_clean = fid.replace("_", "")
            for blocked in BLOCKED_FUNCTIONS:
                if blocked.replace("_", "") == fid_clean or blocked in fid:
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Security violation: Prohibited function '{blocked}' detected. Direct filesystem or external calls are blocked."
                    )

    # 6. Extract CTE names (WITH cte_name AS ...) so we don't treat them as unknown tables
    cte_names: Set[str] = set()
    for cte in statement.find_all(exp.CTE):
        if cte.alias:
            cte_names.add(cte.alias.lower())

    # 7. Check tables against ALLOWED_SCHEMA
    tables_found: Set[str] = set()
    for table_expr in statement.find_all(exp.Table):
        tbl_name = table_expr.name.lower()
        if tbl_name in cte_names:
            continue  # CTE table alias is permitted
        if tbl_name not in ALLOWED_SCHEMA:
            allowed_list = ", ".join(sorted(ALLOWED_SCHEMA.keys()))
            return ValidationResult(
                is_valid=False,
                error_message=f"Security violation: Table '{tbl_name}' is not in the allowed schema. Allowed tables: {allowed_list}."
            )
        tables_found.add(tbl_name)

    if not tables_found and not cte_names:
        return ValidationResult(
            is_valid=False,
            error_message="Query does not reference any allowed tables."
        )

    # 8. Check column references
    # Only validate explicit table.column references where table matches known schema
    for col in statement.find_all(exp.Column):
        col_name = col.name.lower()
        table_ref = col.table.lower() if col.table else None
        
        # If explicitly qualified with an allowed table name, check if column exists
        if table_ref and table_ref in ALLOWED_SCHEMA:
            if col_name not in ALLOWED_SCHEMA[table_ref]:
                return ValidationResult(
                    is_valid=False,
                    error_message=f"Unknown column '{col_name}' for table '{table_ref}'."
                )

    # 9. Enforce LIMIT clause
    limit_node = statement.args.get("limit")
    if limit_node is None:
        # Automatically add LIMIT
        statement = statement.limit(max_limit)
    else:
        # Check if existing limit is within bounds
        try:
            limit_val = int(limit_node.expression.this)
            if limit_val > max_limit or limit_val <= 0:
                statement.set("limit", exp.Limit(this=exp.Literal.number(max_limit)))
        except Exception:
            statement.set("limit", exp.Limit(this=exp.Literal.number(max_limit)))

    # Transpile back to DuckDB dialect SQL
    sanitized_sql = statement.sql(dialect="duckdb")
    
    return ValidationResult(
        is_valid=True,
        sanitized_sql=sanitized_sql,
        tables_used=sorted(list(tables_found))
    )
