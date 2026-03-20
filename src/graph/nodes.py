import os

from botocore.exceptions import ClientError
from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt

from src.core.s3_client import create_s3_client
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


def _check_bucket_restricted(tool_call: dict) -> bool:
    """Pre-flight check: does the target bucket have classification=restricted?

    Returns True (fail-closed) if:
    - Tag classification=restricted is found
    - Any non-tagging error occurs (fail-closed)
    - bucket_name is missing from tool_call args

    Returns False only when the bucket exists but has no tags (NoSuchTagSet).
    """
    bucket_name = tool_call.get("args", {}).get("bucket_name")
    if not bucket_name:
        return True

    try:
        client = create_s3_client()
        response = client.get_bucket_tagging(Bucket=bucket_name)
        tag_set = response.get("TagSet", [])
        for tag in tag_set:
            if tag.get("Key") == "classification" and tag.get("Value") == "restricted":
                return True
        return False
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchTagSet":
            return False
        return True
    except Exception:
        return True


def GatekeeperNode(state: AgentState, config: RunnableConfig) -> dict:
    """Inspect pending tool_calls and enforce role-based access control.

    Case A: User + sensitive tool → block with Security Violation.
    Case B: Admin + sensitive tool on restricted bucket → interrupt for HITL approval.
    Case C: Admin + sensitive tool on untagged bucket → pass through (no HITL needed).
    Case D: Non-sensitive tool → pass through to S3ToolNode.
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
                is_restricted = _check_bucket_restricted(tool_call)

                if is_restricted and not state.get("is_human_approved", False):
                    human_decision = interrupt({
                        "tool_name": tool_call["name"],
                        "tool_args": tool_call["args"],
                        "message": "Admin approval required: bucket is classified as restricted.",
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
    is_policy_exposed = state.get("is_policy_exposed", False)

    for tool_call in last_message.tool_calls:
        tool_fn = TOOLS_BY_NAME[tool_call["name"]]
        result = tool_fn.invoke(tool_call["args"])
        results.append(
            ToolMessage(
                content=str(result),
                tool_call_id=tool_call["id"],
            )
        )
        if tool_call["name"] == "get_bucket_policy" and '"error"' not in str(result):
            is_policy_exposed = True

    return {"messages": results, "is_human_approved": False, "is_policy_exposed": is_policy_exposed}
