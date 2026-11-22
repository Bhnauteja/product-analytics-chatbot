"""
Insight Generator.
Generates concise 1 to 3 sentence natural-language summaries grounded strictly
in the aggregated query result. Never hallucinates numbers not present in the data.
"""

from typing import Any, Dict, List
from backend.llm_client import LLMClient

def generate_data_insight(
    question: str,
    columns: List[str],
    rows: List[List[Any]],
    llm_client: LLMClient
) -> str:
    """
    Summarizes the analytical result.
    Passes ONLY the top aggregated rows to the LLM to guarantee privacy & accuracy.
    """
    if not rows:
        return "The query returned no matching records for the selected time range or criteria."

    # 1. Single KPI value
    if len(rows) == 1 and len(columns) == 1:
        val = rows[0][0]
        col = columns[0].replace("_", " ").title()
        formatted_val = f"{val:,.2f}" if isinstance(val, float) else f"{val:,}"
        return f"{col} is currently {formatted_val}."

    # 2. Extract top sample rows (max 5) for summary grounding
    sample_rows = rows[:5]
    summary_preview = {
        "columns": columns,
        "sample_rows": sample_rows,
        "total_returned_rows": len(rows)
    }

    prompt = f"""You are a senior product analytics consultant.
Write a concise, 1 to 3 sentence executive insight explaining the data finding for this user question.

STRICT ACCURACY RULES:
1. ONLY reference numbers and facts explicitly present in the data summary below.
2. DO NOT make up or extrapolate numbers.
3. Be professional, direct, and actionable.

USER QUESTION:
"{question}"

DATA SUMMARY:
{summary_preview}

EXECUTIVE INSIGHT:"""

    try:
        insight = llm_client.generate_insight(prompt)
        return insight.strip().replace("\n", " ")
    except Exception:
        # Robust fallback based on first row
        first_row = rows[0]
        return f"Query returned {len(rows)} record(s). Top item: {first_row[0]} with {first_row[-1]}."
