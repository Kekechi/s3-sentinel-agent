import importlib.util

import pytest
from langgraph.checkpoint.sqlite import SqliteSaver


@pytest.fixture
def build_graph():
    """Import build_graph from cmd/main.py (not a package, avoids stdlib shadow)."""
    spec = importlib.util.spec_from_file_location("main", "cmd/main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_graph


@pytest.fixture
def build_graph_with_checkpointer(build_graph):
    """Build graph with an in-memory SqliteSaver checkpointer."""
    with SqliteSaver.from_conn_string(":memory:") as checkpointer:
        app = build_graph(checkpointer=checkpointer)
        yield app
