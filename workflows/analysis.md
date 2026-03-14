# Analysis Workflow

## Tool
`tools/analyze_content.py`

## How It Works
1. Loads `.tmp/raw_videos.json` (latest scrape)
2. Loads `.tmp/history/*.json` for 7-day trend context
3. Builds a prompt with video summaries (title, channel, stats, truncated description/transcript)
4. Sends to Claude Sonnet with a structured system prompt requesting JSON output
5. Parses response and saves to `.tmp/analysis.json`

## Output Sections
| Section | Description |
|---------|-------------|
| `trending_topics` | 5-8 topics ranked by relevance with mention counts and sentiment |
| `top_performing` | Top 10 videos by views with performance notes |
| `channel_breakdown` | Per-channel stats: views, format, posting frequency |
| `sentiment` | Overall AI space mood with confidence score and reasoning |
| `content_opportunities` | 3-5 content gap ideas with format suggestions |
| `format_distribution` | Count of videos by type (tutorial, news, opinion, etc.) |
| `title_patterns` | Common title structures with examples |

## Cost Tracking
- Model: `claude-sonnet-4-20250514`
- Input: ~15,000-20,000 tokens (50 videos × metadata + truncated content)
- Output: ~2,000-3,000 tokens
- Cost per run: ~$0.05-0.10
- Monthly (daily runs): ~$1.50-3.00

## Tuning the Analysis
- Edit the `SYSTEM_PROMPT` in `analyze_content.py` to adjust categories, add new sections, or change focus areas
- Adjust `TRANSCRIPT_MAX_CHARS` in `config.py` to send more/less transcript data (affects token cost)
- The prompt includes historical data for trend comparison — more history = better trend detection

## Error Handling
- If Claude API fails, existing `analysis.json` is preserved (stale data > no data)
- If response isn't valid JSON, raw response is printed for debugging
- Missing API key exits with a clear error message
