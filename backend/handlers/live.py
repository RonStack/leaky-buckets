"""
Live expenses handler — manually record expenses in real-time.

POST   /live-expenses             → add a new live expense
GET    /live-expenses?monthKey=   → list live expenses for a month
PUT    /live-expenses/{expenseId} → edit an existing expense
DELETE /live-expenses/{expenseId} → delete an expense
"""

import json
import uuid
from datetime import datetime, timezone

from boto3.dynamodb.conditions import Key

from lib.response import ok, created, bad_request, not_found, server_error
from lib.db import live_expenses_table, put_item, query_items, update_item, delete_item, get_item


def handler(event, context):
    method = event.get("httpMethod", "GET")

    if method == "POST":
        return _add_expense(event)
    elif method == "GET":
        return _list_expenses(event)
    elif method == "PUT":
        return _update_expense(event)
    elif method == "DELETE":
        return _delete_expense(event)
    return bad_request("Unsupported method")


def _get_user_id(event):
    claims = (event.get("requestContext", {})
              .get("authorizer", {})
              .get("claims", {}))
    return claims.get("sub", "anonymous")


def _add_expense(event):
    """Record a new live expense."""
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    amount = body.get("amount")
    bucket_id = body.get("bucketId")
    bucket_name = body.get("bucketName", "")

    if amount is None:
        return bad_request("amount is required")
    if not bucket_id:
        return bad_request("bucketId is required")

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return bad_request("amount must be a number")

    if amount <= 0:
        return bad_request("amount must be positive")

    user_id = _get_user_id(event)
    expense_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    date_str = body.get("date", now.strftime("%Y-%m-%d"))
    month_key = date_str[:7]  # e.g. "2026-02"
    note = body.get("note", "")

    item = {
        "pk": f"USER#{user_id}",
        "sk": f"EXP#{date_str}#{expense_id}",
        "expenseId": expense_id,
        "userId": user_id,
        "amount": amount,
        "bucketId": bucket_id,
        "bucketName": bucket_name,
        "note": note,
        "date": date_str,
        "monthKey": month_key,
        "createdAt": timestamp,
    }

    try:
        table = live_expenses_table()
        put_item(table, item)
        return created(item)
    except Exception as e:
        return server_error(str(e))


def _list_expenses(event):
    """List live expenses for a given month."""
    params = event.get("queryStringParameters") or {}
    month_key = params.get("monthKey")
    if not month_key:
        return bad_request("monthKey query parameter is required (e.g., 2026-02)")

    user_id = _get_user_id(event)

    try:
        table = live_expenses_table()
        items = query_items(
            table,
            Key("monthKey").eq(month_key),
            index_name="byMonth",
            limit=1000,
        )
        # Filter to current user (GSI doesn't have userId as key)
        user_items = [i for i in items if i.get("userId") == user_id]
        # Sort by date descending (newest first)
        user_items.sort(key=lambda x: x.get("sk", ""), reverse=True)

        # Compute totals per bucket
        bucket_totals = {}
        for item in user_items:
            bid = item.get("bucketId", "unknown")
            bname = item.get("bucketName", bid)
            if bid not in bucket_totals:
                bucket_totals[bid] = {"bucketId": bid, "bucketName": bname, "total": 0, "count": 0}
            bucket_totals[bid]["total"] += item.get("amount", 0)
            bucket_totals[bid]["count"] += 1

        total_spent = sum(i.get("amount", 0) for i in user_items)

        return ok({
            "monthKey": month_key,
            "expenses": user_items,
            "totalSpent": round(total_spent, 2),
            "count": len(user_items),
            "bucketTotals": list(bucket_totals.values()),
        })
    except Exception as e:
        return server_error(str(e))


def _update_expense(event):
    """Update an existing live expense."""
    path_params = event.get("pathParameters") or {}
    expense_id = path_params.get("expenseId")
    if not expense_id:
        return bad_request("expenseId path parameter required")

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    user_id = _get_user_id(event)
    pk = body.get("pk", f"USER#{user_id}")
    sk = body.get("sk")

    if not sk:
        return bad_request("sk is required to identify the expense")

    updates = {}
    if "amount" in body:
        try:
            updates["amount"] = float(body["amount"])
        except (TypeError, ValueError):
            return bad_request("amount must be a number")
    if "bucketId" in body:
        updates["bucketId"] = body["bucketId"]
    if "bucketName" in body:
        updates["bucketName"] = body["bucketName"]
    if "note" in body:
        updates["note"] = body["note"]
    if "date" in body:
        updates["date"] = body["date"]
        updates["monthKey"] = body["date"][:7]

    if not updates:
        return bad_request("No fields to update")

    try:
        table = live_expenses_table()
        result = update_item(table, {"pk": pk, "sk": sk}, updates)
        return ok(result)
    except Exception as e:
        return server_error(str(e))


def _delete_expense(event):
    """Delete a live expense."""
    path_params = event.get("pathParameters") or {}
    expense_id = path_params.get("expenseId")
    if not expense_id:
        return bad_request("expenseId path parameter required")

    user_id = _get_user_id(event)
    params = event.get("queryStringParameters") or {}
    sk = params.get("sk")

    if not sk:
        return bad_request("sk query parameter required")

    pk = f"USER#{user_id}"

    try:
        table = live_expenses_table()
        delete_item(table, {"pk": pk, "sk": sk})
        return ok({"deleted": expense_id})
    except Exception as e:
        return server_error(str(e))
