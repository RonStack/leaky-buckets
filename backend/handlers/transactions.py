import json


def handler(event, context):
    """List / review transactions."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"message": "Transactions handler — not yet implemented"}),
    }
