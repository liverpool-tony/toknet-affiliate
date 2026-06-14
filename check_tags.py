import re, glob
from pathlib import Path
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
ARTICLES_DIR = Path('astro/src/content/articles')
cutoff = datetime.now(JST) - timedelta(hours=24)

used_tags = set()
for fpath in glob.glob(str(ARTICLES_DIR / '*.md')):
    fname = Path(fpath).stem
    try:
        date_str = fname[:8]
        file_date = datetime.strptime(date_str, '%Y%m%d').replace(tzinfo=JST)
        if file_date < cutoff:
            continue
    except (ValueError, IndexError):
        continue
    try:
        with open(fpath, encoding='utf-8') as f:
            content = f.read(2000)
        m = re.search(r'tags:\s*\[([^\]]*)\]', content)
        if m:
            tags_raw = m.group(1)
            for tag in re.findall(r'["\']([^"\']+)["\']', tags_raw):
                used_tags.add(tag)
    except Exception:
        pass

print('Recent tags (24h):')
for t in sorted(used_tags):
    print(f'  - {t}')

print(f'\nTotal: {len(used_tags)}')
print(f'"カメラ" in tags: {"カメラ" in used_tags}')
