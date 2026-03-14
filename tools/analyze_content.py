"""
YouTube Content Analyzer (OpenAI API)
Reads scraped video data, sends it to OpenAI for intelligence analysis,
and outputs structured insights for the dashboard.

Usage:
    python tools/analyze_content.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.helpers.config import (
    ANALYSIS_PATH,
    HISTORY_DIR,
    HISTORY_DAYS,
    OPENAI_API_KEY,
    RAW_VIDEOS_PATH,
)

MODEL = "gpt-4o"

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


def load_scraped_data() -> dict | None:
    """Load the most recent scraped data."""
    if not RAW_VIDEOS_PATH.exists():
        print(f"Error: No scraped data found at {RAW_VIDEOS_PATH}")
        print("Run 'python tools/scrape_channels.py' first.")
        return None
    return json.loads(RAW_VIDEOS_PATH.read_text(encoding="utf-8"))


def load_history() -> list[dict]:
    """Load historical data for trend comparison."""
    history = []
    files = sorted(HISTORY_DIR.glob("*.json"))[-HISTORY_DAYS:]
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            history.append({"date": f.stem, "video_count": len(data.get("videos", []))})
        except Exception:
            continue
    return history


def build_prompt(scraped: dict, history: list[dict]) -> str:
    """Build the analysis prompt from scraped video data."""
    videos = scraped.get("videos", [])

    # Summarize each video concisely to manage token count
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

    prompt = f"""Analyze these {len(video_summaries)} recent YouTube videos from AI/tech channels.

## Video Data
{json.dumps(video_summaries, indent=1)}

## Historical Context
Data points from the last {len(history)} days: {json.dumps(history)}

## Scraped At
{scraped.get('scraped_at', 'unknown')}

Provide your analysis as a JSON object following the schema in your instructions."""

    return prompt


def run_analysis(prompt: str) -> dict | None:
    """Send data to OpenAI API and parse the response."""
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set in .env")
        print("Add your key to .env and try again.")
        return None

    client = OpenAI(api_key=OPENAI_API_KEY)

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

        # Strip markdown fences if present
        if raw_text.startswith("```"):
            lines = raw_text.split("\n")
            raw_text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])

        analysis = json.loads(raw_text)

        # Add metadata
        analysis["analyzed_at"] = datetime.now(timezone.utc).isoformat()
        analysis["model_used"] = MODEL
        analysis["video_count"] = len(json.loads(prompt.split("## Video Data\n")[1].split("\n\n## Historical")[0]))

        print(f"Analysis complete -- {len(analysis.get('trending_topics', []))} topics, "
              f"{len(analysis.get('content_opportunities', []))} opportunities identified")

        return analysis

    except json.JSONDecodeError as e:
        print(f"Error: OpenAI returned invalid JSON: {e}")
        print(f"Raw response:\n{raw_text[:500]}")
        return None
    except Exception as e:
        print(f"API error: {e}")
        return None


def main():
    # Load data
    scraped = load_scraped_data()
    if not scraped:
        sys.exit(1)

    print(f"Loaded {len(scraped.get('videos', []))} videos from {RAW_VIDEOS_PATH.name}")

    history = load_history()
    print(f"Loaded {len(history)} days of history")

    # Build prompt and run analysis
    prompt = build_prompt(scraped, history)
    analysis = run_analysis(prompt)

    if analysis:
        ANALYSIS_PATH.write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nSaved analysis to {ANALYSIS_PATH}")
    else:
        if ANALYSIS_PATH.exists():
            print("\nKeeping existing (stale) analysis.json as fallback.")
        else:
            print("\nNo analysis generated. Check your API key and try again.")
            sys.exit(1)


if __name__ == "__main__":
    main()
