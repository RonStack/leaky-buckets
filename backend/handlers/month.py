"""
Month handler —
  GET   /month/{monthKey}       → get monthly summary with bucket totals
  POST  /month/{monthKey}/lock  → lock the month (transactions become immutable)
"""

import json

from boto3.dynamodb.conditions import Key

from lib.response import ok, bad_request, not_found, conflict, server_error
from lib.db import (
    transactions_table, buckets_table, summaries_table,
    query_items, scan_all, put_item, get_item, update_item,
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
