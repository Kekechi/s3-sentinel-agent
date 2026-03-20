import json

from langchain_core.tools import tool

from src.core.s3_client import create_s3_client


@tool
def list_buckets() -> str:
    """List all S3 buckets in the account."""
    client = create_s3_client()
    response = client.list_buckets()
    buckets = [
        {"Name": b["Name"], "CreationDate": b["CreationDate"].isoformat()}
        for b in response.get("Buckets", [])
    ]
    return json.dumps(buckets, indent=2)


@tool
def get_bucket_policy(bucket_name: str) -> str:
    """Get the access policy for a specific S3 bucket."""
    client = create_s3_client()
    try:
        response = client.get_bucket_policy(Bucket=bucket_name)
        return response["Policy"]
    except client.exceptions.NoSuchBucketPolicy:
        return json.dumps({"error": "No policy found", "bucket": bucket_name})
    except Exception as e:
        return json.dumps({"error": str(e), "bucket": bucket_name})
