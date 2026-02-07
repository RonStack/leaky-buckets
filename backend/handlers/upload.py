"""
Upload handler — receives CSV, PDF, or image files, stores raw in S3,
normalises, categorizes, and stores transactions in DynamoDB.

POST /upload
Body (CSV):  { "fileName": "...", "source": "bank"|"credit_card", "csvContent": "..." }
Body (PDF/image): { "fileName": "...", "source": "bank"|"credit_card", "fileContent": "<base64>" }
"""

import json
import os
import uuid
import hashlib
from datetime import datetime, timezone

import boto3

from lib.response import ok, bad_request, server_error
from lib.normalizer import normalize_csv
from lib.statement_parser import parse_statement
from lib.categorizer import categorize_batch
from lib.db import transactions_table, put_item, batch_write

s3 = boto3.client("s3")
BUCKET = os.environ.get("UPLOADS_BUCKET", "")


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    file_name = body.get("fileName", "upload.csv")
    source = body.get("source", "bank")
    csv_content = body.get("csvContent", "")
    file_content = body.get("fileContent", "")  # base64 for PDF/image

    if source not in ("bank", "credit_card"):
        return bad_request("source must be 'bank' or 'credit_card'")

    # Determine file format
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    is_csv = ext == "csv" or (csv_content and not file_content)

    if is_csv and not csv_content:
        return bad_request("csvContent is required for CSV uploads")
    if not is_csv and not file_content:
        return bad_request("fileContent (base64) is required for PDF/image uploads")

    # Extract user ID from Cognito authorizer
    claims = (event.get("requestContext", {})
              .get("authorizer", {})
              .get("claims", {}))
    user_id = claims.get("sub", "anonymous")

    upload_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        # 1. Store raw file in S3
        raw_key = f"uploads/raw/{user_id}/{upload_id}/{file_name}"
        if is_csv:
            s3.put_object(
                Bucket=BUCKET,
                Key=raw_key,
                Body=csv_content.encode("utf-8"),
                ContentType="text/csv",
            )
        else:
            import base64
            content_types = {
                "pdf": "application/pdf",
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "gif": "image/gif",
                "webp": "image/webp",
            }
            s3.put_object(
                Bucket=BUCKET,
                Key=raw_key,
                Body=base64.b64decode(file_content),
                ContentType=content_types.get(ext, "application/octet-stream"),
            )

        # 2. Normalise / Parse
        if is_csv:
            transactions = normalize_csv(csv_content, source)
            if not transactions:
                return bad_request("No valid transactions found in CSV. Check the file format.")
        else:
            transactions = parse_statement(file_content, file_name, source)
            if not transactions:
                return bad_request("No transactions could be extracted from this file.")

        # Store normalised JSON in S3
        normalized_key = f"uploads/normalized/{user_id}/{upload_id}/transactions.json"
        s3.put_object(
            Bucket=BUCKET,
            Key=normalized_key,
            Body=json.dumps(transactions, default=str).encode("utf-8"),
            ContentType="application/json",
        )

        # 3. Categorize (merchant memory + AI)
        categorized = categorize_batch(transactions)

        # 4. Derive month key from first transaction date
        first_date = categorized[0]["date"]  # "2026-01-15"
        month_key = first_date[:7]  # "2026-01"

        # 5. Store in DynamoDB
        table = transactions_table()
        stored = []
        for txn in categorized:
            txn_id = hashlib.sha256(
                f"{txn['date']}{txn['description']}{txn['amount']}{upload_id}".encode()
            ).hexdigest()[:16]

            item = {
                "pk": f"USER#{user_id}",
                "sk": f"TXN#{txn['date']}#{txn_id}",
                "transactionId": txn_id,
                "monthKey": txn["date"][:7],
                "date": txn["date"],
                "description": txn["description"],
                "originalDescription": txn["original_description"],
                "amount": txn["amount"],
                "source": txn["source"],
                "bucket": txn.get("bucket"),
                "confidence": txn.get("confidence", 0),
                "categorizationSource": txn.get("categorization_source"),
                "categorizationReasoning": txn.get("categorization_reasoning"),
                "uploadId": upload_id,
                "uploadedBy": user_id,
                "uploadedAt": timestamp,
                "locked": False,
            }
            stored.append(item)

        batch_write(table, stored)

        # Summary
        total_amount = sum(t["amount"] for t in categorized)
        needs_review = [t for t in categorized if not t.get("bucket") or t.get("confidence", 0) < 0.7]

        return ok({
            "uploadId": upload_id,
            "monthKey": month_key,
            "transactionsProcessed": len(stored),
            "needsReview": len(needs_review),
            "totalAmount": round(total_amount, 2),
            "rawFileKey": raw_key,
        })

    except Exception as e:
        return server_error(f"Upload processing failed: {str(e)}")
