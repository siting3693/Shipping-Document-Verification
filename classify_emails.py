#!/usr/bin/env python3
"""Stage 1 classifier for the SDOC hackathon inbox."""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from loader import Inbox


CATEGORIES = ("BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM")

CLASSIFICATION_RULES = {
    "BL_COMPARISON": {
        "explicit_phrases": (
            "compare the si and draft bl",
            "check the draft bl against the si",
            "check whether the bl matches the si",
            "verify the bl matches the si",
            "check shipping instruction against bill of lading",
            "identify discrepancies",
            "any discrepancy",
            "document verification",
            # Subject patterns from actual data
            "to confirm docs",
            "confirm docs",
            "request bl draft",
            "amend bl",
            # Body patterns from actual data
            "send the draft bl",
            "draft bl for checking",
            "confirm the bl is in order",
            "check the details and confirm",
            "verify the bl matches",
            "confirm bl is in order",
            "kindly confirm the bl",
            "the bl will not open",
            "bl is still missing",
            "si and draft bl",
            "si and the draft bl",
            "si and bl for",
            "si and draft bill of lading",
            "shipping instruction and the draft bill of lading",
        ),
        "comparison_words": ("compare", "discrepancy", "discrepancies", "verify", "matches"),
        "document_words": ("shipping instruction", "bill of lading", "draft bl", " si ", " bl "),
        # Subject-only pattern: coded DEPT-PORT-CARRIER(BLNO) format
        "subject_patterns": (
            "draft bl",
        ),
    },
    "SI_REQUEST": {
        "phrases": (
            "please provide the shipping instruction",
            "requesting shipping instruction",
            "submit the si",
            "submit si",
            "si is required",
            "urgently require the si",
            "request si",
            "cust si",
            "si needed",
            "latest si",
            "please find shipping instruction for",
        ),
    },
    "INVOICE_QUERY": {
        "phrases": (
            "query on invoice",
            "cancel invoice",
            "invoice status",
            "invoice correction",
            "missing gr",
            "detention charges",
            "d&d charges",
            "local charge",
            "thc",
            "release payment",
        ),
        "words": ("invoice", "invoicing", "billing", "payment", "charge", "charges"),
    },
    "SPAM": {
        "phrases": (
            "bitcoin investment",
            "guaranteed 300%",
            "unpaid customs fee",
            "confirm payment within 24 hours",
            "exclusive offer",
            "limited time offer",
            "90% off",
            "update your account to avoid suspension",
            "hot singles",
            "weird trick",
            "email storage is full",
            "verify account immediately",
        ),
        "suspicious_domains": (
            "secure-mailbox.org",
            "webmail-verify.co",
            "parcel-track.co",
            "logistics-deals.biz",
            "crypto-invest.net",
        ),
    },
}


def preprocess_text(*parts: Any) -> str:
    """Return normalized text while retaining word boundaries for phrase rules."""
    text = " ".join(str(part or "") for part in parts)
    text = text.casefold().replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def normalize_attachment_name(path: str) -> str:
    return preprocess_text(Path(path).stem)


def extract_attachment_signals(attachments: list[str]) -> dict[str, Any]:
    names = [normalize_attachment_name(path) for path in attachments]
    has_si = any(re.search(r"(?:^| )si(?: |$)|shipping instruction", name) for name in names)
    has_bl = any(re.search(r"(?:^| )bl(?: |$)|bill of lading", name) for name in names)
    return {
        "normalized_names": names,
        "has_si_attachment": has_si,
        "has_bl_attachment": has_bl,
        "has_si_bl_pair": has_si and has_bl,
        "attachment_types": sorted({Path(path).suffix.casefold().lstrip(".") for path in attachments}),
    }


def _matches(text: str, rules: tuple[str, ...]) -> list[str]:
    return [rule for rule in rules if rule in text]


def score_categories(email: dict[str, Any], attachment_signals: dict[str, Any]) -> tuple[dict[str, float], list[str]]:
    subject = preprocess_text(email.get("subject"))
    body = preprocess_text(email.get("body"))
    sender = preprocess_text(email.get("from"))
    text = f"{subject} {body}"
    scores = {category: 0.0 for category in CATEGORIES}
    matched: list[str] = []

    comparison_hits = _matches(text, CLASSIFICATION_RULES["BL_COMPARISON"]["explicit_phrases"])
    if comparison_hits:
        scores["BL_COMPARISON"] += 8.0 * len(comparison_hits)
        matched.extend(f"comparison phrase: {hit}" for hit in comparison_hits)
    comparison_words = _matches(text, CLASSIFICATION_RULES["BL_COMPARISON"]["comparison_words"])
    if comparison_words and any(word in text for word in CLASSIFICATION_RULES["BL_COMPARISON"]["document_words"]):
        scores["BL_COMPARISON"] += 2.0 * len(comparison_words)
        matched.extend(f"comparison word: {word}" for word in comparison_words)
        
    # Check for coded subject pattern: DEPT - PORT - CARRIER(BL_NO) - ...
    raw_subject = email.get("subject", "")
    if re.search(r'[A-Za-z]{3,4}\s*\([A-Za-z0-9]{10,15}\)', raw_subject) and " - " in raw_subject:
        scores["BL_COMPARISON"] += 10.0
        matched.append("coded subject pattern")
        
    if attachment_signals["has_si_bl_pair"]:
        scores["BL_COMPARISON"] += 5.0
        matched.append("SI and BL attachment pair")
        if any(word in text for word in ("check", "confirm", "review", "verify", "match")):
            scores["BL_COMPARISON"] += 3.0
            matched.append("document review request")

    si_hits = _matches(text, CLASSIFICATION_RULES["SI_REQUEST"]["phrases"])
    if si_hits:
        scores["SI_REQUEST"] += 7.0 * len(si_hits)
        matched.extend(f"SI request: {hit}" for hit in si_hits)
    if "shipping instruction" in text and any(word in text for word in ("prepare", "create", "request", "needed", "submit", "send")):
        scores["SI_REQUEST"] += 4.0
        matched.append("new shipping instruction request")

    invoice_hits = _matches(text, CLASSIFICATION_RULES["INVOICE_QUERY"]["phrases"])
    invoice_words = _matches(text, CLASSIFICATION_RULES["INVOICE_QUERY"]["words"])
    if invoice_hits:
        scores["INVOICE_QUERY"] += 6.0 * len(invoice_hits)
        matched.extend(f"invoice phrase: {hit}" for hit in invoice_hits)
    if invoice_words:
        scores["INVOICE_QUERY"] += 2.0 * len(invoice_words)
        matched.extend(f"invoice term: {word}" for word in invoice_words)

    spam_hits = _matches(text, CLASSIFICATION_RULES["SPAM"]["phrases"])
    if spam_hits:
        scores["SPAM"] += 8.0 * len(spam_hits)
        matched.extend(f"spam phrase: {hit}" for hit in spam_hits)
    for domain in CLASSIFICATION_RULES["SPAM"]["suspicious_domains"]:
        if domain in sender:
            scores["SPAM"] += 4.0
            matched.append(f"suspicious sender domain: {domain}")

    # A clear comparison request wins over incidental SI or invoice vocabulary.
    if scores["BL_COMPARISON"] >= 8:
        scores["SI_REQUEST"] *= 0.25
        scores["INVOICE_QUERY"] *= 0.5
    return scores, matched


def classify_email(email: dict[str, Any], inbox: Inbox) -> dict[str, Any]:
    attachment_signals = extract_attachment_signals(email.get("attachments", []))
    scores, matched = score_categories(email, attachment_signals)
    ranked = sorted(CATEGORIES, key=lambda category: (scores[category], category), reverse=True)
    category = ranked[0] if scores[ranked[0]] >= 4.0 else "GENERAL"
    return {
        "category": category,
        "scores": scores,
        "matched_rules": matched,
        "attachment_signals": attachment_signals,
    }


def validate_submission(submission: dict[str, dict[str, Any]], emails: list[dict[str, Any]], sample: dict[str, Any]) -> None:
    input_ids = [email["email_id"] for email in emails]
    if len(input_ids) != len(set(input_ids)):
        raise ValueError("Input email IDs are not unique")
    if set(submission) != set(input_ids):
        raise ValueError("Submission email IDs do not exactly match the inbox")
    expected_fields = set(next(iter(sample.values())))
    for email_id, result in submission.items():
        if set(result) != expected_fields:
            raise ValueError(f"Unexpected output fields for {email_id}")
        if result["category"] not in CATEGORIES:
            raise ValueError(f"Invalid category for {email_id}: {result['category']}")


def main() -> None:
    inbox = Inbox(".")
    emails = list(inbox)
    sample = inbox.sample_submission()
    submission: dict[str, dict[str, Any]] = {}
    debug: list[dict[str, Any]] = []
    for email in emails:
        decision = classify_email(email, inbox)
        submission[email["email_id"]] = {
            "category": decision["category"],
            "status": "OK",
            "review_reason": None,
            "defect_fields": [],
            "has_defect": False,
        }
        debug.append({
            "email_id": email["email_id"],
            "predicted_category": decision["category"],
            "scores": decision["scores"],
            "matched_rules": decision["matched_rules"],
            "attachment_signals": decision["attachment_signals"],
        })

    validate_submission(submission, emails, sample)
    Path("classified_submission.json").write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
    Path("classification_debug.json").write_text(json.dumps(debug, indent=2) + "\n", encoding="utf-8")
    counts = Counter(result["category"] for result in submission.values())
    print(f"Total emails: {len(emails)}")
    for category in CATEGORIES:
        print(f"{category}: {counts[category]}")
    print("Output written to: classified_submission.json")
    print("Debug written to: classification_debug.json")


if __name__ == "__main__":
    main()