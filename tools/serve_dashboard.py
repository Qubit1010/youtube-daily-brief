"""
Dashboard Server
Flask app that serves the YouTube Intelligence Dashboard and provides a JSON API.

Routes:
    GET /              — Serves the dashboard HTML
    GET /static/<path> — Serves CSS and JS from dashboard/
    GET /api/data      — Returns merged raw + analysis JSON

Usage:
    python tools/serve_dashboard.py
"""

import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.helpers.config import (
    ANALYSIS_PATH,
    DASHBOARD_DIR,
    DASHBOARD_PORT,
    RAW_VIDEOS_PATH,
)

app = Flask(__name__, static_folder=None)


@app.route("/")
def index():
    return send_from_directory(str(DASHBOARD_DIR), "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(str(DASHBOARD_DIR), filename)


@app.route("/api/data")
def api_data():
    """Return combined raw video data and analysis results."""
    raw = {}
    analysis = {}

    if RAW_VIDEOS_PATH.exists():
        try:
            raw = json.loads(RAW_VIDEOS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    if ANALYSIS_PATH.exists():
        try:
            analysis = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    return jsonify({"raw": raw, "analysis": analysis})


@app.route("/api/generate-brief", methods=["POST"])
def generate_brief():
    """Generate a content brief for a suggested topic using OpenAI."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return jsonify({"error": "OPENAI_API_KEY not set"}), 500

    topic_data = request.get_json()
    if not topic_data:
        return jsonify({"error": "No topic data provided"}), 400

    topic = topic_data.get("topic", "Unknown topic")
    angle = topic_data.get("angle", "")
    why_now = topic_data.get("why_now", "")
    target_format = topic_data.get("target_format", "")

    prompt = f"""You are a YouTube content strategist. Generate a detailed content brief for the following video topic.

Topic: {topic}
Angle: {angle}
Why now: {why_now}
Format: {target_format}

Return a JSON object with these fields:
- hook: A compelling first-30-seconds script/hook (2-3 sentences)
- talking_points: Array of 5 key talking points
- title_variations: Array of 3 title options
- thumbnail_concept: Description of a thumbnail concept
- cta: A call-to-action suggestion
- estimated_length: Suggested video length (e.g., "12-15 minutes")

Return ONLY valid JSON, no markdown."""

    try:
        import urllib.request

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps({
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
            }).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())

        content = result["choices"][0]["message"]["content"].strip()
        # Strip markdown fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        brief = json.loads(content)
        return jsonify(brief)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


SHEET_ID = "1TwAuLDKak3hpPWqlojpNL_OTsUyCOBaAVjRRncOpb9Q"
SHEET_TAB = "Youtube bookmarked"
SHEET_HEADERS = ["Date Saved", "Title", "Channel", "URL", "Views", "Likes", "Eng Rate", "Duration", "Published Date"]


def _gws(*args):
    """Run a gws command and return (stdout, returncode)."""
    env = os.environ.copy()
    npm_path = os.path.expanduser(r"~\AppData\Roaming\npm")
    env["PATH"] = npm_path + ";" + env.get("PATH", "")
    cmd = subprocess.list2cmdline(["gws"] + list(args))
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True, env=env)
    return result.stdout.strip(), result.returncode


@app.route("/api/save-to-sheets", methods=["POST"])
def save_to_sheets():
    """Save bookmarked videos to the Youtube bookmarked tab in Google Sheets."""
    videos = request.get_json()
    if not videos or not isinstance(videos, list):
        return jsonify({"error": "Expected a JSON array of video objects"}), 400

    # Check which tabs exist
    out, _ = _gws(
        "sheets", "spreadsheets", "get",
        "--params", json.dumps({"spreadsheetId": SHEET_ID, "fields": "sheets.properties.title"}),
        "--format", "json",
    )
    try:
        sheet_data = json.loads(out)
        existing_tabs = [s["properties"]["title"] for s in sheet_data.get("sheets", [])]
    except Exception:
        return jsonify({"error": f"Could not read sheet metadata: {out}"}), 500

    # Create tab + headers if it doesn't exist yet
    if SHEET_TAB not in existing_tabs:
        _, rc = _gws(
            "sheets", "spreadsheets", "batchUpdate",
            "--params", json.dumps({"spreadsheetId": SHEET_ID}),
            "--json", json.dumps({"requests": [{"addSheet": {"properties": {"title": SHEET_TAB}}}]}),
        )
        if rc != 0:
            return jsonify({"error": "Failed to create sheet tab"}), 500

        _gws(
            "sheets", "spreadsheets", "values", "append",
            "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": f"{SHEET_TAB}!A1", "valueInputOption": "USER_ENTERED"}),
            "--json", json.dumps({"values": [SHEET_HEADERS]}),
        )

    # Fetch existing URLs from the sheet to deduplicate
    existing_urls = set()
    url_out, _ = _gws(
        "sheets", "spreadsheets", "values", "get",
        "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": f"{SHEET_TAB}!D1:D500"}),
        "--format", "json",
    )
    try:
        url_data = json.loads(url_out)
        for row in url_data.get("values", [])[1:]:  # skip header row
            if row:
                existing_urls.add(row[0].strip())
    except Exception:
        pass  # if we can't read existing, proceed without dedup

    # Build rows, skipping already-saved URLs
    date_saved = datetime.date.today().isoformat()
    skipped = 0
    rows = []
    for v in videos:
        incoming_url = v.get("url", "").strip()
        if incoming_url in existing_urls:
            skipped += 1
            continue
        views = v.get("view_count", "")
        likes = v.get("like_count", "")
        comments = v.get("comment_count", 0)
        eng_rate = ""
        if isinstance(views, (int, float)) and views > 0:
            eng_rate = round(((likes or 0) + (comments or 0)) / views * 100, 2)
        rows.append([
            date_saved,
            v.get("title", ""),
            v.get("channel", ""),
            v.get("url", ""),
            views, likes, eng_rate,
            v.get("duration_formatted", ""),
            v.get("published_date", ""),
        ])

    if not rows:
        return jsonify({"saved": 0, "skipped": skipped})

    _, rc = _gws(
        "sheets", "spreadsheets", "values", "append",
        "--params", json.dumps({"spreadsheetId": SHEET_ID, "range": f"{SHEET_TAB}!A1", "valueInputOption": "USER_ENTERED"}),
        "--json", json.dumps({"values": rows}),
    )
    if rc != 0:
        return jsonify({"error": "Failed to append rows"}), 500

    return jsonify({"saved": len(rows), "skipped": skipped})


def main():
    print(f"\n  YouTube Intelligence Dashboard")
    print(f"  http://localhost:{DASHBOARD_PORT}")
    print(f"  Press Ctrl+C to stop\n")
    app.run(host="127.0.0.1", port=DASHBOARD_PORT, debug=False)


if __name__ == "__main__":
    main()
