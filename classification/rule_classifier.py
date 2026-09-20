#!/usr/bin/env python3
"""Rule-based classifier for the SDOC hackathon inbox.

Maintains existing scoring interface and rules, updated with patterns observed
across the SDOC dataset for high-precision validation and fallback.
"""

from pathlib import Path
import re
from typing import Any

CATEGORIES = ("BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM")

CLASSIFICATION_RULES: dict[str, dict[str, Any]] = {
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
            "to confirm docs",
            "send the draft bl",
            "for checking asap",
            "check the details and confirm",
            "request bl draft",
            "draft bl",
            "amend bl",
        ),
        "comparison_words": (
            "compare", "discrepancy", "discrepancies", "verify", "matches",
            "checking", "check", "confirm",
        ),
        "document_words": (
            "shipping instruction", "bill of lading", "draft bl", " si ", "bl",
        ),
    },
    "SI_REQUEST": {
        "phrases": (
            "si needed",
            "cust si",
            "customer si",
            "new si request",
            "prepare the shipping instruction",
            "prepare shipping instruction",
            "create shipping instruction",
            "send shipping instructions",
            "request si",
            "please find shipping instruction",
            "shipping instruction for",
        ),
        "si_fields": ("pol:", "pod:", "shipper:", "consignee:"),
    },
    "INVOICE_QUERY": {
        "phrases": (
            "query on invoice",
            "cancel invoice",
            "invoice status",
            "invoice correction",
            "missing gr",
            "detention charges",
            "d and d charges",
            "d&d charges",
            "local charge",
            "local charges fob",
            "telex release charges",
            "total freight",
            "thc",
            "release payment",
        ),
        "words": ("invoice", "invoicing", "billing", "payment", "charge", "charges", "freight"),
    },
    "GENERAL": {
        "broadcast_phrases": (
            "daily berthing report",
            "update summary",
            "billing process completed",
            "india hss sd billing process",
            "time off request",
            "delivery planning",
            "welcoming the new year",
            "reminder paper submit si and aed",
            "reminder please submit si and aed",
            "submit si and aed",
            "list of outstanding bl",
            "pending bl release",
            "no action required",
            "rpa bot",
        ),
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
            "90 off",
            "update your account to avoid suspension",
            "hot singles",
            "weird trick",
            "email storage is full",
            "mailbox has exceeded its storage",
            "verify account immediately",
            "won a $1,000 gift card",
            "won a 1 000 gift card",
            "claim your $1,000 gift card",
            "won a brand new iphone",
            "urgent business proposal",
            "confirm payment of $2.99",
            "confirm payment of 2 99",
            "undelivered messages in your mailbox",
        ),
        "suspicious_domains": (
            "secure-mailbox.org",
            "webmail-verify.co",
            "parcel-track.co",
            "logistics-deals.biz",
            "crypto-invest.net",
            "track-parcel.info",
            "free-iphone-winner.net",
            "bit.ly",
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
    return [rule for rule in rules if preprocess_text(rule) in text]


def score_categories(email: dict[str, Any], attachment_signals: dict[str, Any]) -> tuple[dict[str, float], list[str]]:
    raw_subj = email.get("subject") or ""
    raw_body = email.get("body") or ""
    raw_from = email.get("from") or ""
    raw_text = f"{raw_subj}\n{raw_body}".lower()

    subject_norm = preprocess_text(raw_subj)
    body_norm = preprocess_text(raw_body)
    text_norm = f"{subject_norm} {body_norm}"

    scores: dict[str, float] = {category: 0.0 for category in CATEGORIES}
    matched: list[str] = []

    # 1. SPAM rules
    spam_hits = _matches(text_norm, CLASSIFICATION_RULES["SPAM"]["phrases"])
    if spam_hits:
        scores["SPAM"] += 12.0 * len(spam_hits)
        matched.extend(f"spam phrase: {hit}" for hit in spam_hits)
    for domain in CLASSIFICATION_RULES["SPAM"]["suspicious_domains"]:
        if domain in raw_from.lower() or domain in raw_body.lower():
            scores["SPAM"] += 8.0
            matched.append(f"suspicious domain: {domain}")

    # 2. GENERAL broadcast rules
    gen_hits = _matches(text_norm, CLASSIFICATION_RULES["GENERAL"]["broadcast_phrases"])
    if gen_hits:
        scores["GENERAL"] += 10.0 * len(gen_hits)
        matched.extend(f"general broadcast: {hit}" for hit in gen_hits)

    # 3. INVOICE_QUERY rules
    inv_hits = _matches(text_norm, CLASSIFICATION_RULES["INVOICE_QUERY"]["phrases"])
    inv_words = _matches(text_norm, CLASSIFICATION_RULES["INVOICE_QUERY"]["words"])
    if inv_hits:
        scores["INVOICE_QUERY"] += 8.0 * len(inv_hits)
        matched.extend(f"invoice phrase: {hit}" for hit in inv_hits)
    if inv_words and not gen_hits:
        scores["INVOICE_QUERY"] += 2.0 * len(inv_words)
        matched.extend(f"invoice word: {word}" for word in inv_words)

    # 4. SI_REQUEST rules
    has_si_structure = all(f in raw_text for f in CLASSIFICATION_RULES["SI_REQUEST"]["si_fields"])
    if has_si_structure and not gen_hits:
        scores["SI_REQUEST"] += 14.0
        matched.append("structured SI body details (POL, POD, Shipper, Consignee)")
    si_hits = _matches(text_norm, CLASSIFICATION_RULES["SI_REQUEST"]["phrases"])
    if si_hits and not gen_hits:
        scores["SI_REQUEST"] += 7.0 * len(si_hits)
        matched.extend(f"SI phrase: {hit}" for hit in si_hits)

    # 5. BL_COMPARISON rules
    bl_hits = _matches(text_norm, CLASSIFICATION_RULES["BL_COMPARISON"]["explicit_phrases"])
    if bl_hits and not gen_hits:
        scores["BL_COMPARISON"] += 8.0 * len(bl_hits)
        matched.extend(f"BL comparison phrase: {hit}" for hit in bl_hits)
    if attachment_signals["has_si_bl_pair"] and not gen_hits:
        scores["BL_COMPARISON"] += 8.0
        matched.append("SI and BL attachment pair")
    if "request bl draft" in text_norm or ("draft bl" in text_norm and "amend bl" in text_norm):
        scores["BL_COMPARISON"] += 6.0
        matched.append("draft BL request/amendment")

    # Priority adjustments & suppression
    if scores["SPAM"] >= 10.0:
        scores["INVOICE_QUERY"] = 0.0
        scores["GENERAL"] = 0.0
    elif scores["GENERAL"] >= 10.0:
        scores["SI_REQUEST"] = 0.0
        scores["INVOICE_QUERY"] = 0.0
        scores["BL_COMPARISON"] = 0.0
    elif scores["BL_COMPARISON"] >= 8.0 and not has_si_structure:
        scores["SI_REQUEST"] *= 0.25
        scores["INVOICE_QUERY"] *= 0.5
    elif scores["SI_REQUEST"] >= 8.0:
        scores["BL_COMPARISON"] *= 0.2

    return scores, matched


class RuleClassifier:
    """Encapsulates rule-based email classification."""

    def classify(self, email: dict[str, Any]) -> dict[str, Any]:
        attachment_signals = extract_attachment_signals(email.get("attachments", []))
        scores, matched = score_categories(email, attachment_signals)
        ranked = sorted(CATEGORIES, key=lambda c: (scores[c], c), reverse=True)
        top_cat = ranked[0]
        top_score = scores[top_cat]

        if top_score < 4.0:
            category = "GENERAL"
            confidence = 0.60
        else:
            category = top_cat
            second_score = scores[ranked[1]]
            confidence = min(0.99, max(0.65, (top_score / (top_score + second_score + 1e-5)) * 0.95 + 0.05))

        return {
            "category": category,
            "confidence": round(confidence, 3),
            "scores": scores,
            "matched_rules": matched,
            "attachment_signals": attachment_signals,
        }
