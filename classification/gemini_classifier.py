#!/usr/bin/env python3
"""Gemini Flash semantic classifier for SDOC hackathon emails.

Uses Gemini Flash as the primary classifier with structured JSON output,
zero third-party dependencies (stdlib urllib), and robust error handling.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import time
from typing import Any
import urllib.error
import urllib.request

from classification.rule_classifier import CATEGORIES

SYSTEM_INSTRUCTION = """You are an expert shipping operations documentation classifier for an international container shipping logistics line.
Your task is to classify incoming operational emails into EXACTLY ONE of the following five official categories based on the email's PRIMARY INTENT:

1. BL_COMPARISON:
   The main request is to check, compare, or verify a draft Bill of Lading (BL) against a Shipping Instruction (SI), identify discrepancies, confirm shipping documents match, or request/follow-up on a draft BL specifically for checking/verification.
   Key signals:
   - "check the draft BL against the SI"
   - "verify the BL matches the SI"
   - "Attached are the SI and draft BL... please check and confirm"
   - "revert with any discrepancy"
   - "Please assist to send the draft BL for [booking/ref] for checking asap"
   - "Draft BL ... amend BL" / "REQUEST BL DRAFT"

2. SI_REQUEST:
   The main request is to create, prepare, submit, issue, or provide a new Shipping Instruction (SI).
   Key signals:
   - "Please find Shipping instruction for [OC/Booking]... POL:... POD:... Shipper:... Consignee:..."
   - "REQUEST SI" / "SI NEEDED" / "CUST SI"
   - "Please prepare the shipping instruction"
   - "Please revert with draft BL once available" (following an SI specification in body)

3. INVOICE_QUERY:
   The main request concerns billing, invoices, accounting, payments, or local/port charges.
   Key signals:
   - "missing GR" / "query on invoice" / "cancel invoice" / "reverse PGI"
   - "detention charges" / "D&D charges" / "THC" / "local charges FOB" / "telex release charges"
   - "Total Freight"

4. GENERAL:
   Legitimate operational communications that do NOT belong to the above categories.
   Key signals:
   - Broadcast status reports, daily berthing reports ("daily Berthing Report")
   - Vessel loading update summaries ("UPDATE SUMMARY")
   - Automated broadcast reminders across all pending shipments ("Reminder: Please submit SI & AED for all pending shipments", "_Reminder_Paper - Submit SI & AED")
   - RPA bot automated notifications ("RPA India HSS SD Billing Process Completed")
   - Internal administrative notices (holiday greetings, time off requests, office delivery planning)
   - General document tracking ("List of Outstanding BL")

5. SPAM:
   Irrelevant, unsolicited, promotional, phishing, or suspicious messages.
   Key signals:
   - Prize draws, gift cards ($1,000 gift card, iPhone winner)
   - Fake unpaid customs fees / parcel delivery release links
   - Mailbox quota full / account suspension threats
   - Software discounts ("90% off"), crypto investments, suspicious links

CRITICAL INSTRUCTIONS:
- Classify by PRIMARY INTENT, not mere keyword presence.
  - "Please prepare the SI." -> SI_REQUEST
  - "Please check the BL against the SI." -> BL_COMPARISON
  - "Attached is the SI for your reference." -> likely GENERAL
  - Broadcast operational reminders mentioning "Submit SI & AED" without a specific shipment's SI details -> GENERAL.
- Return structured JSON conforming strictly to the requested schema.
- Confidence must be a float between 0.0 and 1.0.
"""

JSON_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "category": {
            "type": "STRING",
            "enum": list(CATEGORIES),
        },
        "confidence": {
            "type": "NUMBER",
        },
        "reason": {
            "type": "STRING",
        },
        "evidence": {
            "type": "ARRAY",
            "items": {
                "type": "STRING",
            },
        },
    },
    "required": ["category", "confidence", "reason", "evidence"],
}


def _load_dotenv_if_present() -> None:
    """Read .env file in the current directory if it exists."""
    env_file = Path(".env")
    if not env_file.exists():
        return
    try:
        content = env_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


class GeminiClassifier:
    """Client for Gemini Flash semantic email classification."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: int = 25,
        max_retries: int = 3,
    ) -> None:
        _load_dotenv_if_present()
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    @property
    def is_available(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def format_email_prompt(self, email: dict[str, Any]) -> str:
        """Format email metadata without attachment contents."""
        attachments = email.get("attachments", [])
        att_descriptions = [
            f"{path} ({Path(path).suffix.lstrip('.') or 'file'})"
            for path in attachments
        ]
        return (
            f"email_id: {email.get('email_id', 'unknown')}\n"
            f"sender: {email.get('from', 'unknown')}\n"
            f"subject: {email.get('subject', '(no subject)')}\n"
            f"attachments: {att_descriptions if att_descriptions else 'none'}\n"
            f"body:\n{email.get('body', '')}\n"
        )

    def _call_gemini_api(self, prompt: str) -> dict[str, Any]:
        if not self.is_available:
            raise ValueError("GEMINI_API_KEY is not configured")

        url = f"{self.base_url}/models/{self.model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {
                "parts": [{"text": SYSTEM_INSTRUCTION}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": JSON_SCHEMA,
                "temperature": 0.1,
            },
        }

        data = json.dumps(payload).encode("utf-8")
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
                    return json.loads(resp_bytes.decode("utf-8"))
            except urllib.error.HTTPError as err:
                status = err.code
                error_body = err.read().decode("utf-8", errors="replace")
                # Retry on rate limits (429) or server errors (500, 503)
                if status in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    backoff = (2 ** attempt) + 1.0
                    time.sleep(backoff)
                    continue
                raise RuntimeError(f"Gemini API HTTP {status}: {error_body}") from err
            except urllib.error.URLError as err:
                if attempt < self.max_retries:
                    time.sleep(2.0)
                    continue
                raise RuntimeError(f"Gemini connection error: {err}") from err

        raise RuntimeError("Gemini API call exceeded max retries")

    def _parse_candidate_text(self, raw_resp: dict[str, Any]) -> dict[str, Any]:
        try:
            candidates = raw_resp.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates in Gemini response")
            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise ValueError("No parts in Gemini candidate content")
            raw_text = parts[0].get("text", "").strip()

            # Attempt direct JSON decode
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                # Attempt regex extraction if wrapped in code blocks or extra text
                match = re.search(r"\{[\s\S]*\}", raw_text)
                if match:
                    data = json.loads(match.group(0))
                else:
                    raise

            # Validate required fields
            category = data.get("category")
            if category not in CATEGORIES:
                raise ValueError(f"Invalid category from Gemini: {category}")

            confidence = float(data.get("confidence", 0.9))
            confidence = max(0.0, min(1.0, confidence))

            reason = str(data.get("reason", ""))
            evidence = list(data.get("evidence", []))

            return {
                "category": category,
                "confidence": round(confidence, 3),
                "reason": reason,
                "evidence": evidence,
            }
        except Exception as ex:
            raise ValueError(f"Failed to parse Gemini output: {ex}") from ex

    def classify(self, email: dict[str, Any]) -> dict[str, Any]:
        """Classify a single email using Gemini Flash."""
        if not self.is_available:
            return {
                "success": False,
                "error": "GEMINI_API_KEY not set",
                "result": None,
            }

        prompt = self.format_email_prompt(email)
        try:
            api_resp = self._call_gemini_api(prompt)
            result = self._parse_candidate_text(api_resp)
            return {
                "success": True,
                "error": None,
                "result": result,
            }
        except Exception as err:
            return {
                "success": False,
                "error": str(err),
                "result": None,
            }

    def batch_classify(
        self,
        emails: list[dict[str, Any]],
        max_workers: int = 5,
        delay_between_calls: float = 0.1,
    ) -> dict[str, dict[str, Any]]:
        """Classify multiple emails in parallel or gracefully fail if key not set."""
        results: dict[str, dict[str, Any]] = {}
        if not self.is_available:
            for email in emails:
                results[email["email_id"]] = {
                    "success": False,
                    "error": "GEMINI_API_KEY not set",
                    "result": None,
                }
            return results

        def _worker(em: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            if delay_between_calls > 0:
                time.sleep(delay_between_calls)
            return em["email_id"], self.classify(em)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_worker, em) for em in emails]
            for future in as_completed(futures):
                eid, res = future.result()
                results[eid] = res

        return results
