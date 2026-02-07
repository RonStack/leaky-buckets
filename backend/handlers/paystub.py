"""
Paystub handler — upload and manage paystub/income data.

POST  /paystub          → upload & parse a paystub PDF
GET   /paystub?monthKey= → list paystubs for a month
PUT   /paystub/{id}     → edit parsed amounts (user corrections)
DELETE /paystub/{id}    → delete a paystub entry
"""

import json
import os
import uuid
import base64
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

from lib.response import ok, bad_request, not_found, server_error
from lib.db import put_item, get_item, query_items, update_item, delete_item, scan_all
from lib.paystub_parser import parse_paystub

s3 = boto3.client("s3")
BUCKET = os.environ.get("UPLOADS_BUCKET", "")
PAYSTUBS_TABLE_NAME = os.environ.get("PAYSTUBS_TABLE", "")

_dynamodb = boto3.resource("dynamodb")


def _paystubs_table():
    return _dynamodb.Table(PAYSTUBS_TABLE_NAME)


def handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "")

    if method == "POST":
        return _upload_paystub(event)
    elif method == "GET":
        return _list_paystubs(event)
    elif method == "PUT":
        return _update_paystub(event)
    elif method == "DELETE":
        return _delete_paystub(event)
    return bad_request("Unsupported method")


def _upload_paystub(event):
    """Parse a paystub PDF or image and store the extracted data."""
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    # Support both old pdfContent and new fileContent field names
    file_base64 = body.get("fileContent", "") or body.get("pdfContent", "")
    source_name = body.get("source", "Primary Job")
    file_name = body.get("fileName", "paystub.pdf")

    if not file_base64:
        return bad_request("fileContent (base64-encoded PDF or image) is required")

    claims = (event.get("requestContext", {})
              .get("authorizer", {})
              .get("claims", {}))
    user_id = claims.get("sub", "anonymous")

    paystub_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        # 1. Store raw file in S3
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "pdf"
        content_types = {
            "pdf": "application/pdf",
            "png": "image/png",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "gif": "image/gif",
            "webp": "image/webp",
        }
        raw_key = f"uploads/paystubs/{user_id}/{paystub_id}/{file_name}"
        s3.put_object(
            Bucket=BUCKET,
            Key=raw_key,
            Body=base64.b64decode(file_base64),
            ContentType=content_types.get(ext, "application/octet-stream"),
        )

        # 2. Parse with OpenAI
        parsed = parse_paystub(file_base64, file_name)

        # 3. Derive month key from pay date
        pay_date = parsed.get("payDate", "")
        if pay_date and len(pay_date) >= 7:
            month_key = pay_date[:7]
        else:
            # Fallback to current month
            month_key = datetime.now(timezone.utc).strftime("%Y-%m")

        # 4. Store in DynamoDB
        table = _paystubs_table()
        item = {
            "paystubId": paystub_id,
            "monthKey": month_key,
            "payDate": pay_date,
            "source": source_name,
            "employer": parsed.get("employer", "Unknown"),
            "grossPay": parsed["grossPay"],
            "netPay": parsed["netPay"],
            "federalTax": parsed["federalTax"],
            "stateTax": parsed["stateTax"],
            "ficaMedicare": parsed["ficaMedicare"],
            "retirement": parsed["retirement"],
            "hsaFsa": parsed["hsaFsa"],
            "debtPayments": parsed["debtPayments"],
            "otherDeductions": parsed["otherDeductions"],
            "details": parsed.get("details", {}),
            "rawFileKey": raw_key,
            "uploadedBy": user_id,
            "uploadedAt": timestamp,
        }
        put_item(table, item)

        return ok({
            "paystubId": paystub_id,
            "monthKey": month_key,
            "parsed": item,
        })

    except ValueError as e:
        return bad_request(str(e))
    except Exception as e:
        return server_error(f"Paystub processing failed: {str(e)}")


def _list_paystubs(event):
    """List paystubs for a given month."""
    params = event.get("queryStringParameters") or {}
    month_key = params.get("monthKey")

    try:
        table = _paystubs_table()

        if month_key:
            items = query_items(
                table,
                Key("monthKey").eq(month_key),
                index_name="byMonth",
                limit=100,
            )
        else:
            items = scan_all(table)

        # Sort by pay date
        items.sort(key=lambda x: x.get("payDate", ""))

        # Compute totals
        totals = {
            "grossPay": 0, "netPay": 0, "federalTax": 0, "stateTax": 0,
            "ficaMedicare": 0, "retirement": 0, "hsaFsa": 0,
            "debtPayments": 0, "otherDeductions": 0,
        }
        for item in items:
            for key in totals:
                totals[key] += item.get(key, 0)

        # Round totals
        totals = {k: round(v, 2) for k, v in totals.items()}

        return ok({
            "monthKey": month_key,
            "paystubs": items,
            "totals": totals,
            "count": len(items),
        })

    except Exception as e:
        return server_error(str(e))


def _update_paystub(event):
    """Update a paystub's parsed amounts (user corrections)."""
    path_params = event.get("pathParameters") or {}
    paystub_id = path_params.get("paystubId")
    if not paystub_id:
        return bad_request("paystubId path parameter required")

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Invalid JSON body")

    try:
        table = _paystubs_table()
        existing = get_item(table, {"paystubId": paystub_id})
        if not existing:
            return not_found(f"Paystub {paystub_id} not found")

        # Allowed editable fields
        editable = [
            "grossPay", "netPay", "federalTax", "stateTax",
            "ficaMedicare", "retirement", "hsaFsa", "debtPayments",
            "otherDeductions", "source", "employer", "payDate",
        ]
        updates = {}
        for field in editable:
            if field in body:
                val = body[field]
                if field in ("source", "employer", "payDate"):
                    updates[field] = val
                else:
                    updates[field] = float(val)

        if not updates:
            return bad_request("Nothing to update")

        # If payDate changed, update monthKey too
        if "payDate" in updates:
            new_date = updates["payDate"]
            if new_date and len(new_date) >= 7:
                updates["monthKey"] = new_date[:7]

        updated = update_item(table, {"paystubId": paystub_id}, updates)
        return ok(updated)

    except Exception as e:
        return server_error(str(e))


def _delete_paystub(event):
    """Delete a paystub entry."""
    path_params = event.get("pathParameters") or {}
    paystub_id = path_params.get("paystubId")
    if not paystub_id:
        return bad_request("paystubId path parameter required")

    try:
        table = _paystubs_table()
        existing = get_item(table, {"paystubId": paystub_id})
        if not existing:
            return not_found(f"Paystub {paystub_id} not found")

        # Delete from S3 if raw file exists
        raw_key = existing.get("rawFileKey")
        if raw_key and BUCKET:
            try:
                s3.delete_object(Bucket=BUCKET, Key=raw_key)
            except Exception:
                pass

        delete_item(table, {"paystubId": paystub_id})
        return ok({"deleted": paystub_id})

    except Exception as e:
        return server_error(str(e))
