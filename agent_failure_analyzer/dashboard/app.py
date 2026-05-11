"""FastAPI web dashboard application."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from ..analyzers.engine import AnalysisEngine
from ..reports.json_report import JSONReporter


def create_app(log_path: Path) -> FastAPI:
    """Create and configure the dashboard FastAPI app."""
    app = FastAPI(title="Agent Failure Analyzer", version="0.1.0")
    engine = AnalysisEngine()
    reporter = JSONReporter()

    # Analyze on startup
    if log_path.is_dir():
        batch = engine.analyze_directory(log_path)
    else:
        results = engine.analyze_file(log_path)
        batch = engine.analyze_sessions([r.session for r in results])

    batch_data = reporter.batch_to_dict(batch)

    @app.get("/", response_class=HTMLResponse)
    async def index():
        return _render_dashboard(batch_data)

    @app.get("/api/report", response_class=JSONResponse)
    async def api_report():
        return batch_data

    @app.get("/api/sessions", response_class=JSONResponse)
    async def api_sessions():
        return batch_data.get("sessions", [])

    @app.get("/api/sessions/{session_id}", response_class=JSONResponse)
    async def api_session(session_id: str):
        for s in batch_data.get("sessions", []):
            if s["session_id"] == session_id:
                return s
        return JSONResponse({"error": "Session not found"}, status_code=404)

    @app.post("/api/refresh", response_class=JSONResponse)
    async def api_refresh():
        nonlocal batch, batch_data
        if log_path.is_dir():
            batch = engine.analyze_directory(log_path)
        else:
            results = engine.analyze_file(log_path)
            batch = engine.analyze_sessions([r.session for r in results])
        batch_data = reporter.batch_to_dict(batch)
        return {"status": "refreshed", "total_sessions": batch_data["total_sessions"]}

    return app


def _render_dashboard(data: dict) -> str:
    """Render the dashboard HTML with embedded data."""
    sessions_json = _safe_json(data.get("sessions", []))
    category_json = _safe_json(data.get("category_counts", {}))
    severity_json = _safe_json(data.get("severity_counts", {}))
    top_failures_json = _safe_json(data.get("top_failures", []))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Failure Analyzer</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f1117;
            color: #e1e4e8;
            line-height: 1.5;
        }}
        .header {{
            background: linear-gradient(135deg, #1a1e2e 0%, #2d1b3d 100%);
            padding: 2rem;
            border-bottom: 1px solid #30363d;
        }}
        .header h1 {{ font-size: 1.75rem; font-weight: 600; }}
        .header p {{ color: #8b949e; margin-top: 0.25rem; }}
        .container {{ max-width: 1400px; margin: 0 auto; padding: 1.5rem; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .stat-card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1.25rem;
        }}
        .stat-card .label {{ color: #8b949e; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }}
        .stat-card .value {{ font-size: 2rem; font-weight: 700; margin-top: 0.25rem; }}
        .stat-card .value.danger {{ color: #f85149; }}
        .stat-card .value.warning {{ color: #d29922; }}
        .stat-card .value.success {{ color: #3fb950; }}
        .charts-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        .chart-card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1.5rem;
        }}
        .chart-card h3 {{
            font-size: 1rem;
            margin-bottom: 1rem;
            color: #c9d1d9;
        }}
        .bar-chart {{ display: flex; flex-direction: column; gap: 0.5rem; }}
        .bar-row {{
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }}
        .bar-label {{
            width: 180px;
            font-size: 0.85rem;
            color: #8b949e;
            text-align: right;
            flex-shrink: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .bar-track {{
            flex: 1;
            height: 24px;
            background: #21262d;
            border-radius: 4px;
            overflow: hidden;
        }}
        .bar-fill {{
            height: 100%;
            border-radius: 4px;
            display: flex;
            align-items: center;
            padding-left: 8px;
            font-size: 0.75rem;
            font-weight: 600;
            min-width: 30px;
        }}
        .sessions-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 1rem;
        }}
        .sessions-table th {{
            text-align: left;
            padding: 0.75rem;
            border-bottom: 2px solid #30363d;
            color: #8b949e;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .sessions-table td {{
            padding: 0.75rem;
            border-bottom: 1px solid #21262d;
            font-size: 0.9rem;
        }}
        .sessions-table tr:hover {{ background: #161b22; }}
        .badge {{
            display: inline-block;
            padding: 0.15rem 0.5rem;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 600;
        }}
        .badge-critical {{ background: #f8514922; color: #f85149; }}
        .badge-high {{ background: #f8514922; color: #ff7b72; }}
        .badge-medium {{ background: #d2992222; color: #d29922; }}
        .badge-low {{ background: #3fb95022; color: #3fb950; }}
        .badge-info {{ background: #8b949e22; color: #8b949e; }}
        .risk-meter {{
            width: 60px;
            height: 8px;
            background: #21262d;
            border-radius: 4px;
            overflow: hidden;
            display: inline-block;
            vertical-align: middle;
            margin-right: 0.5rem;
        }}
        .risk-fill {{ height: 100%; border-radius: 4px; }}
        .failure-list {{ list-style: none; }}
        .failure-list li {{
            padding: 0.5rem 0;
            border-bottom: 1px solid #21262d;
            font-size: 0.85rem;
        }}
        .failure-list .desc {{ color: #c9d1d9; }}
        .failure-list .meta {{ color: #8b949e; font-size: 0.75rem; }}
        .refresh-btn {{
            background: #238636;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.85rem;
            float: right;
        }}
        .refresh-btn:hover {{ background: #2ea043; }}
        .detail-panel {{
            display: none;
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 1.5rem;
            margin-top: 0.5rem;
        }}
        .detail-panel.active {{ display: block; }}
        @media (max-width: 768px) {{
            .charts-grid {{ grid-template-columns: 1fr; }}
            .bar-label {{ width: 100px; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div style="max-width:1400px;margin:0 auto;display:flex;justify-content:space-between;align-items:center;">
            <div>
                <h1>Agent Failure Analyzer</h1>
                <p>Session failure classification and diagnostics</p>
            </div>
            <button class="refresh-btn" onclick="refresh()">Refresh</button>
        </div>
    </div>
    <div class="container">
        <div class="stats-grid" id="stats"></div>
        <div class="charts-grid" id="charts"></div>
        <div class="chart-card">
            <h3>Sessions</h3>
            <table class="sessions-table">
                <thead>
                    <tr>
                        <th>Session ID</th>
                        <th>Framework</th>
                        <th>Model</th>
                        <th>Risk</th>
                        <th>Failures</th>
                        <th>Outcome</th>
                        <th>Tokens</th>
                    </tr>
                </thead>
                <tbody id="sessions-body"></tbody>
            </table>
        </div>
    </div>

    <script>
    const sessions = {sessions_json};
    const categories = {category_json};
    const severities = {severity_json};
    const topFailures = {top_failures_json};

    const totalSessions = {data.get('total_sessions', 0)};
    const failedSessions = {data.get('failed_sessions', 0)};
    const totalFailures = sessions.reduce((s, x) => s + x.failure_count, 0);
    const failRate = totalSessions > 0 ? (failedSessions / totalSessions * 100).toFixed(0) : 0;

    const sevColors = {{
        critical: '#f85149', high: '#ff7b72', medium: '#d29922',
        low: '#3fb950', info: '#8b949e'
    }};
    const catColors = [
        '#f85149','#ff7b72','#d29922','#3fb950','#58a6ff',
        '#bc8cff','#f778ba','#79c0ff','#7ee787','#ffa657'
    ];

    function riskColor(s) {{
        if (s >= 0.7) return '#f85149';
        if (s >= 0.4) return '#d29922';
        return '#3fb950';
    }}

    // Stats
    document.getElementById('stats').innerHTML = `
        <div class="stat-card">
            <div class="label">Total Sessions</div>
            <div class="value">${{totalSessions}}</div>
        </div>
        <div class="stat-card">
            <div class="label">Failed Sessions</div>
            <div class="value ${{failedSessions > 0 ? 'danger' : 'success'}}">${{failedSessions}}</div>
        </div>
        <div class="stat-card">
            <div class="label">Total Failures</div>
            <div class="value ${{totalFailures > 0 ? 'warning' : 'success'}}">${{totalFailures}}</div>
        </div>
        <div class="stat-card">
            <div class="label">Failure Rate</div>
            <div class="value ${{failRate > 30 ? 'danger' : failRate > 10 ? 'warning' : 'success'}}">${{failRate}}%</div>
        </div>
    `;

    // Charts
    function barChart(title, data, colors) {{
        const entries = Object.entries(data).sort((a,b) => b[1] - a[1]);
        const max = Math.max(...entries.map(e => e[1]), 1);
        const bars = entries.map(([k, v], i) => {{
            const color = typeof colors === 'object' && !Array.isArray(colors)
                ? (colors[k] || catColors[i % catColors.length])
                : catColors[i % catColors.length];
            const pct = (v / max * 100).toFixed(0);
            return `<div class="bar-row">
                <div class="bar-label">${{k}}</div>
                <div class="bar-track">
                    <div class="bar-fill" style="width:${{pct}}%;background:${{color}}">${{v}}</div>
                </div>
            </div>`;
        }}).join('');
        return `<div class="chart-card"><h3>${{title}}</h3><div class="bar-chart">${{bars}}</div></div>`;
    }}

    const topObj = {{}};
    topFailures.forEach(t => topObj[t.subcategory] = t.count);

    document.getElementById('charts').innerHTML =
        barChart('Failures by Category', categories, catColors) +
        barChart('Failures by Severity', severities, sevColors) +
        barChart('Top Failure Types', topObj, catColors);

    // Sessions table
    const tbody = document.getElementById('sessions-body');
    sessions.sort((a,b) => b.risk_score - a.risk_score).forEach(s => {{
        const rc = riskColor(s.risk_score);
        const pct = (s.risk_score * 100).toFixed(0);
        const topFail = s.failures.length > 0
            ? s.failures.map(f => `<span class="badge badge-${{f.severity}}">${{f.subcategory}}</span>`).slice(0,3).join(' ')
            : '<span style="color:#3fb950">None</span>';
        const row = document.createElement('tr');
        row.style.cursor = 'pointer';
        row.innerHTML = `
            <td style="font-family:monospace;font-size:0.8rem">${{s.session_id.substring(0,24)}}</td>
            <td>${{s.framework}}</td>
            <td style="font-size:0.8rem">${{s.model || '-'}}</td>
            <td>
                <div class="risk-meter"><div class="risk-fill" style="width:${{pct}}%;background:${{rc}}"></div></div>
                <span style="color:${{rc}}">${{pct}}%</span>
            </td>
            <td>${{topFail}}</td>
            <td>${{s.outcome}}</td>
            <td>${{s.total_tokens ? s.total_tokens.toLocaleString() : '-'}}</td>
        `;
        row.onclick = () => toggleDetail(s.session_id);
        tbody.appendChild(row);

        // Detail panel
        const detailRow = document.createElement('tr');
        detailRow.id = 'detail-' + s.session_id;
        detailRow.style.display = 'none';
        const failHtml = s.failures.length > 0
            ? '<ul class="failure-list">' + s.failures.map(f => `
                <li>
                    <span class="badge badge-${{f.severity}}">${{f.severity}}</span>
                    <span class="desc">${{f.description}}</span>
                    <div class="meta">Category: ${{f.category}} | Subcategory: ${{f.subcategory}} | Confidence: ${{(f.confidence*100).toFixed(0)}}%</div>
                    ${{f.evidence.length > 0 ? '<div class="meta">Evidence: ' + f.evidence.slice(0,2).join('; ').substring(0,200) + '</div>' : ''}}
                </li>
            `).join('') + '</ul>'
            : '<p style="color:#3fb950">No failures detected</p>';
        detailRow.innerHTML = `<td colspan="7" style="padding:0"><div class="detail-panel active">${{failHtml}}</div></td>`;
        tbody.appendChild(detailRow);
    }});

    function toggleDetail(id) {{
        const row = document.getElementById('detail-' + id);
        row.style.display = row.style.display === 'none' ? '' : 'none';
    }}

    async function refresh() {{
        const res = await fetch('/api/refresh', {{ method: 'POST' }});
        if (res.ok) location.reload();
    }}
    </script>
</body>
</html>"""


def _safe_json(obj) -> str:
    import json
    return json.dumps(obj)
