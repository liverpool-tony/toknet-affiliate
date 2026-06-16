#!/usr/bin/env python3
import os, glob, re
from datetime import datetime, timedelta
from collections import Counter

articles_dir = os.path.expanduser('~/Projects/toknet-affiliate/astro/src/content/articles/')
files = sorted(glob.glob(os.path.join(articles_dir, '*.md')), key=os.path.getmtime, reverse=True)
now = datetime.now()
cutoff_24h = now - timedelta(hours=24)
cutoff_6h = now - timedelta(hours=6)

print(f"Total articles: {len(files)}")
print(f"Now: {now}")
print()

tags_24h = []
tags_6h = []
recent_articles = []

for f in files:
    mtime = datetime.fromtimestamp(os.path.getmtime(f))
    with open(f) as fh:
        content = fh.read()
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            fm_text = parts[1]
            tag_match = re.search(r'tags:\s*\[(.*?)\]', fm_text, re.DOTALL)
            tags = []
            if tag_match:
                tags = [t.strip().strip("'\"") for t in tag_match.group(1).split(',') if t.strip()]
            title_match = re.search(r'title:\s*(.+)', fm_text)
            title = title_match.group(1).strip() if title_match else 'N/A'
            
            entry = {
                'file': os.path.basename(f),
                'mtime': mtime,
                'tags': tags,
                'title': title[:80]
            }
            recent_articles.append(entry)
            
            if mtime >= cutoff_24h:
                tags_24h.extend(tags)
            if mtime >= cutoff_6h:
                tags_6h.extend(tags)

print("=== Articles in last 24h ===")
for a in recent_articles:
    if a['mtime'] >= cutoff_24h:
        print(f"  {a['file']}")
        print(f"    mtime: {a['mtime']}")
        print(f"    tags: {a['tags']}")
        print(f"    title: {a['title']}")
        print()

print("=== Tag frequency in last 24h ===")
tag_counts_24h = Counter(tags_24h)
for tag, count in tag_counts_24h.most_common(20):
    print(f"  {tag}: {count}")

print()
print("=== Tag frequency in last 6h ===")
tag_counts_6h = Counter(tags_6h)
for tag, count in tag_counts_6h.most_common(20):
    print(f"  {tag}: {count}")

print()
print("=== Duplicate tag check (3+ in 24h) ===")
dupes = {tag: count for tag, count in tag_counts_24h.items() if count >= 3}
if dupes:
    for tag, count in dupes.items():
        print(f"  DUPLICATE #{tag}: {count} articles in 24h")
else:
    print("  OK - No tags with 3+ articles in 24h")
