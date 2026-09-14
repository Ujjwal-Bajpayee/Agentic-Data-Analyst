import json
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from app.graph.state import AgentState
from app.config import settings


class PlannerOutput(BaseModel):
    intent: str
    plan: list[str]
    needs_visualization: bool


SYSTEM_PROMPT = """You are a business data analyst planning agent.

Given a natural language question about business data, your job is to:
1. Identify the core business intent of the question.
2. Break it down into a step-by-step analytical plan.
3. Decide whether a chart/visualization would add value.

Return a JSON object with:
- "intent": a one-sentence description of what the user wants to know
- "plan": an ordered list of analytical steps (3-6 steps)
- "needs_visualization": true if a chart would help, false otherwise

Do NOT generate any SQL. Only plan."""


def run_planner(state: AgentState) -> dict:
    model_name = state.get("groq_model") or settings.groq_model
    llm = ChatGroq(api_key=state["groq_api_key"], model=model_name)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Question: {state['question']}\n\nReturn valid JSON only."),
    ]

    response = llm.invoke(messages)
    content = response.content.strip()

    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1])

    try:
        parsed = json.loads(content)
        output = PlannerOutput(**parsed)
    except Exception:
        output = PlannerOutput(
            intent=state["question"],
            plan=["Inspect schema", "Generate SQL", "Execute query", "Analyze results"],
            needs_visualization=False,
        )

    return {
        "intent": output.intent,
        "plan": output.plan,
    }
