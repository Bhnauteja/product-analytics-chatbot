"""
Security Audit & Query Logger.
Logs every question, sanitized SQL, execution latency, validation status, and user feedback
into an append-only JSONL file and SQLite database for auditability and compliance.
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, Optional

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
AUDIT_DB = os.path.join(LOG_DIR, "audit.db")

def init_audit_db():
    conn = sqlite3.connect(AUDIT_DB)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS query_audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            answer_id TEXT NOT NULL,
            session_id TEXT,
            timestamp TEXT NOT NULL,
            question TEXT NOT NULL,
            sql_generated TEXT,
            validation_passed INTEGER,
            validation_error TEXT,
            execution_time_ms REAL,
            total_latency_ms REAL,
            row_count INTEGER,
            chart_type TEXT,
            feedback TEXT
        );
    """)
    conn.commit()
    conn.close()

init_audit_db()

def log_query_event(event_data: Dict[str, Any]):
    """
    Persists an audit log event.
    """
    event_data["timestamp"] = datetime.now().isoformat()
    
    # 1. Append to audit JSONL file
    jsonl_path = os.path.join(LOG_DIR, "audit_events.jsonl")
    try:
        with open(jsonl_path, "a") as f:
            f.write(json.dumps(event_data) + "\n")
    except Exception as e:
        print(f"Error writing to audit JSONL: {e}")

    # 2. Insert into SQLite audit database
    try:
        conn = sqlite3.connect(AUDIT_DB)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO query_audit_logs (
                answer_id, session_id, timestamp, question, sql_generated,
                validation_passed, validation_error, execution_time_ms,
                total_latency_ms, row_count, chart_type, feedback
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event_data.get("answer_id", ""),
            event_data.get("session_id", ""),
            event_data["timestamp"],
            event_data.get("question", ""),
            event_data.get("sql", ""),
            1 if event_data.get("validation_passed") else 0,
            event_data.get("validation_error"),
            event_data.get("execution_time_ms", 0.0),
            event_data.get("total_latency_ms", 0.0),
            event_data.get("row_count", 0),
            event_data.get("chart_type", ""),
            event_data.get("feedback")
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error writing to SQLite audit: {e}")

def update_feedback(answer_id: str, feedback: str, notes: Optional[str] = None):
    try:
        conn = sqlite3.connect(AUDIT_DB)
        cursor = conn.cursor()
        cursor.execute("UPDATE query_audit_logs SET feedback = ? WHERE answer_id = ?", (feedback, answer_id))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error updating audit feedback: {e}")
