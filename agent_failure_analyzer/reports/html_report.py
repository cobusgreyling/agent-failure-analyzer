"""Standalone HTML report output."""

from __future__ import annotations

import json
from pathlib import Path

from ..models import AnalysisResult, BatchAnalysisResult
from .json_report import JSONReporter


class HTMLReporter:
    """Export analysis results as a self-contained HTML file."""

    def __init__(self) -> None:
        self._json = JSONReporter()

    def batch_to_html(self, batch: BatchAnalysisResult) -> str:
        """Render batch results as a standalone HTML report."""
        data = self._json.batch_to_dict(batch)
        return _render_html(data)

    def session_to_html(self, result: AnalysisResult) -> str:
        """Render a single session as a standalone HTML report."""
        data = self._json.session_to_dict(result)
        # Wrap single session in batch-like structure for the template
        category_counts: dict[str, int] = {}
        severity_counts: dict[str, int] = {}
        for f in result.failures:
            cat = f.category.value
            sev = f.severity.value
            category_counts[cat] = category_counts.get(cat, 0) + 1
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        wrapped: dict[str, object] = {
            "total_sessions": 1,
            "failed_sessions": 1 if result.failures else 0,
            "category_counts": category_counts,
            "severity_counts": severity_counts,
            "top_failures": [],
            "sessions": [data],
        }
        return _render_html(wrapped)

    def write_batch(self, batch: BatchAnalysisResult, path: str | Path) -> None:
        Path(path).write_text(self.batch_to_html(batch))

    def write_session(self, result: AnalysisResult, path: str | Path) -> None:
        Path(path).write_text(self.session_to_html(result))


def _render_html(data: dict) -> str:
    """Render the standalone HTML report."""
    sessions_json = json.dumps(data.get("sessions", []))
    category_json = json.dumps(data.get("category_counts", {}))
    severity_json = json.dumps(data.get("severity_counts", {}))
    top_failures_json = json.dumps(data.get("top_failures", []))
    total_sessions = data.get("total_sessions", 0)
    failed_sessions = data.get("failed_sessions", 0)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Failure Analysis Report</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f6f8fa;
            color: #24292f;
            line-height: 1.6;
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ font-size: 1.75rem; margin-bottom: 0.5rem; }}
        .subtitle {{ color: #57606a; margin-bottom: 2rem; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }}
        .stat-card {{
            background: white;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            padding: 1rem;
        }}
        .stat-card .label {{ color: #57606a; font-size: 0.8rem; text-transform: uppercase; }}
        .stat-card .value {{ font-size: 1.75rem; font-weight: 700; }}
        .stat-card .value.danger {{ color: #cf222e; }}
        .stat-card .value.warning {{ color: #9a6700; }}
        .stat-card .value.success {{ color: #1a7f37; }}
        .chart-section {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        .card {{
            background: white;
            border: 1px solid #d0d7de;
            border-radius: 6px;
            padding: 1.25rem;
        }}
        .card h3 {{ font-size: 0.95rem; margin-bottom: 1rem; color: #24292f; }}
        .bar-row {{ display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.4rem; }}
        .bar-label {{ width: 160px; font-size: 0.8rem; color: #57606a; text-align: right; }}
        .bar-track {{ flex: 1; height: 20px; background: #f0f0f0; border-radius: 3px; overflow: hidden; }}
        .bar-fill {{
            height: 100%; border-radius: 3px; display: flex; align-items: center;
            padding-left: 6px; font-size: 0.7rem; font-weight: 600; color: white; min-width: 24px;
        }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ text-align: left; padding: 0.6rem; border-bottom: 2px solid #d0d7de;
             font-size: 0.75rem; text-transform: uppercase; color: #57606a; }}
        td {{ padding: 0.6rem; border-bottom: 1px solid #eaeef2; font-size: 0.85rem; }}
        tr:hover {{ background: #f6f8fa; }}
        .badge {{
            display: inline-block; padding: 0.1rem 0.4rem; border-radius: 10px;
            font-size: 0.7rem; font-weight: 600;
        }}
        .badge-critical {{ background: #ffebe9; color: #cf222e; }}
        .badge-high {{ background: #ffebe9; color: #cf222e; }}
        .badge-medium {{ background: #fff8c5; color: #9a6700; }}
        .badge-low {{ background: #dafbe1; color: #1a7f37; }}
        .badge-info {{ background: #ddf4ff; color: #0969da; }}
        .risk-meter {{ width: 50px; height: 6px; background: #eee; border-radius: 3px;
                       display: inline-block; vertical-align: middle; margin-right: 0.4rem; }}
        .risk-fill {{ height: 100%; border-radius: 3px; }}
        .footer {{ margin-top: 2rem; text-align: center; color: #8c959f; font-size: 0.8rem; }}
        @media (max-width: 768px) {{ .chart-section {{ grid-template-columns: 1fr; }} }}
    </style>
</head>
<body>
<div class="container">
    <h1>Agent Failure Analysis Report</h1>
    <p class="subtitle">{total_sessions} session(s) analyzed</p>
    <div class="stats-grid" id="stats"></div>
    <div class="chart-section" id="charts"></div>
    <div class="card">
        <h3>Sessions</h3>
        <table>
            <thead>
                <tr><th>Session</th><th>Framework</th><th>Model</th><th>Risk</th>
                    <th>Failures</th><th>Outcome</th><th>Tokens</th></tr>
            </thead>
            <tbody id="sessions-body"></tbody>
        </table>
    </div>
    <p class="footer">Generated by Agent Failure Analyzer</p>
</div>
<script>
const sessions = {sessions_json};
const categories = {category_json};
const severities = {severity_json};
const topFailures = {top_failures_json};
const totalSessions = {total_sessions};
const failedSessions = {failed_sessions};
const totalFailures = sessions.reduce((s, x) => s + (x.failure_count || x.failures?.length || 0), 0);
const failRate = totalSessions > 0 ? (failedSessions / totalSessions * 100).toFixed(0) : 0;

const sevColors = {{critical:'#cf222e',high:'#cf222e',medium:'#9a6700',low:'#1a7f37',info:'#0969da'}};
const catColors = ['#cf222e','#bc4c00','#9a6700','#1a7f37','#0969da','#8250df','#bf3989','#57606a'];

function riskColor(s) {{ return s >= 0.7 ? '#cf222e' : s >= 0.4 ? '#9a6700' : '#1a7f37'; }}

document.getElementById('stats').innerHTML = `
    <div class="stat-card"><div class="label">Total Sessions</div><div class="value">${{totalSessions}}</div></div>
    <div class="stat-card"><div class="label">Failed Sessions</div><div class="value ${{failedSessions>0?'danger':'success'}}">${{failedSessions}}</div></div>
    <div class="stat-card"><div class="label">Total Failures</div><div class="value ${{totalFailures>0?'warning':'success'}}">${{totalFailures}}</div></div>
    <div class="stat-card"><div class="label">Failure Rate</div><div class="value ${{failRate>30?'danger':failRate>10?'warning':'success'}}">${{failRate}}%</div></div>
`;

function barChart(title, data, colors) {{
    const entries = Object.entries(data).sort((a,b)=>b[1]-a[1]);
    const max = Math.max(...entries.map(e=>e[1]),1);
    const bars = entries.map(([k,v],i) => {{
        const color = typeof colors==='object'&&!Array.isArray(colors)?(colors[k]||catColors[i%catColors.length]):catColors[i%catColors.length];
        const pct = (v/max*100).toFixed(0);
        return `<div class="bar-row"><div class="bar-label">${{k}}</div><div class="bar-track"><div class="bar-fill" style="width:${{pct}}%;background:${{color}}">${{v}}</div></div></div>`;
    }}).join('');
    return `<div class="card"><h3>${{title}}</h3>${{bars}}</div>`;
}}

const topObj = {{}};
(topFailures||[]).forEach(t => topObj[t.subcategory] = t.count);
document.getElementById('charts').innerHTML =
    barChart('By Category', categories, catColors) +
    barChart('By Severity', severities, sevColors) +
    (Object.keys(topObj).length > 0 ? barChart('Top Failures', topObj, catColors) : '');

const tbody = document.getElementById('sessions-body');
sessions.sort((a,b)=>(b.risk_score||0)-(a.risk_score||0)).forEach(s => {{
    const rc = riskColor(s.risk_score||0);
    const pct = ((s.risk_score||0)*100).toFixed(0);
    const fails = (s.failures||[]).slice(0,3).map(f=>`<span class="badge badge-${{f.severity}}">${{f.subcategory}}</span>`).join(' ') || '<span style="color:#1a7f37">None</span>';
    const row = document.createElement('tr');
    row.innerHTML = `
        <td style="font-family:monospace;font-size:0.8rem">${{(s.session_id||'').substring(0,24)}}</td>
        <td>${{s.framework||''}}</td>
        <td style="font-size:0.8rem">${{s.model||'-'}}</td>
        <td><div class="risk-meter"><div class="risk-fill" style="width:${{pct}}%;background:${{rc}}"></div></div><span style="color:${{rc}}">${{pct}}%</span></td>
        <td>${{fails}}</td>
        <td>${{s.outcome||''}}</td>
        <td>${{s.total_tokens?s.total_tokens.toLocaleString():'-'}}</td>
    `;
    tbody.appendChild(row);
}});
</script>
</body>
</html>"""
