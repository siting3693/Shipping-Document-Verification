"""Classification module for SDOC Hackathon Stage 1."""

from classification.rule_classifier import RuleClassifier, CATEGORIES
from classification.gemini_classifier import GeminiClassifier
from classification.hybrid_classifier import HybridClassifier, classify_email

__all__ = [
    "CATEGORIES",
    "RuleClassifier",
    "GeminiClassifier",
    "HybridClassifier",
    "classify_email",
]
