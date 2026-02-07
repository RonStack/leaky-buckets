import json


def handler(event, context):
    """Handle CSV upload (bank / credit card statements)."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Upload handler — not yet implemented"}),
    }
