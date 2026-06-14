import sys
sys.path.insert(0, 'scripts')
from trend_collector import get_trending_tags, is_product_related
tags = get_trending_tags(limit=30)
print('All tags:')
for t in tags:
    marker = 'SHOP' if t['is_product'] else '    '
    print(f'  {marker} #{t["name"]} - uses:{t["total_uses_7d"]} score:{t["score"]}')
print(f'\nProduct tags: {sum(1 for t in tags if t["is_product"])}/{len(tags)}')
