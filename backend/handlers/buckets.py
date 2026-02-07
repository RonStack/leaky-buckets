import json


def handler(event, context):
    """List / update buckets."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Buckets handler — not yet implemented"}),
    }
