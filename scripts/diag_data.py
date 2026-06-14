#!/usr/bin/env python3
"""Check keyword history and cache state"""
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
DATA_DIR = Path('scripts/data')

# Keyword history
kh = json.load(open(DATA_DIR / 'keyword_history.json'))
snapshots = kh.get('snapshots', [])
print(f"Keyword snapshots: {len(snapshots)}")
if snapshots:
    latest = snapshots[-1]
    ts = latest.get('timestamp', 'unknown')
    print(f"Latest snapshot: {ts}")
    kw_counts = latest.get('keyword_counts', {})
    active = {k: v for k, v in kw_counts.items() if v > 0}
    print(f"Active keyword hits: {active}")
    print(f"Total keywords tracked: {len(kw_counts)}")

# Cache state
cache_file = DATA_DIR / 'trend_cache.json'
if cache_file.exists():
    cache = json.load(open(cache_file))
    cached_at = cache.get('cached_at', 'unknown')
    tags = cache.get('tags', [])
    print(f"\nTrend cache: {len(tags)} tags, cached_at={cached_at}")
