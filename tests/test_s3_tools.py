import json

import pytest
from botocore.exceptions import ClientError
from langchain_core.messages import AIMessage

from src.graph.nodes import S3ToolNode
from src.tools.s3_tools import get_bucket_policy, list_buckets


class TestListBuckets:
    """Unit tests for list_buckets tool."""

    def test_list_buckets_returns_json(self, mock_s3_client):
        """list_buckets returns valid JSON with expected bucket shape."""
        result = list_buckets.invoke({})
        parsed = json.loads(result)

        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["Name"] == "public-data"
        assert parsed[1]["Name"] == "restricted-confidential"
        assert "CreationDate" in parsed[0]


class TestGetBucketPolicy:
    """Unit tests for get_bucket_policy tool."""

    def test_get_bucket_policy_returns_policy(self, mock_s3_client):
        """Successful get_bucket_policy returns policy JSON with s3:GetObject."""
        result = get_bucket_policy.invoke({"bucket_name": "restricted-confidential"})
        parsed = json.loads(result)

        assert parsed["Version"] == "2012-10-17"
        assert any(
            stmt["Action"] == "s3:GetObject"
            for stmt in parsed["Statement"]
        )

    def test_get_bucket_policy_no_policy(self, mock_s3_client):
        """NoSuchBucketPolicy returns structured error JSON."""
        error_response = {"Error": {"Code": "NoSuchBucketPolicy", "Message": "No policy"}}
        mock_s3_client.exceptions.NoSuchBucketPolicy = type(
            "NoSuchBucketPolicy", (ClientError,), {}
        )
        mock_s3_client.get_bucket_policy.side_effect = (
            mock_s3_client.exceptions.NoSuchBucketPolicy(error_response, "GetBucketPolicy")
        )

        result = get_bucket_policy.invoke({"bucket_name": "public-data"})
        parsed = json.loads(result)

        assert parsed["error"] == "No policy found"
        assert parsed["bucket"] == "public-data"

    def test_get_bucket_policy_nonexistent_bucket(self, mock_s3_client):
        """ClientError (e.g. NoSuchBucket) returns structured error JSON."""
        mock_s3_client.exceptions.NoSuchBucketPolicy = type(
            "NoSuchBucketPolicy", (ClientError,), {}
        )
        mock_s3_client.get_bucket_policy.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "Not found"}},
            "GetBucketPolicy",
        )

        result = get_bucket_policy.invoke({"bucket_name": "nonexistent"})
        parsed = json.loads(result)

        assert "error" in parsed
        assert parsed["bucket"] == "nonexistent"


class TestPolicyExposed:
    """Tests for is_policy_exposed wiring in S3ToolNode."""

    def _make_tool_state(self, tool_name, args=None, is_policy_exposed=False):
        """Build state with a synthetic tool call for S3ToolNode."""
        ai_msg = AIMessage(
            content="",
            tool_calls=[{"id": "call_1", "name": tool_name, "args": args or {}}],
        )
        return {
            "messages": [ai_msg],
            "is_policy_exposed": is_policy_exposed,
            "is_human_approved": True,
            "is_blocked": False,
        }

    def test_policy_exposed_set_on_success(self, mock_s3_client):
        """Successful get_bucket_policy sets is_policy_exposed=True."""
        state = self._make_tool_state("get_bucket_policy", {"bucket_name": "restricted-confidential"})
        result = S3ToolNode(state)
        assert result["is_policy_exposed"] is True

    def test_policy_exposed_not_set_on_error(self, mock_s3_client):
        """Failed get_bucket_policy keeps is_policy_exposed=False."""
        mock_s3_client.get_bucket_policy.return_value = {
            "Policy": json.dumps({"error": "No policy found", "bucket": "public-data"})
        }
        state = self._make_tool_state("get_bucket_policy", {"bucket_name": "public-data"})
        result = S3ToolNode(state)
        assert result["is_policy_exposed"] is False

    def test_policy_exposed_high_water_mark(self, mock_s3_client):
        """Once is_policy_exposed=True, it stays True even for non-policy tools."""
        state = self._make_tool_state("list_buckets", is_policy_exposed=True)
        result = S3ToolNode(state)
        assert result["is_policy_exposed"] is True


@pytest.mark.minio
class TestLiveMinio:
    """Integration tests requiring a running MinIO container."""

    def test_list_buckets_live(self):
        """Live MinIO: list_buckets returns seeded buckets."""
        result = list_buckets.invoke({})
        parsed = json.loads(result)
        bucket_names = [b["Name"] for b in parsed]

        assert "public-data" in bucket_names
        assert "restricted-confidential" in bucket_names

    def test_get_bucket_policy_live(self):
        """Live MinIO: get_bucket_policy returns seeded policy for restricted bucket."""
        result = get_bucket_policy.invoke({"bucket_name": "restricted-confidential"})
        parsed = json.loads(result)

        assert "Statement" in parsed
        for stmt in parsed["Statement"]:
            action = stmt["Action"]
            if isinstance(action, list):
                assert "s3:GetObject" in action
            else:
                assert action == "s3:GetObject"
