"""
Month handler —
  GET    /month/{monthKey}            → get monthly summary with bucket totals
  POST   /month/{monthKey}/lock       → lock the month (transactions become immutable)
  DELETE /month/{monthKey}/expenses   → delete all expense transactions for a month
  DELETE /month/{monthKey}/income     → delete all paystub/income data for a month
"""

import json
import os

import boto3
from boto3.dynamodb.conditions import Key

from lib.response import ok, bad_request, not_found, conflict, server_error
from lib.db import (
    transactions_table, buckets_table, summaries_table,
    query_items, scan_all, put_item, get_item, update_item, delete_item,
)


def handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "")
    path_params = event.get("pathParameters") or {}
    month_key = path_params.get("monthKey")

    if not month_key:
        return bad_request("monthKey path parameter required (e.g., 2026-01)")

    if method == "GET":
        return _get_summary(month_key)
    elif method == "POST" and path.endswith("/lock"):
        return _lock_month(month_key, event)
    elif method == "DELETE" and path.endswith("/expenses"):
        return _delete_expenses(month_key, event)
    elif method == "DELETE" and path.endswith("/income"):
        return _delete_income(month_key, event)
    return bad_request("Unsupported method")


def _get_summary(month_key: str):
    """Build or retrieve the monthly summary with bucket breakdown."""
    try:
        # Check if we have a cached/locked summary
        s_table = summaries_table()
        existing = get_item(s_table, {"monthKey": month_key})
        if existing and existing.get("locked"):
            return ok(existing)

        # Build live summary from transactions
        t_table = transactions_table()
        transactions = query_items(
            t_table,
            Key("monthKey").eq(month_key),
            index_name="byMonth",
            limit=2000,
        )

        if not transactions:
            return ok({
                "monthKey": month_key,
                "locked": False,
                "totalSpent": 0,
                "totalIncome": 0,
                "transactionCount": 0,
                "needsReview": 0,
                "buckets": [],
            })

        # Get bucket definitions
        b_table = buckets_table()
        all_buckets = scan_all(b_table)
        bucket_map = {b["name"]: b for b in all_buckets}

        # Aggregate by bucket
        bucket_totals = {}
        total_spent = 0
        total_income = 0
        needs_review = 0

        for txn in transactions:
            amount = txn.get("amount", 0)
            bucket_name = txn.get("bucket")

            if amount < 0:
                total_spent += abs(amount)
            else:
                total_income += amount

            if not bucket_name or txn.get("confidence", 0) < 0.7:
                needs_review += 1

            if bucket_name:
                if bucket_name not in bucket_totals:
                    bucket_totals[bucket_name] = {"spent": 0, "count": 0}
                if amount < 0:
                    bucket_totals[bucket_name]["spent"] += abs(amount)
                bucket_totals[bucket_name]["count"] += 1

        # Build bucket summaries with status (🟢🟡🔴)
        bucket_summaries = []
        for b in sorted(all_buckets, key=lambda x: x.get("displayOrder", 99)):
            name = b["name"]
            totals = bucket_totals.get(name, {"spent": 0, "count": 0})
            target = b.get("monthlyTarget", 0)

            # Determine status
            if target <= 0:
                status = "stable"  # No target set
            elif totals["spent"] <= target * 0.8:
                status = "stable"       # 🟢 Under 80% of target
            elif totals["spent"] <= target:
                status = "dripping"     # 🟡 80-100% of target
            else:
                status = "overflowing"  # 🔴 Over target

            bucket_summaries.append({
                "bucketId": b["bucketId"],
                "name": name,
                "emoji": b.get("emoji", "🪣"),
                "spent": round(totals["spent"], 2),
                "target": target,
                "count": totals["count"],
                "status": status,
            })

        summary = {
            "monthKey": month_key,
            "locked": False,
            "totalSpent": round(total_spent, 2),
            "totalIncome": round(total_income, 2),
            "transactionCount": len(transactions),
            "needsReview": needs_review,
            "buckets": bucket_summaries,
        }

        return ok(summary)

    except Exception as e:
        return server_error(str(e))


def _delete_expenses(month_key: str, event):
    """
    Delete all expense transactions for a given month.
    Requires { "confirmation": "DELETE" } in the body.
    """
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    if body.get("confirmation") != "DELETE":
        return bad_request('Safety check: set "confirmation" to "DELETE" to proceed.')

    try:
        # Check if month is locked
        s_table = summaries_table()
        existing = get_item(s_table, {"monthKey": month_key})
        if existing and existing.get("locked"):
            return conflict(f"{month_key} is locked — unlock it first to delete data.")

        t_table = transactions_table()
        transactions = query_items(
            t_table,
            Key("monthKey").eq(month_key),
            index_name="byMonth",
            limit=5000,
        )

        if not transactions:
            return not_found(f"No transactions found for {month_key}")

        deleted_count = 0
        for txn in transactions:
            delete_item(t_table, {"pk": txn["pk"], "sk": txn["sk"]})
            deleted_count += 1

        # Clear cached summary if it exists
        if existing:
            delete_item(s_table, {"monthKey": month_key})

        return ok({
            "message": f"Deleted {deleted_count} expense transaction(s) for {month_key}.",
            "monthKey": month_key,
            "deletedCount": deleted_count,
        })

    except Exception as e:
        return server_error(str(e))


def _delete_income(month_key: str, event):
    """
    Delete all paystub/income data for a given month.
    Requires { "confirmation": "DELETE" } in the body.
    """
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    if body.get("confirmation") != "DELETE":
        return bad_request('Safety check: set "confirmation" to "DELETE" to proceed.')

    try:
        _dynamodb = boto3.resource("dynamodb")
        p_table = _dynamodb.Table(os.environ.get("PAYSTUBS_TABLE", ""))

        paystubs = query_items(
            p_table,
            Key("monthKey").eq(month_key),
            index_name="byMonth",
            limit=500,
        )

        if not paystubs:
            return not_found(f"No paystubs found for {month_key}")

        # Delete S3 files and DynamoDB records
        s3 = boto3.client("s3")
        uploads_bucket = os.environ.get("UPLOADS_BUCKET", "")
        deleted_count = 0

        for stub in paystubs:
            # Delete S3 raw file if exists
            raw_key = stub.get("rawFileKey", "")
            if raw_key and uploads_bucket:
                try:
                    s3.delete_object(Bucket=uploads_bucket, Key=raw_key)
                except Exception as e:
                    print(f"S3 delete warning for {raw_key}: {e}")

            delete_item(p_table, {"paystubId": stub["paystubId"]})
            deleted_count += 1

        return ok({
            "message": f"Deleted {deleted_count} paystub(s) for {month_key}.",
            "monthKey": month_key,
            "deletedCount": deleted_count,
        })

    except Exception as e:
        return server_error(str(e))


def _lock_month(month_key: str, event):
    """
    Lock a month — transactions become immutable, summary is finalized.
    """
    claims = (event.get("requestContext", {})
              .get("authorizer", {})
              .get("claims", {}))
    user_id = claims.get("sub", "anonymous")

    try:
        # Check for unreviewed transactions
        t_table = transactions_table()
        transactions = query_items(
            t_table,
            Key("monthKey").eq(month_key),
            index_name="byMonth",
            limit=2000,
        )

        if not transactions:
            return not_found(f"No transactions found for {month_key}")

        unreviewed = [t for t in transactions if not t.get("bucket")]
        if unreviewed:
            return bad_request(
                f"Cannot lock — {len(unreviewed)} transaction(s) still uncategorized. "
                "Review them first!"
            )

        # Check if already locked
        s_table = summaries_table()
        existing = get_item(s_table, {"monthKey": month_key})
        if existing and existing.get("locked"):
            return conflict(f"{month_key} is already locked")

        # Lock all transactions
        for txn in transactions:
            update_item(
                t_table,
                {"pk": txn["pk"], "sk": txn["sk"]},
                {"locked": True},
            )

        # Build and save the finalized summary
        from datetime import datetime, timezone
        summary_resp = _get_summary(month_key)
        summary_body = json.loads(summary_resp["body"])
        summary_body["locked"] = True
        summary_body["lockedBy"] = user_id
        summary_body["lockedAt"] = datetime.now(timezone.utc).isoformat() + "Z"

        put_item(s_table, summary_body)

        return ok(summary_body)

    except Exception as e:
        return server_error(str(e))
