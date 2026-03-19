import os

from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
from langchain_openai import ChatOpenAI

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


def GatekeeperNode(state: AgentState) -> dict:
    """Stub: passthrough to S3ToolNode. Security logic added in M2."""
    return state


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
    return {"messages": results}
