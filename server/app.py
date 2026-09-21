#!/usr/bin/env python3
"""
SDOC hackathon inbox + scoring server.

Serves the dataset to participants over HTTP and scores their submissions
against a ground-truth file that is mounted PRIVATELY and never exposed on any
endpoint.

Public (participant) endpoints
    GET  /health                      liveness probe
    GET  /                            API index
    GET  /emails                      list all email records (no labels)
    GET  /emails/{email_id}           one email record
    GET  /attachments/{path}          download an SI/BL attachment
    GET  /sample_submission           the exact output shape to produce
    POST /submit                      score a submission -> scoreboard JSON

Judge-only endpoint (guarded by X-Judge-Token, off unless JUDGE_TOKEN is set)
    GET  /ground_truth                the labels (returns 404 when disabled)

Environment
    DATA_DIR       default /data           (mount data_v2 here, read-only)
    GROUND_TRUTH   default /secrets/ground_truth.json   (private mount)
    REVEAL_GT      "1" to enable /ground_truth (default off)
    JUDGE_TOKEN    if set, /ground_truth requires header X-Judge-Token: <token>
"""
import json
import os
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.middleware.wsgi import WSGIMiddleware

sys.path.insert(0, str(Path(__file__).parent.resolve()))
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from app_ui import app as flask_app
from jinja2 import Template

import scoring

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
INBOX_DIR = DATA_DIR / "inbox"
ATTACH_DIR = DATA_DIR / "attachments"
GROUND_TRUTH_PATH = Path(os.environ.get("GROUND_TRUTH", "/secrets/ground_truth.json"))
SAMPLE_PATH = DATA_DIR / "sample_submission.json"
REVEAL_GT = os.environ.get("REVEAL_GT", "0") == "1"
JUDGE_TOKEN = os.environ.get("JUDGE_TOKEN")

app = FastAPI(title="SDOC Hackathon Inbox", version="2.0",
              description="Serves the shipping-docs inbox and scores submissions. "
                          "Ground truth is held privately and never served.")


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _load_inbox():
    """All email records, sorted by id. Labels are NOT here — inbox files only
    contain email_id/from/subject/body/attachments."""
    out = []
    for p in sorted(INBOX_DIR.glob("email_*.json")):
        out.append(json.loads(p.read_text()))
    return out


def _load_ground_truth():
    if not GROUND_TRUTH_PATH.exists():
        raise HTTPException(503, "ground truth not mounted; scoring unavailable")
    return json.loads(GROUND_TRUTH_PATH.read_text())


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SDOC Verification Dashboard</title>
    <style>
        body { font-family: -apple-system, system-ui, sans-serif; margin: 20px; background: #f5f7f9; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }
        .disclaimer { background: #fff3cd; color: #856404; padding: 10px 15px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; border: 1px solid #ffeeba; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .stat-box { background: #e3f2fd; padding: 15px; border-radius: 8px; text-align: center; }
        .stat-box.score { background: #e8f5e9; }
        .stat-box h3 { margin: 0; font-size: 14px; color: #555; }
        .stat-box .num { font-size: 24px; font-weight: bold; color: #1976d2; margin-top: 5px; }
        .stat-box.score .num { color: #2e7d32; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .badge { padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
        .badge.ok { background: #e8f5e9; color: #2e7d32; }
        .badge.mismatch { background: #ffebee; color: #c62828; }
        .badge.needs_review { background: #fff3e0; color: #ef6c00; }
        .defects { font-family: monospace; font-size: 12px; background: #f1f3f4; padding: 2px 4px; border-radius: 4px; }
        .section-title { margin-top: 30px; margin-bottom: 15px; color: #333; border-bottom: 2px solid #ccc; padding-bottom: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>SDOC Verification Dashboard</h1>
        </div>
        
        <div class="disclaimer">
            <strong>Note:</strong> Final Score reflects the official self-evaluation metrics. Status counts show the current pipeline decisions and are not themselves the final score.
        </div>
        
        <h2 class="section-title">SELF-EVALUATION RESULTS</h2>
        {% if score %}
        <div class="grid" style="margin-bottom: 20px;">
            <div class="stat-box score">
                <h3>Final Score</h3>
                <div class="num">{{ "%.4f"|format(score.final_score) }}</div>
            </div>
            <div class="stat-box score">
                <h3>Stage 1 Macro F1</h3>
                <div class="num">{{ "%.1f"|format(score.stage1.macro_f1 * 100) }}%</div>
            </div>
            <div class="stat-box score">
                <h3>Stage 3 Defect F1</h3>
                <div class="num">{{ "%.1f"|format(score.stage3.defect_f1 * 100) }}%</div>
            </div>
            <div class="stat-box score">
                <h3>Field F1</h3>
                <div class="num">{{ "%.1f"|format(score.stage3.field_f1 * 100) }}%</div>
            </div>
            <div class="stat-box score">
                <h3>End-to-End Rate</h3>
                <div class="num">{{ score.end_to_end.success }}/{{ score.end_to_end.total }}</div>
            </div>
            <div class="stat-box score">
                <h3>Exact Match Rate</h3>
                <div class="num">{{ "%.1f"|format(score.stage3.exact_match_rate * 100) }}%</div>
            </div>
            <div class="stat-box score">
                <h3>Reliability Recall</h3>
                <div class="num">{{ "%.1f"|format(score.reliability.escalation_recall * 100) }}%</div>
            </div>
            <div class="stat-box score">
                <h3>Reliability Precision</h3>
                <div class="num">{{ "%.1f"|format(score.reliability.escalation_precision * 100) }}%</div>
            </div>
        </div>
        {% else %}
        <div class="card" style="background: #f8f9fa; border: 1px dashed #ccc; text-align: center; color: #777;">
            <p>Self-evaluation score not available. (Run scorer to generate score_result.json)</p>
        </div>
        {% endif %}

        <h2 class="section-title">PIPELINE STATUS</h2>
        <div class="grid">
            <div class="stat-box">
                <h3>Total Emails</h3>
                <div class="num">{{ summary.total }}</div>
            </div>
            <div class="stat-box">
                <h3>Non-Document Emails</h3>
                <div class="num">{{ summary.non_doc }}</div>
            </div>
            <div class="stat-box">
                <h3>BL_COMPARISON Emails</h3>
                <div class="num">{{ summary.bl_comp }}</div>
            </div>
            <div class="stat-box">
                <h3>OK</h3>
                <div class="num" style="color: #2e7d32;">{{ summary.ok }}</div>
            </div>
            <div class="stat-box">
                <h3>MISMATCH</h3>
                <div class="num" style="color: #c62828;">{{ summary.mismatch }}</div>
            </div>
            <div class="stat-box">
                <h3>NEEDS_REVIEW</h3>
                <div class="num" style="color: #ef6c00;">{{ summary.needs_review }}</div>
            </div>
        </div>

        <div class="card">
            <h2>Human Review Queue</h2>
            <table>
                <tr>
                    <th>Email ID</th>
                    <th>Status</th>
                    <th>Reason</th>
                    <th>Defect Fields</th>
                </tr>
                {% for item in items %}
                {% if item.status == 'NEEDS_REVIEW' %}
                <tr>
                    <td>{{ item.email_id }}</td>
                    <td><span class="badge needs_review">NEEDS_REVIEW</span></td>
                    <td>{{ item.review_reason }}</td>
                    <td></td>
                </tr>
                {% endif %}
                {% endfor %}
            </table>
        </div>

        <div class="card">
            <h2>Discrepancies Found</h2>
            <table>
                <tr>
                    <th>Email ID</th>
                    <th>Status</th>
                    <th>Defect Fields</th>
                </tr>
                {% for item in items %}
                {% if item.status == 'MISMATCH' %}
                <tr>
                    <td>{{ item.email_id }}</td>
                    <td><span class="badge mismatch">MISMATCH</span></td>
                    <td>
                        {% for field in item.defect_fields %}
                        <span class="defects">{{ field }}</span>
                        {% endfor %}
                    </td>
                </tr>
                {% endif %}
                {% endfor %}
            </table>
        </div>
    </div>
</body>
</html>
"""


# --------------------------------------------------------------------------
# public endpoints
# --------------------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok",
            "emails": len(list(INBOX_DIR.glob("email_*.json"))),
            "scoring_available": GROUND_TRUTH_PATH.exists()}


@app.get("/api")
def api_index():
    return {
        "api": "SDOC Hackathon Inbox",
        "endpoints": {
            "GET /health": "liveness probe",
            "GET /emails": "list all email records",
            "GET /emails/{email_id}": "one email record",
            "GET /attachments/{path}": "download an SI/BL attachment",
            "GET /sample_submission": "the output shape you must produce",
            "POST /submit": "score your submission (JSON body: {email_id: {...}})",
        },
        "note": "Ground truth is private. Score yourself via POST /submit.",
    }


@app.get("/", response_class=HTMLResponse)
def index():
    try:
        with open('submission.json') as f:
            data = json.load(f)
    except:
        data = {}
        
    try:
        with open('score_result.json') as f:
            score = json.load(f)
    except:
        score = None
    
    non_doc_count = sum(1 for v in data.values() if v.get('category') != 'BL_COMPARISON')
    bl_comp_count = sum(1 for v in data.values() if v.get('category') == 'BL_COMPARISON')
    
    summary = {
        'total': len(data),
        'non_doc': non_doc_count,
        'bl_comp': bl_comp_count,
        'ok': sum(1 for v in data.values() if v.get('category') == 'BL_COMPARISON' and v.get('status') == 'OK'),
        'mismatch': sum(1 for v in data.values() if v.get('category') == 'BL_COMPARISON' and v.get('status') == 'MISMATCH'),
        'needs_review': sum(1 for v in data.values() if v.get('category') == 'BL_COMPARISON' and v.get('status') == 'NEEDS_REVIEW')
    }
    
    items = []
    for k, v in data.items():
        if v.get('category') == 'BL_COMPARISON':
            items.append({
                'email_id': k,
                'status': v.get('status'),
                'review_reason': v.get('review_reason', ''),
                'defect_fields': v.get('defect_fields', [])
            })
    
    t = Template(HTML_TEMPLATE)
    return t.render(summary=summary, items=items, score=score)


@app.get("/emails")
def list_emails():
    return _load_inbox()


@app.get("/emails/{email_id}")
def get_email(email_id: str):
    p = INBOX_DIR / f"{email_id}.json"
    if not p.exists():
        raise HTTPException(404, f"no such email: {email_id}")
    return json.loads(p.read_text())


@app.get("/attachments/{path:path}")
def get_attachment(path: str):
    # normalise and confine to ATTACH_DIR (no path traversal)
    target = (ATTACH_DIR / path).resolve()
    if not str(target).startswith(str(ATTACH_DIR.resolve())) or not target.is_file():
        raise HTTPException(404, f"no such attachment: {path}")
    return FileResponse(target)


@app.get("/sample_submission")
def sample_submission():
    if not SAMPLE_PATH.exists():
        raise HTTPException(404, "sample_submission.json not found")
    return json.loads(SAMPLE_PATH.read_text())


@app.post("/submit")
async def submit(request: Request):
    """Score a submission against the private ground truth. The ground truth is
    never returned — only the scoreboard."""
    try:
        sub = await request.json()
    except Exception:
        raise HTTPException(400, "body must be JSON: {email_id: {category,status,has_defect,defect_fields}}")
    if not isinstance(sub, dict):
        raise HTTPException(400, "submission must be a JSON object keyed by email_id")
    truth = _load_ground_truth()
    result = scoring.score_all(truth, sub)
    return JSONResponse(result)


# --------------------------------------------------------------------------
# judge-only (disabled by default)
# --------------------------------------------------------------------------
@app.get("/ground_truth")
def ground_truth(x_judge_token: Optional[str] = Header(default=None)):
    if not REVEAL_GT:
        raise HTTPException(404, "not found")
    if JUDGE_TOKEN and x_judge_token != JUDGE_TOKEN:
        raise HTTPException(403, "bad judge token")
    return _load_ground_truth()
