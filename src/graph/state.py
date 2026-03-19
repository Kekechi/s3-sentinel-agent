from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    is_policy_exposed: bool
    is_human_approved: bool
    is_blocked: bool
    role: str
