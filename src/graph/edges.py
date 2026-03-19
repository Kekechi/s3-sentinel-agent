from langgraph.graph import END

from src.graph.state import AgentState


def route_after_assistant(state: AgentState) -> str:
    """Route based on whether the LLM requested tool calls."""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "GatekeeperNode"
    return END


def route_after_gatekeeper(state: AgentState) -> str:
    """Route based on gatekeeper decision: blocked → AssistantNode, authorized → S3ToolNode."""
    if state.get("is_blocked", True):
        return "AssistantNode"
    return "S3ToolNode"
