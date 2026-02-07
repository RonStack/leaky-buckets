"""
Merchant Categorizer — rules first, AI second.

Flow:
1. Check merchant memory (DynamoDB merchants table)
2. If unknown → call OpenAI for suggestion + confidence score
3. Return category + confidence + reasoning

Merchant memory always overrides AI.
AI calls are idempotent (same input → same-ish output, and we store the result).
"""

import json
import os
import logging

import boto3
from openai import OpenAI

from lib.db import merchants_table, get_item, put_item

logger = logging.getLogger(__name__)

# The canonical bucket list — must match what the frontend shows
BUCKETS = [
    "Home & Utilities",
    "Groceries",
    "Dining & Coffee",
    "Subscriptions",
    "Health",
    "Transport",
    "Fun & Travel",
    "One-Off & Big Hits",
]


def categorize_transaction(description: str) -> dict:
    """
    Categorize a single transaction description.

    Returns:
        {
            "bucket": "Dining & Coffee",
            "confidence": 0.95,
            "source": "merchant_memory" | "ai",
            "reasoning": "..."
        }
    """
    # Normalise merchant key: lowercase, strip trailing whitespace
    merchant_key = description.strip().lower()

    # 1. Check merchant memory
    table = merchants_table()
    stored = get_item(table, {"merchantName": merchant_key})
    if stored and stored.get("bucket"):
        return {
            "bucket": stored["bucket"],
            "confidence": 1.0,
            "source": "merchant_memory",
            "reasoning": f"Merchant '{description}' previously categorized by user.",
        }

    # 2. AI fallback
    try:
        result = _ai_categorize(description)
        return result
    except Exception as e:
        logger.error("AI categorization failed for '%s': %s", description, e)
        return {
            "bucket": None,
            "confidence": 0.0,
            "source": "ai_error",
            "reasoning": f"AI categorization failed: {str(e)}",
        }


def remember_merchant(description: str, bucket: str):
    """
    Save a merchant → bucket mapping permanently.
    This overrides AI forever for this merchant.
    """
    merchant_key = description.strip().lower()
    table = merchants_table()
    put_item(table, {
        "merchantName": merchant_key,
        "bucket": bucket,
        "originalDescription": description,
    })


def categorize_batch(transactions: list[dict]) -> list[dict]:
    """Categorize a list of transactions, adding bucket info to each."""
    for txn in transactions:
        result = categorize_transaction(txn["description"])
        txn["bucket"] = result["bucket"]
        txn["confidence"] = result["confidence"]
        txn["categorization_source"] = result["source"]
        txn["categorization_reasoning"] = result["reasoning"]
    return transactions


# ---- OpenAI integration ----

def _ai_categorize(description: str) -> dict:
    """Call OpenAI to categorize a merchant description."""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key == "PLACEHOLDER_UPDATE_ME":
        return {
            "bucket": None,
            "confidence": 0.0,
            "source": "ai_unavailable",
            "reasoning": "OpenAI API key not configured.",
        }

    client = OpenAI(api_key=api_key)

    prompt = f"""You are a personal finance categorizer. Given a transaction description, 
categorize it into exactly ONE of these buckets:

{json.dumps(BUCKETS)}

Respond with valid JSON only:
{{"bucket": "<bucket name>", "confidence": <0.0 to 1.0>, "reasoning": "<one sentence>"}}

Transaction: "{description}"
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=150,
    )

    raw = response.choices[0].message.content.strip()

    # Parse the JSON response
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    parsed = json.loads(raw)

    # Validate bucket is in our list
    if parsed.get("bucket") not in BUCKETS:
        parsed["bucket"] = None
        parsed["confidence"] = 0.0
        parsed["reasoning"] = f"AI suggested unknown bucket. Original: {raw}"

    parsed["source"] = "ai"
    return parsed
