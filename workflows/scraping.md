# Scraping Workflow

## Tool
`tools/scrape_channels.py`

## How It Works
1. Iterates through each channel in `config.CHANNELS`
2. **Pass 1 (flat extraction)**: Hits `youtube.com/@handle/videos` with `extract_flat=True` to get the 5 most recent video IDs without downloading anything
3. **Pass 2 (metadata extraction)**: For each video, extracts full metadata (title, views, likes, comments, duration, description, thumbnail)
4. **Transcript extraction**: Checks for auto-generated English captions → downloads json3/vtt format → parses to plain text. Falls back to video description if unavailable
5. Saves results to `.tmp/raw_videos.json` and copies to `.tmp/history/YYYY-MM-DD.json`
6. Cleans up history older than 7 days

## Rate Limiting
- 1.5-second delay between channels (configurable in `config.py`)
- No delay between videos within a channel
- If YouTube starts blocking, increase `DELAY_BETWEEN_CHANNELS` in config

## Known Issues
- **Shorts appear in /videos tab**: Videos under 60 seconds may be Shorts. Currently kept for completeness.
- **Handle case sensitivity**: YouTube handles are case-sensitive. `@AIExplainedSWE` ≠ `@aiexplainedswe`
- **yt-dlp updates**: YouTube changes their site frequently. Run `pip install -U yt-dlp` if scraping breaks.
- **Geo-blocking**: Some videos may not be accessible depending on location.
- **Null counts**: Very new or private videos may return null for view/like/comment counts. Defaults to 0.

## Fallback: YouTube Data API v3
If yt-dlp stops working entirely:
1. Get a YouTube Data API key from Google Cloud Console
2. Add `GOOGLE_API_KEY=your_key` to `.env`
3. Use the `search.list` and `videos.list` endpoints
4. Quota: 10,000 units/day. `search.list` costs 100 units, `videos.list` costs 1 unit.
   - 10 channels × 100 units = 1,000 units for search
   - 50 videos × 1 unit = 50 units for details
   - Total: ~1,050 units per run (well within daily quota)
