import json
from datetime import datetime
from unittest.mock import MagicMock, patch

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


@pytest.fixture(autouse=True)
def mock_s3_client(request):
    """Auto-mock the S3 client for all tests unless marked with 'minio'."""
    if "minio" in [m.name for m in request.node.iter_markers()]:
        yield
        return

    mock_client = MagicMock()

    mock_client.list_buckets.return_value = {
        "Buckets": [
            {"Name": "public-data", "CreationDate": datetime(2025, 1, 15)},
            {"Name": "restricted-confidential", "CreationDate": datetime(2025, 3, 1)},
        ]
    }

    mock_client.get_bucket_policy.return_value = {
        "Policy": json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": "*",
                    "Action": "s3:GetObject",
                    "Resource": "arn:aws:s3:::restricted-confidential/*",
                }
            ],
        })
    }

    mock_client.get_bucket_tagging.return_value = {
        "TagSet": [{"Key": "classification", "Value": "restricted"}]
    }

    with patch("src.tools.s3_tools.create_s3_client", return_value=mock_client), \
         patch("src.graph.nodes.create_s3_client", return_value=mock_client):
        yield mock_client
