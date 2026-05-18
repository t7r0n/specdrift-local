from __future__ import annotations

from pathlib import Path

import duckdb
from jinja2 import Environment, select_autoescape

from specdrift_local.models import RunSummary, project_root
from specdrift_local.runner import verify_outputs

TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>API Spec Drift Scoreboard</title>
  <style>
    :root { color-scheme: light dark; --bg:#f8fafc; --panel:#fff; --ink:#172033; --muted:#64748b; --line:#dbe3ef; --blue:#2563eb; --green:#0e9f6e; --red:#c2410c; --amber:#d97706; }
    @media (prefers-color-scheme: dark) { :root { --bg:#10141c; --panel:#171e2b; --ink:#eef4ff; --muted:#9aa8bc; --line:#2a3446; --blue:#7aa2ff; --green:#38c989; --red:#ff9363; --amber:#f6b955; } }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    main { max-width:1180px; margin:0 auto; padding:32px 20px 48px; }
    header { display:flex; justify-content:space-between; align-items:flex-end; gap:20px; margin-bottom:24px; }
    h1 { margin:0 0 8px; font-size:28px; letter-spacing:0; }
    h2 { font-size:18px; margin:0 0 14px; }
    p { margin:0; color:var(--muted); }
    .grid { display:grid; gap:16px; }
    .metrics { grid-template-columns:repeat(4, minmax(0, 1fr)); }
    .charts { grid-template-columns:1fr 1fr; margin-top:16px; }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:18px; box-shadow:0 14px 28px rgba(15,23,42,.06); }
    .metric strong { display:block; font-size:26px; line-height:1.1; }
    .metric span { color:var(--muted); font-size:13px; }
    .bar-row { display:grid; grid-template-columns:170px 1fr 64px; gap:12px; align-items:center; margin:12px 0; }
    .track { height:18px; border-radius:999px; background:color-mix(in srgb, var(--line) 75%, transparent); overflow:hidden; border:1px solid var(--line); }
    .fill { height:100%; border-radius:999px; background:linear-gradient(90deg, var(--blue), var(--green)); min-width:2px; }
    table { width:100%; border-collapse:collapse; margin-top:8px; font-size:14px; }
    th, td { text-align:left; padding:10px 8px; border-bottom:1px solid var(--line); }
    th { color:var(--muted); font-weight:600; }
    .pass { color:var(--green); font-weight:700; }
    .fail { color:var(--red); font-weight:700; }
    @media (max-width:780px) { header { display:block; } .metrics, .charts { grid-template-columns:1fr; } }
  </style>
</head>
<body>
<main>
  <header><div><h1>API Spec Drift Scoreboard</h1><p>Run {{ summary.run_id }} · raw OpenAPI, generated MCP, routed-agent modes, and minimal patches.</p></div><p class="{{ 'pass' if verification.passed else 'fail' }}">{{ 'Verification passed' if verification.passed else 'Verification failed' }}</p></header>
  <section class="grid metrics">
    <div class="panel metric"><strong>{{ summary.api_count }}</strong><span>API scorecards</span></div>
    <div class="panel metric"><strong>{{ summary.result_count }}</strong><span>agent-call simulations</span></div>
    <div class="panel metric"><strong>{{ summary.avg_aci }}</strong><span>average ACI</span></div>
    <div class="panel metric"><strong>{{ summary.aci_human_correlation }}</strong><span>human correlation</span></div>
  </section>
  <section class="grid charts">
    <div class="panel">
      <h2>Agent Callability Index</h2>
      {% for row in scores %}
        <div class="bar-row"><strong>{{ row.title }}</strong><div class="track"><div class="fill" style="width: {{ row.aci }}%"></div></div><span>{{ row.aci }}</span></div>
      {% endfor %}
    </div>
    <div class="panel">
      <h2>Drift Types</h2>
      <table><thead><tr><th>Type</th><th>Count</th></tr></thead><tbody>{% for row in drift %}<tr><td>{{ row.drift_type }}</td><td>{{ row.count }}</td></tr>{% endfor %}</tbody></table>
    </div>
  </section>
  <section class="panel" style="margin-top:16px">
    <h2>Mode Comparison</h2>
    <table><thead><tr><th>API</th><th>Raw</th><th>MCP</th><th>Routed</th><th>Patch Gain</th></tr></thead><tbody>{% for row in scores %}<tr><td>{{ row.title }}</td><td>{{ row.raw_aci }}</td><td>{{ row.mcp_aci }}</td><td>{{ row.routed_aci }}</td><td>{{ row.estimated_patch_gain }}</td></tr>{% endfor %}</tbody></table>
  </section>
  <section class="panel" style="margin-top:16px">
    <h2>Verification Gates</h2>
    <table><tbody>{% for key, value in verification.checks.items() %}<tr><td>{{ key }}</td><td class="{{ 'pass' if value else 'fail' }}">{{ value }}</td></tr>{% endfor %}</tbody></table>
  </section>
</main>
</body>
</html>
"""


def dashboard_data() -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    db_path = project_root() / "runs" / "latest" / "specdrift.duckdb"
    conn = duckdb.connect(str(db_path), read_only=True)
    scores = [
        {
            "title": row[0],
            "aci": float(row[1]),
            "raw_aci": float(row[2]),
            "mcp_aci": float(row[3]),
            "routed_aci": float(row[4]),
            "estimated_patch_gain": float(row[5]),
        }
        for row in conn.execute("select title, aci, raw_aci, mcp_aci, routed_aci, estimated_patch_gain from api_scores order by aci desc").fetchall()
    ]
    drift = [
        {"drift_type": row[0], "count": int(row[1])}
        for row in conn.execute("select drift_type, count(*) from call_results where drift_type is not null group by drift_type order by 2 desc").fetchall()
    ]
    conn.close()
    return scores, drift


def build_dashboard() -> Path:
    root = project_root()
    summary_path = root / "outputs" / "summary.json"
    if not summary_path.exists():
        raise FileNotFoundError("Run `uv run specdrift-local score` first.")
    summary = RunSummary.model_validate_json(summary_path.read_text(encoding="utf-8"))
    scores, drift = dashboard_data()
    html = Environment(autoescape=select_autoescape(["html", "xml"])).from_string(TEMPLATE).render(
        summary=summary,
        verification=verify_outputs(),
        scores=scores,
        drift=drift,
    )
    target = root / "outputs" / "dashboard.html"
    target.write_text(html, encoding="utf-8")
    return target


def benchmark_summary() -> dict[str, float]:
    db_path = project_root() / "runs" / "latest" / "specdrift.duckdb"
    conn = duckdb.connect(str(db_path), read_only=True)
    row = conn.execute("select count(*), avg(aci), avg(mcp_aci - raw_aci), avg(routed_aci - raw_aci) from api_scores").fetchone()
    conn.close()
    return {"apis": float(row[0]), "avg_aci": float(row[1]), "avg_mcp_delta": float(row[2]), "avg_routed_delta": float(row[3])}
