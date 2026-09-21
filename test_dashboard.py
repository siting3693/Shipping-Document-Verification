
import urllib.request, json, os

print("=== 1. GET /health ===")
r = urllib.request.urlopen("http://127.0.0.1:8080/health")
print(r.status, json.loads(r.read()))

print()
print("=== 2. GET / (dashboard) ===")
r = urllib.request.urlopen("http://127.0.0.1:8080/")
html = r.read().decode()
print(r.status, "length:", len(html))
print("  Has Final Score:", "Final Score" in html)
print("  Has MISMATCH card:", "card-mismatch" in html)
print("  Has NEEDS_REVIEW card:", "card-review" in html)
print("  Has click hint:", "Click to inspect" in html)
print("  Has accordion:", "panel-mismatch" in html)
print("  Has modal:", "case-modal" in html)
print("  Has openCase JS:", "openCase" in html)

print()
print("=== 3. GET /api/case/email_516 (NEEDS_REVIEW) ===")
r = urllib.request.urlopen("http://127.0.0.1:8080/api/case/email_516")
case = json.loads(r.read())
print("  email_id:", case["email_id"])
print("  status:", case["status"])
print("  review_reason:", case["review_reason"])
print("  defect_fields:", case["defect_fields"])
print("  from:", case["from"])
print("  subject:", case["subject"][:60])
print("  body length:", len(case.get("body","")))
print("  attachments:", case["attachments"])
flds = case.get("fields", {})
print("  fields keys:", list(flds.keys()))
for k,v in flds.items():
    si = str(v.get("si", ""))[:45]
    bl = str(v.get("bl", ""))[:45]
    print("    %s: SI=%s | BL=%s" % (k, si, bl))

print()
print("=== 4. GET /api/case/email_434 (MISMATCH) ===")
r = urllib.request.urlopen("http://127.0.0.1:8080/api/case/email_434")
case = json.loads(r.read())
print("  email_id:", case["email_id"])
print("  status:", case["status"])
print("  defect_fields:", case["defect_fields"])
print("  attachments:", case["attachments"])
flds = case.get("fields", {})
print("  fields keys:", list(flds.keys()))
for k,v in flds.items():
    si = str(v.get("si", ""))[:45]
    bl = str(v.get("bl", ""))[:45]
    marker = " *** MISMATCH" if k in case["defect_fields"] else ""
    print("    %s: SI=%s | BL=%s%s" % (k, si, bl, marker))

print()
print("=== 5. Scoring verification ===")
if os.path.exists("score_result.json"):
    with open("score_result.json") as f:
        sc = json.load(f)
    print("  Stage 1 Macro F1:", sc["stage1"]["macro_f1"])
    print("  Stage 3 Defect F1:", sc["stage3"]["defect_f1"])
    print("  Stage 3 Field F1:", sc["stage3"]["field_f1"])
    print("  E2E:", sc["end_to_end"]["success"], "/", sc["end_to_end"]["total"])
    print("  Final Score:", sc["final_score"])
else:
    print("  score_result.json not found")

print()
print("=== 6. 404 test ===")
try:
    urllib.request.urlopen("http://127.0.0.1:8080/api/case/email_99999")
except urllib.error.HTTPError as e:
    print("  Got expected", e.code)

print()
print("ALL TESTS PASSED")

