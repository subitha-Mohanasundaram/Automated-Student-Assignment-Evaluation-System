"""Lightweight local admin dashboard for evaluation analytics."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local admin dashboard for evaluation analytics.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--batch-json", default="results/batch/batch_report.json", help="Batch report JSON")
    parser.add_argument("--attempt-history", default="results/attempt_history.jsonl", help="Attempt history JSONL")
    return parser.parse_args()


def load_batch_rows(batch_json: Path) -> list[dict[str, object]]:
    if not batch_json.exists():
        return []
    try:
        data = json.loads(batch_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def load_attempts(history_path: Path) -> list[dict[str, object]]:
    if not history_path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in history_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def compute_summary(batch_rows: list[dict[str, object]], attempts: list[dict[str, object]]) -> dict[str, object]:
    total = len(batch_rows)
    avg_score = round(sum(float(r.get("score", 0.0)) for r in batch_rows) / total, 2) if total else 0.0
    plagiarism_detected = sum(1 for r in batch_rows if str(r.get("plagiarism", "")).upper() == "DETECTED")
    anti_cheat_fail = sum(1 for r in batch_rows if str(r.get("anti_cheat", "")).upper() != "PASS")
    lang_counter = Counter(str(r.get("language", "unknown")).lower() for r in batch_rows)

    attempts_total = len(attempts)
    attempts_last_24h = 0
    now = datetime.utcnow()
    for item in attempts:
        ts_raw = str(item.get("timestamp_utc", ""))
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            continue
        if (now - ts).total_seconds() <= 86400:
            attempts_last_24h += 1

    return {
        "total_submissions": total,
        "average_score": avg_score,
        "plagiarism_detected": plagiarism_detected,
        "anti_cheat_failures": anti_cheat_fail,
        "language_breakdown": dict(lang_counter),
        "attempts_total": attempts_total,
        "attempts_last_24h": attempts_last_24h,
    }


def render_html(summary: dict[str, object], rows: list[dict[str, object]]) -> str:
    cards = f"""
    <div class='grid'>
      <div class='card'><h3>Total Submissions</h3><p>{summary['total_submissions']}</p></div>
      <div class='card'><h3>Average Score</h3><p>{summary['average_score']}</p></div>
      <div class='card'><h3>Plagiarism</h3><p>{summary['plagiarism_detected']}</p></div>
      <div class='card'><h3>Anti-Cheat Fails</h3><p>{summary['anti_cheat_failures']}</p></div>
      <div class='card'><h3>Total Attempts</h3><p>{summary['attempts_total']}</p></div>
      <div class='card'><h3>Attempts (24h)</h3><p>{summary['attempts_last_24h']}</p></div>
    </div>
    """

    row_html = []
    for r in rows:
        row_html.append(
            "<tr>"
            f"<td>{r.get('github_username', '')}</td>"
            f"<td>{r.get('problem_id', '')}</td>"
            f"<td>{r.get('language', '')}</td>"
            f"<td>{r.get('anti_cheat', '')}</td>"
            f"<td>{r.get('plagiarism', '')}</td>"
            f"<td>{r.get('score', '')}</td>"
            "</tr>"
        )

    table = (
        "<table><thead><tr><th>User</th><th>Problem</th><th>Lang</th><th>Anti-Cheat</th>"
        "<th>Plagiarism</th><th>Score</th></tr></thead>"
        f"<tbody>{''.join(row_html)}</tbody></table>"
    )
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Evaluation Admin Dashboard</title>
  <style>
    body {{ font-family: Segoe UI, Arial, sans-serif; margin: 24px; background: #f4f7fb; color: #121212; }}
    h1 {{ margin: 0 0 12px 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-bottom: 20px; }}
    .card {{ background: white; border-radius: 10px; padding: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
    .card h3 {{ margin: 0; font-size: 14px; color: #445; }}
    .card p {{ margin: 8px 0 0 0; font-size: 22px; font-weight: 700; }}
    table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; }}
    th, td {{ text-align: left; padding: 10px; border-bottom: 1px solid #e8ebf0; font-size: 13px; }}
    th {{ background: #0f2742; color: white; }}
  </style>
</head>
<body>
  <h1>Evaluation Admin Dashboard</h1>
  <p>Live snapshot from local result files.</p>
  {cards}
  {table}
</body>
</html>"""


def build_handler(batch_json: Path, attempt_history: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            rows = load_batch_rows(batch_json)
            attempts = load_attempts(attempt_history)
            summary = compute_summary(rows, attempts)

            if parsed.path == "/api/summary":
                body = json.dumps(summary, indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            html = render_html(summary, rows).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, format: str, *args) -> None:  # noqa: A003
            return

    return Handler


def main() -> int:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), build_handler(Path(args.batch_json), Path(args.attempt_history)))
    print(f"Admin dashboard running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
