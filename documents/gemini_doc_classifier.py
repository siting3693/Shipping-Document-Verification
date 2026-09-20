#!/usr/bin/env python3
"""Gemini Flash document classifier for ambiguous or low-confidence shipping documents."""

import json
import os
from pathlib import Path
import re
import time
from typing import Any
import urllib.error
import urllib.request

DOC_SYSTEM_INSTRUCTION = """You are an expert shipping document specialist.
Your task is to classify an attachment document into EXACTLY ONE of the following three document types:

1. SI (Shipping Instruction):
   A document provided by the shipper to the carrier containing instructions for generating the Bill of Lading.
   Headers/signals: "SHIPPING INSTRUCTION", "BILL OF LADING INSTRUCTION", "BL INSTRUCTION", sheet title "S.I.", Booking reference, Shipper instructions.

2. BL (Draft Bill of Lading):
   The draft transport document issued by the carrier or agent acknowledging receipt of cargo.
   Headers/signals: "BILL OF LADING (DRAFT)", "DRAFT BILL OF LADING", "BILL OF LADING", "B/L NO.", "B/L NUMBER", carrier terms, B/L conditions.

3. OTHER:
   Any document that is neither a Shipping Instruction nor a draft Bill of Lading.
   Examples: Commercial Invoice, Packing List, Certificate of Origin, Cargo Manifest, Insurance Certificate, Delivery Order.

Analyze the provided filename, file type, and text excerpt. Focus on the primary legal and commercial nature of the document.
Return structured JSON with document_type, confidence (0.0 to 1.0), and reason.
"""

DOC_JSON_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "document_type": {
            "type": "STRING",
            "enum": ["SI", "BL", "OTHER"],
        },
        "confidence": {
            "type": "NUMBER",
        },
        "reason": {
            "type": "STRING",
        },
    },
    "required": ["document_type", "confidence", "reason"],
}


class GeminiDocClassifier:
    """Classifies ambiguous attachment documents using Gemini Flash."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: int = 25,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def classify_document(
        self,
        filename: str,
        file_type: str,
        text_excerpt: str,
    ) -> dict[str, Any]:
        """Classify an ambiguous document using Gemini Flash."""
        if not self.is_available:
            return {
                "success": False,
                "error": "GEMINI_API_KEY not set",
                "result": None,
            }

        prompt_payload = {
            "filename": Path(filename).name,
            "file_type": file_type,
            "text_excerpt": text_excerpt[:1500],
        }
        prompt_str = json.dumps(prompt_payload, indent=2)

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        body = {
            "system_instruction": {
                "parts": [{"text": DOC_SYSTEM_INSTRUCTION}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt_str}],
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": DOC_JSON_SCHEMA,
                "temperature": 0.1,
            },
        }

        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        for attempt in range(self.max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    resp_bytes = resp.read()
                    raw_json = json.loads(resp_bytes.decode("utf-8"))
                    candidates = raw_json.get("candidates", [])
                    if not candidates:
                        raise ValueError("No candidates returned from Gemini")
                    part_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    parsed = json.loads(part_text)
                    doc_type = parsed.get("document_type")
                    if doc_type not in ("SI", "BL", "OTHER"):
                        raise ValueError(f"Invalid document_type: {doc_type}")
                    conf = float(parsed.get("confidence", 0.9))
                    return {
                        "success": True,
                        "error": None,
                        "result": {
                            "document_type": doc_type,
                            "confidence": round(max(0.0, min(1.0, conf)), 3),
                            "reason": str(parsed.get("reason", "")),
                        },
                    }
            except urllib.error.HTTPError as err:
                status = err.code
                if status in (429, 500, 503) and attempt < self.max_retries:
                    time.sleep(2.0 ** attempt)
                    continue
                return {"success": False, "error": f"HTTP {status}", "result": None}
            except Exception as ex:
                if attempt < self.max_retries:
                    time.sleep(1.0)
                    continue
                return {"success": False, "error": str(ex), "result": None}

        return {"success": False, "error": "Exceeded max retries", "result": None}
