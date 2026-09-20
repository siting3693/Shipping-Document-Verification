import json
gt = json.load(open('data_v2/ground_truth.json'))
sub = json.load(open('submission.json'))

end_to_end = []
for k, v in gt.items():
    if v['has_defect'] == True:
        end_to_end.append(k)

for k in end_to_end:
    gv = gt[k]
    sv = sub.get(k, {})
    if sv.get('has_defect') != True or set(sv.get('defect_fields', [])) != set(gv['defect_fields']):
        print(f"Failed E2E: {k}")
        print(f"  Gold fields: {gv['defect_fields']}")
        print(f"  Pred fields: {sv.get('defect_fields', [])}")
        print(f"  Pred status: {sv.get('status')}")
