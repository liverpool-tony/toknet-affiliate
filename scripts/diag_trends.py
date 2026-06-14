#!/usr/bin/env python3
"""Quick diagnostic: check trend tags and product detection"""
import json, sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
SCRIPTS_DIR = Path(__file__).parent
DATA_DIR = SCRIPTS_DIR / 'data'
CACHE_FILE = DATA_DIR / 'trend_cache.json'

sys.path.insert(0, str(SCRIPTS_DIR))
from trend_collector import get_trending_tags, is_product_related, load_cache

# Check cache
cached_tags, cache_status = load_cache()
print(f"Cache status: {cache_status}")
if cached_tags:
    print(f"Cached tags: {len(cached_tags)}")
    for t in cached_tags[:15]:
        print(f"  #{t['name']} score:{t['score']} is_product:{t.get('is_product','?')}")

# Fresh API
print("\n--- Fresh API ---")
try:
    tags = get_trending_tags(limit=30)
    product_count = 0
    for t in tags:
        tag_name = t['name']
        is_prod = is_product_related('#' + tag_name)
        marker = 'SHOP' if is_prod else '---'
        print(f"  [{marker}] #{tag_name} score:{t['score']} uses7d:{t['total_uses_7d']} accts7d:{t['total_accts_7d']}")
        if is_prod:
            product_count += 1
    print(f"\nTotal product tags: {product_count}/{len(tags)}")
except Exception as e:
    print(f"API Error: {e}")
