import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# TASK 1: Conservative garbled-text detector
# ---------------------------------------------------------------------------
# The old heuristic (≥2 mid-word uppercase) fired on 114/220 emails because
# normal ALL-CAPS company names like TOPKOPY, NOVAKOPA, SINGAPORE all matched.
#
# The new heuristic targets actual OCR corruption: words with ≥4 case
# transitions (upper→lower→upper→lower→...) within a single alphabetic
# token. Normal text is either ALL CAPS (0 transitions), Title Case
# (1 transition), or camelCase (1-2 transitions). Garbled OCR text like
# "ConsKiTgPne" has 7 transitions.
# ---------------------------------------------------------------------------

def is_garbled(text: str) -> bool:
    """Detect genuinely corrupted OCR text by counting case transitions.

    Returns True only when a word shows ≥4 case transitions, which indicates
    garbled/overlapping font rendering.  Normal company names (ALL CAPS,
    Title Case, camelCase) will NOT trigger this.
    """
    if not text:
        return False

    for token in str(text).split():
        # Strip non-alpha from each token for analysis
        alpha = ''.join(c for c in token if c.isalpha())
        if len(alpha) < 5:
            continue

        transitions = sum(
            1 for i in range(1, len(alpha))
            if alpha[i - 1].isupper() != alpha[i].isupper()
        )
        if transitions >= 4:
            return True

    return False


# ---------------------------------------------------------------------------
# TASK 2: Current google-genai SDK (replaces deprecated google.generativeai)
# TASK 5: Safety — validate response, fallback to deterministic on failure
# ---------------------------------------------------------------------------

_EXTRACTION_PROMPT = (
    "Extract exactly these 7 shipping document fields from the attached PDF. "
    "Return a JSON object with these exact keys: "
    "shipper (string or null), consignee (string or null), "
    "notify_party (string or null), port_of_loading (string or null), "
    "port_of_discharge (string or null), container_count (integer or null), "
    "gross_weight_kg (integer or null). "
    "If a field cannot be determined, use null."
)

_EXPECTED_KEYS = frozenset([
    "shipper", "consignee", "notify_party",
    "port_of_loading", "port_of_discharge",
    "container_count", "gross_weight_kg",
])

_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "required": list(_EXPECTED_KEYS),
    "properties": {
        "shipper":            {"type": "STRING", "nullable": True},
        "consignee":          {"type": "STRING", "nullable": True},
        "notify_party":       {"type": "STRING", "nullable": True},
        "port_of_loading":    {"type": "STRING", "nullable": True},
        "port_of_discharge":  {"type": "STRING", "nullable": True},
        "container_count":    {"type": "INTEGER", "nullable": True},
        "gross_weight_kg":    {"type": "INTEGER", "nullable": True},
    },
}


def extract_with_gemini(pdf_bytes: bytes) -> Optional[dict]:
    """Fallback to Gemini API to extract 7 canonical fields from raw PDF bytes.

    Uses the current google-genai SDK (``from google import genai``).
    If the API key is missing or the call fails, falls back to the
    deterministic pypdfium2 re-extraction.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set. Falling back to alternative renderer.")
        return _fallback_deterministic(pdf_bytes)

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                _EXTRACTION_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=_RESPONSE_SCHEMA,
            ),
        )

        result = json.loads(response.text)
        logger.info(f"Gemini API call succeeded. Keys returned: {sorted(result.keys())}")

        # TASK 5 — Safety: validate schema
        if not isinstance(result, dict):
            logger.warning("Gemini returned non-dict response, falling back.")
            return _fallback_deterministic(pdf_bytes)

        if not _EXPECTED_KEYS.issubset(result.keys()):
            missing = _EXPECTED_KEYS - set(result.keys())
            logger.warning(f"Gemini response missing keys {missing}, falling back.")
            return _fallback_deterministic(pdf_bytes)

        return result

    except Exception as e:
        logger.error(f"Gemini extraction failed: {e}")
        return _fallback_deterministic(pdf_bytes)


def _fallback_deterministic(pdf_bytes: bytes) -> Optional[dict]:
    """Deterministic fallback using pypdfium2 to re-extract document text."""
    try:
        import pypdfium2 as pdfium
        from document_parser import detect_document_type, _parse_text_content
        from field_extraction import extract_fields

        text = ""
        pdf = pdfium.PdfDocument(pdf_bytes)
        for i in range(len(pdf)):
            text += pdf[i].get_textpage().get_text_range() + "\n"

        doc_type = detect_document_type(text)
        raw_fields = _parse_text_content(text)
        doc = {
            'doc_type': doc_type,
            'raw_fields': raw_fields,
            'raw_text': text,
        }
        extracted = extract_fields(doc)

        result = {}
        for key in _EXPECTED_KEYS:
            result[key] = extracted.get(key, {}).get("normalized_value")
        return result
    except Exception as e:
        logger.error(f"Deterministic fallback failed: {e}")
        return None
