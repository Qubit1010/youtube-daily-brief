# YouTube Daily Brief — Master Workflow

## Objective
Generate a daily YouTube intelligence dashboard covering AI, business, and AI automation content. Scrape recent videos from 10 channels, analyze trends via Claude API, and serve insights on a local web dashboard.

## How to Run

### Full pipeline (scrape + analyze + dashboard)
```bash
bash run.sh
```

### Data refresh only (for cron / scheduled runs)
```bash
bash run.sh --no-serve
```

### Individual tools
```bash
python tools/scrape_channels.py    # Scrape only
python tools/analyze_content.py    # Analyze only (requires scraped data)
python tools/serve_dashboard.py    # Serve dashboard only (requires data files)
```

## Data Flow
```
scrape_channels.py → .tmp/raw_videos.json → analyze_content.py → .tmp/analysis.json → serve_dashboard.py → localhost:8080
                   → .tmp/history/YYYY-MM-DD.json (7-day rolling archive)
```

## Required Setup
1. Python 3.12+ with dependencies: `pip install -r requirements.txt`
2. Set `ANTHROPIC_API_KEY` in `.env` (required for analysis step)
3. No YouTube API key needed — uses yt-dlp for public data scraping

## Channel List
Edit `tools/helpers/config.py` → `CHANNELS` list to add/remove channels. Each entry needs a `handle` (@username) and `name` (display name).

## Cost
~$0.05–0.10 per analysis run (Claude Sonnet, ~20K input tokens).

## Cron Setup (Daily at 7 AM)
```bash
0 7 * * * cd /path/to/youtube-daily-brief && bash run.sh --no-serve >> .tmp/cron.log 2>&1
```

## Troubleshooting
- **yt-dlp errors**: Update with `pip install -U yt-dlp`. YouTube frequently changes their site.
- **No transcript**: Some videos don't have auto-captions. The analyzer uses descriptions as fallback.
- **API errors**: Check `.env` for valid `ANTHROPIC_API_KEY`. Stale analysis.json is kept as fallback.
- **Channel not found**: Verify the @handle is correct on YouTube. Handles are case-sensitive.

## Key Files
| File | Purpose |
|------|---------|
| `tools/helpers/config.py` | Channel list, paths, settings |
| `tools/scrape_channels.py` | yt-dlp scraper |
| `tools/analyze_content.py` | Claude API analysis |
| `tools/serve_dashboard.py` | Flask dashboard server |
| `dashboard/` | Frontend HTML/CSS/JS |
| `.tmp/raw_videos.json` | Latest scraped data |
| `.tmp/analysis.json` | Latest analysis output |
| `.tmp/history/` | 7-day rolling snapshots |
