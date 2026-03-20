import os

from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt

from src.core.security import SENSITIVE_TOOLS
from src.graph.state import AgentState
from src.tools.s3_tools import get_bucket_policy, list_buckets

load_dotenv()

ALL_TOOLS = [list_buckets, get_bucket_policy]
TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}

model = ChatOpenAI(
    model="gpt-4o-mini",
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("API_URL")
).bind_tools(ALL_TOOLS)


def AssistantNode(state: AgentState) -> dict:
    """Call the LLM with the current message history and bound tools."""
    response = model.invoke(state["messages"])
    return {"messages": [response]}


def GatekeeperNode(state: AgentState, config: RunnableConfig) -> dict:
    """Inspect pending tool_calls and enforce role-based access control.

    Case A: Guest/user + sensitive tool → block with Security Violation.
    Case B: Admin + sensitive tool → interrupt for HITL approval.
    Case C: Authorized (non-sensitive or admin-approved) → pass through to S3ToolNode.
    """
    last_message = state["messages"][-1]
    role = config.get("configurable", {}).get("role", "user")
    is_blocked = False
    results = []

    for tool_call in last_message.tool_calls:
        if tool_call["name"] in SENSITIVE_TOOLS:
            if role == "user":
                results.append(
                    ToolMessage(
                        content="Security Violation: Unauthorized",
                        tool_call_id=tool_call["id"],
                    )
                )
                is_blocked = True
            elif role == "admin":
                human_decision = interrupt({
                    "tool_name": tool_call["name"],
                    "tool_args": tool_call["args"],
                    "message": "Admin approval required for sensitive operation.",
                })
                if not human_decision:
                    results.append(
                        ToolMessage(
                            content="Admin denied the action.",
                            tool_call_id=tool_call["id"],
                        )
                    )
                    is_blocked = True

    if is_blocked:
        return {"messages": results, "is_blocked": True}
    return {"is_blocked": False, "is_human_approved": True}


def S3ToolNode(state: AgentState) -> dict:
    """Execute tool calls from the last AI message and return ToolMessages."""
    last_message = state["messages"][-1]
    results = []
    for tool_call in last_message.tool_calls:
        tool_fn = TOOLS_BY_NAME[tool_call["name"]]
        result = tool_fn.invoke(tool_call["args"])
        results.append(
            ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
            )
        )
    return {"messages": results, "is_human_approved": False}
