"""
Paystub Parser — PDF/image → OpenAI GPT-4o → structured income data.

Flow:
- PDF: Extract text with pypdf → send text to GPT-4o
- Image (PNG/JPG/etc): Send directly to GPT-4o vision

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

IMAGE_MIMES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
}


def parse_paystub(file_base64: str, file_name: str = "paystub.pdf") -> dict:
    """
    Parse a paystub from PDF or image using OpenAI GPT-4o.

    Args:
        file_base64: base64-encoded file content
        file_name: original file name (used to detect format)

    Returns:
        { "grossPay": ..., "netPay": ..., ... }
    """
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key or api_key == "PLACEHOLDER_UPDATE_ME":
        raise ValueError("OpenAI API key not configured — required for paystub parsing")

    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""

    if ext == "pdf":
        return _parse_pdf_paystub(file_base64, api_key)
    elif ext in IMAGE_MIMES:
        return _parse_image_paystub(file_base64, ext, api_key)
    else:
        raise ValueError(f"Unsupported paystub format: .{ext}. Use PDF or image (PNG/JPG).")


# Keep backward compatibility
def parse_paystub_pdf(pdf_base64: str) -> dict:
    """Legacy wrapper — parse PDF paystub."""
    return parse_paystub(pdf_base64, "paystub.pdf")


def _parse_pdf_paystub(pdf_base64: str, api_key: str) -> dict:
    """Extract paystub data from a PDF via text extraction + GPT-4o."""
    from pypdf import PdfReader

    pdf_bytes = base64.b64decode(pdf_base64)
    reader = PdfReader(io.BytesIO(pdf_bytes))

    all_text = []
    for page in reader.pages[:4]:
        text = page.extract_text()
        if text:
            all_text.append(text)

    pdf_text = "\n\n--- Page Break ---\n\n".join(all_text)

    if not pdf_text or len(pdf_text.strip()) < 50:
        raise ValueError(
            "Could not extract readable text from this PDF. "
            "The paystub may be image-based (scanned). "
            "Try uploading a screenshot/image of the paystub instead."
        )

    logger.info(f"Extracted {len(pdf_text)} chars of text from PDF")
    return _extract_from_text(api_key, pdf_text)


def _parse_image_paystub(image_base64: str, ext: str, api_key: str) -> dict:
    """Extract paystub data from an image via GPT-4o vision."""
    mime = IMAGE_MIMES[ext]
    return _extract_from_image(api_key, image_base64, mime)


_PAYSTUB_PROMPT = """You are a paystub parser. Extract the following information from this paystub.

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


def _extract_from_text(api_key: str, text: str) -> dict:
    """Send paystub text to GPT-4o and extract structured data."""
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": _PAYSTUB_PROMPT},
            {"role": "user", "content": f"Extract paystub data from this text:\n\n{text}"},
        ],
        temperature=0,
        max_tokens=1500,
    )

    return _parse_paystub_response(response)


def _extract_from_image(api_key: str, image_base64: str, mime_type: str) -> dict:
    """Send paystub image to GPT-4o vision and extract structured data."""
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"{_PAYSTUB_PROMPT}\n\nExtract paystub data from this image:"},
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
        max_tokens=1500,
    )

    return _parse_paystub_response(response)


def _parse_paystub_response(response) -> dict:
    """Parse GPT response into structured paystub data."""
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
