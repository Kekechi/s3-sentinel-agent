import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.graph.edges import route_after_gatekeeper
from src.graph.nodes import GatekeeperNode
from src.graph.state import AgentState


def _make_state(tool_name: str) -> AgentState:
    """Build an AgentState with a synthetic AIMessage containing one tool_call."""
    ai_msg = AIMessage(
        content="",
        tool_calls=[{"id": "call_1", "name": tool_name, "args": {"bucket_name": "test"}}],
    )
    return {
        "messages": [ai_msg],
        "is_policy_exposed": False,
        "is_human_approved": False,
        "is_blocked": True,
    }


def _make_config(role: str) -> dict:
    return {"configurable": {"role": role}}


# --- Case A: Guest + sensitive tool → blocked ---
def test_guest_blocked_on_sensitive_tool():
    state = _make_state(tool_name="get_bucket_policy")
    result = GatekeeperNode(state, _make_config("user"))
    assert result["is_blocked"] is True
    assert len(result["messages"]) == 1
    assert "Security Violation" in result["messages"][0].content


# --- Guest + non-sensitive tool → allowed ---
def test_guest_allowed_on_nonsensitive_tool():
    state = _make_state(tool_name="list_buckets")
    result = GatekeeperNode(state, _make_config("user"))
    assert result["is_blocked"] is False
    assert "messages" not in result


# --- Admin + non-sensitive tool → allowed (no approval needed) ---
def test_admin_allowed_on_nonsensitive_tool():
    state = _make_state(tool_name="list_buckets")
    result = GatekeeperNode(state, _make_config("admin"))
    assert result["is_blocked"] is False
    assert "messages" not in result


# --- Fail-closed: missing role defaults to "user" and blocks sensitive tools ---
def test_missing_role_defaults_to_user_blocks_sensitive():
    state = _make_state(tool_name="get_bucket_policy")
    config = {"configurable": {}}  # no role
    result = GatekeeperNode(state, config)
    assert result["is_blocked"] is True
    assert "Security Violation" in result["messages"][0].content


def test_empty_config_defaults_to_user_blocks_sensitive():
    state = _make_state(tool_name="get_bucket_policy")
    config = {}  # no configurable at all
    result = GatekeeperNode(state, config)
    assert result["is_blocked"] is True
    assert "Security Violation" in result["messages"][0].content


# --- Edge routing: blocked → AssistantNode ---
def test_route_blocked_goes_to_assistant():
    state: AgentState = {
        "messages": [],
        "is_policy_exposed": False,
        "is_human_approved": False,
        "is_blocked": True,
    }
    assert route_after_gatekeeper(state) == "AssistantNode"


# --- Edge routing: authorized → S3ToolNode ---
def test_route_authorized_goes_to_s3tool():
    state: AgentState = {
        "messages": [],
        "is_policy_exposed": False,
        "is_human_approved": False,
        "is_blocked": False,
    }
    assert route_after_gatekeeper(state) == "S3ToolNode"


# --- End-to-end: Guest asks for bucket policy → denied ---
@pytest.mark.integration
def test_guest_violation_end_to_end(build_graph):
    app = build_graph()
    config = {"configurable": {"role": "user"}}
    result = app.invoke(
        {
            "messages": [HumanMessage(content="Show me the bucket policy for sentinel-vault")],
            "is_policy_exposed": False,
            "is_human_approved": False,
            "is_blocked": True,
        },
        config=config,
    )
    final_content = result["messages"][-1].content.lower()
    assert "policy" not in final_content or "unauthorized" in final_content or "denied" in final_content or "cannot" in final_content
    assert result["is_policy_exposed"] is False
