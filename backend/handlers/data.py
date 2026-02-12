"""
Data management handler.

DELETE /data  → hard-delete all household data (categories + transactions).
               User and household records remain (use Settings to leave).
"""

from boto3.dynamodb.conditions import Key

from lib.response import ok, bad_request, server_error
from lib.db import (
    users_table, categories_table, transactions_table,
    get_item, query_items, delete_item, scan_all,
)


def handler(event, context):
    method = event.get("httpMethod", "DELETE")
    if method == "DELETE":
        return _delete_all(event)
    return bad_request("Unsupported method")


def _delete_all(event):
    """Delete all categories and transactions for the household."""
    claims = (event.get("requestContext", {})
              .get("authorizer", {})
              .get("claims", {}))
    user_id = claims.get("sub", "anonymous")
    user = get_item(users_table(), {"userId": user_id})
    if not user:
        return bad_request("User not set up. Call GET /me first.")

    hid = user.get("householdId")
    if not hid:
        return bad_request("No household found.")

    deleted_cats = 0
    deleted_txns = 0

    try:
        # Delete all categories
        cat_table = categories_table()
        cats = query_items(cat_table, Key("householdId").eq(hid), limit=1000)
        for cat in cats:
            delete_item(cat_table, {
                "householdId": hid,
                "categoryId": cat["categoryId"],
            })
            deleted_cats += 1

        # Delete all transactions
        txn_table = transactions_table()
        txns = query_items(txn_table, Key("householdId").eq(hid), limit=5000)
        for txn in txns:
            delete_item(txn_table, {
                "householdId": hid,
                "sk": txn["sk"],
            })
            deleted_txns += 1

        return ok({
            "deleted": {
                "categories": deleted_cats,
                "transactions": deleted_txns,
            }
        })
    except Exception as e:
        return server_error(str(e))
