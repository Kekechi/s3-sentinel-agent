import sys
import uuid

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.types import Command

from src.graph.edges import route_after_assistant, route_after_gatekeeper
from src.graph.nodes import AssistantNode, GatekeeperNode, ResponseSanitizerNode, S3ToolNode
from src.graph.state import AgentState


def build_graph(checkpointer=None):
    """Construct and compile the S3 Sentinel StateGraph."""
    graph = StateGraph(AgentState)

    graph.add_node("AssistantNode", AssistantNode)
    graph.add_node("GatekeeperNode", GatekeeperNode)
    graph.add_node("S3ToolNode", S3ToolNode)
    graph.add_node("ResponseSanitizerNode", ResponseSanitizerNode)

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
    graph.add_edge("S3ToolNode", "ResponseSanitizerNode")
    graph.add_edge("ResponseSanitizerNode", "AssistantNode")

    return graph.compile(checkpointer=checkpointer)


def main():
    from langgraph.checkpoint.sqlite import SqliteSaver

    role = "admin"
    if "--role" in sys.argv:
        role = sys.argv[sys.argv.index("--role") + 1]

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id, "role": role}}

    with SqliteSaver.from_conn_string("s3_sentinel.db") as checkpointer:
        app = build_graph(checkpointer=checkpointer)

        print(f"S3 Sentinel Agent (role={role}, type 'quit' to exit)")

        while True:
            user_input = input("\nYou: ").strip()
            if not user_input or user_input.lower() == "quit":
                break

            input_state = {"messages": [HumanMessage(content=user_input)]}

            while True:
                result = app.invoke(input_state, config=config)
                graph_state = app.get_state(config)
                if not graph_state.next:
                    break  # completed without interrupt
                # Graph is paused at an interrupt
                interrupt_value = graph_state.tasks[0].interrupts[0].value
                print(f"\n[HITL] {interrupt_value['message']}")
                print(f"  Tool: {interrupt_value['tool_name']}")
                print(f"  Args: {interrupt_value['tool_args']}")
                approval = input("  Approve? (y/n): ").strip().lower()
                input_state = Command(resume=(approval == "y"))

            final_message = result["messages"][-1]
            print(f"\nAgent: {final_message.content}")


if __name__ == "__main__":
    main()
