"""Standardised API Gateway response helpers."""

import json


CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "https://leakingbuckets.goronny.com",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
}


def ok(body: dict | list, status: int = 200) -> dict:
    return {
        "statusCode": status,
        "headers": CORS_HEADERS,
        "body": json.dumps(body, default=str),
    }


def created(body: dict) -> dict:
    return ok(body, 201)


def bad_request(message: str = "Bad request") -> dict:
    return ok({"error": message}, 400)


def not_found(message: str = "Not found") -> dict:
    return ok({"error": message}, 404)


def conflict(message: str = "Conflict") -> dict:
    return ok({"error": message}, 409)


def server_error(message: str = "Internal server error") -> dict:
    return ok({"error": message}, 500)
