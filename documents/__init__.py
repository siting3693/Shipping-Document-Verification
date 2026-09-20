"""Stage 2 Documents package for SDOC Hackathon.

Provides attachment text extraction, document type scoring, and candidate selection.
"""

from documents.extractor import extract_attachment_text
from documents.classifier import DocumentClassifier, score_document
from documents.gemini_doc_classifier import GeminiDocClassifier
from documents.selector import AttachmentSelector, select_attachments_for_email

__all__ = [
    "extract_attachment_text",
    "DocumentClassifier",
    "score_document",
    "GeminiDocClassifier",
    "AttachmentSelector",
    "select_attachments_for_email",
]
