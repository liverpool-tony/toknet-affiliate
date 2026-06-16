#!/usr/bin/env python3
"""Check for duplicate tags in last 24h and other pipeline health checks."""
import os, re, glob
from datetime import datetime, timezone, timedelta
from collections import Counter

JST = timezone(timedelta(hours=9))
ARTICLES_DIR = '/Users/yuta/Projects/toknet-affiliate/astro/src/content/articles'
cutoff = datetime.now(JST) - timedelta(hours=24)

tags_in_24h = []
for fpath in sorted(glob.glob(f'{ARTICLES_DIR}/2026061*.md')):
    mtime = os.path.getmtime(fpath)
    file_dt = datetime.fromtimestamp(mtime, tz=JST)
    if file_dt < cutoff:
        continue
    with open(fpath, encoding='utf-8') as f:
        content = f.read(2000)
    m = re.search(r'tags:\s*\[([^\]]*)\]', content)
    if m:
        tags_raw = m.group(1)
        first_tag = re.search(r'["\']([^"\']+)["\']', tags_raw)
        if first_tag:
            tags_in_24h.append((os.path.basename(fpath), first_tag.group(1), str(file_dt)))

print('=== Tags in last 24h ===')
for fname, tag, dt in tags_in_24h:
    print(f'  {dt[:16]}  {tag}  ({fname[:50]})')

tag_counts = Counter(t for _, t, _ in tags_in_24h)
print()
print('=== Duplicate check (3+ in 24h) ===')
found_dup = False
for tag, count in tag_counts.items():
    if count >= 3:
        print(f'  WARNING: {tag} appears {count} times in 24h')
        found_dup = True
if not found_dup:
    print('  No duplicates >= 3 found in 24h window.')

# Also check total articles in 24h
print(f'\nTotal articles in 24h: {len(tags_in_24h)}')
