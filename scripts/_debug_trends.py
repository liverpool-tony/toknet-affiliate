#!/usr/bin/env python3
import sys
sys.path.insert(0, '/Users/yuta/Projects/toknet-affiliate/scripts')
from trend_collector import get_trending_tags, is_product_related

tags = get_trending_tags(limit=20)
print('=== ALL TAGS ===')
for t in tags:
    product = is_product_related('#' + t['name'])
    marker = 'SHOP' if product else 'SKIP'
    print(f'{marker} #{t["name"]} - uses:{t["total_uses_7d"]} accts:{t["total_accts_7d"]} score:{t["score"]}')
