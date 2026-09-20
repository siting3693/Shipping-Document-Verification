#!/usr/bin/env python3
"""Hybrid decision layer combining Gemini Flash and Rule-based classifiers."""

from typing import Any

from classification.gemini_classifier import GeminiClassifier
from classification.rule_classifier import RuleClassifier, CATEGORIES


class HybridClassifier:
    """Combines Gemini Flash semantic classification with rule validation/fallback."""

    def __init__(
        self,
        gemini_classifier: GeminiClassifier | None = None,
        rule_classifier: RuleClassifier | None = None,
        confidence_threshold: float = 0.85,
    ) -> None:
        self.gemini = gemini_classifier or GeminiClassifier()
        self.rules = rule_classifier or RuleClassifier()
        self.confidence_threshold = confidence_threshold

    def decide(
        self,
        email: dict[str, Any],
        gemini_response: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Combine Gemini and Rule outputs to produce final category and debug info."""
        email_id = email.get("email_id", "unknown")

        # 1. Run rule classifier
        rule_result = self.rules.classify(email)
        rule_cat = rule_result["category"]
        rule_scores = rule_result["scores"]
        rule_conf = rule_result["confidence"]

        # 2. Obtain Gemini classification if not provided
        if gemini_response is None:
            gemini_response = self.gemini.classify(email)

        gemini_success = gemini_response.get("success", False)
        gemini_data = gemini_response.get("result")
        gemini_error = gemini_response.get("error")

        gemini_cat = gemini_data.get("category") if gemini_data else None
        gemini_conf = gemini_data.get("confidence", 0.0) if gemini_data else 0.0

        # Disagreement check
        is_agreed = (gemini_cat == rule_cat) if (gemini_success and gemini_cat) else None

        # 3. Decision Logic
        final_category: str
        decision_method: str

        if not gemini_success or gemini_data is None:
            # Case A: Gemini API failed or unavailable
            final_category = rule_cat
            if gemini_error and "not set" in gemini_error.lower():
                decision_method = "rule_fallback_api_unavailable"
            else:
                decision_method = "rule_fallback_api_error"
        elif gemini_cat not in CATEGORIES:
            # Case B: Gemini returned invalid category
            final_category = rule_cat
            decision_method = "rule_fallback_invalid_response"
        elif gemini_conf < self.confidence_threshold:
            # Case C: Low Gemini confidence (< 0.85) -> rely on rule classifier
            final_category = rule_cat
            decision_method = "rule_fallback_low_confidence"
        else:
            # Case D: Gemini confidence >= 0.85
            # Check for strong disagreement where rule has unambiguous signal
            rule_strong_spam = rule_scores.get("SPAM", 0.0) >= 12.0 and gemini_cat != "SPAM"
            rule_strong_general = rule_scores.get("GENERAL", 0.0) >= 10.0 and gemini_cat in ("BL_COMPARISON", "SI_REQUEST")

            if rule_strong_spam:
                final_category = "SPAM"
                decision_method = "rule_override_strong_disagreement"
            elif rule_strong_general:
                final_category = "GENERAL"
                decision_method = "rule_override_strong_disagreement"
            else:
                final_category = gemini_cat
                decision_method = "gemini_high_confidence"

        return {
            "email_id": email_id,
            "final_category": final_category,
            "agreed": is_agreed,
            "decision_method": decision_method,
            "gemini": gemini_data,
            "gemini_error": gemini_error,
            "rule": {
                "category": rule_cat,
                "confidence": rule_conf,
                "scores": rule_scores,
                "matched_rules": rule_result["matched_rules"],
                "attachment_signals": rule_result["attachment_signals"],
            },
        }


def classify_email(email: dict[str, Any], hybrid_classifier: HybridClassifier | None = None) -> dict[str, Any]:
    """Top-level functional helper for classifying a single email."""
    classifier = hybrid_classifier or HybridClassifier()
    return classifier.decide(email)
