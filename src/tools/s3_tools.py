import json

from langchain_core.tools import tool


@tool
def list_buckets() -> str:
    """List all S3 buckets in the account."""
    buckets = [
        {"Name": "sentinel-logs", "CreationDate": "2025-01-15"},
        {"Name": "sentinel-vault", "CreationDate": "2025-03-01"},
        {"Name": "sentinel-public", "CreationDate": "2025-06-10"},
    ]
    return json.dumps(buckets, indent=2)


@tool
def get_bucket_policy(bucket_name: str) -> str:
    """Get the access policy for a specific S3 bucket."""
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket_name}/*",
            }
        ],
    }
    return json.dumps(policy, indent=2)
