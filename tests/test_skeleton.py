import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END

from src.graph.edges import route_after_assistant
from src.graph.state import AgentState


# --- 7.1: AgentState instantiation ---
def test_agent_state_instantiation():
    state: AgentState = {
        "messages": [],
        "is_policy_exposed": False,
        "is_human_approved": False,
        "role": "admin",
    }
    assert set(state.keys()) == {"messages", "is_policy_exposed", "is_human_approved", "role"}
    assert state["is_policy_exposed"] is False
    assert state["is_human_approved"] is False
    assert state["role"] == "admin"


# --- 7.2: Graph compiles ---
def test_graph_compiles(build_graph):
    app = build_graph()
    node_names = set(app.get_graph().nodes.keys())
    assert "AssistantNode" in node_names
    assert "GatekeeperNode" in node_names
    assert "S3ToolNode" in node_names


# --- 7.3: End-to-end "Hello" routing (requires LLM) ---
@pytest.mark.integration
def test_hello_routing(build_graph):
    app = build_graph()
    result = app.invoke(
        {
            "messages": [HumanMessage(content="Hello")],
            "is_policy_exposed": False,
            "is_human_approved": False,
            "role": "admin",
        }
    )
    assert len(result["messages"]) >= 2, "Expected at least the input + an AI reply"
    assert result["messages"][-1].content, "Final message should have content"


# --- 7.4: route_after_assistant returns END with no tool calls ---
def test_route_after_assistant_no_tools():
    state: AgentState = {
        "messages": [AIMessage(content="Just a greeting.")],
        "is_policy_exposed": False,
        "is_human_approved": False,
        "role": "admin",
    }
    assert route_after_assistant(state) == END


def test_route_after_assistant_with_tools():
    ai_msg = AIMessage(
        content="",
        tool_calls=[{"id": "call_1", "name": "list_buckets", "args": {}}],
    )
    state: AgentState = {
        "messages": [ai_msg],
        "is_policy_exposed": False,
        "is_human_approved": False,
        "role": "admin",
    }
    assert route_after_assistant(state) == "GatekeeperNode"
