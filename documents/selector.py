#!/usr/bin/env python3
"""Attachment candidate selector and review escalation arbiter for Stage 2."""

from pathlib import Path
from typing import Any

from documents.classifier import DocumentClassifier
from documents.extractor import extract_attachment_text
from documents.gemini_doc_classifier import GeminiDocClassifier


class AttachmentSelector:
    """Selects SI and BL candidates and detects review escalations for BL_COMPARISON emails."""

    def __init__(
        self,
        classifier: DocumentClassifier | None = None,
        gemini_doc: GeminiDocClassifier | None = None,
        min_confidence: float = 0.60,
    ) -> None:
        self.classifier = classifier or DocumentClassifier()
        self.gemini_doc = gemini_doc or GeminiDocClassifier()
        self.min_confidence = min_confidence

    def process_email(self, email: dict[str, Any]) -> dict[str, Any]:
        """Process a BL_COMPARISON email's attachments."""
        email_id = email.get("email_id", "unknown")
        attachments = email.get("attachments", [])
        body = (email.get("body") or "").lower()
        subject = (email.get("subject") or "").lower()

        # -------------------------------------------------------------------
        # Case 1: 0 attachments
        # -------------------------------------------------------------------
        if not attachments:
            # Check if attachments were intended/dropped
            is_dropped = (
                "dropped" in body
                or "missing" in body
                or "please compare the si and draft bl" in body
                or "compare the si and draft bl" in subject
            )
            # Check if this was merely an initial draft BL request
            is_request_for_bl = "send the draft bl" in body and "for checking" in body

            if is_dropped and not is_request_for_bl:
                return {
                    "email_id": email_id,
                    "attachments": [],
                    "selected_SI": None,
                    "selected_BL": None,
                    "status": "NEEDS_REVIEW",
                    "review_reason": "missing_attachment",
                }
            else:
                return {
                    "email_id": email_id,
                    "attachments": [],
                    "selected_SI": None,
                    "selected_BL": None,
                    "status": "OK",
                    "review_reason": None,
                }

        # -------------------------------------------------------------------
        # Case 2: Process each attachment
        # -------------------------------------------------------------------
        scored_attachments: list[dict[str, Any]] = []
        has_unreadable = False
        unreadable_file = None

        for att in attachments:
            ext_info = extract_attachment_text(att)
            score_res = self.classifier.score_document(att, ext_info)

            if score_res.get("unreadable"):
                has_unreadable = True
                unreadable_file = att

            # If ambiguous and Gemini is available, query Gemini for arbitration
            if score_res.get("is_ambiguous") and self.gemini_doc.is_available:
                gem_res = self.gemini_doc.classify_document(
                    filename=att,
                    file_type=ext_info["format"],
                    text_excerpt=ext_info["text"][:1000],
                )
                if gem_res.get("success") and gem_res.get("result"):
                    g_data = gem_res["result"]
                    g_type = g_data["document_type"]
                    g_conf = g_data["confidence"]
                    score_res["evidence"].append(
                        f"Gemini Flash classified as {g_type} ({g_conf:.2f}): {g_data.get('reason')}"
                    )
                    # Adjust probabilities based on Gemini response
                    if g_type == "SI":
                        score_res["SI_probability"] = round(max(score_res["SI_probability"], g_conf), 3)
                        rem = round(1.0 - score_res["SI_probability"], 3)
                        score_res["BL_probability"] = round(rem * 0.5, 3)
                        score_res["OTHER_probability"] = round(rem - score_res["BL_probability"], 3)
                    elif g_type == "BL":
                        score_res["BL_probability"] = round(max(score_res["BL_probability"], g_conf), 3)
                        rem = round(1.0 - score_res["BL_probability"], 3)
                        score_res["SI_probability"] = round(rem * 0.5, 3)
                        score_res["OTHER_probability"] = round(rem - score_res["SI_probability"], 3)
                    else:
                        score_res["OTHER_probability"] = round(max(score_res["OTHER_probability"], g_conf), 3)
                        rem = round(1.0 - score_res["OTHER_probability"], 3)
                        score_res["SI_probability"] = round(rem * 0.5, 3)
                        score_res["BL_probability"] = round(rem - score_res["SI_probability"], 3)

                    # Re-rank selected_type
                    t_probs = [
                        ("SI", score_res["SI_probability"]),
                        ("BL", score_res["BL_probability"]),
                        ("OTHER", score_res["OTHER_probability"]),
                    ]
                    t_probs.sort(key=lambda x: x[1], reverse=True)
                    score_res["selected_type"] = t_probs[0][0]
                    score_res["confidence"] = t_probs[0][1]

            scored_attachments.append({
                "file": att,
                "SI_probability": score_res["SI_probability"],
                "BL_probability": score_res["BL_probability"],
                "OTHER_probability": score_res["OTHER_probability"],
                "selected_type": score_res["selected_type"],
                "confidence": score_res["confidence"],
                "evidence": score_res["evidence"],
            })

        # -------------------------------------------------------------------
        # Case 3: Review Escalation Checks
        # -------------------------------------------------------------------
        # 3a. Unreadable attachment
        if has_unreadable:
            return {
                "email_id": email_id,
                "attachments": scored_attachments,
                "selected_SI": None,
                "selected_BL": None,
                "status": "NEEDS_REVIEW",
                "review_reason": "unreadable",
            }

        # 3b. Missing one attachment (only 1 attachment present in comparison request)
        if len(attachments) < 2:
            return {
                "email_id": email_id,
                "attachments": scored_attachments,
                "selected_SI": scored_attachments[0]["file"] if scored_attachments[0]["selected_type"] == "SI" else None,
                "selected_BL": scored_attachments[0]["file"] if scored_attachments[0]["selected_type"] == "BL" else None,
                "status": "NEEDS_REVIEW",
                "review_reason": "missing_attachment",
            }

        # 3c. Wrong document type (e.g. one attachment is COMMERCIAL INVOICE, PACKING LIST, etc.)
        other_candidates = [a for a in scored_attachments if a["selected_type"] == "OTHER"]
        if other_candidates:
            si_cand = next((a["file"] for a in scored_attachments if a["selected_type"] == "SI"), None)
            bl_cand = next((a["file"] for a in scored_attachments if a["selected_type"] == "BL"), None)
            return {
                "email_id": email_id,
                "attachments": scored_attachments,
                "selected_SI": si_cand,
                "selected_BL": bl_cand,
                "status": "NEEDS_REVIEW",
                "review_reason": "wrong_doc_type",
            }

        # -------------------------------------------------------------------
        # Case 4: Candidate Selection for SI and BL
        # -------------------------------------------------------------------
        # Rank by SI_probability and BL_probability
        by_si = sorted(scored_attachments, key=lambda a: a["SI_probability"], reverse=True)
        by_bl = sorted(scored_attachments, key=lambda a: a["BL_probability"], reverse=True)

        best_si = by_si[0]
        best_bl = by_bl[0]

        # Ensure different files
        if best_si["file"] == best_bl["file"]:
            if len(scored_attachments) > 1:
                # If tied, pick the assignment that maximizes sum of probabilities
                si_alt = by_si[1]
                bl_alt = by_bl[1]
                combo1 = best_si["SI_probability"] + bl_alt["BL_probability"]
                combo2 = si_alt["SI_probability"] + best_bl["BL_probability"]
                if combo1 >= combo2:
                    selected_si = best_si["file"]
                    selected_bl = bl_alt["file"]
                else:
                    selected_si = si_alt["file"]
                    selected_bl = best_bl["file"]
            else:
                return {
                    "email_id": email_id,
                    "attachments": scored_attachments,
                    "selected_SI": best_si["file"],
                    "selected_BL": None,
                    "status": "NEEDS_REVIEW",
                    "review_reason": "missing_attachment",
                }
        else:
            selected_si = best_si["file"]
            selected_bl = best_bl["file"]

        return {
            "email_id": email_id,
            "attachments": scored_attachments,
            "selected_SI": selected_si,
            "selected_BL": selected_bl,
            "status": "OK",
            "review_reason": None,
        }


def select_attachments_for_email(email: dict[str, Any]) -> dict[str, Any]:
    """Top-level functional helper."""
    selector = AttachmentSelector()
    return selector.process_email(email)
