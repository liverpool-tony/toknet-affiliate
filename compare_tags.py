import re, glob
from pathlib import Path
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
ARTICLES_DIR = Path('astro/src/content/articles')
cutoff = datetime.now(JST) - timedelta(hours=24)

used_tags_old = set()
used_tags_new = set()

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
            all_tags = re.findall(r'["\']([^"\']+)["\']', tags_raw)
            for tag in all_tags:
                used_tags_old.add(tag)
            if all_tags:
                used_tags_new.add(all_tags[0])
    except Exception:
        pass

print('OLD (all tags):')
for t in sorted(used_tags_old):
    print(f'  - {t}')
print(f'\nTotal old: {len(used_tags_old)}')

print('\nNEW (primary tag only):')
for t in sorted(used_tags_new):
    print(f'  - {t}')
print(f'\nTotal new: {len(used_tags_new)}')

# Simulate RSS product keywords that would be proposed
rss_candidates = ['カメラ', 'スマホ', 'iPhone', 'Switch', 'ノートPC', 'PS5', 'ヘッドホン', 'MacBook', 'ダイソン', 'SSD']
print('\nRSS candidate tags that would be BLOCKED:')
for c in rss_candidates:
    old_blocked = c in used_tags_old
    new_blocked = c in used_tags_new
    print(f'  {c}: old={old_blocked} new={new_blocked}')
