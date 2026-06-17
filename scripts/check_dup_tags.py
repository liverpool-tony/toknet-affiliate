#!/usr/bin/env python3
"""Check for duplicate tags in articles from the last 24 hours."""
import glob, os, re
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
cutoff = datetime.now(JST) - timedelta(hours=24)

def parse_frontmatter_tags(content):
    """Simple regex-based frontmatter tag extraction."""
    if not content.startswith('---'):
        return []
    end = content.find('---', 3)
    if end == -1:
        return []
    fm_text = content[3:end]
    # Find tags line
    m = re.search(r'^tags:\s*\[(.*?)\]', fm_text, re.MULTILINE)
    if not m:
        m = re.search(r'^tags:\s*\n((?:\s+-\s+.+\n?)+)', fm_text, re.MULTILINE)
        if m:
            return [line.strip().lstrip('- ').strip().strip('"').strip("'") for line in m.group(1).strip().split('\n') if line.strip()]
        return []
    items = m.group(1)
    return [t.strip().strip('"').strip("'") for t in items.split(',') if t.strip()]

tag_files = {}
for fpath in glob.glob('astro/src/content/articles/*.md'):
    mtime = os.path.getmtime(fpath)
    file_dt = datetime.fromtimestamp(mtime, tz=JST)
    if file_dt < cutoff:
        continue
    with open(fpath) as f:
        content = f.read()
    tags = parse_frontmatter_tags(content)
    for t in tags:
        tl = t.lower()
        if tl not in tag_files:
            tag_files[tl] = []
        tag_files[tl].append(os.path.basename(fpath))

dupes = {k: v for k, v in tag_files.items() if len(v) > 1}
if dupes:
    print("DUPLICATE TAGS FOUND:")
    for tag, files in sorted(dupes.items()):
        print(f"  #{tag}: {len(files)} articles")
        for f in files:
            print(f"    - {f}")
else:
    print("No duplicate tags found in the last 24 hours.")
