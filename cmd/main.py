import sys

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

from src.graph.edges import route_after_assistant, route_after_gatekeeper
from src.graph.nodes import AssistantNode, GatekeeperNode, S3ToolNode
from src.graph.state import AgentState


def build_graph() -> StateGraph:
    """Construct and compile the S3 Sentinel StateGraph."""
    graph = StateGraph(AgentState)

    graph.add_node("AssistantNode", AssistantNode)
    graph.add_node("GatekeeperNode", GatekeeperNode)
    graph.add_node("S3ToolNode", S3ToolNode)

    graph.set_entry_point("AssistantNode")

    graph.add_conditional_edges(
        "AssistantNode",
        route_after_assistant,
        {"GatekeeperNode": "GatekeeperNode", END: END},
    )
    graph.add_conditional_edges(
        "GatekeeperNode",
        route_after_gatekeeper,
        {"S3ToolNode": "S3ToolNode", "AssistantNode": "AssistantNode"},
    )
    graph.add_edge("S3ToolNode", "AssistantNode")

    return graph.compile()


def main():
    app = build_graph()

    role = "admin"
    if "--role" in sys.argv:
        role = sys.argv[sys.argv.index("--role") + 1]

    print(f"S3 Sentinel Agent (role={role}, type 'quit' to exit)")

    while True:
        user_input = input("\nYou: ").strip()
        if not user_input or user_input.lower() == "quit":
            break

        result = app.invoke(
            {
                "messages": [HumanMessage(content=user_input)],
                "is_policy_exposed": False,
                "is_human_approved": False,
                "is_blocked": True,
                "role": role,
            }
        )

        final_message = result["messages"][-1]
        print(f"\nAgent: {final_message.content}")


if __name__ == "__main__":
    main()
