import json


def handler(event, context):
    """Monthly summary + lock month."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Month handler — not yet implemented"}),
    }
