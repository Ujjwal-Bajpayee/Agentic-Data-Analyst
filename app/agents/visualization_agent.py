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
from typing import Optional


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


import plotly.graph_objects as go


def _build_plotly_figure(df: pd.DataFrame, chart_type: str, x_col: Optional[str], y_col: Optional[str], title: str) -> Optional[go.Figure]:
    palette = ["#6366f1", "#10b981", "#f59e0b", "#ec4899", "#38bdf8", "#8b5cf6", "#14b8a6"]
    fig = go.Figure()

    if chart_type in ("bar", "horizontal_bar") and x_col and y_col:
        numeric_y = pd.to_numeric(df[y_col], errors="coerce")
        df_plot = df.assign(**{y_col: numeric_y}).dropna(subset=[y_col])
        if chart_type == "bar":
            fig.add_trace(go.Bar(
                x=df_plot[x_col].astype(str),
                y=df_plot[y_col],
                marker=dict(color=palette[0], line=dict(width=0)),
                hovertemplate=f"<b>%{{x}}</b><br>{y_col}: %{{y:,.2f}}<extra></extra>",
            ))
            fig.update_xaxes(title_text=x_col)
            fig.update_yaxes(title_text=y_col)
        else:
            fig.add_trace(go.Bar(
                x=df_plot[y_col],
                y=df_plot[x_col].astype(str),
                orientation="h",
                marker=dict(color=palette[1], line=dict(width=0)),
                hovertemplate=f"<b>%{{y}}</b><br>{y_col}: %{{x:,.2f}}<extra></extra>",
            ))
            fig.update_xaxes(title_text=y_col)
            fig.update_yaxes(title_text=x_col)

    elif chart_type == "line" and x_col and y_col:
        numeric_y = pd.to_numeric(df[y_col], errors="coerce")
        df_plot = df.assign(**{y_col: numeric_y}).dropna(subset=[y_col])
        fig.add_trace(go.Scatter(
            x=df_plot[x_col].astype(str),
            y=df_plot[y_col],
            mode="lines+markers",
            line=dict(color=palette[0], width=3),
            marker=dict(size=7, color=palette[0]),
            fill="tozeroy",
            fillcolor="rgba(99, 102, 241, 0.12)",
            hovertemplate=f"<b>%{{x}}</b><br>{y_col}: %{{y:,.2f}}<extra></extra>",
        ))
        fig.update_xaxes(title_text=x_col)
        fig.update_yaxes(title_text=y_col)

    elif chart_type == "scatter" and x_col and y_col:
        numeric_x = pd.to_numeric(df[x_col], errors="coerce")
        numeric_y = pd.to_numeric(df[y_col], errors="coerce")
        df_plot = df.assign(**{x_col: numeric_x, y_col: numeric_y}).dropna(subset=[x_col, y_col])
        fig.add_trace(go.Scatter(
            x=df_plot[x_col],
            y=df_plot[y_col],
            mode="markers",
            marker=dict(size=9, color=palette[4], opacity=0.85),
            hovertemplate=f"{x_col}: %{{x:,.2f}}<br>{y_col}: %{{y:,.2f}}<extra></extra>",
        ))
        fig.update_xaxes(title_text=x_col)
        fig.update_yaxes(title_text=y_col)

    elif chart_type in ("pie", "donut") and x_col and y_col:
        numeric_y = pd.to_numeric(df[y_col], errors="coerce")
        df_plot = df.assign(**{y_col: numeric_y}).dropna(subset=[y_col]).head(10)
        hole = 0.55 if chart_type == "donut" else 0.0
        fig.add_trace(go.Pie(
            labels=df_plot[x_col].astype(str),
            values=df_plot[y_col],
            hole=hole,
            marker=dict(colors=palette),
            textinfo="label+percent",
            hovertemplate="<b>%{label}</b><br>Value: %{value:,.2f} (%{percent})<extra></extra>",
        ))

    elif chart_type == "histogram" and (x_col or y_col):
        col = x_col or y_col
        numeric_col = pd.to_numeric(df[col], errors="coerce").dropna()
        fig.add_trace(go.Histogram(
            x=numeric_col,
            marker=dict(color=palette[0]),
            nbinsx=20,
            hovertemplate=f"{col}: %{{x}}<br>Count: %{{y}}<extra></extra>",
        ))
        fig.update_xaxes(title_text=col)
        fig.update_yaxes(title_text="Count")

    else:
        return None

    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#f8fafc")),
        paper_bgcolor="#090d16",
        plot_bgcolor="#0d131f",
        font=dict(color="#94a3b8", size=12),
        margin=dict(l=40, r=40, t=50, b=40),
        xaxis=dict(gridcolor="#1a2333", zerolinecolor="#1a2333"),
        yaxis=dict(gridcolor="#1a2333", zerolinecolor="#1a2333"),
        hoverlabel=dict(bgcolor="#131b2a", font_size=12),
    )
    return fig


def run_visualization_agent(state: AgentState) -> dict:
    df = state.get("query_result")

    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return {"visualization_path": None, "plotly_spec": None}

    columns = list(df.columns)
    decision = _decide_chart(state, columns)

    if decision.get("chart_type", "none") == "none":
        return {"visualization_path": None, "plotly_spec": None}

    chart_type = decision["chart_type"]
    x_col = decision.get("x_column")
    y_col = decision.get("y_column")
    title = decision.get("title", state["question"][:80])

    if x_col and x_col not in df.columns:
        x_col = None
    if y_col and y_col not in df.columns:
        y_col = None

    # 1. Build Plotly Interactive Figure
    plotly_fig = _build_plotly_figure(df, chart_type, x_col, y_col, title)
    plotly_spec = plotly_fig.to_dict() if plotly_fig is not None else None

    # 2. Build Matplotlib Static Fallback
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
            return {"visualization_path": None, "plotly_spec": plotly_spec}

        ax.set_title(title, fontsize=13, fontweight="bold", pad=14, color="#ffffff")
        fig.tight_layout()
        fig.savefig(filepath, dpi=130, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)

        return {"visualization_path": str(filepath), "plotly_spec": plotly_spec}

    except Exception:
        plt.close("all")
        return {"visualization_path": None, "plotly_spec": plotly_spec}
