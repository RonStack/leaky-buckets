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

    Uses merchant memory first, deduplicates descriptions, then sends
    unique descriptions to OpenAI in chunked batch requests.
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

    if not needs_ai:
        return transactions

    # 2. Deduplicate — categorize each unique description only once
    unique_descs = list(dict.fromkeys(desc for _, desc in needs_ai))
    logger.info(
        "Categorizing %d transactions (%d unique) via AI",
        len(needs_ai), len(unique_descs),
    )

    # 3. Batch-categorize unique descriptions (chunked to avoid model dropping items)
    desc_to_result = _ai_categorize_batch(unique_descs)

    # 4. Apply results back to all transactions (including duplicates)
    for idx, desc in needs_ai:
        result = desc_to_result.get(desc, {
            "bucket": None,
            "confidence": 0.0,
            "source": "ai_error",
            "reasoning": "No AI result returned for this transaction.",
        })
        transactions[idx]["bucket"] = result["bucket"]
        transactions[idx]["confidence"] = result["confidence"]
        transactions[idx]["categorization_source"] = result["source"]
        transactions[idx]["categorization_reasoning"] = result["reasoning"]

    return transactions


# ---- OpenAI integration ----

# Max descriptions per API call — keeps GPT-4o-mini from dropping items
_CHUNK_SIZE = 20


def _ai_categorize_batch(descriptions: list[str]) -> dict[str, dict]:
    """
    Categorize multiple transaction descriptions via OpenAI.

    Chunks the list into groups of _CHUNK_SIZE, sends each as a single
    API call, and returns a dict mapping description -> result.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key == "PLACEHOLDER_UPDATE_ME":
        empty = {
            "bucket": None,
            "confidence": 0.0,
            "source": "ai_unavailable",
            "reasoning": "OpenAI API key not configured.",
        }
        return {d: empty for d in descriptions}

    client = OpenAI(api_key=api_key)
    results: dict[str, dict] = {}

    # Process in chunks
    for start in range(0, len(descriptions), _CHUNK_SIZE):
        chunk = descriptions[start : start + _CHUNK_SIZE]
        chunk_results = _ai_categorize_chunk(chunk, client)
        results.update(chunk_results)

    return results


def _ai_categorize_chunk(descriptions: list[str], client: OpenAI) -> dict[str, dict]:
    """
    Categorize a chunk of descriptions in a single OpenAI call.
    Returns a dict mapping description -> result.
    Falls back to individual calls only for this chunk on failure.
    """
    txn_list = "\n".join(
        f"{i + 1}. \"{desc}\"" for i, desc in enumerate(descriptions)
    )

    prompt = f"""You are a personal finance categorizer. Categorize each of the following {len(descriptions)} transactions into exactly ONE of these buckets:

{json.dumps(BUCKETS)}

You MUST return EXACTLY {len(descriptions)} results — one for each transaction, in the same order.

Respond with ONLY a valid JSON array:

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
                "AI chunk returned %s items, expected %s — falling back to singles for this chunk",
                len(parsed) if isinstance(parsed, list) else "non-list",
                len(descriptions),
            )
            return _ai_categorize_singles(descriptions, client)

        # Validate and map results back to descriptions
        results = {}
        for desc, item in zip(descriptions, parsed):
            if item.get("bucket") not in BUCKETS:
                item["bucket"] = None
                item["confidence"] = 0.0
                item["reasoning"] = f"AI suggested unknown bucket. Original: {json.dumps(item)}"
            item["source"] = "ai"
            results[desc] = item

        return results

    except Exception as e:
        logger.error("AI chunk categorization failed: %s — falling back to singles", e)
        return _ai_categorize_singles(descriptions, client)


def _ai_categorize_singles(descriptions: list[str], client: OpenAI) -> dict[str, dict]:
    """Categorize descriptions one-at-a-time (fallback). Returns dict mapping desc -> result."""
    results = {}
    for desc in descriptions:
        results[desc] = _ai_categorize_single(desc, client)
    return results


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
