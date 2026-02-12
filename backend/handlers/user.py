"""
User + Household handler.

GET  /me               → get or auto-create user + household
POST /household/join    → join an existing household by code
"""

import json
import uuid
from datetime import datetime, timezone

from boto3.dynamodb.conditions import Key

from lib.response import ok, bad_request, server_error
from lib.db import users_table, households_table, categories_table, put_item, get_item

# Default treasure chests for new households
DEFAULT_CATEGORIES = [
    {"name": "Groceries",      "emoji": "🛒", "limitCents": 60000, "sortOrder": 1},
    {"name": "Dining",         "emoji": "🍽️", "limitCents": 30000, "sortOrder": 2},
    {"name": "Entertainment",  "emoji": "🎬", "limitCents": 15000, "sortOrder": 3},
    {"name": "Shopping",       "emoji": "🛍️", "limitCents": 20000, "sortOrder": 4},
    {"name": "Transport",      "emoji": "⛽", "limitCents": 15000, "sortOrder": 5},
    {"name": "Health",         "emoji": "💊", "limitCents": 10000, "sortOrder": 6},
    {"name": "Subscriptions",  "emoji": "📱", "limitCents": 10000, "sortOrder": 7},
    {"name": "Miscellaneous",  "emoji": "📦", "limitCents": 10000, "sortOrder": 8},
]


def handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "")

    if method == "GET" and path.endswith("/me"):
        return _get_me(event)
    elif method == "POST" and "join" in path:
        return _join_household(event)
    return bad_request("Unsupported method")


def _get_user_id(event):
    claims = (event.get("requestContext", {})
              .get("authorizer", {})
              .get("claims", {}))
    return claims.get("sub", "anonymous")


def _get_user_email(event):
    claims = (event.get("requestContext", {})
              .get("authorizer", {})
              .get("claims", {}))
    return claims.get("email", "")


def _get_me(event):
    """Get current user profile. Auto-creates user + household on first call."""
    user_id = _get_user_id(event)
    email = _get_user_email(event)

    try:
        u_table = users_table()
        user = get_item(u_table, {"userId": user_id})

        if user:
            # Existing user — fetch household
            h_table = households_table()
            household = get_item(h_table, {"householdId": user["householdId"]})
            return ok({
                "user": user,
                "household": household,
            })

        # New user — create household + user + default categories
        household_id = str(uuid.uuid4())[:8]  # Short code for easy sharing
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Create household
        h_table = households_table()
        household = {
            "householdId": household_id,
            "members": [user_id],
            "memberEmails": [email],
            "createdAt": timestamp,
        }
        put_item(h_table, household)

        # Create user
        user = {
            "userId": user_id,
            "email": email,
            "householdId": household_id,
            "displayName": email.split("@")[0],
            "createdAt": timestamp,
        }
        put_item(u_table, user)

        # Seed default categories
        c_table = categories_table()
        for cat in DEFAULT_CATEGORIES:
            cat_id = str(uuid.uuid4())
            put_item(c_table, {
                "householdId": household_id,
                "categoryId": cat_id,
                "name": cat["name"],
                "emoji": cat["emoji"],
                "monthlyLimitCents": cat["limitCents"],
                "isActive": True,
                "sortOrder": cat["sortOrder"],
                "createdAt": timestamp,
            })

        return ok({
            "user": user,
            "household": household,
            "isNew": True,
        })

    except Exception as e:
        return server_error(str(e))


def _join_household(event):
    """Join an existing household by householdId code."""
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    household_id = body.get("householdId", "").strip()
    if not household_id:
        return bad_request("householdId is required")

    user_id = _get_user_id(event)
    email = _get_user_email(event)

    try:
        h_table = households_table()
        household = get_item(h_table, {"householdId": household_id})
        if not household:
            return bad_request("Household not found")

        members = household.get("members", [])
        if user_id in members:
            return ok({"message": "Already a member", "household": household})

        if len(members) >= 2:
            return bad_request("Household already has 2 members (max for v1)")

        # Add user to household
        members.append(user_id)
        emails = household.get("memberEmails", [])
        emails.append(email)

        from lib.db import update_item
        update_item(h_table, {"householdId": household_id}, {
            "members": members,
            "memberEmails": emails,
        })

        # Update or create user record
        u_table = users_table()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        put_item(u_table, {
            "userId": user_id,
            "email": email,
            "householdId": household_id,
            "displayName": email.split("@")[0],
            "createdAt": timestamp,
        })

        household["members"] = members
        household["memberEmails"] = emails
        return ok({"message": "Joined household", "household": household})

    except Exception as e:
        return server_error(str(e))
