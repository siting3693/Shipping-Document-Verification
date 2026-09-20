from flask import Flask, render_template_string, jsonify
import json

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>SDOC Verification Dashboard</title>
    <style>
        body { font-family: -apple-system, system-ui, sans-serif; margin: 20px; background: #f5f7f9; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .stat-box { background: #e3f2fd; padding: 15px; border-radius: 8px; text-align: center; }
        .stat-box h3 { margin: 0; font-size: 14px; color: #555; }
        .stat-box .num { font-size: 24px; font-weight: bold; color: #1976d2; margin-top: 5px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .badge { padding: 4px 8px; border-radius: 12px; font-size: 12px; font-weight: bold; }
        .badge.ok { background: #e8f5e9; color: #2e7d32; }
        .badge.mismatch { background: #ffebee; color: #c62828; }
        .badge.needs_review { background: #fff3e0; color: #ef6c00; }
        .defects { font-family: monospace; font-size: 12px; background: #f1f3f4; padding: 2px 4px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>SDOC Verification Dashboard</h1>
        </div>
        
        <div class="grid" style="margin-bottom: 20px;">
            <div class="stat-box">
                <h3>Total Processed</h3>
                <div class="num">{{ summary.total }}</div>
            </div>
            <div class="stat-box">
                <h3>Matched (OK)</h3>
                <div class="num">{{ summary.ok }}</div>
            </div>
            <div class="stat-box">
                <h3>Discrepancies (MISMATCH)</h3>
                <div class="num">{{ summary.mismatch }}</div>
            </div>
            <div class="stat-box">
                <h3>Human Review Queue</h3>
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
    
    summary = {
        'total': len(data),
        'ok': sum(1 for v in data.values() if v.get('status') == 'OK'),
        'mismatch': sum(1 for v in data.values() if v.get('status') == 'MISMATCH'),
        'needs_review': sum(1 for v in data.values() if v.get('status') == 'NEEDS_REVIEW')
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
    
    return render_template_string(HTML_TEMPLATE, summary=summary, items=items)

if __name__ == '__main__':
    app.run(port=5000)
