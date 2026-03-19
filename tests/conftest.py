import importlib.util

import pytest


@pytest.fixture
def build_graph():
    """Import build_graph from cmd/main.py (not a package, avoids stdlib shadow)."""
    spec = importlib.util.spec_from_file_location("main", "cmd/main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build_graph
