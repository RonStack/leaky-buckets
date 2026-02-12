"""
Transactions handler — the core spend-logging endpoint.

POST   /transactions                    → log a spend
GET    /transactions?monthKey=2025-06   → list transactions for a month
DELETE /transactions/{transactionId}    → remove a transaction
"""

import json
import uuid
from datetime import datetime, timezone

from boto3.dynamodb.conditions import Key

from lib.response import ok, created, bad_request, not_found, server_error
from lib.db import (
    users_table, transactions_table,
    put_item, get_item, query_items, delete_item,
)


def handler(event, context):
    method = event.get("httpMethod", "GET")
    if method == "POST":
        return _create(event)
    elif method == "GET":
        return _list(event)
    elif method == "DELETE":
        return _delete(event)
    return bad_request("Unsupported method")


def _user_info(event):
    """Return (userId, householdId) for the caller."""
    claims = (event.get("requestContext", {})
              .get("authorizer", {})
              .get("claims", {}))
    user_id = claims.get("sub", "anonymous")
    user = get_item(users_table(), {"userId": user_id})
    if not user:
        return user_id, None
    return user_id, user.get("householdId")


def _create(event):
    """Log a spend.  Body: {amountCents, categoryId, note?}"""
    user_id, hid = _user_info(event)
    if not hid:
        return bad_request("User not set up. Call GET /me first.")

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    amount = body.get("amountCents")
    category_id = body.get("categoryId", "").strip()
    note = body.get("note", "").strip()

    if amount is None:
        return bad_request("amountCents is required")
    try:
        amount = int(amount)
    except (TypeError, ValueError):
        return bad_request("amountCents must be an integer")
    if amount <= 0:
        return bad_request("amountCents must be positive")

    if not category_id:
        return bad_request("categoryId is required")

    now = datetime.now(timezone.utc)
    created_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    month_key = now.strftime("%Y-%m")
    txn_id = str(uuid.uuid4())

    # SK format: {monthKey}#TXN#{createdAt}#{txnId}
    sk = f"{month_key}#TXN#{created_at}#{txn_id}"

    item = {
        "householdId": hid,
        "sk": sk,
        "transactionId": txn_id,
        "amountCents": amount,
        "categoryId": category_id,
        "note": note,
        "userId": user_id,
        "monthKey": month_key,
        "createdAt": created_at,
    }

    try:
        table = transactions_table()
        put_item(table, item)
        return created(item)
    except Exception as e:
        return server_error(str(e))


def _list(event):
    """List transactions for a month.  QS: monthKey=2025-06"""
    _, hid = _user_info(event)
    if not hid:
        return bad_request("User not set up. Call GET /me first.")

    params = event.get("queryStringParameters") or {}
    month_key = params.get("monthKey")
    if not month_key:
        # Default to current month
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")

    try:
        table = transactions_table()
        items = query_items(
            table,
            Key("householdId").eq(hid) & Key("sk").begins_with(f"{month_key}#TXN#"),
        )
        # Sort newest first
        items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
        return ok({"transactions": items, "monthKey": month_key})
    except Exception as e:
        return server_error(str(e))


def _delete(event):
    """Delete a transaction by transactionId (needs household context)."""
    _, hid = _user_info(event)
    if not hid:
        return bad_request("User not set up. Call GET /me first.")

    path_params = event.get("pathParameters") or {}
    txn_id = path_params.get("transactionId")
    if not txn_id:
        return bad_request("transactionId path parameter required")

    try:
        # We need the SK to delete.  Query for matching txnId.
        table = transactions_table()
        items = query_items(
            table,
            Key("householdId").eq(hid),
        )
        target = next((i for i in items if i.get("transactionId") == txn_id), None)
        if not target:
            return not_found("Transaction not found")

        delete_item(table, {"householdId": hid, "sk": target["sk"]})
        return ok({"deleted": txn_id})
    except Exception as e:
        return server_error(str(e))
