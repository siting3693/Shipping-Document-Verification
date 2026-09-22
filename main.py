#!/usr/bin/env python3
"""
main.py — Complete end-to-end shipping document verification pipeline.

Pipeline:
1. Load inbox emails
2. Classify each email (Stage 1)
3. For BL_COMPARISON emails:
   a. Resolve SI and BL attachments
   b. Parse documents
   c. Extract 7 canonical fields
   d. Normalize values
   e. Compare fields deterministically
   f. Generate defect_fields and status
4. Handle NEEDS_REVIEW cases (missing/wrong/unreadable)
5. Generate submission JSON
6. Optionally submit to scorer
"""

import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from loader import Inbox
from classify_emails import classify_email, CATEGORIES, validate_submission
from attachment_resolver import resolve_attachments
from field_extraction import extract_fields
from comparison_engine import compare_documents

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('sdoc_pipeline')


def process_bl_comparison(email: dict, inbox: Inbox) -> dict:
    """Process a BL_COMPARISON email through the full verification pipeline.
    
    Returns a result dict with status, defect_fields, has_defect, review_reason.
    """
    email_id = email['email_id']
    
    # Step 1: Resolve attachments (identify SI and BL)
    resolution = resolve_attachments(email, inbox)
    
    if resolution['status'] == 'NEEDS_REVIEW':
        logger.info(f"  {email_id}: NEEDS_REVIEW ({resolution['review_reason']}) — {resolution['details']}")
        return {
            'status': 'NEEDS_REVIEW',
            'review_reason': resolution['review_reason'],
            'defect_fields': [],
            'has_defect': False,
            '_details': resolution['details'],
        }
    
    if resolution['status'] == 'OK_EMPTY':
        logger.info(f"  {email_id}: OK — {resolution['details']}")
        return {
            'status': 'OK',
            'review_reason': None,
            'defect_fields': [],
            'has_defect': False,
            '_details': resolution['details'],
        }
    
    si_doc = resolution['si_doc']
    bl_doc = resolution['bl_doc']
    
    # Step 2: Extract fields from both documents
    try:
        si_fields = extract_fields(si_doc)
        bl_fields = extract_fields(bl_doc)
        
        # Garbled text detection -> Gemini fallback
        from gemini_fallback import is_garbled, extract_with_gemini
        
        # Check SI fields
        if any(is_garbled(str(f.get('raw_value', ''))) for f in si_fields.values()):
            logger.info(f"  {email_id}: Garbled text detected in SI! Triggering AI fallback...")
            gemini_data = extract_with_gemini(inbox.read_bytes(resolution['si_path']))
            if gemini_data:
                for k, v in gemini_data.items():
                    if k in si_fields:
                        si_fields[k]['normalized_value'] = v
                        si_fields[k]['method'] = 'gemini_fallback'
                        
        # Check BL fields
        if any(is_garbled(str(f.get('raw_value', ''))) for f in bl_fields.values()):
            logger.info(f"  {email_id}: Garbled text detected in BL! Triggering AI fallback...")
            gemini_data = extract_with_gemini(inbox.read_bytes(resolution['bl_path']))
            if gemini_data:
                for k, v in gemini_data.items():
                    if k in bl_fields:
                        bl_fields[k]['normalized_value'] = v
                        bl_fields[k]['method'] = 'gemini_fallback'
    except Exception as e:
        logger.error(f"  {email_id}: Field extraction failed: {e}")
        return {
            'status': 'NEEDS_REVIEW',
            'review_reason': 'unreadable',
            'defect_fields': [],
            'has_defect': False,
            '_details': f'Field extraction failed: {e}',
        }
    
    # Step 3: Compare documents
    try:
        comparison = compare_documents(si_fields, bl_fields)
    except Exception as e:
        logger.error(f"  {email_id}: Comparison failed: {e}")
        return {
            'status': 'NEEDS_REVIEW',
            'review_reason': 'unreadable',
            'defect_fields': [],
            'has_defect': False,
            '_details': f'Comparison failed: {e}',
        }
    
    logger.info(f"  {email_id}: {comparison['status']} — {comparison['summary']}")
    if comparison['defect_fields']:
        logger.info(f"    Defect fields: {comparison['defect_fields']}")
    
    return {
        'status': comparison['status'],
        'review_reason': comparison.get('review_reason'),
        'defect_fields': comparison['defect_fields'],
        'has_defect': comparison['has_defect'],
        '_field_results': comparison.get('field_results', []),
        '_summary': comparison['summary'],
    }


def run_pipeline(source: str = ".", submit: bool = False) -> dict:
    """Run the full verification pipeline.
    
    Args:
        source: Data source (local path or HTTP URL)
        submit: Whether to POST to /submit endpoint
    
    Returns:
        The submission dict
    """
    start = time.time()
    inbox = Inbox(source)
    emails = list(inbox)
    sample = inbox.sample_submission()
    
    logger.info(f"Loaded {len(emails)} emails from {source}")
    
    submission: dict[str, dict[str, Any]] = {}
    stats = {
        'total': len(emails),
        'categories': Counter(),
        'verification': Counter(),
        'formats': Counter(),
        'errors': Counter(),
    }
    
    for email in emails:
        email_id = email['email_id']
        
        # Stage 1: Classify
        decision = classify_email(email, inbox)
        category = decision['category']
        stats['categories'][category] += 1
        
        if category == 'BL_COMPARISON':
            # Stage 2+3: Full verification pipeline
            result = process_bl_comparison(email, inbox)
            
            submission[email_id] = {
                'category': category,
                'status': result['status'],
                'review_reason': result['review_reason'],
                'defect_fields': result['defect_fields'],
                'has_defect': result['has_defect'],
            }
            stats['verification'][result['status']] += 1
            
            # Track attachment formats
            for att in email.get('attachments', []):
                ext = Path(att).suffix.lower().lstrip('.')
                stats['formats'][ext] += 1
        else:
            # Non-comparison emails: default output
            submission[email_id] = {
                'category': category,
                'status': 'OK',
                'review_reason': None,
                'defect_fields': [],
                'has_defect': False,
            }
    
    # Validate submission
    try:
        validate_submission(submission, emails, sample)
        logger.info("✓ Submission schema validated successfully")
    except ValueError as e:
        logger.error(f"✗ Submission validation failed: {e}")
    
    elapsed = time.time() - start
    
    # Print report
    print(f"\n{'='*60}")
    print(f"  SheepMeal VERIFICATION REPORT")
    print(f"{'='*60}")
    print(f"\nEmails processed: {stats['total']}")
    print(f"Processing time: {elapsed:.1f}s")
    print(f"\nStage 1 — Classification:")
    for cat in CATEGORIES:
        print(f"  {cat}: {stats['categories'][cat]}")
    
    print(f"\nStage 2+3 — Verification (BL_COMPARISON only):")
    for status in ['OK', 'MISMATCH', 'NEEDS_REVIEW']:
        print(f"  {status}: {stats['verification'][status]}")
    
    if stats['formats']:
        print(f"\nAttachment Formats Processed:")
        for fmt, count in stats['formats'].most_common():
            print(f"  .{fmt}: {count}")
    
    print(f"\n{'='*60}")
    
    # Save submission
    output_path = Path("submission.json")
    output_path.write_text(json.dumps(submission, indent=2) + "\n", encoding="utf-8")
    logger.info(f"Submission written to {output_path}")
    
    # Submit to scorer if requested
    if submit:
        try:
            logger.info("Submitting to scorer at http://localhost:8080/submit...")
            import httpx
            r = httpx.post("http://localhost:8080/submit", json=submission)
            result = r.json()
            print(f"\n{'='*60}")
            print(f"  SELF-EVALUATION RESULT")
            print(f"{'='*60}")
            print(json.dumps(result, indent=2))
            
            # Save score result
            Path("score_result.json").write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )
        except Exception as e:
            logger.error(f"Submission failed: {e}")
    
    return submission


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else "."
    submit = "--submit" in sys.argv or "-s" in sys.argv
    run_pipeline(source, submit)
