import json
import os

import boto3

s3 = boto3.client("s3")


def parse_s3_uri(s3_uri: str):
    """Return (bucket, prefix, filename, extension, file) from an s3:// URI."""
    without_scheme = s3_uri.split("s3://", 1)[1]
    parts = without_scheme.split("/")
    bucket = parts[0]
    prefix = "/".join(parts[1:-1])
    file = parts[-1]
    filename, extension = file.rsplit(".", 1)
    return bucket, prefix, filename, extension, file


def download_file(bucket: str, key: str, local_path: str) -> None:
    if os.path.exists(local_path):
        print(f"Already cached: {local_path}")
        return
    print(f"Downloading s3://{bucket}/{key} → {local_path}")
    s3.download_file(bucket, key, local_path)


def upload_json(bucket: str, key: str, data) -> None:
    body = json.dumps(data).encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")
    print(f"Uploaded JSON → s3://{bucket}/{key}")