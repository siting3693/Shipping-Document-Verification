#!/usr/bin/env python3
"""Check emails with attachments that were classified as non-BL_COMPARISON."""
import json
from loader import Inbox
from classify_emails import classify_email

inbox = Inbox('.')
emails = list(inbox)

# Check non-BL emails that have attachments
non_bl_with_att = []
for email in emails:
    atts = email.get('attachments', [])
    if not atts:
        continue
    decision = classify_email(email, inbox)
    cat = decision['category']
    if cat != 'BL_COMPARISON':
        non_bl_with_att.append({
            'id': email['email_id'],
            'cat': cat,
            'subject': email['subject'][:120],
            'body': email.get('body', '')[:200],
            'atts': atts,
        })

print(f"Non-BL_COMPARISON emails WITH attachments: {len(non_bl_with_att)}")
for m in non_bl_with_att:
    print(f"  {m['id']}: {m['cat']}")
    print(f"    subject: {m['subject']}")
    print(f"    body: {m['body'][:100]}")
    print(f"    attachments: {m['atts']}")
    print()

# Also show the subjects of BL emails that have no explicit comparison words
bl_emails = []
for email in emails:
    decision = classify_email(email, inbox)
    if decision['category'] == 'BL_COMPARISON':
        bl_emails.append(email)

# Show BL subjects to understand patterns
print(f"\nBL_COMPARISON subjects ({len(bl_emails)} total):")
for e in bl_emails[:5]:
    print(f"  {e['email_id']}: {e['subject'][:120]}")

# Count how many emails are in each category that have attachments
cat_att_counts = {}
for email in emails:
    decision = classify_email(email, inbox)
    cat = decision['category']
    has_att = bool(email.get('attachments'))
    key = f"{cat}_{'att' if has_att else 'no_att'}"
    cat_att_counts[key] = cat_att_counts.get(key, 0) + 1

print(f"\nCategory vs attachment counts:")
for k, v in sorted(cat_att_counts.items()):
    print(f"  {k}: {v}")
