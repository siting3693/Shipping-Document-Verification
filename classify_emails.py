#!/usr/bin/env python3
"""Stage 1 hybrid email classifier for the SDOC hackathon inbox.

Combines Gemini Flash semantic classification with an enhanced rule-based
classifier for high-reliability validation, fallback, and conflict resolution.
"""

from collections import Counter
import json
from pathlib import Path
from typing import Any

from loader import Inbox
from classification.rule_classifier import (
    CATEGORIES,
    CLASSIFICATION_RULES,
    preprocess_text,
    normalize_attachment_name,
    extract_attachment_signals,
    score_categories,
    RuleClassifier,
)
from classification.gemini_classifier import GeminiClassifier
from classification.hybrid_classifier import HybridClassifier, classify_email


def validate_submission(
    submission: dict[str, dict[str, Any]],
    emails: list[dict[str, Any]],
    sample: dict[str, Any],
) -> None:
    """Ensure submission strictly conforms to hackathon requirements."""
    input_ids = [email["email_id"] for email in emails]
    if len(input_ids) != len(set(input_ids)):
        raise ValueError("Input email IDs are not unique")
    if set(submission) != set(input_ids):
        missing = set(input_ids) - set(submission)
        extra = set(submission) - set(input_ids)
        raise ValueError(f"Submission email IDs mismatch. Missing: {len(missing)}, Extra: {len(extra)}")

    expected_fields = set(next(iter(sample.values())))
    for email_id, result in submission.items():
        if set(result) != expected_fields:
            extra_f = set(result) - expected_fields
            missing_f = expected_fields - set(result)
            raise ValueError(
                f"Field mismatch for {email_id}. Extra: {extra_f}, Missing: {missing_f}"
            )
        if result["category"] not in CATEGORIES:
            raise ValueError(f"Invalid category for {email_id}: {result['category']}")


def main() -> None:
    inbox = Inbox(".")
    emails = list(inbox)
    sample = inbox.sample_submission()

    print(f"Loaded {len(emails)} emails from inbox.")

    # Initialize classifiers
    gemini = GeminiClassifier()
    rules = RuleClassifier()
    hybrid = HybridClassifier(gemini_classifier=gemini, rule_classifier=rules)

    if gemini.is_available:
        print(f"Using Gemini model: {gemini.model} as primary classifier.")
        print("Running batch semantic classification via Gemini Flash...")
        gemini_results = gemini.batch_classify(emails, max_workers=5)
    else:
        print("NOTE: GEMINI_API_KEY is not set or empty.")
        print("Operating in rule fallback mode (using enhanced rule-based classifier).")
        gemini_results = {
            e["email_id"]: {
                "success": False,
                "error": "GEMINI_API_KEY not set",
                "result": None,
            }
            for e in emails
        }

    submission: dict[str, dict[str, Any]] = {}
    debug: list[dict[str, Any]] = []

    gemini_count = 0
    fallback_count = 0
    disagreement_count = 0
    low_confidence_count = 0

    for email in emails:
        eid = email["email_id"]
        g_resp = gemini_results.get(eid)
        decision = hybrid.decide(email, gemini_response=g_resp)

        # Update tracking stats
        method = decision["decision_method"]
        if method.startswith("gemini"):
            gemini_count += 1
        elif method.startswith("rule_fallback"):
            fallback_count += 1

        if method == "rule_fallback_low_confidence":
            low_confidence_count += 1

        if decision["agreed"] is False:
            disagreement_count += 1

        # Strict submission format matching sample_submission.json
        submission[eid] = {
            "category": decision["final_category"],
            "status": "OK",
            "review_reason": None,
            "defect_fields": [],
            "has_defect": False,
        }

        # Detailed debug record
        debug.append({
            "email_id": eid,
            "final_category": decision["final_category"],
            "decision_method": decision["decision_method"],
            "agreed": decision["agreed"],
            "gemini": decision["gemini"],
            "gemini_error": decision["gemini_error"],
            "rule": decision["rule"],
        })

    # Validate output integrity
    validate_submission(submission, emails, sample)

    # Write output files
    submission_path = Path("classified_submission.json")
    debug_path = Path("classification_debug.json")

    submission_path.write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
    debug_path.write_text(json.dumps(debug, indent=2) + "\n", encoding="utf-8")

    # Output report
    counts = Counter(result["category"] for result in submission.values())
    print("\n" + "=" * 55)
    print("STAGE 1 CLASSIFICATION REPORT")
    print("=" * 55)
    print(f"Total emails processed         : {len(emails)}")
    print(f"Gemini classifications used    : {gemini_count}")
    print(f"Rule fallbacks used            : {fallback_count}")
    print(f"Gemini/rule disagreements      : {disagreement_count}")
    print(f"Low-confidence cases (<0.85)   : {low_confidence_count}")
    print("-" * 55)
    print("Category Breakdown:")
    for category in CATEGORIES:
        print(f"  {category:<16}: {counts[category]}")
    print("-" * 55)
    print(f"Official output written to : {submission_path}")
    print(f"Debug records written to   : {debug_path}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()