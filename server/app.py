#!/usr/bin/env python3
"""
SDOC hackathon inbox + scoring server.

Serves the dataset to participants over HTTP and scores their submissions
against a ground-truth file that is mounted PRIVATELY and never exposed on any
endpoint.

Public (participant) endpoints
    GET  /health                      liveness probe
    GET  /                            dashboard (HTML)
    GET  /api                         API index
    GET  /emails                      list all email records (no labels)
    GET  /emails/{email_id}           one email record
    GET  /attachments/{path}          download an SI/BL attachment
    GET  /sample_submission           the exact output shape to produce
    POST /submit                      score a submission -> scoreboard JSON
    POST /api/initialize              trigger pipeline run
    GET  /api/case/{email_id}         case detail for dashboard modal

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
import asyncio
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from jinja2 import Template

sys.path.insert(0, str(Path(__file__).parent.resolve()))
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import scoring

pipeline_lock = asyncio.Lock()
pipeline_running = False

DATA_DIR = Path(os.environ.get("DATA_DIR", "."))
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


# --------------------------------------------------------------------------
# Dashboard HTML template
# --------------------------------------------------------------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SDOC Verification Dashboard</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; margin: 20px; background: #f5f7f9; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header h1 { margin: 0 0 10px 0; }
        .disclaimer { background: #fff3cd; color: #856404; padding: 10px 15px; border-radius: 6px; margin-bottom: 20px; font-size: 14px; border: 1px solid #ffeeba; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.08); margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
        .stat-box { background: #e3f2fd; padding: 15px; border-radius: 8px; text-align: center; }
        .stat-box.score { background: #e8f5e9; }
        .stat-box h3 { margin: 0; font-size: 13px; color: #555; text-transform: uppercase; letter-spacing: 0.3px; }
        .stat-box .num { font-size: 26px; font-weight: 700; color: #1976d2; margin-top: 6px; }
        .stat-box.score .num { color: #2e7d32; }
        .stat-box.clickable { cursor: pointer; transition: transform 0.15s, box-shadow 0.15s; position: relative; border: 2px solid transparent; }
        .stat-box.clickable:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(0,0,0,0.12); }
        .stat-box.clickable.active { border-color: #1976d2; }
        .stat-box .hint { font-size: 11px; color: #999; margin-top: 5px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; font-size: 14px; }
        th { background: #f8f9fa; font-weight: 600; color: #555; font-size: 13px; text-transform: uppercase; letter-spacing: 0.3px; }
        .badge { padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; display: inline-block; }
        .badge.ok { background: #e8f5e9; color: #2e7d32; }
        .badge.mismatch { background: #ffebee; color: #c62828; }
        .badge.needs_review { background: #fff3e0; color: #ef6c00; }
        .defects { font-family: 'SF Mono', Monaco, monospace; font-size: 12px; background: #f1f3f4; padding: 2px 6px; border-radius: 4px; margin-right: 4px; display: inline-block; margin-bottom: 2px; }
        .section-title { margin-top: 30px; margin-bottom: 15px; color: #333; border-bottom: 2px solid #ddd; padding-bottom: 5px; font-size: 16px; }
        .accordion { max-height: 0; overflow: hidden; transition: max-height 0.3s ease-out; }
        .accordion.open { max-height: 2000px; transition: max-height 0.5s ease-in; }
        .btn-view { background: #1976d2; color: white; border: none; padding: 5px 14px; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 500; }
        .btn-view:hover { background: #1565c0; }

        .modal-overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.45); z-index: 1000; justify-content: center; align-items: flex-start; padding-top: 40px; }
        .modal-overlay.open { display: flex; }
        .modal { background: white; border-radius: 10px; width: 92%; max-width: 820px; max-height: 85vh; overflow-y: auto; box-shadow: 0 12px 40px rgba(0,0,0,0.25); }
        .modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #eee; position: sticky; top: 0; background: white; z-index: 1; border-radius: 10px 10px 0 0; }
        .modal-header h2 { margin: 0; font-size: 18px; }
        .modal-close { background: none; border: none; font-size: 26px; cursor: pointer; color: #888; padding: 0 4px; line-height: 1; }
        .modal-close:hover { color: #333; }
        .modal-body { padding: 20px; }
        .field-row { display: flex; gap: 12px; padding: 8px 0; border-bottom: 1px solid #f5f5f5; }
        .field-label { font-weight: 600; min-width: 130px; color: #555; font-size: 13px; flex-shrink: 0; }
        .field-value { flex: 1; font-size: 13px; word-break: break-word; }
        .email-body { background: #f8f9fa; padding: 14px; border-radius: 6px; max-height: 200px; overflow-y: auto; font-size: 13px; line-height: 1.6; white-space: pre-wrap; word-break: break-word; margin: 8px 0; border: 1px solid #eee; }
        .comparison-table { width: 100%; margin-top: 8px; border: 1px solid #eee; border-radius: 6px; overflow: hidden; }
        .comparison-table th { font-size: 12px; background: #f0f4f8; }
        .comparison-table td { font-size: 13px; }
        .comparison-table tr.diff td { background: #fff5f5; }
        .comparison-table tr.missing td { background: #fffde7; }
        .comparison-table .status-icon { font-weight: 600; }
        .comparison-table .status-icon.match { color: #2e7d32; }
        .comparison-table .status-icon.mismatch { color: #c62828; }
        .comparison-table .status-icon.missing { color: #ef6c00; }
        .modal-footer { padding: 12px 20px; border-top: 1px solid #eee; text-align: right; }
        .modal-footer .btn-close { background: #666; color: white; border: none; padding: 8px 20px; border-radius: 4px; cursor: pointer; font-size: 13px; }
        .modal-footer .btn-close:hover { background: #555; }
        .loading { text-align: center; padding: 30px; color: #888; }
        .sub-heading { font-size: 14px; font-weight: 600; color: #333; margin: 16px 0 6px 0; }
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
            <div class="stat-box score"><h3>Final Score</h3><div class="num">{{ "%.4f"|format(score.final_score) }}</div></div>
            <div class="stat-box score"><h3>Stage 1 Macro F1</h3><div class="num">{{ "%.1f"|format(score.stage1.macro_f1 * 100) }}%</div></div>
            <div class="stat-box score"><h3>Stage 3 Defect F1</h3><div class="num">{{ "%.1f"|format(score.stage3.defect_f1 * 100) }}%</div></div>
            <div class="stat-box score"><h3>Field F1</h3><div class="num">{{ "%.1f"|format(score.stage3.field_f1 * 100) }}%</div></div>
            <div class="stat-box score"><h3>End-to-End Rate</h3><div class="num">{{ score.end_to_end.success }}/{{ score.end_to_end.total }}</div></div>
            <div class="stat-box score"><h3>Exact Match Rate</h3><div class="num">{{ "%.1f"|format(score.stage3.exact_match_rate * 100) }}%</div></div>
            <div class="stat-box score"><h3>Reliability Recall</h3><div class="num">{{ "%.1f"|format(score.reliability.escalation_recall * 100) }}%</div></div>
            <div class="stat-box score"><h3>Reliability Precision</h3><div class="num">{{ "%.1f"|format(score.reliability.escalation_precision * 100) }}%</div></div>
        </div>
        {% else %}
        <div class="card" style="background: #f8f9fa; border: 1px dashed #ccc; text-align: center; color: #777;">
            <p>Self-evaluation score not available. (Run scorer to generate score_result.json)</p>
        </div>
        {% endif %}

        <h2 class="section-title">PIPELINE STATUS</h2>
        {% if initializing %}
        <div class="card" style="background: #e3f2fd; border: 1px dashed #2196f3; text-align: center; color: #0d47a1;">
            {% if pipeline_running %}
            <p><strong>Pipeline is processing documents...</strong><br>Refreshing automatically.</p>
            <script>setTimeout(function(){ window.location.reload(); }, 3000);</script>
            {% else %}
            <p id="status-msg"><strong>Pipeline is waiting to initialize...</strong></p>
            <script>
                document.getElementById('status-msg').innerHTML = '<strong>Starting pipeline initialization...</strong><br>This may take a moment. Please stay on this page.';
                fetch('/api/initialize', {method: 'POST'})
                    .then(function(r){ window.location.reload(); })
                    .catch(function(e){ document.getElementById('status-msg').innerText = 'Initialization failed. Please refresh the page.'; });
            </script>
            {% endif %}
        </div>
        {% else %}
        <div class="grid">
            <div class="stat-box"><h3>Total Emails</h3><div class="num">{{ summary.total }}</div></div>
            <div class="stat-box"><h3>Non-Document</h3><div class="num">{{ summary.non_doc }}</div></div>
            <div class="stat-box"><h3>BL_COMPARISON</h3><div class="num">{{ summary.bl_comp }}</div></div>
            <div class="stat-box"><h3>OK</h3><div class="num" style="color: #2e7d32;">{{ summary.ok }}</div></div>
            <div class="stat-box clickable" id="card-mismatch" onclick="togglePanel('mismatch')">
                <h3>MISMATCH</h3>
                <div class="num" style="color: #c62828;">{{ summary.mismatch }}</div>
                <div class="hint">Click to inspect &#9662;</div>
            </div>
            <div class="stat-box clickable" id="card-review" onclick="togglePanel('review')">
                <h3>NEEDS_REVIEW</h3>
                <div class="num" style="color: #ef6c00;">{{ summary.needs_review }}</div>
                <div class="hint">Click to inspect &#9662;</div>
            </div>
        </div>

        <!-- MISMATCH accordion -->
        <div id="panel-mismatch" class="accordion">
            <div class="card" style="margin-top:12px;">
                <h2 style="margin-top:0;">Discrepancies Found ({{ summary.mismatch }})</h2>
                <table>
                    <tr><th>Email ID</th><th>Defective Field(s)</th><th style="width:80px">Action</th></tr>
                    {% for item in items %}{% if item.status == 'MISMATCH' %}
                    <tr>
                        <td>{{ item.email_id }}</td>
                        <td>{% for f in item.defect_fields %}<span class="defects">{{ f }}</span>{% endfor %}</td>
                        <td><button class="btn-view" onclick="openCase('{{ item.email_id }}')">View</button></td>
                    </tr>
                    {% endif %}{% endfor %}
                </table>
            </div>
        </div>

        <!-- NEEDS_REVIEW accordion -->
        <div id="panel-review" class="accordion">
            <div class="card" style="margin-top:12px;">
                <h2 style="margin-top:0;">Human Review Queue ({{ summary.needs_review }})</h2>
                <table>
                    <tr><th>Email ID</th><th>Reason</th><th style="width:80px">Action</th></tr>
                    {% for item in items %}{% if item.status == 'NEEDS_REVIEW' %}
                    <tr>
                        <td>{{ item.email_id }}</td>
                        <td><span class="badge needs_review">{{ item.review_reason }}</span></td>
                        <td><button class="btn-view" onclick="openCase('{{ item.email_id }}')">View</button></td>
                    </tr>
                    {% endif %}{% endfor %}
                </table>
            </div>
        </div>
        {% endif %}
    </div>

    <!-- Case Detail Modal -->
    <div id="case-modal" class="modal-overlay" onclick="if(event.target===this)closeModal()">
        <div class="modal">
            <div class="modal-header">
                <h2 id="modal-title">Case Detail</h2>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="modal-body" id="modal-body">
                <div class="loading">Loading...</div>
            </div>
            <div class="modal-footer">
                <button class="btn-close" onclick="closeModal()">Close</button>
            </div>
        </div>
    </div>

    <script>
    function togglePanel(name) {
        var panel = document.getElementById('panel-' + name);
        var card = document.getElementById('card-' + name);
        var wasOpen = panel.classList.contains('open');

        // close all
        document.querySelectorAll('.accordion').forEach(function(a){ a.classList.remove('open'); });
        document.querySelectorAll('.stat-box.clickable').forEach(function(b){ b.classList.remove('active'); });

        if (!wasOpen) {
            panel.classList.add('open');
            card.classList.add('active');
            setTimeout(function(){ panel.scrollIntoView({behavior:'smooth', block:'nearest'}); }, 50);
        }
    }

    function openCase(emailId) {
        var modal = document.getElementById('case-modal');
        var body = document.getElementById('modal-body');
        document.getElementById('modal-title').textContent = emailId;
        body.innerHTML = '<div class="loading">Loading case details...</div>';
        modal.classList.add('open');
        document.body.style.overflow = 'hidden';

        fetch('/api/case/' + emailId)
            .then(function(r){ 
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json(); 
            })
            .then(function(data){ renderCase(data, body); })
            .catch(function(err){ body.innerHTML = '<p style="color:#c62828;text-align:center">Failed to load case details.</p>'; });
    }

    function closeModal() {
        document.getElementById('case-modal').classList.remove('open');
        document.body.style.overflow = '';
    }

    document.addEventListener('keydown', function(e){ if(e.key==='Escape') closeModal(); });

    function esc(s) {
        if (!s && s !== 0) return '<span style="color:#aaa">&mdash;</span>';
        var d = document.createElement('div');
        d.textContent = String(s);
        return d.innerHTML;
    }

    function renderCase(data, container) {
        var h = '';

        // Metadata
        h += '<div class="field-row"><span class="field-label">Email ID</span><span class="field-value"><strong>' + esc(data.email_id) + '</strong></span></div>';
        h += '<div class="field-row"><span class="field-label">From</span><span class="field-value">' + esc(data.from) + '</span></div>';
        h += '<div class="field-row"><span class="field-label">Subject</span><span class="field-value">' + esc(data.subject) + '</span></div>';
        h += '<div class="field-row"><span class="field-label">Classification</span><span class="field-value"><code>' + esc(data.category) + '</code></span></div>';

        // Decision badge
        var cls = data.status === 'MISMATCH' ? 'mismatch' : data.status === 'NEEDS_REVIEW' ? 'needs_review' : 'ok';
        h += '<div class="field-row"><span class="field-label">Decision</span><span class="field-value"><span class="badge ' + cls + '">' + esc(data.status) + '</span></span></div>';

        if (data.review_reason) {
            h += '<div class="field-row"><span class="field-label">Review Reason</span><span class="field-value">' + esc(data.review_reason) + '</span></div>';
        }
        if (data.defect_fields && data.defect_fields.length > 0) {
            h += '<div class="field-row"><span class="field-label">Defect Fields</span><span class="field-value">' +
                data.defect_fields.map(function(f){ return '<span class="defects">' + esc(f) + '</span>'; }).join(' ') + '</span></div>';
        }

        // Attachments
        h += '<div class="field-row"><span class="field-label">Attachments</span><span class="field-value">';
        if (data.attachments && data.attachments.length > 0) {
            h += data.attachments.map(function(a){ return '<code style="margin-right:8px">' + esc(a) + '</code>'; }).join('');
        } else {
            h += '<span style="color:#aaa">None</span>';
        }
        h += '</span></div>';

        // Email body
        h += '<div class="sub-heading">Email Body</div>';
        h += '<div class="email-body">' + esc(data.body || 'No body content available.') + '</div>';

        // Field comparison
        if (data.fields && Object.keys(data.fields).length > 0) {
            h += '<div class="sub-heading">Field Comparison &mdash; SI vs BL</div>';
            h += '<table class="comparison-table"><tr><th>Field</th><th>SI Value</th><th>BL Value</th><th style="width:90px">Status</th></tr>';
            var defects = data.defect_fields || [];
            Object.keys(data.fields).forEach(function(field) {
                var v = data.fields[field];
                var si = v.si || '', bl = v.bl || '';
                var isDiff = defects.indexOf(field) !== -1;
                var isMissing = !si || !bl;
                var rowCls = isDiff ? 'diff' : (isMissing ? 'missing' : '');
                var iconCls = isDiff ? 'mismatch' : (isMissing ? 'missing' : 'match');
                var label = isDiff ? '&#10008; Mismatch' : (isMissing ? '&#63; Missing' : '&#10004; Match');
                h += '<tr class="' + rowCls + '"><td>' + esc(field) + '</td><td>' + esc(si || '—') + '</td><td>' + esc(bl || '—') + '</td>';
                h += '<td><span class="status-icon ' + iconCls + '">' + label + '</span></td></tr>';
            });
            h += '</table>';
        }

        container.innerHTML = h;
    }
    </script>
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
            "POST /api/initialize": "trigger pipeline initialization",
            "GET /api/case/{email_id}": "case detail for dashboard inspection",
        },
        "note": "Ground truth is private. Score yourself via POST /submit.",
    }


@app.post("/api/initialize")
async def initialize():
    global pipeline_running
    if pipeline_lock.locked():
        return {"status": "already running"}

    async with pipeline_lock:
        if Path('submission.json').exists():
            return {"status": "already complete"}

        pipeline_running = True
        try:
            process = await asyncio.create_subprocess_exec(
                sys.executable, "main.py", ".",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

            if GROUND_TRUTH_PATH.exists():
                env = os.environ.copy()
                env["GROUND_TRUTH"] = str(GROUND_TRUTH_PATH)
                score_proc = await asyncio.create_subprocess_exec(
                    sys.executable, "_score_local.py",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env
                )
                stdout, _ = await score_proc.communicate()
                Path('score_result.json').write_bytes(stdout)
        finally:
            pipeline_running = False

    return {"status": "complete"}


@app.get("/api/case/{email_id}")
def get_case_detail(email_id: str):
    """Return enriched case detail for the dashboard modal.
    Combines email fixture data, submission decision, and re-extracted field
    values from attachments so the UI can render a side-by-side comparison."""

    # Fallback logic for path resolution (mirroring loader.py / main.py)
    email_path = (INBOX_DIR / f"{email_id}.json").resolve()
    if not email_path.exists():
        fallback_path = (Path(__file__).parent.parent / "inbox" / f"{email_id}.json").resolve()
        if fallback_path.exists():
            email_path = fallback_path

    # Load email fixture
    if not email_path.exists():
        raise HTTPException(404, f"no such email: {email_id} (looked in {email_path})")
    email = json.loads(email_path.read_text())

    # Load submission decision
    sub = {}
    try:
        sub = json.loads(Path('submission.json').read_text()).get(email_id, {})
    except Exception:
        pass

    result = {
        "email_id": email.get("email_id", email_id),
        "from": email.get("from", ""),
        "subject": email.get("subject", ""),
        "body": email.get("body", ""),
        "attachments": email.get("attachments", []),
        "category": sub.get("category", ""),
        "status": sub.get("status", ""),
        "review_reason": sub.get("review_reason"),
        "defect_fields": sub.get("defect_fields", []),
        "has_defect": sub.get("has_defect", False),
        "fields": {},
    }

    # Extract fields from attachments for comparison view
    if sub.get("category") == "BL_COMPARISON":
        try:
            from document_parser import parse_document
            from field_extraction import extract_fields

            si_fields = {}
            bl_fields = {}
            for att_path in email.get("attachments", []):
                full = (DATA_DIR / att_path).resolve()
                if not full.exists():
                    full = (Path(__file__).parent.parent / att_path).resolve()
                if full.exists():
                    parsed = parse_document(str(full))
                    fields = extract_fields(parsed)
                    if "_SI" in str(full) or "_SI." in str(full):
                        si_fields = fields
                    elif "_BL" in str(full) or "_BL." in str(full):
                        bl_fields = fields

            all_keys = sorted(set(list(si_fields.keys()) + list(bl_fields.keys())))
            for key in all_keys:
                si_obj = si_fields.get(key, {})
                bl_obj = bl_fields.get(key, {})
                si_val = si_obj.get("normalized_value") if isinstance(si_obj, dict) else si_obj
                bl_val = bl_obj.get("normalized_value") if isinstance(bl_obj, dict) else bl_obj
                result["fields"][key] = {
                    "si": si_val if si_val is not None else "",
                    "bl": bl_val if bl_val is not None else "",
                }
        except Exception:
            # Field extraction is best-effort for the UI; never crash
            pass

    return result


@app.get("/", response_class=HTMLResponse)
def dashboard():
    try:
        with open('submission.json') as f:
            data = json.load(f)
    except Exception:
        data = {}

    try:
        with open('score_result.json') as f:
            score = json.load(f)
    except Exception:
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

    initializing = (len(data) == 0)

    t = Template(HTML_TEMPLATE)
    return t.render(summary=summary, items=items, score=score,
                    initializing=initializing, pipeline_running=pipeline_running)


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
