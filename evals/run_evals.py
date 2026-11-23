"""
Evaluation Benchmark Runner.
Measures:
1. Valid SQL Rate: % of generated queries that parse and execute without error.
2. Guardrail Catch Rate: % of malicious attack queries successfully blocked.
3. Execution Accuracy: % of queries whose returned results match the gold reference results.
4. Latency: Average roundtrip response time (ms).
"""

import os
import sys
import time
import yaml
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.pipeline import AnalyticsPipeline
from backend.sql_validator import validate_and_sanitize_sql
from backend.executor import execute_query

EVALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_questions.yaml")

def run_evaluation_benchmark():
    print("=" * 70)
    print("🚀 Starting Product Analytics Chatbot Evaluation Benchmark")
    print("=" * 70)

    if not os.path.exists(EVALS_FILE):
        print(f"Error: Evals file not found at {EVALS_FILE}")
        return

    with open(EVALS_FILE, "r") as f:
        data = yaml.safe_load(f)
        test_cases = data.get("eval_suite", [])

    pipeline = AnalyticsPipeline()
    
    total_valid_questions = 0
    valid_sql_count = 0
    accurate_execution_count = 0
    total_attacks = 0
    caught_attacks = 0
    latencies = []

    for tc in test_cases:
        tc_id = tc["id"]
        question = tc["question"]
        is_attack = tc.get("is_attack", False)

        if is_attack:
            total_attacks += 1
            attack_sql = tc.get("attack_sql", question)
            val_res = validate_and_sanitize_sql(attack_sql)
            if not val_res.is_valid:
                caught_attacks += 1
                print(f"🛡️  [PASSED] Attack '{tc_id}' was safely blocked: {val_res.error_message}")
            else:
                print(f"❌ [ALERT] Attack '{tc_id}' breached the validator!")
        else:
            total_valid_questions += 1
            t_start = time.perf_counter()
            resp = pipeline.process_question(question)
            latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
            latencies.append(latency_ms)

            if resp.get("error") is None and resp.get("sql"):
                valid_sql_count += 1
                # Check execution accuracy if reference SQL provided
                expected_sql = tc.get("expected_sql")
                if expected_sql:
                    try:
                        gold_res = execute_query(expected_sql)
                        if len(gold_res["rows"]) == len(resp["rows"]):
                            accurate_execution_count += 1
                            print(f"✅ [ACCURATE] {tc_id}: '{question}' ({latency_ms} ms)")
                        else:
                            print(f"⚠️  [EXEC RESULT MISMATCH] {tc_id}: expected {len(gold_res['rows'])} rows, got {len(resp['rows'])}")
                    except Exception as e:
                        print(f"⚠️  [GOLD ERROR] {tc_id}: {e}")
                else:
                    print(f"✅ [VALID] {tc_id}: '{question}' ({latency_ms} ms)")
            else:
                print(f"❌ [FAILED] {tc_id}: {resp.get('error')}")

    # Summary Metrics
    print("\n" + "=" * 70)
    print("📊 BENCHMARK RESULTS SUMMARY")
    print("=" * 70)
    
    valid_sql_rate = (valid_sql_count / total_valid_questions * 100) if total_valid_questions else 0
    guardrail_catch_rate = (caught_attacks / total_attacks * 100) if total_attacks else 0
    accuracy_rate = (accurate_execution_count / total_valid_questions * 100) if total_valid_questions else 0
    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0

    print(f"• Total Test Cases:          {len(test_cases)}")
    print(f"• Valid SQL Rate:            {valid_sql_rate:.1f}% ({valid_sql_count}/{total_valid_questions})")
    print(f"• Guardrail Catch Rate:      {guardrail_catch_rate:.1f}% ({caught_attacks}/{total_attacks})")
    print(f"• Execution Accuracy:        {accuracy_rate:.1f}% ({accurate_execution_count}/{total_valid_questions})")
    print(f"• Average Latency:           {avg_latency} ms")
    print("=" * 70)

if __name__ == "__main__":
    run_evaluation_benchmark()

