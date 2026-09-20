#!/usr/bin/env python3
"""Document type classifier using content evidence, filename normalization, and probability scoring."""

import math
from pathlib import Path
import re
from typing import Any

from documents.extractor import extract_attachment_text

DOCUMENT_TYPES = ("SI", "BL", "OTHER")


def normalize_filename(path_str: str) -> str:
    """Normalize filename: lowercase, replace punctuation with spaces, trim."""
    stem = Path(path_str).stem.lower()
    normalized = re.sub(r"[\W_]+", " ", stem).strip()
    return normalized


class DocumentClassifier:
    """Classifies attachment documents into SI, BL, or OTHER."""

    def __init__(self, confidence_threshold: float = 0.85) -> None:
        self.confidence_threshold = confidence_threshold

    def score_document(
        self,
        file_path: str,
        ext_info: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Score an attachment document and return probabilities for SI, BL, and OTHER."""
        if ext_info is None:
            ext_info = extract_attachment_text(file_path)

        if ext_info["status"] != "ok":
            return {
                "file": file_path,
                "SI_probability": 0.0,
                "BL_probability": 0.0,
                "OTHER_probability": 1.0,
                "selected_type": "OTHER",
                "confidence": 0.0,
                "evidence": [f"Extraction failed: {ext_info['error']}"],
                "unreadable": True,
                "is_ambiguous": False,
                "extracted_info": ext_info,
            }

        text = ext_info["text"]
        norm_text = text.lower()
        clean_text = re.sub(r"[\W_]+", " ", norm_text)
        fname_norm = normalize_filename(file_path)
        fname_tokens = fname_norm.split()

        evidence: list[str] = []
        si_score = 0.0
        bl_score = 0.0
        other_score = 0.0

        # -------------------------------------------------------------------
        # 1. OTHER document evidence (Commercial Invoice, Packing List, COO)
        # -------------------------------------------------------------------
        other_markers = [
            ("commercial invoice", 10.0),
            ("packing list", 10.0),
            ("certificate of origin", 10.0),
            ("not an si or bl", 12.0),
            ("not a shipping instruction", 12.0),
            ("packing list only", 12.0),
            ("customs invoice", 8.0),
            ("unit price", 5.0),
            ("carton no", 5.0),
            ("country of origin", 5.0),
        ]
        for marker, weight in other_markers:
            if marker in clean_text:
                other_score += weight
                evidence.append(f"Content mentions '{marker}' (+{weight:.1f} OTHER)")

        if any(tok in fname_tokens for tok in ("invoice", "packing", "coo", "origin")):
            other_score += 4.0
            evidence.append("Filename suggests non-SI/BL document (+4.0 OTHER)")

        # -------------------------------------------------------------------
        # 2. Filename evidence (SI vs BL)
        # -------------------------------------------------------------------
        if "si" in fname_tokens or "shipping instruction" in fname_norm:
            si_score += 3.0
            evidence.append("Filename indicates SI (+3.0 SI)")
        if "bl" in fname_tokens or "bill of lading" in fname_norm:
            bl_score += 3.0
            evidence.append("Filename indicates BL (+3.0 BL)")

        # -------------------------------------------------------------------
        # 3. Heading & Title evidence (first ~40 words)
        # -------------------------------------------------------------------
        first_words = " ".join(clean_text.split()[:40])
        if "shipping instruction" in first_words or "bill of lading instruction" in first_words or "bl instruction" in first_words:
            si_score += 10.0
            evidence.append("Header indicates Shipping Instruction (+10.0 SI)")
        elif "bill of lading draft" in first_words or "draft bill of lading" in first_words:
            bl_score += 10.0
            evidence.append("Header indicates Draft Bill of Lading (+10.0 BL)")
        elif "bill of lading" in first_words and "instruction" not in first_words:
            bl_score += 8.0
            evidence.append("Header indicates Bill of Lading (+8.0 BL)")

        # -------------------------------------------------------------------
        # 4. Sheet name evidence for Excel files
        # -------------------------------------------------------------------
        if "sheet: s.i." in norm_text or "sheet: si" in norm_text:
            si_score += 8.0
            evidence.append("Excel sheet named 'S.I.' (+8.0 SI)")
        elif "sheet: bl" in norm_text:
            bl_score += 8.0
            evidence.append("Excel sheet named 'BL' (+8.0 BL)")

        # -------------------------------------------------------------------
        # 5. Core content markers
        # -------------------------------------------------------------------
        if "shipping instruction" in clean_text and "bill of lading" not in first_words:
            si_score += 4.0
            evidence.append("Mentions 'shipping instruction' (+4.0 SI)")

        if any(pat in clean_text for pat in ("b l no", "bl no", "b l number", "bl number", "bill of lading no")):
            bl_score += 4.0
            evidence.append("Contains 'B/L No.' (+4.0 BL)")

        if "freight prepaid" in clean_text:
            bl_score += 1.0
            si_score += 1.0

        if any(pat in clean_text for pat in ("shipper", "consignee", "port of loading")):
            # Shared evidence: adds minor baseline weight to both SI and BL
            si_score += 0.5
            bl_score += 0.5

        if any(pat in clean_text for pat in ("cargo description", "description of goods")):
            bl_score += 2.0
            si_score += 1.0
            evidence.append("Contains cargo description (+2.0 BL, +1.0 SI)")

        # -------------------------------------------------------------------
        # 6. Softmax probability transformation
        # -------------------------------------------------------------------
        raw_scores = [si_score, bl_score, other_score]
        max_s = max(raw_scores)
        exp_scores = [math.exp(s - max_s) for s in raw_scores]
        sum_exp = sum(exp_scores)

        p_si = round(exp_scores[0] / sum_exp, 3)
        p_bl = round(exp_scores[1] / sum_exp, 3)
        p_other = round(exp_scores[2] / sum_exp, 3)

        # Enforce exact sum = 1.0
        delta = round(1.0 - (p_si + p_bl + p_other), 3)
        p_other = round(p_other + delta, 3)

        type_probs = [("SI", p_si), ("BL", p_bl), ("OTHER", p_other)]
        type_probs.sort(key=lambda x: x[1], reverse=True)
        top_type, top_conf = type_probs[0]
        second_type, second_conf = type_probs[1]

        is_ambiguous = (top_conf < self.confidence_threshold) or ((top_conf - second_conf) < 0.25)

        return {
            "file": file_path,
            "SI_probability": p_si,
            "BL_probability": p_bl,
            "OTHER_probability": p_other,
            "selected_type": top_type,
            "confidence": top_conf,
            "evidence": evidence,
            "unreadable": False,
            "is_ambiguous": is_ambiguous,
            "extracted_info": ext_info,
        }


def score_document(file_path: str, ext_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Functional convenience helper."""
    classifier = DocumentClassifier()
    return classifier.score_document(file_path, ext_info)
