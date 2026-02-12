"""DynamoDB helper utilities for ChestCheck."""

import os
import boto3
from boto3.dynamodb.conditions import Key
from decimal import Decimal
import json

_dynamodb = boto3.resource("dynamodb")


def _table(name_env_var: str):
    """Get a DynamoDB Table resource from an env var name."""
    return _dynamodb.Table(os.environ[name_env_var])


def users_table():
    return _table("USERS_TABLE")


def households_table():
    return _table("HOUSEHOLDS_TABLE")


def categories_table():
    return _table("CATEGORIES_TABLE")


def transactions_table():
    return _table("TRANSACTIONS_TABLE")


# ---- Generic helpers ----

def put_item(table, item: dict) -> dict:
    """Put an item, converting floats to Decimal."""
    table.put_item(Item=_sanitize(item))
    return item


def get_item(table, key: dict) -> dict | None:
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    return _desanitize(item) if item else None


def query_items(table, key_condition, index_name: str | None = None, limit: int = 500) -> list[dict]:
    kwargs = {"KeyConditionExpression": key_condition, "Limit": limit}
    if index_name:
        kwargs["IndexName"] = index_name
    resp = table.query(**kwargs)
    return [_desanitize(i) for i in resp.get("Items", [])]


def update_item(table, key: dict, updates: dict) -> dict:
    """Simple attribute-level update."""
    expr_parts = []
    names = {}
    values = {}
    for i, (k, v) in enumerate(updates.items()):
        token = f"#k{i}"
        val_token = f":v{i}"
        expr_parts.append(f"{token} = {val_token}")
        names[token] = k
        values[val_token] = _sanitize_value(v)
    resp = table.update_item(
        Key=key,
        UpdateExpression="SET " + ", ".join(expr_parts),
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
        ReturnValues="ALL_NEW",
    )
    return _desanitize(resp.get("Attributes", {}))


def delete_item(table, key: dict):
    table.delete_item(Key=key)


def scan_all(table) -> list[dict]:
    items = []
    resp = table.scan()
    items.extend(resp.get("Items", []))
    while "LastEvaluatedKey" in resp:
        resp = table.scan(ExclusiveStartKey=resp["LastEvaluatedKey"])
        items.extend(resp.get("Items", []))
    return [_desanitize(i) for i in items]


def batch_write(table, items: list[dict]):
    with table.batch_writer() as batch:
        for item in items:
            batch.put_item(Item=_sanitize(item))


# ---- Decimal / float conversion ----

def _sanitize_value(v):
    if isinstance(v, float):
        return Decimal(str(v))
    if isinstance(v, int) and not isinstance(v, bool):
        return v
    if isinstance(v, dict):
        return _sanitize(v)
    if isinstance(v, list):
        return [_sanitize_value(i) for i in v]
    return v


def _sanitize(obj: dict) -> dict:
    return {k: _sanitize_value(v) for k, v in obj.items()}


def _desanitize(obj):
    if isinstance(obj, dict):
        return {k: _desanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_desanitize(i) for i in obj]
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    return obj
