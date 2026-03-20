import pytest
from langgraph.checkpoint.sqlite import SqliteSaver

from cli.main import build_graph as _build_graph


@pytest.fixture
def build_graph():
    """Provide the build_graph function from cmd.main."""
    return _build_graph


@pytest.fixture
def build_graph_with_checkpointer(build_graph):
    """Build graph with an in-memory SqliteSaver checkpointer."""
    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        app = build_graph(checkpointer=checkpointer)
        yield app
