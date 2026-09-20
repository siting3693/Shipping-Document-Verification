#!/usr/bin/env python3
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path("server").resolve()))
from scoring import score_all

gt = json.loads(Path("data_v2/ground_truth.json").read_text(encoding="utf-8"))
sub = json.loads(Path("submission.json").read_text(encoding="utf-8"))

res = score_all(gt, sub)
print(json.dumps(res, indent=2))
