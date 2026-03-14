"""
Shared configuration for YouTube Intelligence Dashboard.
Central place for channel list, file paths, and environment setup.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TMP_DIR = PROJECT_ROOT / ".tmp"
HISTORY_DIR = TMP_DIR / "history"
RAW_VIDEOS_PATH = TMP_DIR / "raw_videos.json"
ANALYSIS_PATH = TMP_DIR / "analysis.json"
DASHBOARD_DIR = PROJECT_ROOT / "dashboard"

# Ensure directories exist
TMP_DIR.mkdir(exist_ok=True)
HISTORY_DIR.mkdir(exist_ok=True)

# ── Environment ────────────────────────────────────────────────────────────────
load_dotenv(PROJECT_ROOT / ".env")

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── Channel List ───────────────────────────────────────────────────────────────
# Edit this list to add/remove channels. Each entry needs:
#   handle  — the @username (used to resolve the channel via YouTube API)
#   name    — display name (used in dashboard and analysis)
CHANNELS = [
    {"handle": "@AIDailyBrief",  "name": "AI Daily Brief"},
    {"handle": "@mreflow",       "name": "MreFlow"},
    {"handle": "@TheAiGrid",     "name": "TheAIGrid"},
    {"handle": "@DaveShap",      "name": "Dave Shap"},
    {"handle": "@nicksaraev",    "name": "Nick Saraev"},
    {"handle": "@LiamOttley",    "name": "Liam Ottley"},
    {"handle": "@nateherk",      "name": "Nate Herk"},
    {"handle": "@NateBJones",    "name": "Nate B Jones"},
]

# ── Scraper Settings ──────────────────────────────────────────────────────────
VIDEOS_PER_CHANNEL = 5
TRANSCRIPT_MAX_CHARS = 2000      # Max chars of transcript to keep per video
HISTORY_DAYS = 7                 # Days of history to keep for trend comparison

# ── Dashboard Settings ────────────────────────────────────────────────────────
DASHBOARD_PORT = 8080
