import os, glob
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
now = datetime.now(JST)

files = sorted(glob.glob('astro/src/content/articles/*.md'))
print(f'Total article files: {len(files)}')

# Check tags in the last 24h
recent_tags = []
for f in files:
    mtime = os.path.getmtime(f)
    dt = datetime.fromtimestamp(mtime, tz=JST)
    age_h = (now - dt).total_seconds() / 3600
    if age_h <= 24:
        with open(f) as fh:
            content = fh.read()
        # Extract tags from frontmatter
        in_fm = False
        tags = []
        for line in content.split('\n'):
            if line.strip() == '---':
                in_fm = not in_fm
                continue
            if in_fm and line.strip().startswith('tags:'):
                tags_str = line.split(':', 1)[1].strip()
                tags = [t.strip().strip('"').strip("'") for t in tags_str.strip('[]').split(',') if t.strip()]
                break
        recent_tags.append((os.path.basename(f), age_h, tags))

print(f'Articles in last 24h: {len(recent_tags)}')
for name, age, tags in recent_tags:
    print(f'  [{age:.1f}h ago] {name}: tags={tags}')

# Count tag frequency in last 24h
from collections import Counter
tag_counts = Counter()
for _, _, tags in recent_tags:
    for t in tags:
        tag_counts[t] += 1

print('\nTag frequency (24h):')
for tag, count in tag_counts.most_common():
    print(f'  {tag}: {count}')

# Check for same-tag articles within 24h (3+)
print('\nDuplicate tag check (3+ within 24h):')
for tag, count in tag_counts.most_common():
    if count >= 3:
        print(f'  WARNING: {tag} appears {count} times in 24h')
