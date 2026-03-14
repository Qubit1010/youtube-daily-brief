"""
YouTube Channel Scraper (YouTube Data API v3)
Scrapes the N most recent videos from each configured channel using the
Google YouTube Data API. Outputs raw video data to .tmp/raw_videos.json
and archives to .tmp/history/.

Usage:
    python tools/scrape_channels.py
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from googleapiclient.discovery import build

# Add project root to path so we can import config
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.helpers.config import (
    CHANNELS,
    GOOGLE_API_KEY,
    HISTORY_DIR,
    HISTORY_DAYS,
    RAW_VIDEOS_PATH,
    TRANSCRIPT_MAX_CHARS,
    VIDEOS_PER_CHANNEL,
)


def get_youtube_client():
    """Build and return a YouTube Data API client."""
    if not GOOGLE_API_KEY:
        print("Error: GOOGLE_API_KEY not set in .env")
        print("Add your YouTube Data API v3 key to .env and try again.")
        sys.exit(1)
    return build("youtube", "v3", developerKey=GOOGLE_API_KEY)


def resolve_channel_id(youtube, handle: str) -> str | None:
    """Resolve a @handle to a YouTube channel ID."""
    # Strip the @ prefix for the API query
    query = handle.lstrip("@")
    try:
        # Use search to find the channel by handle
        resp = youtube.search().list(
            part="snippet",
            q=query,
            type="channel",
            maxResults=1,
        ).execute()

        items = resp.get("items", [])
        if items:
            return items[0]["snippet"]["channelId"]

        # Fallback: try channels.list with forHandle
        resp = youtube.channels().list(
            part="id",
            forHandle=query,
        ).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["id"]

    except Exception as e:
        print(f"    Error resolving channel {handle}: {e}")

    return None


def get_uploads_playlist_id(youtube, channel_id: str) -> str | None:
    """Get the uploads playlist ID for a channel."""
    try:
        resp = youtube.channels().list(
            part="contentDetails",
            id=channel_id,
        ).execute()
        items = resp.get("items", [])
        if items:
            return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
    except Exception as e:
        print(f"    Error getting uploads playlist: {e}")
    return None


def get_recent_video_ids(youtube, playlist_id: str, max_results: int = 5) -> list[str]:
    """Get the most recent video IDs from an uploads playlist."""
    try:
        resp = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=max_results,
        ).execute()
        return [
            item["contentDetails"]["videoId"]
            for item in resp.get("items", [])
        ]
    except Exception as e:
        print(f"    Error fetching playlist items: {e}")
        return []


def get_video_details(youtube, video_ids: list[str]) -> list[dict]:
    """Fetch full metadata for a batch of video IDs (up to 50)."""
    if not video_ids:
        return []
    try:
        resp = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=",".join(video_ids),
        ).execute()
        return resp.get("items", [])
    except Exception as e:
        print(f"    Error fetching video details: {e}")
        return []


def parse_duration(iso_duration: str) -> tuple[int, str]:
    """Convert ISO 8601 duration (PT1H2M3S) to seconds and formatted string."""
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


def get_transcript(youtube, video_id: str) -> str | None:
    """Try to get captions/transcript for a video. Returns None if unavailable."""
    # The YouTube Data API captions.list requires OAuth for downloading.
    # For public auto-captions, we use the youtube_transcript_api library as fallback.
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en"])
        text = " ".join(entry["text"] for entry in transcript_list)
        return text[:TRANSCRIPT_MAX_CHARS] if text else None
    except Exception:
        return None


def scrape_channel(youtube, channel: dict) -> tuple[list[dict], str | None]:
    """Scrape recent videos from a single channel. Returns (videos, error_msg)."""
    handle = channel["handle"]
    name = channel["name"]

    # Step 1: Resolve channel ID
    channel_id = resolve_channel_id(youtube, handle)
    if not channel_id:
        return [], f"Could not resolve channel ID for {handle}"

    # Step 2: Get uploads playlist
    playlist_id = get_uploads_playlist_id(youtube, channel_id)
    if not playlist_id:
        return [], f"Could not find uploads playlist for {handle}"

    # Step 3: Get recent video IDs
    video_ids = get_recent_video_ids(youtube, playlist_id, VIDEOS_PER_CHANNEL)
    if not video_ids:
        return [], f"No videos found for {handle}"

    # Step 4: Get full video details (single batch request)
    raw_videos = get_video_details(youtube, video_ids)

    videos = []
    for item in raw_videos:
        snippet = item.get("snippet", {})
        stats = item.get("statistics", {})
        content = item.get("contentDetails", {})
        video_id = item["id"]

        duration_sec, duration_fmt = parse_duration(content.get("duration", ""))

        # Get transcript (best effort)
        transcript = get_transcript(youtube, video_id)

        # Get best thumbnail
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
    """Scrape all configured channels and return structured data."""
    youtube = get_youtube_client()
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


def save_results(data: dict):
    """Save scraped data to .tmp/ and archive to history."""
    # Save main output
    RAW_VIDEOS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {len(data['videos'])} videos to {RAW_VIDEOS_PATH}")

    # Archive daily snapshot
    today = datetime.now().strftime("%Y-%m-%d")
    history_path = HISTORY_DIR / f"{today}.json"
    history_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Archived to {history_path}")

    # Clean up old history
    history_files = sorted(HISTORY_DIR.glob("*.json"))
    if len(history_files) > HISTORY_DAYS:
        for old_file in history_files[:-HISTORY_DAYS]:
            old_file.unlink()
            print(f"Cleaned up old snapshot: {old_file.name}")


def main():
    data = scrape_all_channels()

    # Summary
    print(f"\n{'='*50}")
    print("Scraping complete!")
    print(f"  Channels: {data['channels_succeeded']}/{data['channels_attempted']} succeeded")
    print(f"  Videos:   {len(data['videos'])} total")
    if data["errors"]:
        print(f"  Errors:   {len(data['errors'])}")
        for err in data["errors"]:
            print(f"    - {err['channel']}: {err['error']}")

    save_results(data)


if __name__ == "__main__":
    main()
