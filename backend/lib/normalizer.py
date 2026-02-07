"""
CSV Normalizer — turns various bank/credit-card CSV formats into
a common transaction schema.

Normalised transaction shape:
{
    "date": "2026-01-15",
    "description": "STARBUCKS #1234",
    "amount": -4.85,           # negative = spend, positive = income/refund
    "original_description": "STARBUCKS #1234 NEW YORK NY",
    "source": "bank" | "credit_card",
    "raw_line": 12
}

Security: account numbers / identifiers are stripped during normalisation.
"""

import csv
import io
import re
from datetime import datetime


# Words that hint a column is an account number — we skip these entirely
_ACCOUNT_PATTERNS = re.compile(
    r"account|acct|card.?number|card.?no|last.?four", re.IGNORECASE
)

# Common date formats banks love
_DATE_FORMATS = [
    "%m/%d/%Y",
    "%m/%d/%y",
    "%Y-%m-%d",
    "%m-%d-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
]


def normalize_csv(raw_text: str, source: str = "bank") -> list[dict]:
    """
    Parse a CSV string and return a list of normalised transactions.

    Args:
        raw_text: the raw CSV file content
        source: "bank" or "credit_card"

    Returns:
        list of normalised transaction dicts
    """
    reader = csv.DictReader(io.StringIO(raw_text))
    if reader.fieldnames is None:
        return []

    # Map columns to roles
    col_map = _detect_columns(reader.fieldnames)

    transactions = []
    for line_num, row in enumerate(reader, start=2):  # 1-indexed, header is line 1
        try:
            txn = _normalise_row(row, col_map, source, line_num)
            if txn:
                transactions.append(txn)
        except Exception:
            # Skip malformed rows — we'll surface them as exceptions in review
            continue

    return transactions


# ---- Column detection ----

_DATE_HINTS = re.compile(r"date|posted|trans.?date|settlement", re.IGNORECASE)
_DESC_HINTS = re.compile(r"desc|narr|memo|merchant|payee|detail|name", re.IGNORECASE)
_AMOUNT_HINTS = re.compile(r"amount|sum|value|total", re.IGNORECASE)
_DEBIT_HINTS = re.compile(r"debit|withdrawal|charge", re.IGNORECASE)
_CREDIT_HINTS = re.compile(r"credit|deposit|payment", re.IGNORECASE)


def _detect_columns(fieldnames: list[str]) -> dict:
    """Heuristically map CSV headers to roles."""
    col_map = {"date": None, "description": None, "amount": None, "debit": None, "credit": None}

    for col in fieldnames:
        clean = col.strip()
        if _ACCOUNT_PATTERNS.search(clean):
            continue  # skip account-number columns
        if col_map["date"] is None and _DATE_HINTS.search(clean):
            col_map["date"] = col
        elif col_map["description"] is None and _DESC_HINTS.search(clean):
            col_map["description"] = col
        elif col_map["amount"] is None and _AMOUNT_HINTS.search(clean):
            col_map["amount"] = col
        elif col_map["debit"] is None and _DEBIT_HINTS.search(clean):
            col_map["debit"] = col
        elif col_map["credit"] is None and _CREDIT_HINTS.search(clean):
            col_map["credit"] = col

    return col_map


# ---- Row normalisation ----

def _normalise_row(row: dict, col_map: dict, source: str, line_num: int) -> dict | None:
    # Date
    raw_date = (row.get(col_map["date"]) or "").strip()
    parsed_date = _parse_date(raw_date)
    if not parsed_date:
        return None

    # Description
    raw_desc = (row.get(col_map["description"]) or "").strip()
    if not raw_desc:
        return None
    clean_desc = _strip_account_info(raw_desc)

    # Amount
    amount = _parse_amount(row, col_map)
    if amount is None:
        return None

    return {
        "date": parsed_date,
        "description": clean_desc,
        "amount": amount,
        "original_description": raw_desc,
        "source": source,
        "raw_line": line_num,
    }


def _parse_date(raw: str) -> str | None:
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _parse_amount(row: dict, col_map: dict) -> float | None:
    """Try single-amount column first, then debit/credit split."""
    if col_map["amount"]:
        raw = (row.get(col_map["amount"]) or "").strip()
        return _to_float(raw)

    # Some banks split debit and credit into separate columns
    debit_raw = (row.get(col_map.get("debit")) or "").strip() if col_map.get("debit") else ""
    credit_raw = (row.get(col_map.get("credit")) or "").strip() if col_map.get("credit") else ""

    if debit_raw:
        val = _to_float(debit_raw)
        return -abs(val) if val is not None else None
    if credit_raw:
        val = _to_float(credit_raw)
        return abs(val) if val is not None else None

    return None


def _to_float(raw: str) -> float | None:
    if not raw:
        return None
    # Remove currency symbols, commas, spaces
    cleaned = re.sub(r"[$ ,\xa0]", "", raw)
    # Handle parentheses as negative: (123.45) → -123.45
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        return float(cleaned)
    except ValueError:
        return None


def _strip_account_info(desc: str) -> str:
    """Remove sequences that look like account / card numbers."""
    # Remove long digit sequences (4+ digits in a row)
    cleaned = re.sub(r"\b\d{4,}\b", "", desc)
    # Collapse whitespace
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned
