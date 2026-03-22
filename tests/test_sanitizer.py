import json

from langchain_core.messages import ToolMessage

from src.graph.nodes import ResponseSanitizerNode


def _make_config(role="user"):
    return {"configurable": {"role": role}}


def _make_state(content, tool_call_id="call_1"):
    """Build minimal state with a single ToolMessage."""
    return {
        "messages": [
            ToolMessage(content=content, tool_call_id=tool_call_id),
        ],
        "is_policy_exposed": False,
        "is_human_approved": False,
        "is_blocked": False,
    }


# --- Task 5.2: Error Masking Tests ---


class TestErrorMasking:
    """Tests for 403/AccessDenied error masking in ResponseSanitizerNode."""

    def test_user_403_masked(self):
        """User role + '403 Forbidden' content is rewritten to generic error."""
        state = _make_state("Error: 403 Forbidden - Access to bucket denied")
        result = ResponseSanitizerNode(state, _make_config("user"))
        assert result["messages"][0].content == "Error: Bucket not found"

    def test_user_access_denied_masked(self):
        """User role + 'AccessDenied' content is rewritten to generic error."""
        state = _make_state("An error occurred: AccessDenied when calling GetBucketPolicy")
        result = ResponseSanitizerNode(state, _make_config("user"))
        assert result["messages"][0].content == "Error: Bucket not found"

    def test_admin_403_not_masked(self):
        """Admin role + '403 Forbidden' content is passed through unchanged."""
        original = "Error: 403 Forbidden - Access to bucket denied"
        state = _make_state(original)
        result = ResponseSanitizerNode(state, _make_config("admin"))
        assert result["messages"][0].content == original

    def test_user_non_error_not_masked(self):
        """User role + normal JSON content has redaction applied but no masking."""
        original = '{"Version": "2012-10-17", "Statement": []}'
        state = _make_state(original)
        result = ResponseSanitizerNode(state, _make_config("user"))
        parsed = json.loads(result["messages"][0].content)
        assert parsed["Version"] == "2012-10-17"
        assert parsed["Statement"] == []


# --- Task 5.3: Data Redaction Tests ---


class TestDataRedaction:
    """Tests for key-based data redaction in ResponseSanitizerNode."""

    def test_resource_arn_redacted(self):
        """JSON with 'Resource' key has its value replaced with '[REDACTED]'."""
        content = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Action": "s3:GetObject", "Resource": "arn:aws:s3:::bucket/*"}],
        })
        state = _make_state(content)
        result = ResponseSanitizerNode(state, _make_config("admin"))
        parsed = json.loads(result["messages"][0].content)
        assert parsed["Statement"][0]["Resource"] == "[REDACTED]"
        assert parsed["Statement"][0]["Effect"] == "Allow"
        assert parsed["Statement"][0]["Action"] == "s3:GetObject"

    def test_owner_id_redacted(self):
        """JSON with nested 'Owner' > 'ID' keys has both redacted."""
        content = json.dumps({
            "Owner": {"ID": "abc123def456", "DisplayName": "admin"},
        })
        state = _make_state(content)
        result = ResponseSanitizerNode(state, _make_config("admin"))
        parsed = json.loads(result["messages"][0].content)
        assert parsed["Owner"] == "[REDACTED]"

    def test_principal_redacted(self):
        """JSON with 'Principal' key has its value replaced with '[REDACTED]'."""
        content = json.dumps({
            "Statement": [{"Effect": "Allow", "Principal": "*", "Action": "s3:GetObject"}],
        })
        state = _make_state(content)
        result = ResponseSanitizerNode(state, _make_config("admin"))
        parsed = json.loads(result["messages"][0].content)
        assert parsed["Statement"][0]["Principal"] == "[REDACTED]"

    def test_condition_redacted(self):
        """JSON with 'Condition' key has its value replaced with '[REDACTED]'."""
        content = json.dumps({
            "Statement": [{"Effect": "Allow", "Condition": {"IpAddress": {"aws:SourceIp": "10.0.0.0/8"}}}],
        })
        state = _make_state(content)
        result = ResponseSanitizerNode(state, _make_config("admin"))
        parsed = json.loads(result["messages"][0].content)
        assert parsed["Statement"][0]["Condition"] == "[REDACTED]"

    def test_non_sensitive_keys_preserved(self):
        """Keys not in SENSITIVE_KEYS are preserved unchanged."""
        content = json.dumps({
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Action": "s3:GetObject"}],
        })
        state = _make_state(content)
        result = ResponseSanitizerNode(state, _make_config("admin"))
        parsed = json.loads(result["messages"][0].content)
        assert parsed["Version"] == "2012-10-17"
        assert parsed["Statement"][0]["Effect"] == "Allow"
        assert parsed["Statement"][0]["Action"] == "s3:GetObject"

    def test_non_json_content_unchanged(self):
        """Plain text content passes through without modification."""
        original = "This is a plain text response with no JSON."
        state = _make_state(original)
        result = ResponseSanitizerNode(state, _make_config("admin"))
        assert result["messages"][0].content == original

    def test_admin_also_redacted(self):
        """Admin role still gets key-based redaction applied."""
        content = json.dumps({
            "Statement": [{"Effect": "Allow", "Principal": "arn:aws:iam::123456789012:root", "Resource": "arn:aws:s3:::bucket/*"}],
        })
        state = _make_state(content)
        result = ResponseSanitizerNode(state, _make_config("admin"))
        parsed = json.loads(result["messages"][0].content)
        assert parsed["Statement"][0]["Principal"] == "[REDACTED]"
        assert parsed["Statement"][0]["Resource"] == "[REDACTED]"
        assert parsed["Statement"][0]["Effect"] == "Allow"
