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

import json
import os
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


def main():
    print(f"\n  YouTube Intelligence Dashboard")
    print(f"  http://localhost:{DASHBOARD_PORT}")
    print(f"  Press Ctrl+C to stop\n")
    app.run(host="127.0.0.1", port=DASHBOARD_PORT, debug=False)


if __name__ == "__main__":
    main()
