#!/usr/bin/env python3
"""Check for duplicate tags in articles within 24h window. No external deps."""
import os, glob, re
from datetime import datetime, timedelta

articles_dir = '/Users/yuta/Projects/toknet-affiliate/astro/src/content/articles/'
files = sorted(glob.glob(os.path.join(articles_dir, '*.md')), key=os.path.getmtime, reverse=True)

now = datetime.now()
tag_dates = {}

for f in files[:30]:
    with open(f) as fh:
        content = fh.read()
    if content.startswith('---'):
        parts = content.split('---')
        if len(parts) >= 3:
            fm_text = parts[1]
            # Extract tags
            tags_match = re.search(r'tags:\s*\n((?:\s*-\s*.+\n?)+)', fm_text)
            date_match = re.search(r'date:\s*["\']?([^"\'\n]+)', fm_text)
            if tags_match:
                date = date_match.group(1).strip() if date_match else ''
                tags = [t.strip().lstrip('- ').strip() for t in tags_match.group(1).strip().split('\n') if t.strip()]
                for tag in tags:
                    if tag not in tag_dates:
                        tag_dates[tag] = []
                    tag_dates[tag].append((f, date))

print('=== Tag frequency (top 30 files) ===')
dup_found = False
for tag, entries in sorted(tag_dates.items(), key=lambda x: -len(x[1])):
    if len(entries) >= 3:
        dup_found = True
        print(f'  DUPLICATE Tag "{tag}": {len(entries)} articles')
        for e in entries:
            print(f'    - {os.path.basename(e[0])} (date: {e[1]})')
    elif len(entries) >= 2:
        print(f'  Tag "{tag}": {len(entries)} articles')
        for e in entries:
            print(f'    - {os.path.basename(e[0])} (date: {e[1]})')

if not dup_found:
    print('  No tags with 3+ duplicates found.')

# Also check articles from last 24h
recent = []
for f in files:
    mtime = datetime.fromtimestamp(os.path.getmtime(f))
    if (now - mtime).total_seconds() < 86400:
        recent.append(f)

print(f'\n=== Articles created in last 24h: {len(recent)} ===')
for f in recent:
    mtime = datetime.fromtimestamp(os.path.getmtime(f))
    print(f'  {os.path.basename(f)} (mtime: {mtime.strftime("%Y-%m-%d %H:%M")})')
