"""
Prompt Builder.
Constructs production-grade Text-to-SQL prompts incorporating:
1. System Role & DuckDB SQL instructions
2. Database Schema (tables, columns, types, sample values)
3. Semantic Layer (metric dictionary and time rules)
4. Security & syntax rules (SELECT only, LIMIT, no DDL/DML)
5. Few-shot examples
6. Session history (for follow-up questions)
7. Target question
"""

import os
from typing import Any, Dict, List, Optional
import yaml
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRICS_PATH = os.path.join(ROOT_DIR, "semantic_layer", "metrics.yaml")
EXAMPLES_PATH = os.path.join(ROOT_DIR, "semantic_layer", "examples.yaml")

SCHEMA_DOCUMENTATION = """
DATABASE SCHEMA (DuckDB SQL):

1. users (
    user_id VARCHAR PRIMARY KEY,           -- Unique identifier e.g. 'usr_1a2b3c4d'
    signup_date DATE,                      -- Date user created account e.g. '2026-01-15'
    country VARCHAR,                       -- Country e.g. 'United States', 'India', 'Germany', 'Canada'
    device VARCHAR,                        -- Signup device: 'Desktop', 'Mobile iOS', 'Mobile Android', 'Tablet'
    plan VARCHAR,                          -- Subscription plan: 'Free', 'Starter', 'Pro', 'Enterprise'
    acquisition_channel VARCHAR            -- Marketing source: 'Organic Search', 'Direct', 'Paid Search', 'Social Media', 'Referral', 'Email'
)

2. events (
    event_id VARCHAR PRIMARY KEY,          -- Unique event ID e.g. 'evt_00012345'
    user_id VARCHAR,                       -- References users.user_id
    event_type VARCHAR,                    -- Funnel steps: 'visit', 'signup', 'add_to_cart', 'checkout_start', 'purchase'
    event_timestamp TIMESTAMP,             -- Exact time event occurred e.g. '2026-02-10 14:22:15'
    feature_name VARCHAR,                  -- Page or feature accessed e.g. 'homepage', 'checkout_page', product name
    platform VARCHAR                       -- Client platform: 'web', 'ios', 'android'
)

3. orders (
    order_id VARCHAR PRIMARY KEY,          -- Unique order ID e.g. 'ord_0000123'
    user_id VARCHAR,                       -- References users.user_id
    order_date TIMESTAMP,                  -- Date and time of order
    amount DOUBLE,                         -- Monetary transaction value in USD e.g. 199.00
    product_id VARCHAR,                    -- References products.product_id
    status VARCHAR                         -- Status: 'completed', 'cancelled', 'refunded'
)

4. products (
    product_id VARCHAR PRIMARY KEY,        -- Product ID e.g. 'prod_001'
    name VARCHAR,                          -- Product name e.g. 'Enterprise Analytics Suite'
    category VARCHAR,                      -- Category e.g. 'Software', 'Security', 'DevOps'
    price DOUBLE                           -- List price in USD
)

5. sessions (
    session_id VARCHAR PRIMARY KEY,        -- Unique session identifier
    user_id VARCHAR,                       -- References users.user_id
    start_time TIMESTAMP,                  -- Session start time
    duration_seconds INTEGER,              -- Duration of session in seconds
    device VARCHAR                         -- Session device
)
"""

def load_semantic_layer() -> Dict[str, Any]:
    if os.path.exists(METRICS_PATH):
        with open(METRICS_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    return {}

def load_few_shot_examples() -> List[Dict[str, Any]]:
    if os.path.exists(EXAMPLES_PATH):
        with open(EXAMPLES_PATH, "r") as f:
            data = yaml.safe_load(f)
            return data.get("examples", []) if data else []
    return []

def build_sql_prompt(
    question: str,
    history: Optional[List[Dict[str, str]]] = None,
    current_date: Optional[str] = None
) -> str:
    """
    Assembles the complete system and user prompt for DuckDB SQL generation.
    """
    today_str = current_date or datetime.now().strftime("%Y-%m-%d")
    semantic_data = load_semantic_layer()
    examples = load_few_shot_examples()
    
    # Format metrics
    metrics_text = yaml.dump(semantic_data.get("metrics", {}), default_flow_style=False)
    time_rules_text = yaml.dump(semantic_data.get("time_rules", {}), default_flow_style=False)
    synonyms_text = yaml.dump(semantic_data.get("synonyms", {}), default_flow_style=False)

    # Format few-shot examples (select up to 6 most relevant)
    examples_str = ""
    for ex in examples[:6]:
        examples_str += f"Question: {ex['question']}\nSQL:\n```sql\n{ex['sql'].strip()}\n```\n\n"

    # Format history if available
    history_str = ""
    if history:
        history_str = "RECENT CONVERSATION HISTORY:\n"
        for turn in history[-3:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            history_str += f"{role.upper()}: {content}\n"
        history_str += "\n"

    prompt = f"""You are an expert Data & Product Analytics SQL Analyst specializing in DuckDB.
Your mission is to translate natural-language user questions into precise, highly efficient DuckDB SQL queries.

CURRENT SYSTEM DATE: {today_str}

{SCHEMA_DOCUMENTATION}

SEMANTIC LAYER (METRIC DEFINITIONS):
{metrics_text}

TIME RULES:
{time_rules_text}

BUSINESS SYNONYMS:
{synonyms_text}

MANDATORY RULES:
1. Return output strictly in valid JSON format:
   {{
     "sql": "<DuckDB SQL query>",
     "needs_clarification": false,
     "clarifying_question": null
   }}
2. Only write SELECT queries (or WITH ... SELECT). NEVER write INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, or PRAGMA.
3. Only use the 5 tables defined above (users, events, orders, products, sessions).
4. Always specify a LIMIT (e.g. LIMIT 1000) unless returning a single aggregated row.
5. In DuckDB, use standard syntax: `date_trunc('month', CURRENT_DATE)`, `CURRENT_DATE - INTERVAL '30 days'`, etc.
6. If the question is genuinely ambiguous, set "needs_clarification": true and provide a friendly "clarifying_question".
7. Do not include markdown commentary outside the JSON block.

VERIFIED FEW-SHOT EXAMPLES:
{examples_str}
{history_str}
USER QUESTION:
"{question}"

Generate the JSON response:"""

    return prompt
