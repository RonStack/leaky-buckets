"""
Buckets handler —
  GET   /buckets              → list all buckets with targets
  PUT   /buckets/{bucketId}   → update a bucket's monthly target
  POST  /buckets/seed         → seed default buckets (one-time setup)
"""

import json
import uuid

from lib.response import ok, bad_request, not_found, server_error
from lib.db import buckets_table, scan_all, get_item, put_item, update_item
from lib.categorizer import BUCKETS as DEFAULT_BUCKET_NAMES


def handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "")

    if method == "GET":
        return _list_buckets()
    elif method == "PUT":
        return _update_bucket(event)
    elif method == "POST" and path.endswith("/seed"):
        return _seed_buckets()
    return bad_request("Unsupported method")


def _list_buckets():
    """Return all buckets with their targets."""
    try:
        table = buckets_table()
        items = scan_all(table)
        # Sort by display order
        items.sort(key=lambda b: b.get("displayOrder", 99))
        return ok({"buckets": items})
    except Exception as e:
        return server_error(str(e))


def _update_bucket(event):
    """Update a bucket's monthly target or name."""
    path_params = event.get("pathParameters") or {}
    bucket_id = path_params.get("bucketId")
    if not bucket_id:
        return bad_request("bucketId path parameter required")

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    try:
        table = buckets_table()
        existing = get_item(table, {"bucketId": bucket_id})
        if not existing:
            return not_found(f"Bucket {bucket_id} not found")

        updates = {}
        if "monthlyTarget" in body:
            updates["monthlyTarget"] = float(body["monthlyTarget"])
        if "name" in body:
            updates["name"] = body["name"]
        if "emoji" in body:
            updates["emoji"] = body["emoji"]

        if not updates:
            return bad_request("Nothing to update — provide monthlyTarget, name, or emoji")

        updated = update_item(table, {"bucketId": bucket_id}, updates)
        return ok(updated)

    except Exception as e:
        return server_error(str(e))


def _seed_buckets():
    """Create default buckets if none exist, or add any missing ones."""
    try:
        table = buckets_table()
        existing = scan_all(table)
        existing_names = {b["name"] for b in existing}

        emojis = ["🏠", "🛒", "🛍️", "☕", "📱", "💊", "🚗", "🎉", "💥"]

        if not existing:
            # First-time seed — create all buckets
            buckets = []
            for i, name in enumerate(DEFAULT_BUCKET_NAMES):
                bucket = {
                    "bucketId": str(uuid.uuid4()),
                    "name": name,
                    "emoji": emojis[i] if i < len(emojis) else "🪣",
                    "monthlyTarget": 0,
                    "displayOrder": i,
                }
                put_item(table, bucket)
                buckets.append(bucket)
            return ok({"message": "Buckets seeded", "buckets": buckets})

        # Add any new buckets that don't exist yet
        added = []
        for i, name in enumerate(DEFAULT_BUCKET_NAMES):
            if name not in existing_names:
                bucket = {
                    "bucketId": str(uuid.uuid4()),
                    "name": name,
                    "emoji": emojis[i] if i < len(emojis) else "🪣",
                    "monthlyTarget": 0,
                    "displayOrder": i,
                }
                put_item(table, bucket)
                added.append(bucket)

        if added:
            return ok({"message": f"Added {len(added)} new bucket(s)", "added": added, "count": len(existing) + len(added)})

        return ok({"message": "Buckets already seeded", "count": len(existing)})

    except Exception as e:
        return server_error(str(e))
