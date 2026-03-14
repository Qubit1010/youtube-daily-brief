#!/bin/bash
# YouTube Intelligence Dashboard — Daily Run Script
# Scrapes channels, analyzes content, launches dashboard.
#
# Usage:
#   bash run.sh            — full pipeline + dashboard
#   bash run.sh --no-serve — scrape + analyze only (for cron)
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "  YouTube Intelligence Dashboard"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="
echo ""

echo "Step 1/3: Scraping channels..."
python tools/scrape_channels.py
echo ""

echo "Step 2/3: Analyzing content..."
python tools/analyze_content.py
echo ""

if [ "$1" = "--no-serve" ]; then
    echo "Done! (--no-serve mode, skipping dashboard)"
    exit 0
fi

echo "Step 3/3: Starting dashboard..."
echo "Dashboard: http://localhost:8080"
echo ""
python tools/serve_dashboard.py
