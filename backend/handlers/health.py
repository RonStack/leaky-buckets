import json
import datetime


def handler(event, context):
    """Health check — unauthenticated, returns 200."""
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "status": "healthy",
            "app": "leaky-buckets",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        }),
    }
