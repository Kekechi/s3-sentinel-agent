"""Tests for Milestone 6: Observability & Forensic Audit.

Validates that security-critical nodes attach correct LangSmith
metadata and tags for audit reconstructibility.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from src.graph.nodes import GatekeeperNode, ResponseSanitizerNode


def _make_config(role="user", thread_id="test-thread-123"):
    return {"configurable": {"role": role, "thread_id": thread_id}}


def _make_gatekeeper_state(tool_name="get_bucket_policy"):
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


def _make_sanitizer_state(content, is_policy_exposed=False):
    return {
        "messages": [ToolMessage(content=content, tool_call_id="call_1")],
        "is_policy_exposed": is_policy_exposed,
        "is_human_approved": False,
        "is_blocked": False,
    }


def _make_mock_run_tree():
    """Create a mock RunTree with tags list and metadata dict."""
    mock_rt = MagicMock()
    mock_rt.tags = []
    mock_rt.metadata = {}
    return mock_rt


# --- Task 6.2: Security Event Tagging ---


class TestGatekeeperAuditTags:
    """Verify GatekeeperNode attaches correct security event tags."""

    @patch("src.core.audit.get_current_run_tree")
    def test_blocked_guest_tags_access_denied(self, mock_get_rt):
        mock_rt = _make_mock_run_tree()
        mock_get_rt.return_value = mock_rt
        state = _make_gatekeeper_state("get_bucket_policy")
        GatekeeperNode(state, _make_config("user"))
        assert "security_event:access_denied" in mock_rt.tags

    @patch("src.core.audit.get_current_run_tree")
    def test_allowed_nonsensitive_no_access_denied_tag(self, mock_get_rt):
        mock_rt = _make_mock_run_tree()
        mock_get_rt.return_value = mock_rt
        state = _make_gatekeeper_state("list_buckets")
        GatekeeperNode(state, _make_config("user"))
        assert "security_event:access_denied" not in mock_rt.tags


# --- Task 6.3: Metadata Forensics ---


class TestGatekeeperAuditMetadata:
    """Verify GatekeeperNode pushes role, thread_id, is_human_approved to metadata."""

    @patch("src.core.audit.get_current_run_tree")
    def test_metadata_contains_role(self, mock_get_rt):
        mock_rt = _make_mock_run_tree()
        mock_get_rt.return_value = mock_rt
        GatekeeperNode(_make_gatekeeper_state(), _make_config("user", "thread-abc"))
        assert mock_rt.metadata["role"] == "user"

    @patch("src.core.audit.get_current_run_tree")
    def test_metadata_contains_thread_id(self, mock_get_rt):
        mock_rt = _make_mock_run_tree()
        mock_get_rt.return_value = mock_rt
        state = _make_gatekeeper_state("list_buckets")
        GatekeeperNode(state, _make_config("admin", "thread-xyz"))
        assert mock_rt.metadata["thread_id"] == "thread-xyz"

    @patch("src.core.audit.get_current_run_tree")
    def test_metadata_contains_is_human_approved(self, mock_get_rt):
        mock_rt = _make_mock_run_tree()
        mock_get_rt.return_value = mock_rt
        state = _make_gatekeeper_state("list_buckets")
        state["is_human_approved"] = True
        GatekeeperNode(state, _make_config("admin"))
        assert mock_rt.metadata["is_human_approved"] is True

    @patch("src.core.audit.get_current_run_tree")
    def test_metadata_is_blocked_true_when_denied(self, mock_get_rt):
        mock_rt = _make_mock_run_tree()
        mock_get_rt.return_value = mock_rt
        GatekeeperNode(_make_gatekeeper_state("get_bucket_policy"), _make_config("user"))
        assert mock_rt.metadata["is_blocked"] is True


# --- Task 6.2 + 6.3: ResponseSanitizer Audit ---


class TestSanitizerAuditTags:
    """Verify ResponseSanitizerNode tags policy_exposed when high-water mark is set."""

    @patch("src.core.audit.get_current_run_tree")
    def test_policy_exposed_tagged(self, mock_get_rt):
        mock_rt = _make_mock_run_tree()
        mock_get_rt.return_value = mock_rt
        state = _make_sanitizer_state('{"Version": "2012-10-17"}', is_policy_exposed=True)
        ResponseSanitizerNode(state, _make_config("admin"))
        assert "policy_exposed:true" in mock_rt.tags

    @patch("src.core.audit.get_current_run_tree")
    def test_no_policy_exposed_tag_when_false(self, mock_get_rt):
        mock_rt = _make_mock_run_tree()
        mock_get_rt.return_value = mock_rt
        state = _make_sanitizer_state('{"Version": "2012-10-17"}', is_policy_exposed=False)
        ResponseSanitizerNode(state, _make_config("admin"))
        assert "policy_exposed:true" not in mock_rt.tags


class TestSanitizerAuditMetadata:
    """Verify ResponseSanitizerNode pushes role and thread_id to metadata."""

    @patch("src.core.audit.get_current_run_tree")
    def test_metadata_contains_role_and_thread(self, mock_get_rt):
        mock_rt = _make_mock_run_tree()
        mock_get_rt.return_value = mock_rt
        state = _make_sanitizer_state("plain text")
        ResponseSanitizerNode(state, _make_config("admin", "thread-999"))
        assert mock_rt.metadata["role"] == "admin"
        assert mock_rt.metadata["thread_id"] == "thread-999"

    @patch("src.core.audit.get_current_run_tree")
    def test_redacted_run_still_has_metadata(self, mock_get_rt):
        """Even when content is redacted, audit metadata is still attached.
        This is the core 'reconstructibility' requirement of Task 6.4."""
        mock_rt = _make_mock_run_tree()
        mock_get_rt.return_value = mock_rt
        content = json.dumps({"Resource": "arn:aws:s3:::secret/*", "Effect": "Allow"})
        state = _make_sanitizer_state(content, is_policy_exposed=True)
        result = ResponseSanitizerNode(state, _make_config("user", "thread-forensic"))
        # Content is redacted
        parsed = json.loads(result["messages"][0].content)
        assert parsed["Resource"] == "[REDACTED]"
        # But audit trail is fully populated
        assert mock_rt.metadata["role"] == "user"
        assert mock_rt.metadata["thread_id"] == "thread-forensic"
        assert mock_rt.metadata["is_policy_exposed"] is True
        assert "policy_exposed:true" in mock_rt.tags


# --- Graceful degradation: no tracing active ---


class TestAuditGracefulDegradation:
    """Verify nodes work correctly when LangSmith tracing is not active."""

    @patch("src.core.audit.get_current_run_tree", return_value=None)
    def test_gatekeeper_works_without_tracing(self, mock_get_rt):
        state = _make_gatekeeper_state("get_bucket_policy")
        result = GatekeeperNode(state, _make_config("user"))
        assert result["is_blocked"] is True

    @patch("src.core.audit.get_current_run_tree", return_value=None)
    def test_sanitizer_works_without_tracing(self, mock_get_rt):
        state = _make_sanitizer_state("plain text")
        result = ResponseSanitizerNode(state, _make_config("user"))
        assert result["messages"][0].content == "plain text"
