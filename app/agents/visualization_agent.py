import os
import uuid
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.graph.state import AgentState
from app.config import settings
import json


DECISION_PROMPT = """You are deciding whether to generate a chart for a business data result.

Given the question, plan, and data shape, decide:
1. Whether a chart adds value (not every answer needs a chart).
2. If yes, which chart type: "line", "bar", "horizontal_bar", "scatter", "histogram", or "none".
3. Which columns to use for x-axis and y-axis.

Return JSON only:
{
  "chart_type": "bar" | "line" | "horizontal_bar" | "scatter" | "histogram" | "none",
  "x_column": "column_name_or_null",
  "y_column": "column_name_or_null",
  "title": "chart title"
}"""


def _decide_chart(state: AgentState, columns: list[str]) -> dict:
    model_name = state.get("groq_model") or settings.groq_model
    llm = ChatGroq(api_key=state["groq_api_key"], model=model_name)

    msg = f"""Question: {state['question']}
Available columns: {columns}
Row count: {len(state['query_result'])}

Return JSON only."""

    messages = [
        SystemMessage(content=DECISION_PROMPT),
        HumanMessage(content=msg),
    ]

    response = llm.invoke(messages)
    content = response.content.strip()

    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1])

    try:
        return json.loads(content)
    except Exception:
        return {"chart_type": "none", "x_column": None, "y_column": None, "title": ""}


def _apply_style():
    plt.style.use("seaborn-v0_8-darkgrid")
    plt.rcParams.update({
        "figure.facecolor": "#0f1117",
        "axes.facecolor": "#1a1d27",
        "axes.edgecolor": "#2d3047",
        "axes.labelcolor": "#e0e0e0",
        "xtick.color": "#b0b0b0",
        "ytick.color": "#b0b0b0",
        "text.color": "#e0e0e0",
        "grid.color": "#2d3047",
        "grid.alpha": 0.6,
        "font.family": "DejaVu Sans",
    })


def run_visualization_agent(state: AgentState) -> dict:
    df = state.get("query_result")

    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {"visualization_path": None}

    columns = list(df.columns)
    decision = _decide_chart(state, columns)

    if decision.get("chart_type", "none") == "none":
        return {"visualization_path": None}

    chart_type = decision["chart_type"]
    x_col = decision.get("x_column")
    y_col = decision.get("y_column")
    title = decision.get("title", state["question"][:80])

    if x_col and x_col not in df.columns:
        x_col = None
    if y_col and y_col not in df.columns:
        y_col = None

    output_dir = Path(settings.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex[:8]}.png"
    filepath = output_dir / filename

    _apply_style()
    palette = ["#6c63ff", "#48cfad", "#fc6b6b", "#ffd166", "#06d6a0", "#118ab2"]

    try:
        fig, ax = plt.subplots(figsize=(10, 5))

        if chart_type == "bar" and x_col and y_col:
            numeric_y = pd.to_numeric(df[y_col], errors="coerce")
            df_plot = df.assign(**{y_col: numeric_y}).dropna(subset=[y_col])
            colors = [palette[i % len(palette)] for i in range(len(df_plot))]
            ax.bar(df_plot[x_col].astype(str), df_plot[y_col], color=colors, edgecolor="none")
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            plt.xticks(rotation=35, ha="right")

        elif chart_type == "horizontal_bar" and x_col and y_col:
            numeric_y = pd.to_numeric(df[y_col], errors="coerce")
            df_plot = df.assign(**{y_col: numeric_y}).dropna(subset=[y_col])
            colors = [palette[i % len(palette)] for i in range(len(df_plot))]
            ax.barh(df_plot[x_col].astype(str), df_plot[y_col], color=colors, edgecolor="none")
            ax.set_xlabel(y_col)
            ax.set_ylabel(x_col)

        elif chart_type == "line" and x_col and y_col:
            numeric_y = pd.to_numeric(df[y_col], errors="coerce")
            df_plot = df.assign(**{y_col: numeric_y}).dropna(subset=[y_col])
            ax.plot(df_plot[x_col].astype(str), df_plot[y_col], color=palette[0], linewidth=2.5, marker="o", markersize=5)
            ax.fill_between(range(len(df_plot)), df_plot[y_col], alpha=0.15, color=palette[0])
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
            plt.xticks(rotation=35, ha="right")

        elif chart_type == "scatter" and x_col and y_col:
            numeric_x = pd.to_numeric(df[x_col], errors="coerce")
            numeric_y = pd.to_numeric(df[y_col], errors="coerce")
            df_plot = df.assign(**{x_col: numeric_x, y_col: numeric_y}).dropna(subset=[x_col, y_col])
            ax.scatter(df_plot[x_col], df_plot[y_col], color=palette[0], alpha=0.7, edgecolors="none", s=50)
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)

        elif chart_type == "histogram" and (x_col or y_col):
            col = x_col or y_col
            numeric_col = pd.to_numeric(df[col], errors="coerce").dropna()
            ax.hist(numeric_col, bins=20, color=palette[0], edgecolor="#0f1117", linewidth=0.5)
            ax.set_xlabel(col)
            ax.set_ylabel("Frequency")

        else:
            plt.close(fig)
            return {"visualization_path": None}

        ax.set_title(title, fontsize=13, fontweight="bold", pad=14, color="#ffffff")
        fig.tight_layout()
        fig.savefig(filepath, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)

        return {"visualization_path": str(filepath)}

    except Exception:
        plt.close("all")
        return {"visualization_path": None}
