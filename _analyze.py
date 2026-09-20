#!/usr/bin/env python3
"""Analyze classifier misses — find emails with SI+BL attachments not classified as BL_COMPARISON."""
import json
from loader import Inbox
from classify_emails import classify_email

inbox = Inbox('.')
emails = list(inbox)

missed = []
for email in emails:
    atts = email.get('attachments', [])
    has_si = any('_SI.' in a for a in atts)
    has_bl = any('_BL.' in a for a in atts)
    
    decision = classify_email(email, inbox)
    cat = decision['category']
    
    if has_si and has_bl and cat != 'BL_COMPARISON':
        missed.append({
            'id': email['email_id'],
            'cat': cat,
            'subject': email['subject'][:100],
            'body_start': email.get('body', '')[:100],
            'scores': {k: round(v, 1) for k, v in decision['scores'].items()},
            'matched': decision['matched_rules'][:5],
        })
    elif not has_si and not has_bl and cat == 'BL_COMPARISON':
        print(f"FALSE POSITIVE: {email['email_id']} classified as BL_COMPARISON but no SI/BL attachments")
        print(f"  subject: {email['subject'][:100]}")
        print(f"  attachments: {atts}")
        print()

print(f"\nMissed BL_COMPARISON emails (have SI+BL but classified as {len(missed)} other):")
for m in missed[:30]:
    print(f"  {m['id']}: classified as {m['cat']}")
    print(f"    subject: {m['subject']}")
    print(f"    body: {m['body_start']}")
    print(f"    scores: {m['scores']}")
    print(f"    matched: {m['matched']}")
    print()

# Also count emails with attachments (potential BL_COMPARISON) 
has_att = sum(1 for e in emails if e.get('attachments'))
has_si_bl = sum(1 for e in emails if any('_SI.' in a for a in e.get('attachments', [])) and any('_BL.' in a for a in e.get('attachments', [])))
print(f"\nTotal emails: {len(emails)}")
print(f"Emails with any attachments: {has_att}")
print(f"Emails with SI+BL pair: {has_si_bl}")
