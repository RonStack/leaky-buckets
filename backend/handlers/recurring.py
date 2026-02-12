"""
Recurring bills handler — manage recurring bill definitions and apply them to months.

POST   /recurring-bills             → add a new recurring bill
GET    /recurring-bills              → list all recurring bills
PUT    /recurring-bills/{billId}     → edit a bill
DELETE /recurring-bills/{billId}     → delete a bill
POST   /recurring-bills/apply       → apply all bills to a month as live expenses
"""

import json
import uuid
from datetime import datetime, timezone

from boto3.dynamodb.conditions import Key

from lib.response import ok, created, bad_request, server_error
from lib.db import (
    recurring_bills_table, live_expenses_table,
    put_item, query_items, update_item, delete_item, get_item,
)


def handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "")

    if method == "POST" and path.endswith("/apply"):
        return _apply_bills(event)
    elif method == "POST":
        return _add_bill(event)
    elif method == "GET":
        return _list_bills(event)
    elif method == "PUT":
        return _update_bill(event)
    elif method == "DELETE":
        return _delete_bill(event)
    return bad_request("Unsupported method")


def _get_user_id(event):
    claims = (event.get("requestContext", {})
              .get("authorizer", {})
              .get("claims", {}))
    return claims.get("sub", "anonymous")


def _add_bill(event):
    """Add a new recurring bill definition."""
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    name = body.get("name", "").strip()
    amount = body.get("amount")
    bucket_id = body.get("bucketId")
    bucket_name = body.get("bucketName", "")

    if not name:
        return bad_request("name is required")
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
    bill_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    item = {
        "pk": f"USER#{user_id}",
        "sk": f"BILL#{bill_id}",
        "billId": bill_id,
        "userId": user_id,
        "name": name,
        "amount": amount,
        "bucketId": bucket_id,
        "bucketName": bucket_name,
        "createdAt": timestamp,
    }

    try:
        table = recurring_bills_table()
        put_item(table, item)
        return created(item)
    except Exception as e:
        return server_error(str(e))


def _list_bills(event):
    """List all recurring bills for the current user."""
    user_id = _get_user_id(event)

    try:
        table = recurring_bills_table()
        items = query_items(
            table,
            Key("pk").eq(f"USER#{user_id}") & Key("sk").begins_with("BILL#"),
            limit=100,
        )
        return ok({
            "bills": items,
            "count": len(items),
        })
    except Exception as e:
        return server_error(str(e))


def _update_bill(event):
    """Update an existing recurring bill."""
    path_params = event.get("pathParameters") or {}
    bill_id = path_params.get("billId")
    if not bill_id:
        return bad_request("billId path parameter required")

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    user_id = _get_user_id(event)

    updates = {}
    if "name" in body:
        updates["name"] = body["name"].strip()
    if "amount" in body:
        try:
            updates["amount"] = float(body["amount"])
        except (TypeError, ValueError):
            return bad_request("amount must be a number")
    if "bucketId" in body:
        updates["bucketId"] = body["bucketId"]
    if "bucketName" in body:
        updates["bucketName"] = body["bucketName"]

    if not updates:
        return bad_request("No fields to update")

    try:
        table = recurring_bills_table()
        result = update_item(
            table,
            {"pk": f"USER#{user_id}", "sk": f"BILL#{bill_id}"},
            updates,
        )
        return ok(result)
    except Exception as e:
        return server_error(str(e))


def _delete_bill(event):
    """Delete a recurring bill."""
    path_params = event.get("pathParameters") or {}
    bill_id = path_params.get("billId")
    if not bill_id:
        return bad_request("billId path parameter required")

    user_id = _get_user_id(event)

    try:
        table = recurring_bills_table()
        delete_item(table, {"pk": f"USER#{user_id}", "sk": f"BILL#{bill_id}"})
        return ok({"deleted": bill_id})
    except Exception as e:
        return server_error(str(e))


def _apply_bills(event):
    """
    Apply all recurring bills to a specific month as live expenses.
    Skips bills that have already been applied (by recurringBillId).
    """
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    month_key = body.get("monthKey")
    if not month_key:
        return bad_request("monthKey is required (e.g., 2026-02)")

    user_id = _get_user_id(event)

    try:
        # 1. Get all recurring bills for this user
        rb_table = recurring_bills_table()
        bills = query_items(
            rb_table,
            Key("pk").eq(f"USER#{user_id}") & Key("sk").begins_with("BILL#"),
            limit=100,
        )

        if not bills:
            return ok({"applied": 0, "skipped": 0, "message": "No recurring bills defined."})

        # 2. Get existing live expenses for this month to check for duplicates
        le_table = live_expenses_table()
        existing = query_items(
            le_table,
            Key("monthKey").eq(month_key),
            index_name="byMonth",
            limit=1000,
        )
        # Filter to this user's recurring expenses
        applied_bill_ids = set()
        for exp in existing:
            if exp.get("userId") == user_id and exp.get("source") == "recurring":
                rbid = exp.get("recurringBillId")
                if rbid:
                    applied_bill_ids.add(rbid)

        # 3. Create live expenses for each bill not yet applied
        now = datetime.now(timezone.utc)
        timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Use the 1st of the month as the date
        date_str = f"{month_key}-01"

        applied = 0
        skipped = 0

        for bill in bills:
            bill_id = bill.get("billId", "")
            if bill_id in applied_bill_ids:
                skipped += 1
                continue

            expense_id = str(uuid.uuid4())
            item = {
                "pk": f"USER#{user_id}",
                "sk": f"EXP#{date_str}#{expense_id}",
                "expenseId": expense_id,
                "userId": user_id,
                "amount": bill.get("amount", 0),
                "bucketId": bill.get("bucketId", ""),
                "bucketName": bill.get("bucketName", ""),
                "note": f"🔁 {bill.get('name', 'Recurring')}",
                "date": date_str,
                "monthKey": month_key,
                "createdAt": timestamp,
                "source": "recurring",
                "recurringBillId": bill_id,
            }
            put_item(le_table, item)
            applied += 1

        return ok({
            "applied": applied,
            "skipped": skipped,
            "total": len(bills),
            "message": f"Applied {applied} recurring bill(s) to {month_key}."
                + (f" {skipped} already applied." if skipped else ""),
        })

    except Exception as e:
        return server_error(str(e))
