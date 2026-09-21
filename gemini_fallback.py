import os
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def is_garbled(text: str) -> bool:
    """Detect if extracted text contains OCR artifacts or garbled mixed-case."""
    if not text:
        return False
        
    words = str(text).split()
    for w in words:
        if len(w) > 5 and w.isalpha():
            # Count uppercase letters that appear after the first character
            upper_mid = sum(1 for c in w[1:] if c.isupper())
            # If there are multiple uppercase letters in the middle of a word (like ConsKiTgPne)
            if upper_mid >= 2:
                return True
    return False

def extract_with_gemini(pdf_bytes: bytes) -> Optional[dict]:
    """Fallback to Gemini API to extract 7 canonical fields from raw PDF bytes."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set. Falling back to alternative renderer.")
        # Without an API key, we fallback to pypdfium2 as a deterministic mock for the Gemini vision fallback
        return _fallback_mock_extract(pdf_bytes)
        
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = (
            "Extract the following 7 shipping fields from the document. "
            "Return ONLY a valid JSON object with exact keys: "
            '"shipper", "consignee", "notify_party", "port_of_loading", "port_of_discharge", "container_count" (integer), "gross_weight_kg" (integer). '
            "If a field is missing, use null. Do not include markdown blocks."
        )
        response = model.generate_content(
            [{"mime_type": "application/pdf", "data": pdf_bytes}, prompt],
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
    except Exception as e:
        logger.error(f"Gemini extraction failed: {e}")
        return None

def _fallback_mock_extract(pdf_bytes: bytes) -> Optional[dict]:
    """If Gemini is unavailable, use pypdfium2 to re-extract the document text."""
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
        # Extract structured fields
        extracted = extract_fields(doc)
        
        # Format like Gemini JSON output
        result = {}
        for key in ["shipper", "consignee", "notify_party", "port_of_loading", "port_of_discharge", "container_count", "gross_weight_kg"]:
            result[key] = extracted.get(key, {}).get("normalized_value")
        return result
    except Exception as e:
        logger.error(f"Mock fallback failed: {e}")
        return None
