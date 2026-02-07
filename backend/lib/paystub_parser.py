"""
Paystub Parser — PDF → OpenAI GPT-4o vision → structured income data.

Flow:
1. Receive PDF as base64
2. Convert PDF pages to PNG images using PyMuPDF
3. Send images to OpenAI GPT-4o for extraction
4. Return structured paystub data

All deduction categories:
- Federal Tax
- State Tax
- FICA (Social Security + Medicare)
- Retirement (401k, Roth 401k, IRA)
- HSA / FSA
- Debt Payments (401k loan, etc.)
"""

import base64
import json
import os
import logging
import io

from openai import OpenAI

logger = logging.getLogger(__name__)

DEDUCTION_CATEGORIES = [
    "federalTax",
    "stateTax",
    "ficaMedicare",
    "retirement",
    "hsaFsa",
    "debtPayments",
    "otherDeductions",
]


def parse_paystub_pdf(pdf_base64: str) -> dict:
    """
    Parse a paystub PDF using OpenAI GPT-4o vision.

    Args:
        pdf_base64: base64-encoded PDF content

    Returns:
        {
            "grossPay": 5000.00,
            "netPay": 3200.00,
            "payDate": "2026-01-15",
            "employer": "Acme Corp",
            "federalTax": 600.00,
            "stateTax": 250.00,
            "ficaMedicare": 382.50,
            "retirement": 400.00,
            "hsaFsa": 100.00,
            "debtPayments": 67.50,
            "otherDeductions": 0.00,
            "details": { ... raw line items ... }
        }
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key == "PLACEHOLDER_UPDATE_ME":
        raise ValueError("OpenAI API key not configured — required for paystub parsing")

    # Convert PDF pages to images
    images_base64 = _pdf_to_images(pdf_base64)

    if not images_base64:
        raise ValueError("Could not extract any pages from the PDF")

    # Send to OpenAI
    result = _extract_with_openai(api_key, images_base64)
    return result


def _pdf_to_images(pdf_base64: str) -> list[str]:
    """Convert PDF pages to base64-encoded PNG images."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        # Fallback: send PDF directly as base64 to OpenAI
        # GPT-4o supports PDF input in some configurations
        logger.warning("PyMuPDF not available, sending PDF directly")
        return [pdf_base64]

    pdf_bytes = base64.b64decode(pdf_base64)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    images = []

    for page_num in range(min(doc.page_count, 4)):  # Max 4 pages
        page = doc[page_num]
        # Render at 2x for readability
        mat = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")
        images.append(img_b64)

    doc.close()
    return images


def _extract_with_openai(api_key: str, images_base64: list[str]) -> dict:
    """Send paystub images to GPT-4o and extract structured data."""
    client = OpenAI(api_key=api_key)

    prompt = """You are a paystub parser. Extract the following information from this paystub image(s).

Return ONLY valid JSON with these exact fields (use 0.00 for any field not found):

{
    "grossPay": <total gross pay for this pay period as a number>,
    "netPay": <net/take-home pay as a number>,
    "payDate": "<pay date in YYYY-MM-DD format>",
    "employer": "<employer/company name>",
    "federalTax": <federal income tax withheld as a number>,
    "stateTax": <state income tax withheld as a number>,
    "ficaMedicare": <Social Security + Medicare combined as a number>,
    "retirement": <401k + Roth 401k + IRA contributions combined as a number>,
    "hsaFsa": <HSA + FSA contributions combined as a number>,
    "debtPayments": <401k loan repayments + other debt deductions as a number>,
    "otherDeductions": <any other deductions not in the above categories as a number>,
    "details": {
        "lineItems": [
            {"name": "<deduction name>", "amount": <amount>, "category": "<which of the above categories>"}
        ]
    }
}

Important:
- All amounts should be for the CURRENT pay period only (not YTD)
- Use the "Current" column, NOT the "YTD" column
- federalTax = Federal Income Tax / FIT / Fed Withholding
- stateTax = State Income Tax / SIT / State Withholding
- ficaMedicare = Social Security (OASDI) + Medicare combined
- retirement = 401k + Roth 401k + 403b + IRA (employee contributions only)
- hsaFsa = Health Savings Account + Flexible Spending Account
- debtPayments = 401k Loan + any loan repayments deducted from pay
- otherDeductions = dental, vision, life insurance, disability, union dues, etc.
- Return ONLY the JSON, no markdown fences or extra text"""

    # Build message content with images
    content = [{"type": "text", "text": prompt}]
    for img_b64 in images_base64:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{img_b64}",
                "detail": "high",
            },
        })

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": content}],
        temperature=0,
        max_tokens=1500,
    )

    raw = response.choices[0].message.content.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()

    parsed = json.loads(raw)

    # Validate and ensure all fields exist
    for field in DEDUCTION_CATEGORIES:
        if field not in parsed:
            parsed[field] = 0.0
        parsed[field] = float(parsed[field] or 0)

    parsed["grossPay"] = float(parsed.get("grossPay", 0))
    parsed["netPay"] = float(parsed.get("netPay", 0))
    parsed["payDate"] = parsed.get("payDate", "")
    parsed["employer"] = parsed.get("employer", "Unknown")

    return parsed
