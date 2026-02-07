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
        api_key = os.environ.get("OPENAI_API_KEY", "")
        client = OpenAI(api_key=api_key)
        result = _ai_categorize_single(description, client)
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
    """
    Categorize a list of transactions, adding bucket info to each.

    Uses merchant memory first, then sends ALL remaining uncategorized
    transactions to OpenAI in a single batch request (instead of one
    API call per transaction).
    """
    # 1. Check merchant memory for each transaction
    table = merchants_table()
    needs_ai = []  # (index, description) pairs for AI categorization

    for i, txn in enumerate(transactions):
        merchant_key = txn["description"].strip().lower()
        stored = get_item(table, {"merchantName": merchant_key})
        if stored and stored.get("bucket"):
            txn["bucket"] = stored["bucket"]
            txn["confidence"] = 1.0
            txn["categorization_source"] = "merchant_memory"
            txn["categorization_reasoning"] = (
                f"Merchant '{txn['description']}' previously categorized by user."
            )
        else:
            needs_ai.append((i, txn["description"]))

    # 2. Batch-categorize everything that wasn't in merchant memory
    if needs_ai:
        ai_results = _ai_categorize_batch([desc for _, desc in needs_ai])
        for (idx, desc), result in zip(needs_ai, ai_results):
            transactions[idx]["bucket"] = result["bucket"]
            transactions[idx]["confidence"] = result["confidence"]
            transactions[idx]["categorization_source"] = result["source"]
            transactions[idx]["categorization_reasoning"] = result["reasoning"]

    return transactions


# ---- OpenAI integration ----

def _ai_categorize_batch(descriptions: list[str]) -> list[dict]:
    """
    Categorize multiple transaction descriptions in a single OpenAI call.
    Falls back to one-at-a-time if the batch response can't be parsed.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key == "PLACEHOLDER_UPDATE_ME":
        return [
            {
                "bucket": None,
                "confidence": 0.0,
                "source": "ai_unavailable",
                "reasoning": "OpenAI API key not configured.",
            }
            for _ in descriptions
        ]

    client = OpenAI(api_key=api_key)

    # Build a numbered list of transactions for the prompt
    txn_list = "\n".join(
        f"{i + 1}. \"{desc}\"" for i, desc in enumerate(descriptions)
    )

    prompt = f"""You are a personal finance categorizer. Categorize each transaction 
into exactly ONE of these buckets:

{json.dumps(BUCKETS)}

Respond with ONLY a valid JSON array. Each element must correspond to the 
transaction at that index (same order, same count). Format:

[
    {{"bucket": "<bucket name>", "confidence": <0.0 to 1.0>, "reasoning": "<one sentence>"}},
    ...
]

Transactions:
{txn_list}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=4096,
        )

        raw = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        parsed = json.loads(raw)

        if not isinstance(parsed, list) or len(parsed) != len(descriptions):
            logger.warning(
                "AI batch returned %s items, expected %s — falling back to singles",
                len(parsed) if isinstance(parsed, list) else "non-list",
                len(descriptions),
            )
            return [_ai_categorize_single(d, client) for d in descriptions]

        # Validate and normalize each result
        results = []
        for item in parsed:
            if item.get("bucket") not in BUCKETS:
                item["bucket"] = None
                item["confidence"] = 0.0
                item["reasoning"] = f"AI suggested unknown bucket. Original: {json.dumps(item)}"
            item["source"] = "ai"
            results.append(item)

        return results

    except Exception as e:
        logger.error("AI batch categorization failed: %s — falling back to singles", e)
        return [_ai_categorize_single(d, client) for d in descriptions]


def _ai_categorize_single(description: str, client: OpenAI) -> dict:
    """Categorize a single transaction (fallback if batch fails)."""
    try:
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
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        parsed = json.loads(raw)
        if parsed.get("bucket") not in BUCKETS:
            parsed["bucket"] = None
            parsed["confidence"] = 0.0
            parsed["reasoning"] = f"AI suggested unknown bucket. Original: {raw}"

        parsed["source"] = "ai"
        return parsed

    except Exception as e:
        logger.error("AI single categorization failed for '%s': %s", description, e)
        return {
            "bucket": None,
            "confidence": 0.0,
            "source": "ai_error",
            "reasoning": f"AI categorization failed: {str(e)}",
        }
