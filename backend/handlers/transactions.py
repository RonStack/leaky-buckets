"""
Transactions handler —
  GET  /transactions?monthKey=2026-01  → list transactions for a month
  PUT  /transactions/{transactionId}   → update category, remember merchant
"""

import json

from boto3.dynamodb.conditions import Key

from lib.response import ok, bad_request, not_found, server_error
from lib.db import transactions_table, query_items, update_item, get_item
from lib.categorizer import remember_merchant


def handler(event, context):
    method = event.get("httpMethod", "GET")
    if method == "GET":
        return _list_transactions(event)
    elif method == "PUT":
        return _update_transaction(event)
    return bad_request("Unsupported method")


def _list_transactions(event):
    """List transactions for a given month."""
    params = event.get("queryStringParameters") or {}
    month_key = params.get("monthKey")
    if not month_key:
        return bad_request("monthKey query parameter is required (e.g., 2026-01)")

    claims = (event.get("requestContext", {})
              .get("authorizer", {})
              .get("claims", {}))
    user_id = claims.get("sub", "anonymous")

    try:
        table = transactions_table()
        # Query by month using the GSI
        items = query_items(
            table,
            Key("monthKey").eq(month_key),
            index_name="byMonth",
            limit=1000,
        )

        # Split into reviewed / needs-review
        needs_review = []
        categorized = []
        for item in items:
            if not item.get("bucket") or item.get("confidence", 0) < 0.7:
                needs_review.append(item)
            else:
                categorized.append(item)

        return ok({
            "monthKey": month_key,
            "total": len(items),
            "needsReview": needs_review,
            "categorized": categorized,
        })
    except Exception as e:
        return server_error(str(e))


def _update_transaction(event):
    """
    Update a transaction's bucket assignment.
    If rememberMerchant=true, saves to merchant memory permanently.
    """
    path_params = event.get("pathParameters") or {}
    txn_id = path_params.get("transactionId")
    if not txn_id:
        return bad_request("transactionId path parameter required")

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    bucket = body.get("bucket")
    if not bucket:
        return bad_request("bucket is required")

    claims = (event.get("requestContext", {})
              .get("authorizer", {})
              .get("claims", {}))
    user_id = claims.get("sub", "anonymous")

    try:
        table = transactions_table()

        # We need the full key (pk + sk) to update — scan for the txn by ID
        # In practice we'd pass pk+sk from frontend; for now do a targeted query
        items = query_items(
            table,
            Key("monthKey").begins_with("") & Key("sk").begins_with(f"TXN#"),
            index_name="byMonth",
        )
        # Find matching transaction
        target = None
        for item in items:
            if item.get("transactionId") == txn_id:
                target = item
                break

        if not target:
            return not_found(f"Transaction {txn_id} not found")

        if target.get("locked"):
            return bad_request("Cannot modify a locked transaction")

        # Update the transaction
        updates = {
            "bucket": bucket,
            "confidence": 1.0,
            "categorizationSource": "user_override",
            "categorizationReasoning": f"Manually set to '{bucket}' by user",
        }

        updated = update_item(
            table,
            {"pk": target["pk"], "sk": target["sk"]},
            updates,
        )

        # Remember merchant if requested
        if body.get("rememberMerchant", False):
            remember_merchant(target["description"], bucket)

        return ok({
            "transactionId": txn_id,
            "bucket": bucket,
            "merchantRemembered": body.get("rememberMerchant", False),
        })

    except Exception as e:
        return server_error(str(e))
