"""
YouTube Daily Brief — Modal Deployment
Runs the scrape → analyze pipeline on Modal's cloud infrastructure.

Usage:
    modal run modal_app.py          # Run once
    modal deploy modal_app.py       # Deploy (enables scheduled runs)
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import modal

# ── Modal Setup ───────────────────────────────────────────────────────────────
app = modal.App("youtube-daily-brief")

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "google-api-python-client",
        "youtube-transcript-api",
        "openai",
        "python-dotenv",
        "requests",
        "flask",
    )
)

volume = modal.Volume.from_name("youtube-daily-brief-data", create_if_missing=True)

secret = modal.Secret.from_name("youtube-daily-brief")

# ── Config (mirrors tools/helpers/config.py) ──────────────────────────────────
CHANNELS = [
    {"handle": "@AIDailyBrief", "name": "AI Daily Brief"},
    {"handle": "@mreflow", "name": "MreFlow"},
    {"handle": "@TheAiGrid", "name": "TheAIGrid"},
    {"handle": "@DaveShap", "name": "Dave Shap"},
    {"handle": "@nicksaraev", "name": "Nick Saraev"},
    {"handle": "@LiamOttley", "name": "Liam Ottley"},
    {"handle": "@nateherk", "name": "Nate Herk"},
    {"handle": "@NateBJones", "name": "Nate B Jones"},
]

VIDEOS_PER_CHANNEL = 5
TRANSCRIPT_MAX_CHARS = 2000
HISTORY_DAYS = 7
MODEL = "gpt-4o"

# Volume paths
DATA_DIR = Path("/data")
HISTORY_DIR = DATA_DIR / "history"
RAW_VIDEOS_PATH = DATA_DIR / "raw_videos.json"
ANALYSIS_PATH = DATA_DIR / "analysis.json"


# ── Scraper Logic ─────────────────────────────────────────────────────────────

def resolve_channel_id(youtube, handle: str) -> str | None:
    query = handle.lstrip("@")
    try:
        resp = youtube.search().list(
            part="snippet", q=query, type="channel", maxResults=1
        ).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["snippet"]["channelId"]

        resp = youtube.channels().list(part="id", forHandle=query).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["id"]
    except Exception as e:
        print(f"    Error resolving channel {handle}: {e}")
    return None


def get_uploads_playlist_id(youtube, channel_id: str) -> str | None:
    try:
        resp = youtube.channels().list(part="contentDetails", id=channel_id).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    except Exception as e:
        print(f"    Error getting uploads playlist: {e}")
    return None


def get_recent_video_ids(youtube, playlist_id: str, max_results: int = 5) -> list[str]:
    try:
        resp = youtube.playlistItems().list(
            part="contentDetails", playlistId=playlist_id, maxResults=max_results
        ).execute()
        return [item["contentDetails"]["videoId"] for item in resp.get("items", [])]
    except Exception as e:
        print(f"    Error fetching playlist items: {e}")
        return []


def get_video_details(youtube, video_ids: list[str]) -> list[dict]:
    if not video_ids:
        return []
    try:
        resp = youtube.videos().list(
            part="snippet,statistics,contentDetails", id=",".join(video_ids)
        ).execute()
        return resp.get("items", [])
    except Exception as e:
        print(f"    Error fetching video details: {e}")
        return []


def parse_duration(iso_duration: str) -> tuple[int, str]:
    match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration or "")
    if not match:
        return 0, "0:00"
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    total = hours * 3600 + minutes * 60 + seconds
    if hours:
        formatted = f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        formatted = f"{minutes}:{seconds:02d}"
    return total, formatted


def get_transcript(video_id: str) -> str | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        text = " ".join(entry["text"] for entry in transcript_list)
        return text[:TRANSCRIPT_MAX_CHARS] if text else None
    except Exception:
        return None


def scrape_channel(youtube, channel: dict) -> tuple[list[dict], str | None]:
    handle = channel["handle"]
    name = channel["name"]

    channel_id = resolve_channel_id(youtube, handle)
    if not channel_id:
        return [], f"Could not resolve channel ID for {handle}"

    playlist_id = get_uploads_playlist_id(youtube, channel_id)
    if not playlist_id:
        return [], f"Could not find uploads playlist for {handle}"

    video_ids = get_recent_video_ids(youtube, playlist_id, VIDEOS_PER_CHANNEL)
    if not video_ids:
        return [], f"No videos found for {handle}"

    raw_videos = get_video_details(youtube, video_ids)

    videos = []
    for item in raw_videos:
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        video_id = item["id"]

        duration_sec, duration_fmt = parse_duration(content.get("duration", ""))
        transcript = get_transcript(video_id)

        thumbs = snippet.get("thumbnails", {})
        thumbnail = (
            thumbs.get("maxres", {}).get("url")
            or thumbs.get("high", {}).get("url")
            or thumbs.get("medium", {}).get("url")
            or f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
        )

        videos.append({
            "video_id": video_id,
            "title": snippet.get("title", ""),
            "channel_name": name,
            "channel_handle": handle,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail_url": thumbnail,
            "published_date": snippet.get("publishedAt", ""),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
            "duration_seconds": duration_sec,
            "duration_formatted": duration_fmt,
            "description": (snippet.get("description") or "")[:1000],
            "transcript_snippet": transcript,
        })

    return videos, None


def scrape_all_channels() -> dict:
    from googleapiclient.discovery import build

    google_api_key = os.environ["GOOGLE_API_KEY"]
    youtube = build("youtube", "v3", developerKey=google_api_key)

    all_videos = []
    errors = []
    channels_succeeded = 0

    print(f"Scraping {len(CHANNELS)} channels, {VIDEOS_PER_CHANNEL} videos each...\n")

    for i, channel in enumerate(CHANNELS):
        handle = channel["handle"]
        name = channel["name"]
        print(f"[{i+1}/{len(CHANNELS)}] {name} ({handle})")

        videos, error = scrape_channel(youtube, channel)

        if error:
            print(f"  WARN: {error}")
            errors.append({"channel": handle, "error": error})
        else:
            all_videos.extend(videos)
            channels_succeeded += 1
            print(f"  OK -- {len(videos)} videos scraped")

    return {
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "channels_attempted": len(CHANNELS),
        "channels_succeeded": channels_succeeded,
        "errors": errors,
        "videos": all_videos,
    }


# ── Analyzer Logic ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a YouTube content intelligence analyst specializing in AI, technology, and business content.

You will receive data about recent YouTube videos from top channels in the AI/tech space. Analyze the data and return a JSON object with exactly this structure:

{
  "trending_topics": [
    {
      "topic": "Topic Name",
      "mention_count": 5,
      "channels": ["Channel A", "Channel B"],
      "sentiment": "bullish|cautious|neutral|hype-driven",
      "summary": "One sentence summary of why this is trending"
    }
  ],
  "top_performing": [
    {
      "video_id": "...",
      "title": "...",
      "channel_name": "...",
      "url": "...",
      "thumbnail_url": "...",
      "view_count": 500000,
      "published_date": "...",
      "performance_note": "Why this video is notable"
    }
  ],
  "channel_breakdown": [
    {
      "channel_name": "...",
      "channel_handle": "...",
      "videos_scraped": 5,
      "total_views": 1200000,
      "avg_views": 240000,
      "most_common_format": "news|tutorial|opinion|demo|interview",
      "posting_frequency": "daily|every-few-days|weekly"
    }
  ],
  "sentiment": {
    "overall": "bullish|cautious|neutral|hype-driven|mixed",
    "confidence": 0.78,
    "reasoning": "2-3 sentence explanation of the overall mood",
    "signals": [
      {"signal": "Description of signal", "weight": "strong|moderate|weak"}
    ]
  },
  "content_opportunities": [
    {
      "idea": "Content idea title",
      "reasoning": "Why this is an opportunity",
      "format_suggestion": "tutorial|opinion|news|demo|explainer",
      "estimated_interest": "high|medium|low"
    }
  ],
  "suggested_topics": [
    {
      "topic": "Topic title for content creation",
      "angle": "Specific angle or hook to differentiate",
      "why_now": "Why this topic is timely right now",
      "target_format": "tutorial|opinion|news|demo|explainer|comparison|deep-dive",
      "competition_level": "low|medium|high",
      "reference_videos": ["Title of video that inspired this suggestion"]
    }
  ],
  "format_distribution": {
    "tutorial": 0,
    "opinion": 0,
    "news": 0,
    "demo": 0,
    "interview": 0,
    "explainer": 0
  },
  "title_patterns": [
    {"pattern": "Pattern description", "count": 5, "examples": ["Title 1", "Title 2"]}
  ]
}

Guidelines:
- Return ONLY valid JSON, no markdown fences or extra text
- trending_topics: 5-8 topics, sorted by relevance
- top_performing: Top 10 videos by view count
- channel_breakdown: One entry per channel
- content_opportunities: 3-5 actionable ideas based on gaps you spot
- suggested_topics: 5-8 specific content topics I should create, based on what's trending, underserved, or has low competition
- title_patterns: 3-5 patterns you observe in video titles
- Be specific and data-driven in your analysis
- For sentiment, consider the overall tone across all channels, not just one"""


def load_history() -> list[dict]:
    history = []
    if not HISTORY_DIR.exists():
        return history
    files = sorted(HISTORY_DIR.glob("*.json"))[-HISTORY_DAYS:]
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            history.append({"date": f.stem, "video_count": len(data.get("videos", []))})
        except Exception:
            continue
    return history


def build_prompt(scraped: dict, history: list[dict]) -> str:
    videos = scraped.get("videos", [])
    video_summaries = []
    for v in videos:
        summary = {
            "title": v["title"],
            "channel": v["channel_name"],
            "views": v["view_count"],
            "likes": v["like_count"],
            "comments": v["comment_count"],
            "duration_sec": v["duration_seconds"],
            "published": v["published_date"],
            "url": v["url"],
            "video_id": v["video_id"],
            "thumbnail_url": v["thumbnail_url"],
            "description": v.get("description", "")[:500],
        }
        if v.get("transcript_snippet"):
            summary["transcript"] = v["transcript_snippet"][:500]
        video_summaries.append(summary)

    return f"""Analyze these {len(video_summaries)} recent YouTube videos from AI/tech channels.

## Video Data
{json.dumps(video_summaries, indent=1)}

## Historical Context
Data points from the last {len(history)} days: {json.dumps(history)}

## Scraped At
{scraped.get('scraped_at', 'unknown')}

Provide your analysis as a JSON object following the schema in your instructions."""


def run_analysis(prompt: str) -> dict | None:
    from openai import OpenAI

    openai_api_key = os.environ["OPENAI_API_KEY"]
    client = OpenAI(api_key=openai_api_key)

    print(f"Sending to {MODEL}...")
    try:
        response = client.chat.completions.create(
            model=MODEL,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
        )

        raw_text = response.choices[0].message.content.strip()

        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        analysis = json.loads(raw_text)

        analysis["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        analysis["model_used"] = MODEL
        analysis["video_count"] = len(
            json.loads(prompt.split("## Video Data\n")[1].split("\n\n## Historical")[0])
        )

        print(
            f"Analysis complete -- {len(analysis.get('trending_topics', []))} topics, "
            f"{len(analysis.get('content_opportunities', []))} opportunities identified"
        )
        return analysis

    except json.JSONDecodeError as e:
        print(f"Error: OpenAI returned invalid JSON: {e}")
        return None
    except Exception as e:
        print(f"API error: {e}")
        return None


# ── Modal Functions ───────────────────────────────────────────────────────────

@app.function(
    image=image,
    secrets=[secret],
    volumes={"/data": volume},
    timeout=600,
    schedule=modal.Cron("0 8 * * *"),  # Daily at 8:00 AM UTC
)
def run_pipeline():
    """Full scrape → analyze pipeline. Runs daily on schedule."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)

    # ── Step 1: Scrape ────────────────────────────────────────────────────
    print("=" * 50)
    print("STEP 1: Scraping YouTube channels")
    print("=" * 50)

    scraped = scrape_all_channels()

    print(f"\nChannels: {scraped['channels_succeeded']}/{scraped['channels_attempted']} succeeded")
    print(f"Videos:   {len(scraped['videos'])} total")

    # Save raw data
    RAW_VIDEOS_PATH.write_text(json.dumps(scraped, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved to {RAW_VIDEOS_PATH}")

    # Archive daily snapshot
    today = datetime.now().strftime("%Y-%m-%d")
    history_path = HISTORY_DIR / f"{today}.json"
    history_path.write_text(json.dumps(scraped, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Archived to {history_path}")

    # Clean old history
    history_files = sorted(HISTORY_DIR.glob("*.json"))
    if len(history_files) > HISTORY_DAYS:
        for old_file in history_files[:-HISTORY_DAYS]:
            old_file.unlink()
            print(f"Cleaned up: {old_file.name}")

    if not scraped["videos"]:
        print("No videos scraped. Skipping analysis.")
        volume.commit()
        return {"status": "partial", "videos": 0}

    # ── Step 2: Analyze ───────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("STEP 2: Running AI analysis")
    print("=" * 50)

    history = load_history()
    print(f"Loaded {len(history)} days of history")

    prompt = build_prompt(scraped, history)
    analysis = run_analysis(prompt)

    if analysis:
        ANALYSIS_PATH.write_text(
            json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\nSaved analysis to {ANALYSIS_PATH}")
    else:
        print("\nAnalysis failed. Check API key.")

    volume.commit()

    result = {
        "status": "success",
        "videos": len(scraped["videos"]),
        "channels": scraped["channels_succeeded"],
        "topics": len(analysis.get("trending_topics", [])) if analysis else 0,
    }
    print(f"\nPipeline complete: {result}")
    return result


@app.function(
    image=image,
    volumes={"/data": volume},
    timeout=60,
)
def get_results() -> dict:
    """Download the latest results from the volume."""
    volume.reload()
    raw = {}
    analysis = {}

    if RAW_VIDEOS_PATH.exists():
        raw = json.loads(RAW_VIDEOS_PATH.read_text(encoding="utf-8"))
    if ANALYSIS_PATH.exists():
        analysis = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))

    return {"raw": raw, "analysis": analysis}


@app.local_entrypoint()
def main():
    """CLI entrypoint: runs the pipeline and downloads results."""
    print("Starting YouTube Daily Brief pipeline on Modal...\n")
    result = run_pipeline.remote()
    print(f"\nResult: {result}")

    # Download results to local .tmp/
    print("\nDownloading results to local .tmp/ ...")
    data = get_results.remote()

    local_tmp = Path(__file__).parent / ".tmp"
    local_tmp.mkdir(exist_ok=True)

    if data.get("raw"):
        (local_tmp / "raw_videos.json").write_text(
            json.dumps(data["raw"], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"  Saved raw_videos.json ({len(data['raw'].get('videos', []))} videos)")

    if data.get("analysis"):
        (local_tmp / "analysis.json").write_text(
            json.dumps(data["analysis"], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"  Saved analysis.json")

    print("\nDone! Run 'python tools/serve_dashboard.py' to view the dashboard.")
