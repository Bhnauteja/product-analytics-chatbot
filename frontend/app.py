"""
Product Analytics Chatbot - Streamlit Frontend.
Provides an interactive, high-polish analytics chat experience:
- Left Sidebar: Database schema inspector & security guardrail status
- Main Area: Conversational chat stream with KPI cards, Plotly charts, data tables
- Collapsible "View SQL" drawer for full transparency
- Clickable suggested question chips
- Download CSV and user feedback controls
"""

import os
import sys
import time
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.pipeline import AnalyticsPipeline
from backend.sql_validator import get_allowed_schema
from backend.executor import ingest_dataframe_to_duckdb
from backend.logger import update_feedback

st.set_page_config(
    page_title="Product Analytics Chatbot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .kpi-container {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border-radius: 12px;
        padding: 24px;
        color: white;
        border: 1px solid #334155;
        margin-bottom: 16px;
    }
    .kpi-value {
        font-size: 2.6rem;
        font-weight: 800;
        color: #38BDF8;
        line-height: 1.1;
    }
    .kpi-label {
        font-size: 0.95rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 4px;
    }
    .security-badge {
        display: inline-block;
        background-color: #064E3B;
        color: #34D399;
        font-size: 0.75rem;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 9999px;
        margin-bottom: 8px;
    }
    .insight-card {
        background-color: #F8FAFC;
        border-left: 4px solid #3B82F6;
        padding: 14px 18px;
        border-radius: 6px;
        margin-bottom: 14px;
        font-size: 1.05rem;
        color: #0F172A;
        line-height: 1.5;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "session_id" not in st.session_state:
    st.session_state.session_id = f"sess_{int(time.time())}"
if "pipeline" not in st.session_state:
    st.session_state.pipeline = AnalyticsPipeline()

# --- SIDEBAR ---
with st.sidebar:
    st.title("🛡️ Secure Analytics")
    st.caption("AI-powered natural language queries with enterprise-grade guardrails")
    
    st.markdown('<span class="security-badge">● 100% Read-Only Protected</span>', unsafe_allow_html=True)
    st.markdown('<span class="security-badge" style="background-color:#1E3A8A;color:#93C5FD;">● AST SQL Validator Active</span>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("📤 Ingest Custom Data (CSV / Kaggle)")
    st.caption("Upload your own CSV or test with a Kaggle dataset:")
    
    # Kaggle one-click sample loader
    kaggle_csv_path = os.path.join(PROJECT_ROOT, "data", "sample_kaggle", "superstore_kaggle_sample.csv")
    if os.path.exists(kaggle_csv_path):
        if st.button("⚡ Load Kaggle Superstore Sample", use_container_width=True):
            k_df = pd.read_csv(kaggle_csv_path)
            res = ingest_dataframe_to_duckdb(k_df, "superstore_kaggle_sample")
            st.session_state.custom_loaded = "superstore_kaggle_sample"
            st.toast(f"Loaded Kaggle Superstore ({res['row_count']} rows)!", icon="📊")
            st.rerun()

    # Generic CSV Uploader
    uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])
    if uploaded_file is not None:
        file_key = f"uploaded_{uploaded_file.name}"
        if file_key not in st.session_state:
            try:
                up_df = pd.read_csv(uploaded_file)
                base_name = uploaded_file.name.rsplit(".", 1)[0]
                res = ingest_dataframe_to_duckdb(up_df, base_name)
                st.session_state[file_key] = True
                st.session_state.custom_loaded = res["table_name"]
                st.success(f"Ingested '{res['table_name']}' ({res['row_count']:,} rows)")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to ingest CSV: {e}")

    st.markdown("---")
    st.subheader("📚 Available Data Schema")
    current_schema = get_allowed_schema()
    for tbl_name, cols in sorted(current_schema.items()):
        badge = " [Custom]" if tbl_name not in ["users", "events", "orders", "products", "sessions"] else ""
        with st.expander(f"📁 {tbl_name}{badge} ({len(cols)} cols)"):
            for col in sorted(list(cols)):
                st.code(col, language="text")

    st.markdown("---")
    st.subheader("🔒 Security Protections")
    st.markdown("""
    - **Zero Raw Data to LLM**: Only schema & aggregated metrics are sent.
    - **AST SQL Whitelist**: Only single `SELECT` allowed. Blocks `DROP`, `DELETE`, `ALTER`, `INSERT`.
    - **Kernel Read-Only**: Enforced in DuckDB.
    - **Mandatory LIMIT**: Clamped to 1,000 rows.
    """)
    
    if st.button("🗑️ Clear Chat History", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --- MAIN SCREEN ---
st.title("📊 Product Analytics Chatbot")
st.markdown("Ask any question about your product metrics, users, funnels, or revenue in plain English.")

# Suggested Questions Row
base_suggestions = [
    "Show weekly signups for the last 3 months",
    "Top 5 countries by signups last month",
    "Where do users drop off in checkout?",
    "Compare mobile vs desktop conversion",
    "Top 10 products by revenue",
    "Total revenue from completed orders"
]

if "superstore_kaggle_sample" in current_schema:
    suggested_questions = [
        "Top categories by sales in Superstore",
        "Total profit by region in Superstore",
        "Sales by segment in Superstore"
    ] + base_suggestions[:3]
else:
    suggested_questions = base_suggestions

st.markdown("##### 💡 Suggested Questions")
cols = st.columns(3)
clicked_question = None
for i, q in enumerate(suggested_questions):
    col_idx = i % 3
    if cols[col_idx].button(f"👉 {q}", key=f"sugg_{i}", use_container_width=True):
        clicked_question = q

# Render Chat History
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(f"**{msg['content']}**")
        else:
            # Assistant Response Card
            res = msg["data"]
            
            # Insight Box
            if res.get("insight"):
                st.markdown(f"""<div class="insight-card">💡 {res['insight']}</div>""", unsafe_allow_html=True)
                
            # Chart or Table Visualization
            chart_info = res.get("chart", {})
            chart_type = chart_info.get("type")
            chart_spec = chart_info.get("spec", {})
            columns = res.get("columns", [])
            rows = res.get("rows", [])
            
            if chart_type == "kpi":
                val = chart_spec.get("formatted", chart_spec.get("value"))
                lbl = chart_spec.get("label", "Metric")
                st.markdown(f"""
                <div class="kpi-container">
                    <div class="kpi-value">{val}</div>
                    <div class="kpi-label">{lbl}</div>
                </div>
                """, unsafe_allow_html=True)
            elif chart_type in ["line", "bar", "pie", "stacked_bar"] and "data" in chart_spec:
                fig = go.Figure(data=chart_spec.get("data", []), layout=chart_spec.get("layout", {}))
                fig.update_layout(height=380, margin=dict(l=30, r=30, t=30, b=30))
                st.plotly_chart(fig, use_container_width=True)
            elif columns and rows:
                df = pd.DataFrame(rows, columns=columns)
                st.dataframe(df, use_container_width=True)

            # View SQL Accordion
            if res.get("sql"):
                with st.expander("🔍 View Generated SQL (Verified & Read-Only)"):
                    st.code(res["sql"], language="sql")
                    latency = res.get("latency_ms", 0)
                    st.caption(f"⚡ Execution latency: {latency} ms | Rows returned: {len(rows)}")

            # Actions: Download CSV & Feedback
            if columns and rows:
                df = pd.DataFrame(rows, columns=columns)
                csv_bytes = df.to_csv(index=False).encode("utf-8")
                act_cols = st.columns([2, 1, 1, 6])
                act_cols[0].download_button(
                    label="📥 Download CSV",
                    data=csv_bytes,
                    file_name=f"analytics_{res.get('answer_id', 'export')}.csv",
                    mime="text/csv",
                    key=f"dl_{idx}"
                )
                if act_cols[1].button("👍", key=f"up_{idx}"):
                    update_feedback(res.get("answer_id", ""), "thumbs_up")
                    st.toast("Thank you for your feedback!", icon="👍")
                if act_cols[2].button("👎", key=f"down_{idx}"):
                    update_feedback(res.get("answer_id", ""), "thumbs_down")
                    st.toast("Feedback recorded.", icon="👎")

# Handle New User Input
user_query = st.chat_input("Ask a question about user retention, signups, drop-off, revenue...") or clicked_question

if user_query:
    # Append User Message
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(f"**{user_query}**")

    # Generate Response
    with st.chat_message("assistant"):
        status_box = st.status("Analyzing question with LLM and AST guardrails...", expanded=True)
        try:
            status_box.write("1. Assembling schema context and metric dictionary...")
            status_box.write("2. Generating DuckDB SQL...")
            status_box.write("3. Inspecting SQL syntax tree with sqlglot guardrails...")
            status_box.write("4. Executing on read-only analytical database...")
            
            history_tuples = [
                {"role": m["role"], "content": m["content"] if m["role"] == "user" else m["data"].get("insight", "")}
                for m in st.session_state.messages[:-1]
            ]
            
            response = st.session_state.pipeline.process_question(
                question=user_query,
                session_id=st.session_state.session_id,
                history=history_tuples
            )
            
            status_box.update(label="Complete! Visualizing analytics.", state="complete", expanded=False)
            
            # Store in message history and rerun to render cleanly
            st.session_state.messages.append({"role": "assistant", "data": response})
            st.rerun()
        except Exception as e:
            status_box.update(label="Error processing query", state="error", expanded=True)
            st.error(f"Failed to process query: {str(e)}")

