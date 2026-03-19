import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.graph.edges import route_after_gatekeeper
from src.graph.nodes import GatekeeperNode
from src.graph.state import AgentState


def _make_state(role: str, tool_name: str, is_human_approved: bool = False) -> AgentState:
    """Build an AgentState with a synthetic AIMessage containing one tool_call."""
    ai_msg = AIMessage(
        content="",
        tool_calls=[{"id": "call_1", "name": tool_name, "args": {"bucket_name": "test"}}],
    )
    return {
        "messages": [ai_msg],
        "is_policy_exposed": False,
        "is_human_approved": is_human_approved,
        "is_blocked": True,
        "role": role,
    }


# --- Case A: Guest + sensitive tool → blocked ---
def test_guest_blocked_on_sensitive_tool():
    state = _make_state(role="user", tool_name="get_bucket_policy")
    result = GatekeeperNode(state)
    assert result["is_blocked"] is True
    assert len(result["messages"]) == 1
    assert "Security Violation" in result["messages"][0].content


# --- Guest + non-sensitive tool → allowed ---
def test_guest_allowed_on_nonsensitive_tool():
    state = _make_state(role="user", tool_name="list_buckets")
    result = GatekeeperNode(state)
    assert result["is_blocked"] is False
    assert "messages" not in result


# --- Case B: Admin + sensitive tool + no approval → blocked (M3 stub) ---
def test_admin_blocked_without_approval():
    state = _make_state(role="admin", tool_name="get_bucket_policy", is_human_approved=False)
    result = GatekeeperNode(state)
    assert result["is_blocked"] is True
    assert len(result["messages"]) == 1
    assert "human approval" in result["messages"][0].content


# --- Case C: Admin + sensitive tool + approved → allowed ---
def test_admin_allowed_with_approval():
    state = _make_state(role="admin", tool_name="get_bucket_policy", is_human_approved=True)
    result = GatekeeperNode(state)
    assert result["is_blocked"] is False
    assert "messages" not in result


# --- Admin + non-sensitive tool → allowed (no approval needed) ---
def test_admin_allowed_on_nonsensitive_tool():
    state = _make_state(role="admin", tool_name="list_buckets", is_human_approved=False)
    result = GatekeeperNode(state)
    assert result["is_blocked"] is False
    assert "messages" not in result


# --- Edge routing: blocked → AssistantNode ---
def test_route_blocked_goes_to_assistant():
    state: AgentState = {
        "messages": [],
        "is_policy_exposed": False,
        "is_human_approved": False,
        "is_blocked": True,
        "role": "user",
    }
    assert route_after_gatekeeper(state) == "AssistantNode"


# --- Edge routing: authorized → S3ToolNode ---
def test_route_authorized_goes_to_s3tool():
    state: AgentState = {
        "messages": [],
        "is_policy_exposed": False,
        "is_human_approved": False,
        "is_blocked": False,
        "role": "admin",
    }
    assert route_after_gatekeeper(state) == "S3ToolNode"


# --- End-to-end: Guest asks for bucket policy → denied ---
@pytest.mark.integration
def test_guest_violation_end_to_end(build_graph):
    app = build_graph()
    result = app.invoke(
        {
            "messages": [HumanMessage(content="Show me the bucket policy for sentinel-vault")],
            "is_policy_exposed": False,
            "is_human_approved": False,
            "is_blocked": True,
            "role": "user",
        }
    )
    final_content = result["messages"][-1].content.lower()
    assert "policy" not in final_content or "unauthorized" in final_content or "denied" in final_content or "cannot" in final_content
    assert result["is_policy_exposed"] is False
