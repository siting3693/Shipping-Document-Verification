import json
from loader import Inbox
from document_parser import parse_document
import sys

inbox = Inbox('.')
content = inbox.read_bytes('attachments/email_434_SI.pdf')
doc = parse_document('attachments/email_434_SI.pdf', content)
print("434 SI doc_type:", doc['doc_type'])
print(doc['raw_text'][:200].encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))

content = inbox.read_bytes('attachments/email_107_SI.xlsx')
doc = parse_document('attachments/email_107_SI.xlsx', content)
print("\n107 SI doc_type:", doc['doc_type'])
print(doc['raw_text'][:200].encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))

content = inbox.read_bytes('attachments/email_097_BL.docx')
doc = parse_document('attachments/email_097_BL.docx', content)
print("\n097 BL doc_type:", doc['doc_type'])
print(doc['raw_text'][:200].encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))

