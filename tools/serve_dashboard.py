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
import sys
from pathlib import Path

from flask import Flask, jsonify, send_from_directory

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


def main():
    print(f"\n  YouTube Intelligence Dashboard")
    print(f"  http://localhost:{DASHBOARD_PORT}")
    print(f"  Press Ctrl+C to stop\n")
    app.run(host="0.0.0.0", port=DASHBOARD_PORT, debug=False)


if __name__ == "__main__":
    main()
