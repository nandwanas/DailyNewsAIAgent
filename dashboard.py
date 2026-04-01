"""
Daily Agriculture Newsletter — Web Dashboard
==============================================
Run:  python dashboard.py
Open: http://localhost:5050
"""

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template_string, send_file

BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
NEWSLETTER_DIR = OUTPUT_DIR / "newsletters"
EXCEL_DIR = OUTPUT_DIR / "excel"

app = Flask(__name__)

_run_log: list[str] = []
_running = False
_last_result: dict = {}

# ── HTML Dashboard ─────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🌾 Agriculture Newsletter Agent</title>
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Arial, sans-serif; background: #f1f8e9; color: #333; }
header { background: linear-gradient(135deg,#1b5e20,#388e3c); color: #fff; padding: 20px 28px; display:flex; align-items:center; gap:14px; }
header h1 { font-size: 22px; }
header p { font-size: 13px; opacity: .8; margin-top: 3px; }
.container { max-width: 1000px; margin: 0 auto; padding: 24px 16px; }
.card { background: #fff; border-radius: 12px; padding: 22px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }
.card h2 { font-size: 16px; color: #1b5e20; margin-bottom: 14px; border-bottom: 2px solid #c8e6c9; padding-bottom: 8px; }
.btn { display:inline-block; padding: 11px 24px; border-radius: 8px; border: none; cursor: pointer; font-size: 14px; font-weight: 600; }
.btn-run { background: #2e7d32; color: #fff; }
.btn-run:hover { background: #1b5e20; }
.btn-run:disabled { background: #aaa; cursor: not-allowed; }
.btn-view { background: #e8f5e9; color: #2e7d32; border: 1px solid #a5d6a7; margin-left: 8px; text-decoration: none; }
.btn-dl { background: #e3f2fd; color: #1565c0; border: 1px solid #90caf9; margin-left: 8px; text-decoration: none; }
#log { background: #1a1a2e; color: #a5d6a7; font-family: monospace; font-size: 12px; padding: 14px; border-radius: 8px; height: 220px; overflow-y: auto; white-space: pre-wrap; line-height: 1.6; }
.badge { display:inline-block; padding: 2px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.badge-ok { background: #e8f5e9; color: #2e7d32; }
.badge-err { background: #ffebee; color: #c62828; }
.file-row { display:flex; justify-content:space-between; align-items:center; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.file-row:last-child { border-bottom: none; }
.file-name { font-size: 13px; color: #555; }
.stat-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px,1fr)); gap: 14px; }
.stat-box { background: #e8f5e9; border-radius: 10px; padding: 14px; text-align: center; }
.stat-box .num { font-size: 28px; font-weight: 700; color: #1b5e20; }
.stat-box .label { font-size: 12px; color: #555; margin-top: 4px; }
#status-dot { width: 10px; height: 10px; border-radius: 50%; background: #aaa; display:inline-block; margin-right:6px; }
#status-dot.running { background: #f57c00; animation: pulse .8s infinite; }
#status-dot.done { background: #2e7d32; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }
</style>
</head>
<body>

<header>
  <div style="font-size:40px;">🌾</div>
  <div>
    <h1>Daily Agriculture Newsletter Agent</h1>
    <p>Powered by Claude AI &bull; NewsAPI &bull; 11 Indian Languages</p>
  </div>
</header>

<div class="container">

  <!-- Run Agent -->
  <div class="card">
    <h2>▶ Run Agent</h2>
    <button class="btn btn-run" id="runBtn" onclick="runAgent()">Run Now</button>
    <span id="status-text" style="margin-left:14px;font-size:13px;color:#666;">
      <span id="status-dot"></span>Ready
    </span>
    <div style="margin-top:16px;">
      <div id="log">Logs will appear here when you run the agent…</div>
    </div>
  </div>

  <!-- Stats -->
  <div class="card" id="statsCard" style="display:none">
    <h2>📊 Last Run Stats</h2>
    <div class="stat-grid" id="statsGrid"></div>
  </div>

  <!-- Newsletters -->
  <div class="card">
    <h2>📰 Generated Newsletters</h2>
    <div id="nlList"><em style="color:#aaa;font-size:13px;">No newsletters yet — click Run Now above.</em></div>
  </div>

  <!-- Excel Files -->
  <div class="card">
    <h2>📊 Excel Data Files</h2>
    <div id="xlList"><em style="color:#aaa;font-size:13px;">No Excel files yet.</em></div>
  </div>

  <!-- How to use -->
  <div class="card">
    <h2>ℹ️ How It Works</h2>
    <ol style="padding-left:20px;font-size:13px;line-height:2;color:#555;">
      <li><strong>Fetch</strong> — Pulls today's agriculture news from NewsAPI + 12 RSS feeds</li>
      <li><strong>Analyse</strong> — Claude AI summarises, scores importance, detects sentiment</li>
      <li><strong>Translate</strong> — Translates into 11 Indian languages (EN, HI, MR, BN, TE, TA, GU, KN, ML, PA, OR)</li>
      <li><strong>Newsletter</strong> — Generates self-contained interactive HTML file with language tabs</li>
      <li><strong>Excel</strong> — Exports structured 3-sheet .xlsx for downstream agents</li>
      <li><strong>Email</strong> — Creates Gmail draft with full newsletter (if GMAIL_RECIPIENT set)</li>
    </ol>
  </div>

</div>

<script>
let evtSource = null;

function runAgent() {
  const btn = document.getElementById('runBtn');
  const log = document.getElementById('log');
  const dot = document.getElementById('status-dot');
  const txt = document.getElementById('status-text');

  btn.disabled = true;
  log.textContent = '';
  dot.className = 'running';
  txt.innerHTML = '<span id="status-dot" class="running"></span>Running…';

  fetch('/run', { method: 'POST' })
    .then(r => r.json())
    .then(data => {
      if (data.status === 'started') {
        streamLogs();
      }
    });
}

function streamLogs() {
  const log = document.getElementById('log');
  evtSource = new EventSource('/stream');
  evtSource.onmessage = function(e) {
    const data = JSON.parse(e.data);
    if (data.line) {
      log.textContent += data.line + '\\n';
      log.scrollTop = log.scrollHeight;
    }
    if (data.done) {
      evtSource.close();
      document.getElementById('runBtn').disabled = false;
      document.getElementById('status-text').innerHTML =
        '<span id="status-dot" class="done"></span>Done ✓';
      refreshFiles();
      loadStats();
    }
    if (data.error) {
      evtSource.close();
      document.getElementById('runBtn').disabled = false;
      document.getElementById('status-text').innerHTML =
        '<span id="status-dot" style="background:#c62828"></span>Error';
    }
  };
}

function refreshFiles() {
  fetch('/files').then(r => r.json()).then(data => {
    const nlDiv = document.getElementById('nlList');
    const xlDiv = document.getElementById('xlList');
    nlDiv.innerHTML = data.newsletters.length ? data.newsletters.map(f =>
      `<div class="file-row">
        <span class="file-name">📄 ${f.name}</span>
        <div>
          <a class="btn btn-view" href="/view/${encodeURIComponent(f.name)}" target="_blank">Open in Browser</a>
          <a class="btn btn-dl" href="/download/newsletter/${encodeURIComponent(f.name)}">Download</a>
        </div>
       </div>`
    ).join('') : '<em style="color:#aaa;font-size:13px;">No newsletters yet.</em>';

    xlDiv.innerHTML = data.excel.length ? data.excel.map(f =>
      `<div class="file-row">
        <span class="file-name">📊 ${f.name}</span>
        <a class="btn btn-dl" href="/download/excel/${encodeURIComponent(f.name)}">Download Excel</a>
       </div>`
    ).join('') : '<em style="color:#aaa;font-size:13px;">No Excel files yet.</em>';
  });
}

function loadStats() {
  fetch('/stats').then(r => r.json()).then(data => {
    if (!data.articles) return;
    document.getElementById('statsCard').style.display = 'block';
    document.getElementById('statsGrid').innerHTML = `
      <div class="stat-box"><div class="num">${data.articles}</div><div class="label">Articles Fetched</div></div>
      <div class="stat-box"><div class="num">${data.languages}</div><div class="label">Languages</div></div>
      <div class="stat-box"><div class="num">${data.positive}</div><div class="label">Positive News</div></div>
      <div class="stat-box"><div class="num">${data.duration}s</div><div class="label">Run Duration</div></div>
    `;
  });
}

// Load files on page load
refreshFiles();
</script>
</body>
</html>"""


# ── Agent runner ───────────────────────────────────────────────────────────────

_log_queue: list[str] = []
_agent_done = False
_agent_error = False


def _run_agent_thread():
    global _running, _agent_done, _agent_error, _last_result, _log_queue
    _log_queue = []
    _agent_done = False
    _agent_error = False

    try:
        proc = subprocess.Popen(
            [sys.executable, str(BASE_DIR / "agent.py")],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=str(BASE_DIR),
        )
        for line in proc.stdout:
            line = line.rstrip()
            _log_queue.append(line)
        proc.wait()

        if proc.returncode == 0:
            # Parse last-run stats from most recent newsletter/excel
            nls = sorted(NEWSLETTER_DIR.glob("*.html"), reverse=True) if NEWSLETTER_DIR.exists() else []
            xls = sorted(EXCEL_DIR.glob("*.xlsx"), reverse=True) if EXCEL_DIR.exists() else []
            _last_result = {
                "articles": _count_articles(),
                "languages": 11,
                "positive": 0,
                "duration": "—",
                "newsletter": nls[0].name if nls else "",
                "excel": xls[0].name if xls else "",
            }
            _agent_done = True
        else:
            _agent_error = True
    except Exception as e:
        _log_queue.append(f"ERROR: {e}")
        _agent_error = True
    finally:
        _running = False


def _count_articles():
    """Count lines in latest log for 'articles fetched'."""
    for line in reversed(_log_queue):
        if "articles" in line.lower():
            import re
            m = re.search(r"(\d+)\s+article", line)
            if m:
                return int(m.group(1))
    return "—"


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML)


@app.route("/run", methods=["POST"])
def run():
    global _running
    if _running:
        return jsonify({"status": "already_running"})
    _running = True
    t = threading.Thread(target=_run_agent_thread, daemon=True)
    t.start()
    return jsonify({"status": "started"})


@app.route("/stream")
def stream():
    def generate():
        sent = 0
        while True:
            while sent < len(_log_queue):
                line = _log_queue[sent]
                yield f"data: {json.dumps({'line': line})}\n\n"
                sent += 1
            if _agent_done:
                yield f"data: {json.dumps({'done': True})}\n\n"
                break
            if _agent_error:
                yield f"data: {json.dumps({'error': True})}\n\n"
                break
            time.sleep(0.3)
    return Response(generate(), mimetype="text/event-stream")


@app.route("/files")
def files():
    nls, xls = [], []
    if NEWSLETTER_DIR.exists():
        nls = [{"name": f.name} for f in sorted(NEWSLETTER_DIR.glob("*.html"), reverse=True)]
    if EXCEL_DIR.exists():
        xls = [{"name": f.name} for f in sorted(EXCEL_DIR.glob("*.xlsx"), reverse=True)]
    return jsonify({"newsletters": nls, "excel": xls})


@app.route("/view/<filename>")
def view_newsletter(filename):
    path = NEWSLETTER_DIR / filename
    if not path.exists():
        return "File not found", 404
    return path.read_text(encoding="utf-8")


@app.route("/download/newsletter/<filename>")
def download_newsletter(filename):
    path = NEWSLETTER_DIR / filename
    if not path.exists():
        return "File not found", 404
    return send_file(str(path), as_attachment=True)


@app.route("/download/excel/<filename>")
def download_excel(filename):
    path = EXCEL_DIR / filename
    if not path.exists():
        return "File not found", 404
    return send_file(str(path), as_attachment=True)


@app.route("/stats")
def stats():
    return jsonify(_last_result)


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  🌾 Agriculture Newsletter Agent Dashboard")
    print("  Open in Chrome: http://localhost:5050")
    print("=" * 55 + "\n")
    app.run(host="0.0.0.0", port=5050, debug=False)
