import json
import os

from botocore.exceptions import ClientError
from dotenv import load_dotenv
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.types import interrupt

from langsmith import traceable

from src.core.audit import set_audit_metadata, tag_security_event
from src.core.s3_client import create_s3_client
from src.core.security import SENSITIVE_KEYS, SENSITIVE_TOOLS
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


@traceable(run_type="chain", name="GatekeeperNode")
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

    # --- Audit instrumentation (M6) ---
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    set_audit_metadata(
        role=role,
        thread_id=thread_id,
        is_human_approved=state.get("is_human_approved", False),
        is_blocked=is_blocked,
    )
    if is_blocked:
        tag_security_event("security_event:access_denied")

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


_ERROR_INDICATORS = ("403", "Forbidden", "Access Denied", "AccessDenied")


def _is_access_error(content: str) -> bool:
    """Check if tool output contains 403/Access Denied indicators."""
    return any(indicator in content for indicator in _ERROR_INDICATORS)


def _redact_sensitive_keys(data):
    """Recursively walk a JSON structure and replace values under SENSITIVE_KEYS with '[REDACTED]'."""
    if isinstance(data, dict):
        return {
            k: "[REDACTED]" if k in SENSITIVE_KEYS else _redact_sensitive_keys(v)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_redact_sensitive_keys(item) for item in data]
    return data


def _apply_redaction(content: str) -> str:
    """Attempt to parse content as JSON and redact sensitive keys. Pass through on failure."""
    try:
        parsed = json.loads(content)
        redacted = _redact_sensitive_keys(parsed)
        return json.dumps(redacted, indent=2)
    except (json.JSONDecodeError, TypeError):
        return content


@traceable(run_type="chain", name="ResponseSanitizerNode")
def ResponseSanitizerNode(state: AgentState, config: RunnableConfig) -> dict:
    """Sanitize tool outputs before they reach the AssistantNode.

    1. Error masking: rewrites 403/AccessDenied errors to generic message for user role.
    2. Data redaction: scrubs sensitive JSON keys (ARNs, Owner IDs, etc.) for all roles.
    """
    role = config.get("configurable", {}).get("role", "user")
    last_messages = state["messages"]
    sanitized = []

    for msg in last_messages:
        if isinstance(msg, ToolMessage):
            content = msg.content
            if role == "user" and _is_access_error(content):
                content = "Error: Bucket not found"
            else:
                content = _apply_redaction(content)
            sanitized.append(
                ToolMessage(
                    content=content,
                    tool_call_id=msg.tool_call_id,
                    id=msg.id,
                )
            )
        else:
            sanitized.append(msg)

    # --- Audit instrumentation (M6) ---
    thread_id = config.get("configurable", {}).get("thread_id", "unknown")
    set_audit_metadata(
        role=role,
        thread_id=thread_id,
        is_policy_exposed=state.get("is_policy_exposed", False),
    )
    if state.get("is_policy_exposed", False):
        tag_security_event("policy_exposed:true")

    return {"messages": sanitized}
