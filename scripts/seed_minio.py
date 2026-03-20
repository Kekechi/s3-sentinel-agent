"""Seed MinIO with buckets for S3-Sentinel-Graph.

Creates:
  - public-data: untagged, no policy
  - restricted-confidential: tagged classification=restricted, basic read policy

Idempotent — safe to run multiple times.
"""

import json
import os

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv()


def create_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("MINIO_ENDPOINT_URL", "http://localhost:9000"),
        aws_access_key_id=os.getenv("MINIO_ROOT_USER"),
        aws_secret_access_key=os.getenv("MINIO_ROOT_PASSWORD"),
        region_name="us-east-1",
    )


def create_bucket(client, name):
    try:
        client.create_bucket(Bucket=name)
        print(f"  Created bucket: {name}")
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            print(f"  Bucket already exists: {name}")
        else:
            raise


def seed():
    client = create_client()

    # 1. public-data — untagged, no policy
    print("[1/2] public-data")
    create_bucket(client, "public-data")

    # 2. restricted-confidential — tagged + policy
    print("[2/2] restricted-confidential")
    create_bucket(client, "restricted-confidential")

    client.put_bucket_tagging(
        Bucket="restricted-confidential",
        Tagging={
            "TagSet": [{"Key": "classification", "Value": "restricted"}]
        },
    )
    print("  Tagged: classification=restricted")

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": "s3:GetObject",
                "Resource": "arn:aws:s3:::restricted-confidential/*",
            }
        ],
    }
    client.put_bucket_policy(
        Bucket="restricted-confidential",
        Policy=json.dumps(policy),
    )
    print("  Policy applied: s3:GetObject")

    print("\nSeeding complete.")


if __name__ == "__main__":
    seed()
