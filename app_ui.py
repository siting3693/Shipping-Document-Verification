from flask import Flask, render_template_string, jsonify
import json
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SheepMeal Verification Dashboard</title>
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
            <h1>SheepMeal Verification Dashboard</h1>
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
        <div class="card">
            <p>No scorer result available yet. Run the pipeline with --submit to generate score_result.json.</p>
        </div>
        {% endif %}

        <h2 class="section-title">PIPELINE STATUS</h2>
        <div class="grid" style="margin-bottom: 20px;">
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
                <div class="num">{{ summary.ok }}</div>
            </div>
            <div class="stat-box">
                <h3>MISMATCH</h3>
                <div class="num">{{ summary.mismatch }}</div>
            </div>
            <div class="stat-box">
                <h3>NEEDS_REVIEW</h3>
                <div class="num">{{ summary.needs_review }}</div>
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
        
        <div class="card">
            <h2>Clean Matches (OK)</h2>
            <table>
                <tr>
                    <th>Email ID</th>
                    <th>Status</th>
                </tr>
                {% for item in items %}
                {% if item.status == 'OK' %}
                <tr>
                    <td>{{ item.email_id }}</td>
                    <td><span class="badge ok">OK</span></td>
                </tr>
                {% endif %}
                {% endfor %}
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
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
    
    return render_template_string(HTML_TEMPLATE, summary=summary, items=items, score=score)

if __name__ == '__main__':
    app.run(port=5000)
