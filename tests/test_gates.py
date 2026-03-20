import pytest
from botocore.exceptions import ClientError
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from unittest.mock import MagicMock, patch

from src.graph.edges import route_after_gatekeeper
from src.graph.nodes import GatekeeperNode, _check_bucket_restricted
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


# --- Pre-flight tagging: _check_bucket_restricted ---
def test_check_bucket_restricted_returns_true_for_restricted(mock_s3_client):
    """Bucket tagged classification=restricted → True."""
    tool_call = {"name": "get_bucket_policy", "args": {"bucket_name": "restricted-confidential"}}
    assert _check_bucket_restricted(tool_call) is True


def test_check_bucket_restricted_returns_false_for_untagged(mock_s3_client):
    """Bucket with no tags (NoSuchTagSet) → False."""
    mock_s3_client.get_bucket_tagging.side_effect = ClientError(
        {"Error": {"Code": "NoSuchTagSet", "Message": "The TagSet does not exist"}},
        "GetBucketTagging",
    )
    tool_call = {"name": "get_bucket_policy", "args": {"bucket_name": "public-data"}}
    assert _check_bucket_restricted(tool_call) is False


def test_check_bucket_restricted_fail_closed_on_error(mock_s3_client):
    """Generic exception during tagging check → True (fail-closed)."""
    mock_s3_client.get_bucket_tagging.side_effect = Exception("Network error")
    tool_call = {"name": "get_bucket_policy", "args": {"bucket_name": "some-bucket"}}
    assert _check_bucket_restricted(tool_call) is True


def test_check_bucket_restricted_no_bucket_name():
    """Missing bucket_name in args → True (fail-closed)."""
    tool_call = {"name": "get_bucket_policy", "args": {}}
    assert _check_bucket_restricted(tool_call) is True


def test_admin_untagged_bucket_passes_without_interrupt(mock_s3_client):
    """Admin + sensitive tool on untagged bucket → is_blocked=False, no interrupt."""
    mock_s3_client.get_bucket_tagging.side_effect = ClientError(
        {"Error": {"Code": "NoSuchTagSet", "Message": "The TagSet does not exist"}},
        "GetBucketTagging",
    )
    state = _make_state(tool_name="get_bucket_policy")
    result = GatekeeperNode(state, _make_config("admin"))
    assert result["is_blocked"] is False
    assert result.get("is_human_approved") is True


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
