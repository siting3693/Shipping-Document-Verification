#!/usr/bin/env python3
"""Debug XLSX and PDF document parsing."""
from document_parser import parse_document
from loader import Inbox

inbox = Inbox('.')

# Test XLSX files
xlsx_tests = [
    'attachments/email_005_SI.xlsx',
    'attachments/email_005_BL.xlsx',
    'attachments/email_055_SI.xlsx',
]

for path in xlsx_tests:
    try:
        content = inbox.read_bytes(path)
        result = parse_document(path, content)
        print(f"\n{path}:")
        print(f"  doc_type: {result['doc_type']}")
        print(f"  fields: {list(result['raw_fields'].keys())[:10]}")
        print(f"  raw_text preview: {result['raw_text'][:200]}")
        if result['error']:
            print(f"  ERROR: {result['error']}")
    except Exception as e:
        print(f"\n{path}: EXCEPTION: {e}")

# Test PDF files 
pdf_tests = [
    'attachments/email_059_SI.pdf',
    'attachments/email_059_BL.pdf',
    'attachments/email_499_SI.pdf',
    'attachments/email_499_BL.pdf',
    'attachments/email_512_SI.pdf',
    'attachments/email_511_BL.pdf',
]

for path in pdf_tests:
    try:
        content = inbox.read_bytes(path)
        result = parse_document(path, content)
        print(f"\n{path}:")
        print(f"  doc_type: {result['doc_type']}")
        print(f"  fields: {list(result['raw_fields'].keys())[:10]}")
        print(f"  raw_text preview: {result['raw_text'][:300]}")
        if result['error']:
            print(f"  ERROR: {result['error']}")
    except Exception as e:
        print(f"\n{path}: EXCEPTION: {e}")

# Test DOCX
docx_tests = [
    'attachments/email_055_BL.docx',
    'attachments/email_097_BL.docx',
]

for path in docx_tests:
    try:
        content = inbox.read_bytes(path)
        result = parse_document(path, content)
        print(f"\n{path}:")
        print(f"  doc_type: {result['doc_type']}")
        print(f"  fields: {list(result['raw_fields'].keys())[:10]}")
        print(f"  raw_text preview: {result['raw_text'][:300]}")
        if result['error']:
            print(f"  ERROR: {result['error']}")
    except Exception as e:
        print(f"\n{path}: EXCEPTION: {e}")
