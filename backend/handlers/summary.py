"""
Summary handler — computes per-category and overall spending totals.

GET /summary?monthKey=2025-06
"""

from datetime import datetime, timezone

from boto3.dynamodb.conditions import Key

from lib.response import ok, bad_request, server_error
from lib.db import (
    users_table, categories_table, transactions_table,
    get_item, query_items,
)


def handler(event, context):
    method = event.get("httpMethod", "GET")
    if method == "GET":
        return _summary(event)
    return bad_request("Unsupported method")


def _summary(event):
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

    params = event.get("queryStringParameters") or {}
    month_key = params.get("monthKey")
    if not month_key:
        month_key = datetime.now(timezone.utc).strftime("%Y-%m")

    try:
        # Fetch categories
        cats = query_items(
            categories_table(),
            Key("householdId").eq(hid),
        )

        # Fetch transactions for the month
        txns = query_items(
            transactions_table(),
            Key("householdId").eq(hid) & Key("sk").begins_with(f"{month_key}#TXN#"),
        )

        # Aggregate spend per category
        spend_by_cat = {}
        for txn in txns:
            cid = txn.get("categoryId", "unknown")
            spend_by_cat[cid] = spend_by_cat.get(cid, 0) + txn.get("amountCents", 0)

        # Build category summaries
        total_limit = 0
        total_spent = 0
        chests = []

        for cat in cats:
            if not cat.get("isActive", True):
                continue
            cid = cat["categoryId"]
            limit_cents = cat.get("monthlyLimitCents", 0)
            spent = spend_by_cat.get(cid, 0)
            remaining = limit_cents - spent
            pct = (remaining / limit_cents * 100) if limit_cents > 0 else 100

            # Determine chest state
            if pct > 60:
                state = "healthy"
            elif pct > 20:
                state = "low"
            elif pct > 0:
                state = "almost-empty"
            else:
                state = "cracked"

            chests.append({
                "categoryId": cid,
                "name": cat.get("name", ""),
                "emoji": cat.get("emoji", "📦"),
                "monthlyLimitCents": limit_cents,
                "spentCents": spent,
                "remainingCents": remaining,
                "percentRemaining": round(pct, 1),
                "state": state,
                "sortOrder": cat.get("sortOrder", 99),
            })

            total_limit += limit_cents
            total_spent += spent

        # Sort by sortOrder
        chests.sort(key=lambda c: c["sortOrder"])

        overall_remaining = total_limit - total_spent
        overall_pct = (overall_remaining / total_limit * 100) if total_limit > 0 else 100

        summary = {
            "monthKey": month_key,
            "totalLimitCents": total_limit,
            "totalSpentCents": total_spent,
            "totalRemainingCents": overall_remaining,
            "percentRemaining": round(overall_pct, 1),
            "transactionCount": len(txns),
            "chests": chests,
        }

        return ok(summary)
    except Exception as e:
        return server_error(str(e))
