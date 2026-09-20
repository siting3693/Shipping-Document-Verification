#!/usr/bin/env python3
"""Stage 1 + Stage 2 hybrid pipeline for the SDOC hackathon inbox.

Stage 1: Semantic email classification (Gemini Flash + Rule hybrid).
Stage 2: Attachment identification & document type classification for BL_COMPARISON emails.
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
from documents.selector import AttachmentSelector


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

    # -----------------------------------------------------------------------
    # Stage 1: Email Classification
    # -----------------------------------------------------------------------
    gemini = GeminiClassifier()
    rules = RuleClassifier()
    hybrid = HybridClassifier(gemini_classifier=gemini, rule_classifier=rules)

    if gemini.is_available:
        print(f"Using Gemini model: {gemini.model} as primary email classifier.")
        print("Running batch semantic classification via Gemini Flash...")
        gemini_results = gemini.batch_classify(emails, max_workers=5)
    else:
        print("NOTE: GEMINI_API_KEY is not set or empty.")
        print("Operating in rule fallback mode for Stage 1.")
        gemini_results = {
            e["email_id"]: {
                "success": False,
                "error": "GEMINI_API_KEY not set",
                "result": None,
            }
            for e in emails
        }

    submission: dict[str, dict[str, Any]] = {}
    stage1_debug: list[dict[str, Any]] = []

    gemini_count = 0
    fallback_count = 0
    disagreement_count = 0
    low_confidence_count = 0

    for email in emails:
        eid = email["email_id"]
        g_resp = gemini_results.get(eid)
        decision = hybrid.decide(email, gemini_response=g_resp)

        method = decision["decision_method"]
        if method.startswith("gemini"):
            gemini_count += 1
        elif method.startswith("rule_fallback"):
            fallback_count += 1

        if method == "rule_fallback_low_confidence":
            low_confidence_count += 1

        if decision["agreed"] is False:
            disagreement_count += 1

        submission[eid] = {
            "category": decision["final_category"],
            "status": "OK",
            "review_reason": None,
            "defect_fields": [],
            "has_defect": False,
        }

        stage1_debug.append({
            "email_id": eid,
            "final_category": decision["final_category"],
            "decision_method": decision["decision_method"],
            "agreed": decision["agreed"],
            "gemini": decision["gemini"],
            "gemini_error": decision["gemini_error"],
            "rule": decision["rule"],
        })

    # -----------------------------------------------------------------------
    # Stage 2: Attachment Identification for BL_COMPARISON
    # -----------------------------------------------------------------------
    print("\nRunning Stage 2: Attachment Identification + Document Classification...")
    selector = AttachmentSelector()
    stage2_debug: list[dict[str, Any]] = []

    bl_emails = [e for e in emails if submission[e["email_id"]]["category"] == "BL_COMPARISON"]
    confident_pair_count = 0
    needs_review_count = 0
    ambiguous_att_count = 0
    review_reason_breakdown: Counter[str] = Counter()

    for email in bl_emails:
        eid = email["email_id"]
        stage2_result = selector.process_email(email)
        stage2_debug.append(stage2_result)

        # Check ambiguous attachments
        for att_info in stage2_result.get("attachments", []):
            if att_info.get("confidence", 1.0) < 0.85:
                ambiguous_att_count += 1

        # Check candidate status
        if stage2_result["status"] == "NEEDS_REVIEW":
            needs_review_count += 1
            reason = stage2_result.get("review_reason") or "unspecified"
            review_reason_breakdown[reason] += 1
            # Update submission record for reliability axis
            submission[eid]["status"] = "NEEDS_REVIEW"
            submission[eid]["review_reason"] = stage2_result.get("review_reason")
        else:
            if stage2_result["selected_SI"] and stage2_result["selected_BL"]:
                confident_pair_count += 1

    # Validate output integrity
    validate_submission(submission, emails, sample)

    # Write output files
    submission_path = Path("classified_submission.json")
    stage1_debug_path = Path("classification_debug.json")
    stage2_debug_path = Path("attachment_classification_debug.json")

    submission_path.write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
    stage1_debug_path.write_text(json.dumps(stage1_debug, indent=2) + "\n", encoding="utf-8")
    stage2_debug_path.write_text(json.dumps(stage2_debug, indent=2) + "\n", encoding="utf-8")

    # Output reports
    counts = Counter(result["category"] for result in submission.values())
    print("\n" + "=" * 65)
    print("STAGE 1 CLASSIFICATION REPORT")
    print("=" * 65)
    print(f"Total emails processed         : {len(emails)}")
    print(f"Gemini classifications used    : {gemini_count}")
    print(f"Rule fallbacks used            : {fallback_count}")
    print(f"Gemini/rule disagreements      : {disagreement_count}")
    print(f"Low-confidence cases (<0.85)   : {low_confidence_count}")
    print("-" * 65)
    print("Category Breakdown:")
    for category in CATEGORIES:
        print(f"  {category:<16}: {counts[category]}")
    print("-" * 65)

    print("\n" + "=" * 65)
    print("STAGE 2 ATTACHMENT IDENTIFICATION REPORT")
    print("=" * 65)
    print(f"Total BL_COMPARISON emails     : {len(bl_emails)}")
    print(f"Confident SI + BL pairs        : {confident_pair_count}")
    print(f"Requests without attachments   : {len(bl_emails) - confident_pair_count - needs_review_count}")
    print(f"Emails needing review          : {needs_review_count}")
    for reason, r_count in review_reason_breakdown.items():
        print(f"  - {reason:<22}: {r_count}")
    print(f"Ambiguous attachments (<0.85) : {ambiguous_att_count}")
    print("-" * 65)

    print("\nSample Attachment Selections (First 5 BL_COMPARISON emails):")
    for item in stage2_debug[:5]:
        print(f"  [{item['email_id']}] status: {item['status']} (reason: {item.get('review_reason')})")
        print(f"    SI -> {item['selected_SI']}")
        print(f"    BL -> {item['selected_BL']}")

    if needs_review_count > 0:
        print("\nEscalated Review Cases (Sample):")
        review_samples = [item for item in stage2_debug if item["status"] == "NEEDS_REVIEW"][:5]
        for item in review_samples:
            print(f"  [{item['email_id']}] reason: {item['review_reason']}")
            for a in item["attachments"]:
                print(f"    {a['file']} -> type: {a['selected_type']} (conf: {a['confidence']:.2f})")

    print("\n" + "=" * 65)
    print(f"Official output written to : {submission_path}")
    print(f"Stage 1 debug written to   : {stage1_debug_path}")
    print(f"Stage 2 debug written to   : {stage2_debug_path}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    main()