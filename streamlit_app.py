import streamlit as st
import pandas as pd
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import plotly.graph_objects as go
from app.graph.workflow import run_workflow, stream_workflow
from app.db.connection import build_engine, test_connection, ensure_demo_database, get_demo_db_path
from app.db.seed_demo import seed_database
from app.observability import new_run_id, log_run


st.set_page_config(
    page_title="Agentic Data Analyst",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    code, pre, div[data-testid="stCode"] * {
        font-family: 'JetBrains Mono', monospace !important;
    }

    .stApp {
        background: #090d16;
        color: #e2e8f0;
    }

    section[data-testid="stSidebar"] {
        background: #0d131f;
        border-right: 1px solid #1a2333;
        padding-top: 1rem;
    }

    section[data-testid="stSidebar"] .block-container {
        padding: 1.25rem 1rem;
    }

    .sidebar-header {
        padding: 0 0 1rem 0;
        border-bottom: 1px solid #1a2333;
        margin-bottom: 1.25rem;
    }

    .sidebar-header .brand-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f8fafc;
        letter-spacing: -0.01em;
        margin: 0;
    }

    .sidebar-header .brand-subtitle {
        font-size: 0.75rem;
        color: #64748b;
        margin: 0.2rem 0 0 0;
        font-weight: 400;
    }

    .sidebar-label {
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: #94a3b8;
        margin: 1.25rem 0 0.5rem 0;
    }

    .status-badge {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.78rem;
        font-weight: 500;
        padding: 6px 12px;
        border-radius: 6px;
        margin: 0.75rem 0;
    }

    .status-badge.online {
        background: rgba(16, 185, 129, 0.1);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.25);
    }

    .status-badge.offline {
        background: rgba(244, 63, 94, 0.1);
        color: #fb7185;
        border: 1px solid rgba(244, 63, 94, 0.25);
    }

    .status-dot {
        width: 7px;
        height: 7px;
        border-radius: 50%;
        display: inline-block;
    }

    .status-badge.online .status-dot {
        background: #10b981;
        box-shadow: 0 0 8px #10b981;
    }

    .status-badge.offline .status-dot {
        background: #f43f5e;
    }

    .stTextInput input, .stNumberInput input {
        background: #131b2a !important;
        border: 1px solid #1f2a3f !important;
        border-radius: 6px !important;
        color: #f1f5f9 !important;
        font-size: 0.85rem !important;
        padding: 8px 12px !important;
    }

    .stTextInput input:focus, .stNumberInput input:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2) !important;
    }

    .stButton button {
        border-radius: 6px !important;
        font-weight: 600 !important;
        font-size: 0.85rem !important;
        padding: 8px 16px !important;
        transition: all 0.15s ease !important;
        border: 1px solid transparent !important;
    }

    .sidebar-btn button {
        background: #1e293b !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
        width: 100% !important;
    }

    .sidebar-btn button:hover {
        background: #273549 !important;
        border-color: #475569 !important;
    }

    .main-header {
        padding: 2rem 0 1.5rem 0;
        border-bottom: 1px solid #161f30;
        margin-bottom: 2rem;
    }

    .main-header h1 {
        font-size: 1.85rem;
        font-weight: 700;
        color: #f8fafc;
        margin: 0;
        letter-spacing: -0.02em;
    }

    .main-header p {
        color: #64748b;
        font-size: 0.92rem;
        margin: 0.35rem 0 0 0;
    }

    .stTextArea textarea {
        background: #0f1726 !important;
        border: 1px solid #1e293b !important;
        border-radius: 8px !important;
        color: #f8fafc !important;
        font-size: 0.95rem !important;
        padding: 14px !important;
        line-height: 1.5 !important;
    }

    .stTextArea textarea:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15) !important;
    }

    .primary-btn button {
        background: #2563eb !important;
        color: #ffffff !important;
        border: 1px solid #3b82f6 !important;
        font-size: 0.92rem !important;
        padding: 10px 20px !important;
        width: 100% !important;
    }

    .primary-btn button:hover {
        background: #1d4ed8 !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25) !important;
    }

    .card {
        background: #0d131f;
        border: 1px solid #1a2333;
        border-radius: 8px;
        padding: 1.5rem 1.75rem;
        margin-bottom: 1.25rem;
    }

    .card-title {
        font-size: 0.72rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #64748b;
        margin-bottom: 1rem;
        border-bottom: 1px solid #141c2c;
        padding-bottom: 0.5rem;
    }

    .answer-container h3 {
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        color: #f8fafc !important;
        margin-top: 1.25rem !important;
        margin-bottom: 0.6rem !important;
        letter-spacing: -0.01em !important;
    }

    .answer-container h3:first-child {
        margin-top: 0 !important;
    }

    .answer-container p {
        font-size: 0.92rem !important;
        line-height: 1.75 !important;
        color: #cbd5e1 !important;
        margin-bottom: 1rem !important;
    }

    .answer-container ul, .answer-container ol {
        margin-top: 0.4rem !important;
        margin-bottom: 1.1rem !important;
        padding-left: 1.3rem !important;
    }

    .answer-container li {
        font-size: 0.9rem !important;
        line-height: 1.7 !important;
        color: #cbd5e1 !important;
        margin-bottom: 0.55rem !important;
    }

    .answer-container strong {
        color: #f1f5f9 !important;
        font-weight: 600 !important;
    }

    .answer-container code {
        background: #151d2d !important;
        color: #38bdf8 !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-size: 0.84rem !important;
    }

    .meta-item {
        background: #131b2a;
        border: 1px solid #1a2333;
        border-radius: 6px;
        padding: 8px 12px;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .meta-item-label {
        font-size: 0.75rem;
        color: #64748b;
        font-weight: 500;
    }

    .meta-item-val {
        font-size: 0.82rem;
        color: #f1f5f9;
        font-weight: 600;
        font-family: 'JetBrains Mono', monospace;
    }

    .plan-step {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        font-size: 0.82rem;
        color: #94a3b8;
        padding: 6px 0;
        border-bottom: 1px solid #141b29;
    }

    .plan-step:last-child {
        border-bottom: none;
    }

    .step-num {
        font-size: 0.7rem;
        font-weight: 700;
        color: #3b82f6;
        background: rgba(59, 130, 246, 0.1);
        padding: 2px 6px;
        border-radius: 4px;
        min-width: 18px;
        text-align: center;
    }

    .trace-item {
        font-size: 0.82rem;
        color: #64748b;
        padding: 4px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .trace-item.active {
        color: #38bdf8;
    }

    .sample-btn button {
        background: #101623 !important;
        border: 1px solid #1e293b !important;
        color: #94a3b8 !important;
        font-size: 0.78rem !important;
        font-weight: 500 !important;
        padding: 6px 12px !important;
        text-align: left !important;
        width: 100% !important;
        border-radius: 6px !important;
    }

    .sample-btn button:hover {
        border-color: #3b82f6 !important;
        color: #f8fafc !important;
        background: #141d2e !important;
    }

    div[data-testid="stExpander"] {
        background: #0d131f;
        border: 1px solid #1a2333;
        border-radius: 8px;
    }

    div[data-testid="stCode"] {
        background: #070a10 !important;
        border: 1px solid #1a2333 !important;
        border-radius: 6px !important;
    }
</style>
""", unsafe_allow_html=True)


if "connected" not in st.session_state:
    st.session_state.connected = False
if "db_config" not in st.session_state:
    st.session_state.db_config = {}
if "groq_api_key" not in st.session_state:
    st.session_state.groq_api_key = ""
if "groq_model" not in st.session_state:
    st.session_state.groq_model = "openai/gpt-oss-120b"
if "history" not in st.session_state:
    st.session_state.history = []
if "question_input" not in st.session_state:
    st.session_state.question_input = ""


with st.sidebar:
    st.markdown("""
    <div class="sidebar-header">
        <div class="brand-title">Agentic Data Analyst</div>
        <div class="brand-subtitle">Natural Language Analytics Engine</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="sidebar-label">LLM Provider</div>', unsafe_allow_html=True)
    groq_key = st.text_input(
        "Groq API Key",
        type="password",
        value=st.session_state.groq_api_key,
        placeholder="Enter Groq API Key...",
        key="groq_key_input",
    )
    if groq_key:
        st.session_state.groq_api_key = groq_key

    groq_model_input = st.text_input(
        "Model Name",
        value=st.session_state.groq_model,
        placeholder="openai/gpt-oss-120b",
        key="groq_model_input",
    )
    if groq_model_input:
        st.session_state.groq_model = groq_model_input.strip()

    st.markdown('<div class="sidebar-label">Database Source</div>', unsafe_allow_html=True)
    db_source = st.radio(
        "Database Source Mode",
        ["Demo SQLite (Zero-Setup)", "External Database (MySQL / Postgres)"],
        label_visibility="collapsed",
        key="db_source_radio",
    )

    if db_source == "Demo SQLite (Zero-Setup)":
        st.caption("Instant in-project SQLite database with 140 orders, 28 products, and 30 customers.")
        if st.button("Connect Demo Database", key="connect_demo_btn", use_container_width=True):
            try:
                with st.spinner("Initializing demo database..."):
                    engine = ensure_demo_database()
                    ok, err_msg = test_connection(engine)
                if ok:
                    st.session_state.connected = True
                    st.session_state.db_config = {
                        "dialect": "sqlite",
                        "host": "sqlite",
                        "database": str(get_demo_db_path()),
                    }
                else:
                    st.session_state.connected = False
                    st.error(f"Demo connection failed: {err_msg}")
            except Exception as e:
                st.session_state.connected = False
                st.error(f"Error: {str(e)}")

    else:
        dialect_choice = st.selectbox("Engine Dialect", ["MySQL", "PostgreSQL", "SQLite"], index=0, key="dialect_select")
        dialect_key = dialect_choice.lower()

        if dialect_key == "sqlite":
            sqlite_path = st.text_input("SQLite File Path", value=str(get_demo_db_path()), key="custom_sqlite_path")
            if st.button("Connect SQLite", key="connect_custom_sqlite", use_container_width=True):
                engine = build_engine(database=sqlite_path, dialect="sqlite")
                ok, err = test_connection(engine)
                if ok:
                    st.session_state.connected = True
                    st.session_state.db_config = {"dialect": "sqlite", "host": "sqlite", "database": sqlite_path}
                else:
                    st.error(f"Connection failed: {err}")
        else:
            default_port = 5432 if dialect_key == "postgresql" else 3306
            db_host = st.text_input("Host", value="localhost", placeholder="localhost", key="ext_db_host")
            col_port, col_db = st.columns([1, 2])
            with col_port:
                db_port = st.number_input("Port", value=default_port, min_value=1, max_value=65535, key="ext_db_port")
            with col_db:
                db_name = st.text_input("Database", placeholder="db_name", key="ext_db_name")

            db_user = st.text_input("Username", placeholder="username", key="ext_db_user")
            db_password = st.text_input("Password", type="password", placeholder="password", key="ext_db_password")

            st.markdown('<div class="sidebar-btn">', unsafe_allow_html=True)
            connect_btn = st.button("Connect Database", key="connect_btn", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

            if connect_btn:
                if not all([db_host, db_name, db_user]):
                    st.error("Host, Database, and Username are required.")
                else:
                    try:
                        with st.spinner("Connecting..."):
                            engine = build_engine(
                                host=db_host,
                                port=int(db_port),
                                user=db_user,
                                password=db_password,
                                database=db_name,
                                dialect=dialect_key,
                            )
                            ok, err_msg = test_connection(engine)
                        if ok:
                            st.session_state.connected = True
                            st.session_state.db_config = {
                                "dialect": dialect_key,
                                "host": db_host,
                                "port": int(db_port),
                                "user": db_user,
                                "password": db_password,
                                "database": db_name,
                            }
                        else:
                            st.session_state.connected = False
                            st.error(f"Connection failed: {err_msg}")
                    except Exception as e:
                        st.session_state.connected = False
                        st.error(f"Connection error: {str(e)}")

    if st.session_state.connected:
        db_disp = st.session_state.db_config.get("database", "")
        if len(db_disp) > 20:
            db_disp = Path(db_disp).name
        st.markdown(f'''
        <div class="status-badge online">
            <span class="status-dot"></span>
            <span>Connected: {db_disp} ({st.session_state.db_config.get("dialect", "mysql").upper()})</span>
        </div>
        ''', unsafe_allow_html=True)
        st.markdown('<div class="sidebar-btn" style="margin-bottom: 1rem;">', unsafe_allow_html=True)
        if st.button("Reload Sample Dataset", key="seed_btn", use_container_width=True):
            try:
                with st.spinner("Populating demo tables..."):
                    engine = build_engine(**st.session_state.db_config)
                    stats = seed_database(engine)
                    st.success(f"Populated {stats['products']} products, {stats['customers']} customers, {stats['orders']} orders.")
            except Exception as e:
                st.error(f"Seeding failed: {str(e)[:160]}")
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('''
        <div class="status-badge offline">
            <span class="status-dot"></span>
            <span>Database Not Connected</span>
        </div>
        ''', unsafe_allow_html=True)

    if st.session_state.history:
        st.markdown('<div class="sidebar-label">Recent Queries</div>', unsafe_allow_html=True)
        for i, item in enumerate(reversed(st.session_state.history[-5:])):
            q = item["question"]
            label = q[:32] + "..." if len(q) > 32 else q
            st.markdown('<div class="sample-btn">', unsafe_allow_html=True)
            if st.button(label, key=f"hist_{i}", use_container_width=True):
                st.session_state.question_input = q
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)


st.markdown("""
<div class="main-header">
    <h1>Data Analytics Workspace</h1>
    <p>Convert natural language business questions into verified SQL execution and analytical reports.</p>
</div>
""", unsafe_allow_html=True)


example_prompts = [
    "What are the top 5 products by total revenue?",
    "Show monthly order trends and total sales volume",
    "Identify customers with the highest lifetime value",
    "Calculate the average order value grouped by category",
]

st.markdown('<div class="card-title">Sample Inquiries</div>', unsafe_allow_html=True)
p_cols = st.columns(len(example_prompts))
for idx, prompt in enumerate(example_prompts):
    with p_cols[idx]:
        st.markdown('<div class="sample-btn">', unsafe_allow_html=True)
        if st.button(prompt, key=f"sample_{idx}", use_container_width=True):
            st.session_state.question_input = prompt
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

question = st.text_area(
    "Analytical Question",
    value=st.session_state.question_input,
    placeholder="Ask a question about your database (e.g., Which region produced the highest gross margin last quarter?)...",
    height=95,
    key="question_input_area",
)

col_run, col_pad = st.columns([1, 4])
with col_run:
    st.markdown('<div class="primary-btn">', unsafe_allow_html=True)
    run_btn = st.button("Run Analysis", key="run_btn", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)


if run_btn:
    if not st.session_state.groq_api_key:
        st.error("Groq API Key is required. Please set it in the left configuration sidebar.")
        st.stop()
    if not st.session_state.connected:
        st.error("Active database connection required. Please connect via the sidebar.")
        st.stop()
    if not question or len(question.strip()) < 3:
        st.error("Please provide a valid question.")
        st.stop()

    run_id = new_run_id()
    result = None

    status_container = st.status("Agentic Execution Pipeline Initialized...", expanded=True)
    try:
        for step in stream_workflow(
            question=question.strip(),
            db_config=st.session_state.db_config,
            groq_api_key=st.session_state.groq_api_key,
            run_id=run_id,
            groq_model=st.session_state.groq_model,
        ):
            node = step["node"]
            state = step["current_state"]
            result = state

            if node == "planner":
                status_container.update(label="Planner: Decomposed inquiry into analytical steps...", state="running")
                status_container.write(f"• **Planner**: Inferred intent: *{state.get('intent', 'Analysis')}*")
            elif node == "schema_explorer":
                status_container.update(label="Schema Explorer: Linking relevant tables...", state="running")
                linked = state.get("selected_tables", [])
                status_container.write(f"• **Schema Explorer**: Linked tables: `{', '.join(linked)}`")
            elif node == "sql_agent":
                retries = state.get("iteration_count", 1)
                status_container.update(label=f"SQL Agent: Generated query (Attempt {retries})...", state="running")
                warnings = state.get("query_warnings", [])
                warn_text = f" ({len(warnings)} quality audits checked)" if warnings else ""
                status_container.write(f"• **SQL Agent**: Synthesized SQL & verified AST security{warn_text}.")
            elif node == "analysis_agent":
                status_container.update(label="Analyst: Synthesizing executive report...", state="running")
                status_container.write("• **Analyst**: Computed statistical distributions & insights.")
            elif node == "visualization_agent":
                status_container.update(label="Visualizer: Rendering interactive charts...", state="running")
                status_container.write("• **Visualizer**: Chart prepared.")

        status_container.update(label="Analysis & Visualization Complete!", state="complete", expanded=False)

        df = result.get("query_result")
        exec_meta = result.get("execution_metadata") or {}
        status = "success" if df is not None and not (isinstance(df, pd.DataFrame) and df.empty) else "no_data"

        log_run(run_id, {
            "question": question,
            "generated_sql": result.get("generated_sql"),
            "status": status,
            "retries": result.get("iteration_count", 0),
            "execution_time_ms": exec_meta.get("execution_time_ms"),
        })

        st.session_state.history.append({"question": question, "run_id": run_id, "result": result})
        st.session_state.question_input = ""

    except Exception as e:
        status_container.update(label=f"Execution failed: {str(e)[:100]}", state="error")
        st.error(f"Analysis failed: {str(e)}")
        st.stop()

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

    col_main, col_side = st.columns([2, 1])

    with col_main:
        if result.get("final_answer"):
            st.markdown('<div class="card answer-container"><div class="card-title">Analytical Report</div>', unsafe_allow_html=True)
            st.markdown(result["final_answer"])
            st.markdown('</div>', unsafe_allow_html=True)

        if result.get("plotly_spec"):
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">Interactive Visual Insight</div>', unsafe_allow_html=True)
            try:
                fig = go.Figure(result["plotly_spec"])
                st.plotly_chart(fig, use_container_width=True, theme=None)
            except Exception:
                if result.get("visualization_path") and Path(result["visualization_path"]).exists():
                    st.image(result["visualization_path"], use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        elif result.get("visualization_path") and Path(result["visualization_path"]).exists():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown('<div class="card-title">Visual Insight</div>', unsafe_allow_html=True)
            st.image(result["visualization_path"], use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        if df is not None and isinstance(df, pd.DataFrame) and not df.empty:
            with st.expander("Result Dataset", expanded=False):
                st.dataframe(df, use_container_width=True, height=260)

        if result.get("generated_sql"):
            with st.expander("Executed SQL Statement & Execution Plan", expanded=False):
                st.code(result["generated_sql"], language="sql")
                if result.get("sql_purpose"):
                    st.caption(f"**Intent**: {result['sql_purpose']}")
                if result.get("sql_assumptions"):
                    st.caption(f"**Assumptions**: {', '.join(result['sql_assumptions'])}")
                if result.get("explain_plan"):
                    st.markdown("**Query Plan (`EXPLAIN`):**")
                    st.code(result["explain_plan"], language="text")

    with col_side:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown('<div class="card-title">Execution Telemetry</div>', unsafe_allow_html=True)

        exec_time = exec_meta.get("execution_time_ms")
        retries = result.get("iteration_count", 0)
        rows = exec_meta.get("rows_returned", 0)

        st.markdown(f'''
        <div class="meta-item">
            <span class="meta-item-label">Query Latency</span>
            <span class="meta-item-val">{exec_time:.1f} ms</span>
        </div>
        ''' if exec_time is not None else '', unsafe_allow_html=True)

        st.markdown(f'''
        <div class="meta-item">
            <span class="meta-item-label">Rows Returned</span>
            <span class="meta-item-val">{rows}</span>
        </div>
        <div class="meta-item">
            <span class="meta-item-label">Iterations</span>
            <span class="meta-item-val">{retries}</span>
        </div>
        <div class="meta-item">
            <span class="meta-item-label">Execution ID</span>
            <span class="meta-item-val">{run_id[:8]}</span>
        </div>
        ''', unsafe_allow_html=True)

        if result.get("selected_tables"):
            st.markdown(f'''
            <div class="meta-item">
                <span class="meta-item-label">Linked Tables</span>
                <span class="meta-item-val">{", ".join(result["selected_tables"])}</span>
            </div>
            ''', unsafe_allow_html=True)

        if result.get("intent"):
            st.markdown('<div style="margin-top: 1rem;" class="card-title">Inferred Intent</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:0.82rem;color:#94a3b8;line-height:1.5;">{result["intent"]}</div>', unsafe_allow_html=True)

        if result.get("plan"):
            st.markdown('<div style="margin-top: 1rem;" class="card-title">Execution Plan</div>', unsafe_allow_html=True)
            for step_idx, step_desc in enumerate(result["plan"]):
                st.markdown(f'''
                <div class="plan-step">
                    <span class="step-num">{step_idx + 1}</span>
                    <span>{step_desc}</span>
                </div>
                ''', unsafe_allow_html=True)

        if result.get("query_warnings"):
            st.markdown('<div style="margin-top: 1rem;" class="card-title">Query Performance Audits</div>', unsafe_allow_html=True)
            for w in result["query_warnings"]:
                st.markdown(f'<div style="font-size:0.78rem;color:#f59e0b;padding:2px 0;">⚠️ {w}</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        if result.get("execution_error"):
            st.markdown('<div class="card" style="border-color: rgba(244, 63, 94, 0.3);">', unsafe_allow_html=True)
            st.markdown('<div class="card-title" style="color: #f43f5e;">Diagnostics</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:0.82rem;color:#fda4af;">{result["execution_error"]}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)


