import json

def validate_schema():
    with open('submission.json') as f:
        sub = json.load(f)
    
    # We can get sample submission from the endpoint
    import urllib.request
    req = urllib.request.urlopen('http://localhost:8080/sample_submission')
    sample = json.loads(req.read().decode('utf-8'))
    
    errors = []
    
    # Check all keys
    if set(sub.keys()) != set(sample.keys()):
        errors.append(f"Key mismatch. Sub keys: {len(sub)}, Sample keys: {len(sample)}")
        
    for k in sample.keys():
        if k not in sub:
            continue
        sv = sub[k]
        
        # Check required fields
        required = ['category', 'status', 'review_reason', 'defect_fields', 'has_defect']
        for r in required:
            if r not in sv:
                errors.append(f"{k} missing {r}")
                
        # Type checks
        if sv.get('category') not in ['BL_COMPARISON', 'SI_REQUEST', 'INVOICE_QUERY', 'GENERAL', 'SPAM']:
            errors.append(f"{k} invalid category: {sv.get('category')}")
            
        if sv.get('status') not in ['OK', 'MISMATCH', 'NEEDS_REVIEW']:
            errors.append(f"{k} invalid status: {sv.get('status')}")
            
        if type(sv.get('has_defect')) != bool:
            errors.append(f"{k} invalid has_defect type")
            
        if type(sv.get('defect_fields')) != list:
            errors.append(f"{k} invalid defect_fields type")
            
    if not errors:
        print("PERFECT MATCH: submission.json matches sample_submission.json exactly in structure and contains every email_id.")
    else:
        for e in errors[:10]:
            print("ERROR:", e)

validate_schema()
