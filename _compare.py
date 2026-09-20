import re
with open('old_rule_classifier.py') as f: old = f.read()
with open('classify_emails.py') as f: curr = f.read()

def get_phrases(txt, key):
    m = re.search(f'"{key}":.*?\\((.*?)\\)', txt, re.DOTALL)
    if not m: return set()
    return {p.strip().strip('"\'') for p in m.group(1).split(',\n') if p.strip()}

print("Old SI:", get_phrases(old, "SI_REQUEST"))
print("Cur SI:", get_phrases(curr, "SI_REQUEST"))
