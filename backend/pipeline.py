"""
Pipeline Orchestrator.
Orchestrates the entire Natural-Language to Analytics flow:
1. Prompt Assembly
2. LLM Text-to-SQL Generation
3. AST SQL Validation & Sanitization (sqlglot)
4. Self-repair loop (re-prompt LLM on SQL error, max 2 retries)
5. Read-only DuckDB Execution
6. Deterministic Chart Selection
7. Grounded Insight Generation
8. Security Audit Logging
"""

import time
import uuid
from typing import Any, Dict, List, Optional
from backend.prompt_builder import build_sql_prompt, SCHEMA_DOCUMENTATION
from backend.llm_client import LLMClient
from backend.sql_validator import validate_and_sanitize_sql
from backend.executor import execute_query, QueryExecutionError
from backend.chart_selector import select_chart
from backend.insight import generate_data_insight
from backend.logger import log_query_event

MAX_SELF_REPAIR_RETRIES = 2

class AnalyticsPipeline:
    def __init__(self, llm_provider: Optional[str] = None):
        self.llm_client = LLMClient(provider=llm_provider)

    def process_question(
        self,
        question: str,
        session_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Processes a natural language query end-to-end.
        """
        start_time = time.perf_counter()
        answer_id = f"ans_{uuid.uuid4().hex[:8]}"
        session_id = session_id or f"sess_{uuid.uuid4().hex[:8]}"

        # 1. Build Prompt & Call LLM
        prompt = build_sql_prompt(question, history=history)
        
        llm_response = self.llm_client.generate_sql(prompt)
        
        # Check if the LLM requested clarification
        if llm_response.get("needs_clarification"):
            clarifying_q = llm_response.get("clarifying_question") or "Could you clarify what metric or time range you'd like to analyze?"
            return {
                "answer_id": answer_id,
                "session_id": session_id,
                "question": question,
                "needs_clarification": True,
                "clarifying_question": clarifying_q,
                "insight": clarifying_q,
                "sql": None,
                "columns": [],
                "rows": [],
                "chart": {"type": "clarification", "spec": {}},
                "latency_ms": round((time.perf_counter() - start_time) * 1000, 2),
                "error": None
            }

        candidate_sql = llm_response.get("sql", "").strip()
        
        # 2. Validate SQL with sqlglot AST Guardrails & Attempt Execution with Self-Repair Loop
        retries = 0
        last_error = ""
        validated_sql = ""
        exec_result: Optional[Dict[str, Any]] = None

        while retries <= MAX_SELF_REPAIR_RETRIES:
            # Step A: Validate SQL AST
            validation = validate_and_sanitize_sql(candidate_sql)
            if not validation.is_valid:
                last_error = f"Guardrail Validation Failed: {validation.error_message}"
                if retries < MAX_SELF_REPAIR_RETRIES:
                    # Self-repair prompt to LLM
                    repair_prompt = f"""The previous DuckDB SQL generated for the question was invalid or failed security checks.
Question: "{question}"
Failed SQL:
{candidate_sql}
Error:
{last_error}

Fix the query. Follow all rules: ONLY single SELECT, only allowed tables/columns, add LIMIT.
Return JSON: {{"sql": "<corrected SQL>", "needs_clarification": false}}"""
                    try:
                        repair_res = self.llm_client.generate_sql(repair_prompt)
                        candidate_sql = repair_res.get("sql", "").strip()
                        retries += 1
                        continue
                    except Exception:
                        break
                else:
                    break
            
            validated_sql = validation.sanitized_sql
            
            # Step B: Execute query against DuckDB (read-only mode)
            try:
                exec_result = execute_query(validated_sql)
                # Success! Break out of repair loop
                break
            except QueryExecutionError as qe:
                last_error = str(qe)
                if retries < MAX_SELF_REPAIR_RETRIES:
                    repair_prompt = f"""The query failed during execution against the database.
Question: "{question}"
Failed SQL:
{validated_sql}
Execution Error:
{last_error}

Please correct the column names or SQL syntax. Return JSON: {{"sql": "<corrected SQL>", "needs_clarification": false}}"""
                    try:
                        repair_res = self.llm_client.generate_sql(repair_prompt)
                        candidate_sql = repair_res.get("sql", "").strip()
                        retries += 1
                        continue
                    except Exception:
                        break
                else:
                    break

        total_latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Handle failure if execution was unsuccessful
        if exec_result is None:
            friendly_error = "I couldn't run this query safely. " + last_error
            log_query_event({
                "answer_id": answer_id,
                "session_id": session_id,
                "question": question,
                "sql": candidate_sql,
                "validation_passed": False,
                "validation_error": last_error,
                "total_latency_ms": total_latency_ms,
                "row_count": 0
            })
            return {
                "answer_id": answer_id,
                "session_id": session_id,
                "question": question,
                "insight": friendly_error,
                "sql": candidate_sql,
                "columns": [],
                "rows": [],
                "chart": {"type": "error", "spec": {}},
                "latency_ms": total_latency_ms,
                "error": friendly_error
            }

        # 3. Chart Selection
        chart_spec = select_chart(
            columns=exec_result["columns"],
            rows=exec_result["rows"],
            question_hint=question
        )

        # 4. Insight Generation
        insight_text = generate_data_insight(
            question=question,
            columns=exec_result["columns"],
            rows=exec_result["rows"],
            llm_client=self.llm_client
        )

        # 5. Security Audit Logging
        log_query_event({
            "answer_id": answer_id,
            "session_id": session_id,
            "question": question,
            "sql": validated_sql,
            "validation_passed": True,
            "validation_error": None,
            "execution_time_ms": exec_result.get("execution_time_ms", 0.0),
            "total_latency_ms": total_latency_ms,
            "row_count": exec_result.get("row_count", 0),
            "chart_type": chart_spec.get("type", "table")
        })

        return {
            "answer_id": answer_id,
            "session_id": session_id,
            "question": question,
            "insight": insight_text,
            "sql": validated_sql,
            "columns": exec_result["columns"],
            "rows": exec_result["rows"],
            "chart": chart_spec,
            "latency_ms": total_latency_ms,
            "error": None
        }

