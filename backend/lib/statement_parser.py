"""
Statement Parser — PDF/image bank & credit card statements → transactions.

For PDFs:  Extract text with pypdf, send to GPT-4o for structured extraction.
For images: Send directly to GPT-4o vision for extraction.

Returns the same normalized transaction format as normalizer.py:
[
    {
        "date": "2026-01-15",
        "description": "STARBUCKS #1234",
        "amount": -4.85,
        "original_description": "STARBUCKS #1234 NEW YORK NY",
        "source": "bank" | "credit_card",
        "raw_line": 0
    },
    ...
]
"""

import base64
import json
import os
import io
import logging
import re

from openai import OpenAI

logger = logging.getLogger(__name__)

# Image MIME types we support
IMAGE_MIMES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


def parse_statement(file_base64: str, file_name: str, source: str) -> list[dict]:
    """
    Parse a bank/credit card statement from PDF or image.

    Args:
        file_base64: base64-encoded file content
        file_name: original file name (used to detect format)
        source: 'bank' or 'credit_card'

    Returns:
        List of normalized transaction dicts
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key == "PLACEHOLDER_UPDATE_ME":
        raise ValueError("OpenAI API key not configured")

    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

    if ext == "pdf":
        return _parse_pdf_statement(file_base64, source, api_key)
    elif ext in IMAGE_MIMES:
        return _parse_image_statement(file_base64, ext, source, api_key)
    else:
        raise ValueError(f"Unsupported file format: .{ext}. Use CSV, PDF, or image (PNG/JPG).")


def _parse_pdf_statement(file_base64: str, source: str, api_key: str) -> list[dict]:
    """Extract transactions from a PDF statement via text extraction + GPT-4o."""
    from pypdf import PdfReader

    pdf_bytes = base64.b64decode(file_base64)
    reader = PdfReader(io.BytesIO(pdf_bytes))

    all_text = []
    for page in reader.pages[:10]:  # Up to 10 pages for statements
        text = page.extract_text()
        if text:
            all_text.append(text)

    pdf_text = "\n\n--- Page Break ---\n\n".join(all_text)

    if not pdf_text or len(pdf_text.strip()) < 50:
        raise ValueError(
            "Could not extract readable text from this PDF. "
            "The statement may be image-based (scanned). "
            "Try saving it as an image (screenshot/PNG) and uploading that instead."
        )

    logger.info(f"Extracted {len(pdf_text)} chars from PDF statement")
    return _extract_transactions_from_text(pdf_text, source, api_key)


def _parse_image_statement(file_base64: str, ext: str, source: str, api_key: str) -> list[dict]:
    """Extract transactions from a statement image via GPT-4o vision."""
    mime = IMAGE_MIMES[ext]
    return _extract_transactions_from_image(file_base64, mime, source, api_key)


def _build_transaction_prompt(source: str) -> str:
    """Build the system prompt for transaction extraction."""
    source_label = "bank statement" if source == "bank" else "credit card statement"
    return f"""You are a {source_label} parser. Extract ALL transactions from this statement.

Return ONLY valid JSON — an array of transaction objects:

[
    {{
        "date": "2026-01-15",
        "description": "STARBUCKS #1234",
        "amount": -4.85
    }},
    ...
]

Rules:
- "date" must be in YYYY-MM-DD format
- "description" is the merchant/payee name, cleaned up (remove trailing city/state/ID if possible)
- For a {source_label}:
  - Purchases/charges/debits = NEGATIVE amounts
  - Refunds/credits/deposits = POSITIVE amounts
  - {"For bank statements: withdrawals/checks/payments are NEGATIVE, deposits/transfers-in are POSITIVE" if source == "bank" else "For credit cards: charges are NEGATIVE, payments/credits are POSITIVE"}
- Include ALL transactions, do not skip any
- Do NOT include balance entries, fee summaries, or interest unless they are actual line-item transactions
- Do NOT include headers, footers, or account information
- Return ONLY the JSON array, no markdown fences or extra text"""


def _extract_transactions_from_text(text: str, source: str, api_key: str) -> list[dict]:
    """Send statement text to GPT-4o and extract transactions."""
    client = OpenAI(api_key=api_key)
    prompt = _build_transaction_prompt(source)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Extract all transactions from this statement:\n\n{text}"},
        ],
        temperature=0,
        max_tokens=4096,
    )

    return _parse_response(response, source)


def _extract_transactions_from_image(
    image_base64: str, mime_type: str, source: str, api_key: str
) -> list[dict]:
    """Send statement image to GPT-4o vision and extract transactions."""
    client = OpenAI(api_key=api_key)
    prompt = _build_transaction_prompt(source)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{prompt}\n\nExtract all transactions from this statement image:"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_base64}",
                            "detail": "high",
                        },
                    },
                ],
            }
        ],
        temperature=0,
        max_tokens=4096,
    )

    return _parse_response(response, source)


def _parse_response(response, source: str) -> list[dict]:
    """Parse GPT response into normalized transaction list."""
    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    transactions = json.loads(raw)

    if not isinstance(transactions, list):
        raise ValueError("AI did not return a valid transaction list")

    # Normalize into our standard format
    normalized = []
    for i, txn in enumerate(transactions):
        date_str = txn.get("date", "")
        desc = txn.get("description", "Unknown")
        amount = float(txn.get("amount", 0))

        if not date_str or not desc:
            continue

        normalized.append({
            "date": date_str,
            "description": _clean_description(desc),
            "original_description": desc,
            "amount": round(amount, 2),
            "source": source,
            "raw_line": i,
        })

    if not normalized:
        raise ValueError("No transactions could be extracted from this statement")

    return normalized


def _clean_description(desc: str) -> str:
    """Clean up a merchant description."""
    # Remove trailing location info (city, state, zip patterns)
    desc = re.sub(r"\s+[A-Z]{2}\s+\d{5}(-\d{4})?$", "", desc)
    # Remove trailing card digits
    desc = re.sub(r"\s+x{1,4}\d{4}$", "", desc, flags=re.IGNORECASE)
    # Collapse whitespace
    desc = re.sub(r"\s+", " ", desc).strip()
    return desc
