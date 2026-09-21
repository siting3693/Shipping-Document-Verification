import json
from loader import Inbox
from attachment_resolver import resolve_attachments
from document_parser import parse_document
from field_extraction import extract_fields
from comparison_engine import compare_documents

inbox = Inbox('.')
emails_to_check = ['email_313', 'email_351', 'email_434', 'email_499']

try:
    with open('data_v2/ground_truth.json') as f:
        gold = json.load(f)
except:
    gold = {}

for eid in emails_to_check:
    print(f'\n================ FORENSIC: {eid} ================')
    email = next(e for e in inbox.emails() if e['email_id'] == eid)
    res = resolve_attachments(email, inbox)
    
    si_doc = res.get('si_doc')
    bl_doc = res.get('bl_doc')
    
    si_fields = extract_fields(si_doc) if si_doc else {}
    bl_fields = extract_fields(bl_doc) if bl_doc else {}
    
    comp = compare_documents(si_fields, bl_fields) if si_doc and bl_doc else {'status': 'NEEDS_REVIEW', 'review_reason': 'missing_attachment'}
    
    print(f"[ATTACHMENTS]")
    print(f"SI path: {res.get('si_path')} | BL path: {res.get('bl_path')}")
    print(f"SI doc_type: {si_doc.get('doc_type') if si_doc else 'None'} | Error: {si_doc.get('error') if si_doc else 'None'}")
    print(f"BL doc_type: {bl_doc.get('doc_type') if bl_doc else 'None'} | Error: {bl_doc.get('error') if bl_doc else 'None'}")
    
    print(f"\n[EXTRACTION]")
    print(f"SI Fields: { {k: v.get('normalized_value') for k, v in si_fields.items() if v.get('normalized_value') is not None} }")
    print(f"BL Fields: { {k: v.get('normalized_value') for k, v in bl_fields.items() if v.get('normalized_value') is not None} }")
    
    print(f"\n[COMPARISON]")
    print(f"Status: {comp['status']}")
    print(f"Defect Fields: {comp.get('defect_fields', [])}")
    print(f"Review Reason: {comp.get('review_reason', '')}")
    
    if eid in gold:
        print(f"\n[GROUND TRUTH]")
        print(f"Status: {gold[eid]['status']}")
        print(f"Defect Fields: {gold[eid].get('defect_fields', [])}")
        
    print(f"\n[RAW DOC TEXT PREVIEW (first 250 chars)]")
    print(f"SI:\n{si_doc.get('raw_text', '')[:250] if si_doc else ''}")
    print(f"BL:\n{bl_doc.get('raw_text', '')[:250] if bl_doc else ''}")
