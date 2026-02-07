"""
Delete All Data handler — hard-deletes all user data.

POST /delete-all-data
Body: { "confirmation": "DELETE" }

Per spec: "Delete all data" button (hard delete). No soft-delete ambiguity.
"""

import json
import os

import boto3

from lib.response import ok, bad_request, server_error
from lib.db import (
    transactions_table, buckets_table, merchants_table,
    summaries_table, users_table, scan_all, delete_item,
)

s3 = boto3.client("s3")
BUCKET = os.environ.get("UPLOADS_BUCKET", "")


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    confirmation = body.get("confirmation", "")
    if confirmation != "DELETE":
        return bad_request(
            'Safety check: set "confirmation" to "DELETE" to proceed.'
        )

    claims = (event.get("requestContext", {})
              .get("authorizer", {})
              .get("claims", {}))
    user_id = claims.get("sub", "anonymous")

    deleted = {
        "transactions": 0,
        "buckets": 0,
        "merchants": 0,
        "summaries": 0,
        "s3_objects": 0,
    }

    try:
        # 1. Delete all transactions
        t_table = transactions_table()
        txns = scan_all(t_table)
        for txn in txns:
            delete_item(t_table, {"pk": txn["pk"], "sk": txn["sk"]})
            deleted["transactions"] += 1

        # 2. Delete all buckets
        b_table = buckets_table()
        buckets = scan_all(b_table)
        for b in buckets:
            delete_item(b_table, {"bucketId": b["bucketId"]})
            deleted["buckets"] += 1

        # 3. Delete all merchant memories
        m_table = merchants_table()
        merchants = scan_all(m_table)
        for m in merchants:
            delete_item(m_table, {"merchantName": m["merchantName"]})
            deleted["merchants"] += 1

        # 4. Delete all monthly summaries
        s_table = summaries_table()
        summaries = scan_all(s_table)
        for s in summaries:
            delete_item(s_table, {"monthKey": s["monthKey"]})
            deleted["summaries"] += 1

        # 5. Delete all S3 uploads (raw + normalized)
        if BUCKET:
            try:
                paginator = s3.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=BUCKET, Prefix="uploads/"):
                    objects = page.get("Contents", [])
                    if objects:
                        s3.delete_objects(
                            Bucket=BUCKET,
                            Delete={
                                "Objects": [{"Key": o["Key"]} for o in objects]
                            },
                        )
                        deleted["s3_objects"] += len(objects)
            except Exception as e:
                # Log but don't fail — DynamoDB data is already gone
                print(f"S3 cleanup warning: {e}")

        return ok({
            "message": "All data has been permanently deleted.",
            "deletedBy": user_id,
            "deleted": deleted,
        })

    except Exception as e:
        return server_error(f"Delete failed: {str(e)}")
