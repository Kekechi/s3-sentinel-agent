import uuid

import pytest
from botocore.exceptions import ClientError
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command


def _admin_config():
    return {"configurable": {"thread_id": str(uuid.uuid4()), "role": "admin"}}


def _invoke_and_check_interrupt(app, input_state, config):
    """Invoke the graph and return (result, interrupted).

    In LangGraph 1.x, interrupt() doesn't raise — the graph returns
    with an __interrupt__ key and state.next pointing to the paused node.
    """
    result = app.invoke(input_state, config=config)
    state = app.get_state(config)
    interrupted = bool(state.next)
    return result, state, interrupted


class TestAdminInterrupt:
    """Tests for the HITL interrupt/resume flow with admin + sensitive tools."""

    def _setup_sensitive_call(self, build_graph, checkpointer, config):
        """Set up a graph with a pending sensitive tool call at GatekeeperNode."""
        app = build_graph(checkpointer=checkpointer)

        ai_msg = AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": "get_bucket_policy", "args": {"bucket_name": "sentinel-vault"}}],
        )
        input_state = {
            "messages": [HumanMessage(content="get policy"), ai_msg],
            "is_policy_exposed": False,
            "is_human_approved": False,
            "is_blocked": True,
        }

        # Inject state as if AssistantNode just produced the tool call
        app.update_state(config, input_state, as_node="AssistantNode")
        return app

    def test_admin_interrupt_pauses_graph(self, build_graph):
        """Admin + sensitive tool → graph pauses with interrupt."""
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            config = _admin_config()
            app = self._setup_sensitive_call(build_graph, checkpointer, config)

            result, state, interrupted = _invoke_and_check_interrupt(app, None, config)

            assert interrupted, "Expected graph to be interrupted for admin + sensitive tool"
            interrupt_value = state.tasks[0].interrupts[0].value
            assert interrupt_value["tool_name"] == "get_bucket_policy"
            assert "approval" in interrupt_value["message"].lower()

    def test_admin_interrupt_approve(self, build_graph):
        """Resume with Command(resume=True) → tool executes, is_blocked=False."""
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            config = _admin_config()
            app = self._setup_sensitive_call(build_graph, checkpointer, config)

            _, _, interrupted = _invoke_and_check_interrupt(app, None, config)
            assert interrupted

            # Resume with approval
            result = app.invoke(Command(resume=True), config=config)
            assert result["is_blocked"] is False
            # The tool should have executed — look for policy content in messages
            tool_messages = [m for m in result["messages"] if hasattr(m, "tool_call_id") and m.tool_call_id]
            assert any("s3:GetObject" in m.content for m in tool_messages), \
                "Expected tool execution with policy content after approval"

    def test_admin_interrupt_deny(self, build_graph):
        """Resume with Command(resume=False) → denial ToolMessage appears in history."""
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            config = _admin_config()
            app = self._setup_sensitive_call(build_graph, checkpointer, config)

            _, _, interrupted = _invoke_and_check_interrupt(app, None, config)
            assert interrupted

            # Resume with denial
            result = app.invoke(Command(resume=False), config=config)
            # Should have denial message somewhere in the message history
            tool_messages = [m for m in result["messages"] if hasattr(m, "tool_call_id") and m.tool_call_id]
            assert any("denied" in m.content.lower() for m in tool_messages), \
                "Expected denial message after rejecting approval"

    def test_approval_reset_after_execution(self, build_graph):
        """After approve+execute cycle, is_human_approved resets to False."""
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            config = _admin_config()
            app = self._setup_sensitive_call(build_graph, checkpointer, config)

            _, _, interrupted = _invoke_and_check_interrupt(app, None, config)
            assert interrupted

            # Resume with approval
            app.invoke(Command(resume=True), config=config)

            # Check that is_human_approved was reset
            final_state = app.get_state(config)
            assert final_state.values["is_human_approved"] is False, \
                "is_human_approved should reset to False after tool execution"


    def test_admin_untagged_bucket_skips_interrupt(self, build_graph, mock_s3_client):
        """Admin + sensitive tool on untagged bucket → graph does NOT pause."""
        mock_s3_client.get_bucket_tagging.side_effect = ClientError(
            {"Error": {"Code": "NoSuchTagSet", "Message": "The TagSet does not exist"}},
            "GetBucketTagging",
        )
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            config = _admin_config()
            app = build_graph(checkpointer=checkpointer)

            ai_msg = AIMessage(
                content="",
                tool_calls=[{"id": "call_1", "name": "get_bucket_policy", "args": {"bucket_name": "public-data"}}],
            )
            input_state = {
                "messages": [HumanMessage(content="get policy"), ai_msg],
                "is_policy_exposed": False,
                "is_human_approved": False,
                "is_blocked": True,
            }
            app.update_state(config, input_state, as_node="AssistantNode")

            result, state, interrupted = _invoke_and_check_interrupt(app, None, config)
            assert not interrupted, "Untagged bucket should NOT trigger interrupt"
            assert result["is_blocked"] is False


class TestCheckpointerPersistence:
    """Tests for SqliteSaver checkpointer integration."""

    def test_graph_with_checkpointer_compiles(self, build_graph):
        """build_graph(checkpointer=saver) compiles and state is retrievable."""
        with SqliteSaver.from_conn_string(":memory:") as checkpointer:
            app = build_graph(checkpointer=checkpointer)
            node_names = set(app.get_graph().nodes.keys())
            assert "AssistantNode" in node_names
            assert "GatekeeperNode" in node_names
            assert "S3ToolNode" in node_names
