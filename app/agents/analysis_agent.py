import pandas as pd
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from app.graph.state import AgentState
from app.tools.python_analysis import descriptive_stats, null_report, validate_result
from app.config import settings


SYSTEM_PROMPT = """You are a senior data analyst and business intelligence consultant. You provide clear, rigorous, executive-level insights based strictly on data query results from MySQL.

Guidelines:
1. Tone: Professional, objective, authoritative, and concise. Avoid colloquialisms, fluff, or generic filler statements.
2. Quantitative Precision: Never make vague claims (e.g., "sales increased significantly" or "some products performed well"). Always ground every statement in exact figures, percentages, rankings, currency values, or rates derived from the data.
3. No Hallucinations: Use only facts, metrics, and numbers explicitly present in the data or derived calculations.
4. Structure & Spacing: Use clean Markdown formatting with clear section headers, bold lead-ins for bullet points, and clean paragraph breaks.

Response Structure:

### Executive Summary
[Direct, unambiguous answer to the user's business question in 2-3 sentences, highlighting the primary metric or outcome.]

### Key Insights
- **[Primary Finding]**: [Specific quantitative detail, comparisons, or distributions from the dataset.]
- **[Secondary Trend / Comparison]**: [Comparative analysis across categories, time periods, or segments with exact numbers.]
- **[Notable Outlier or Distribution]**: [Key pattern, highest/lowest performer, or distribution observation with concrete data points.]

### Data Summary
[A concise summary of key figures, totals, averages, or top/bottom rankings relevant to the inquiry.]

### Considerations & Assumptions
[Any relevant business context, data limitations, filter boundaries, or calculation nuances, or omit if none apply.]"""


def run_analysis_agent(state: AgentState) -> dict:
    df = state.get("query_result")

    if df is None or (isinstance(df, pd.DataFrame) and df.empty):
        return {
            "analysis": "The query executed successfully but returned zero matching records for the specified parameters.",
            "final_answer": "### Executive Summary\nNo data was found matching the specified criteria in the database.",
        }

    stats = descriptive_stats(df)
    nulls = null_report(df)
    result_validation = validate_result(df)

    total_rows = len(df)
    try:
        data_preview = df.head(50).to_markdown(index=False)
    except Exception:
        data_preview = df.head(50).to_string(index=False)
    stats_text = str(stats) if stats else "No numeric columns."
    issues_text = ", ".join(result_validation["issues"]) if result_validation["issues"] else "None detected"

    model_name = state.get("groq_model") or settings.groq_model
    llm = ChatGroq(api_key=state["groq_api_key"], model=model_name, temperature=0.1)

    user_message = f"""Business Question: {state['question']}

Analytical Objective:
{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(state['plan']))}

Dataset Dimensions: {total_rows} total rows returned
Executed SQL:
{state.get('generated_sql', 'N/A')}

Descriptive Metrics:
{stats_text}

Data Quality Assessment:
{issues_text}

Query Results:
{data_preview}

Generate a comprehensive, professional analytical report using the structured format."""

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_message),
    ]

    response = llm.invoke(messages)
    analysis_text = response.content.strip()

    return {
        "analysis": analysis_text,
        "final_answer": analysis_text,
    }
