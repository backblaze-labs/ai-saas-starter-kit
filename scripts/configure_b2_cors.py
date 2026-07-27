#!/usr/bin/env python
"""Configure B2 bucket CORS so the browser can PUT uploads straight to B2.

The presigned direct-upload flow (see docs/features/file-upload.md) has the
browser PUT bytes to ``https://s3.<region>.backblazeb2.com/...`` — a cross-origin
request from your frontend. The bucket must allow that origin, method, and the
``Content-Type`` header, or the browser's preflight blocks the upload. Server-side
S3 calls are unaffected by CORS, so this only matters once real browsers upload.

Usage (from the repo root, using the API venv which already has boto3):

    services/api/.venv/bin/python scripts/configure_b2_cors.py \
        --origin https://your-app.vercel.app --origin http://localhost:3000

Reads B2 credentials from the same B2_* env vars the app uses (load them however
you normally do, e.g. `set -a; . ./.env; set +a`). Prints the applied rules.

WARNING: S3 ``put_bucket_cors`` REPLACES the bucket's entire CORS config. If the
bucket already serves other apps, pass every origin they need too, or this will
drop their rules. Prefer a dedicated bucket per deployment.
"""

import argparse
import os
import sys

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


def build_client():
    key_id = os.environ.get("B2_APPLICATION_KEY_ID", "")
    app_key = os.environ.get("B2_APPLICATION_KEY", "")
    region = os.environ.get("B2_REGION", "")
    if not (key_id and app_key and region):
        sys.exit("B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY and B2_REGION must be set")
    return boto3.client(
        "s3",
        endpoint_url=f"https://s3.{region}.backblazeb2.com",
        region_name=region,
        aws_access_key_id=key_id,
        aws_secret_access_key=app_key,
        # Same custom user agent as the app's S3 client (parent B2 standard #2):
        # every S3 client in the sample is attributed, ops scripts included.
        config=Config(
            signature_version="s3v4",
            user_agent_extra="b2ai-ai-saas-starter-kit",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--origin",
        action="append",
        required=True,
        help="Allowed browser origin (repeatable), e.g. https://app.vercel.app",
    )
    parser.add_argument(
        "--bucket",
        default=os.environ.get("B2_BUCKET_NAME", ""),
        help="Bucket name (defaults to $B2_BUCKET_NAME)",
    )
    args = parser.parse_args()
    if not args.bucket:
        sys.exit("--bucket or $B2_BUCKET_NAME is required")

    cors_config = {
        "CORSRules": [
            {
                "AllowedOrigins": args.origin,
                # PUT for the presigned upload; GET/HEAD so presigned download +
                # inline preview URLs load. The preflight OPTIONS is handled by B2
                # automatically from these rules — it isn't listed here.
                "AllowedMethods": ["GET", "PUT", "HEAD"],
                # Only the signed PUT needs a custom request header (Content-Type);
                # keep the allowlist tight rather than "*".
                "AllowedHeaders": ["Content-Type"],
                "ExposeHeaders": ["ETag"],
                "MaxAgeSeconds": 3600,
            }
        ]
    }

    client = build_client()
    try:
        client.put_bucket_cors(Bucket=args.bucket, CORSConfiguration=cors_config)
    except ClientError as e:
        sys.exit(f"Failed to set CORS: {e}")

    print(f"Applied CORS to bucket '{args.bucket}':")
    for origin in args.origin:
        print(f"  - {origin}  (GET, PUT, HEAD)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
