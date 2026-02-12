"""
Categories (Treasure Chests) handler.

GET  /categories                → list all categories for household
POST /categories                → create a new category
PUT  /categories/{categoryId}   → update name, emoji, limit, active, sortOrder
"""

import json
import uuid
from datetime import datetime, timezone

from boto3.dynamodb.conditions import Key

from lib.response import ok, created, bad_request, server_error
from lib.db import (
    users_table, categories_table,
    put_item, get_item, query_items, update_item,
)


def handler(event, context):
    method = event.get("httpMethod", "GET")
    if method == "GET":
        return _list(event)
    elif method == "POST":
        return _create(event)
    elif method == "PUT":
        return _update(event)
    return bad_request("Unsupported method")


def _get_household_id(event):
    """Look up the household for the current user."""
    claims = (event.get("requestContext", {})
              .get("authorizer", {})
              .get("claims", {}))
    user_id = claims.get("sub", "anonymous")
    user = get_item(users_table(), {"userId": user_id})
    if not user:
        return None
    return user.get("householdId")


def _list(event):
    """List all categories for the household."""
    hid = _get_household_id(event)
    if not hid:
        return bad_request("User not set up. Call GET /me first.")

    try:
        table = categories_table()
        items = query_items(
            table,
            Key("householdId").eq(hid),
            limit=50,
        )
        # Sort by sortOrder
        items.sort(key=lambda x: x.get("sortOrder", 999))
        return ok({"categories": items})
    except Exception as e:
        return server_error(str(e))


def _create(event):
    """Create a new category."""
    hid = _get_household_id(event)
    if not hid:
        return bad_request("User not set up. Call GET /me first.")

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    name = body.get("name", "").strip()
    if not name:
        return bad_request("name is required")

    emoji = body.get("emoji", "📦")
    limit_cents = body.get("monthlyLimitCents", 0)
    sort_order = body.get("sortOrder", 99)

    try:
        limit_cents = int(limit_cents)
    except (TypeError, ValueError):
        return bad_request("monthlyLimitCents must be an integer")

    cat_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    item = {
        "householdId": hid,
        "categoryId": cat_id,
        "name": name,
        "emoji": emoji,
        "monthlyLimitCents": limit_cents,
        "isActive": True,
        "sortOrder": sort_order,
        "createdAt": timestamp,
    }

    try:
        table = categories_table()
        put_item(table, item)
        return created(item)
    except Exception as e:
        return server_error(str(e))


def _update(event):
    """Update a category (name, emoji, limit, active, sortOrder)."""
    hid = _get_household_id(event)
    if not hid:
        return bad_request("User not set up. Call GET /me first.")

    path_params = event.get("pathParameters") or {}
    cat_id = path_params.get("categoryId")
    if not cat_id:
        return bad_request("categoryId path parameter required")

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    updates = {}
    if "name" in body:
        updates["name"] = body["name"].strip()
    if "emoji" in body:
        updates["emoji"] = body["emoji"]
    if "monthlyLimitCents" in body:
        try:
            updates["monthlyLimitCents"] = int(body["monthlyLimitCents"])
        except (TypeError, ValueError):
            return bad_request("monthlyLimitCents must be an integer")
    if "isActive" in body:
        updates["isActive"] = bool(body["isActive"])
    if "sortOrder" in body:
        updates["sortOrder"] = int(body["sortOrder"])

    if not updates:
        return bad_request("No fields to update")

    try:
        table = categories_table()
        result = update_item(
            table,
            {"householdId": hid, "categoryId": cat_id},
            updates,
        )
        return ok(result)
    except Exception as e:
        return server_error(str(e))
