#!/usr/bin/env python3
"""Debug: check mstdn.jp trending tags and is_product_related results"""
import sys, re
sys.path.insert(0, 'scripts')
from trend_collector import get_trending_tags, is_product_related

tags = get_trending_tags(limit=20)
product_count = 0
for t in tags:
    marker = 'PRODUCT' if t['is_product'] else 'skip'
    if t['is_product']:
        product_count += 1
    print(f'{marker} #{t["name"]} - {t["total_uses_7d"]}uses (score:{t["score"]})')

print(f'\nProduct tags: {product_count}/{len(tags)}')

# Show non-product tags and why
KNOWN_GENERIC_TAGS = {
    'top', 'stop', 'new', 'best', 'vs', 'pro', 'max', 'air', 'mini',
    'plus', 'lite', 'neo', 'one', 'go', 'now', 'here', 'there',
    'this', 'that', 'what', 'how', 'why', 'when', 'where', 'who',
    'good', 'nice', 'cool', 'great', 'awesome', 'amazing', 'wow',
    'love', 'like', 'want', 'need', 'get', 'got', 'buy', 'sell',
    'hot', 'big', 'old', 'bad', 'low', 'high', 'fast', 'slow',
    'day', 'week', 'year', 'time', 'work', 'home', 'life', 'world',
    'news', 'info', 'help', 'tips', 'idea', 'plan', 'free', 'easy',
}

print('\n--- Non-product tag analysis ---')
for t in tags:
    if not t['is_product']:
        name = t['name'].lower().lstrip('#')
        reasons = []
        if re.match(r'^[a-zA-Z]{1,3}$', name):
            reasons.append('too_short')
        if name in KNOWN_GENERIC_TAGS:
            reasons.append('generic_word')
        # Check EXCLUDE patterns
        EXCLUDE_PATTERNS = [
            r'^#nba', r'^#nbafinals', r'^#nfl', r'^#mlb', r'^#nhl',
            r'^#knicks', r'^#lakers', r'^#warriors', r'^#celtics',
            r'^#wm2026', r'^#wm', r'^#worldcup', r'^#ワールドカップ',
            r'^#poland', r'^#gaza', r'^#deepfakes', r'^#ガザ',
            r'^#appetizersabook', r'^#hashtaggames', r'^#throwbackthursday',
            r'^#thursdayfivelist', r'^#thursdayfive', r'^#blowinginthewind',
            r'^#doorsday', r'^#jと打って', r'^#今でも怖いもの',
            r'^#io写真', r'^#mexrsa', r'^#musiquinta',
            r'^#iliketowatch', r'^#iliketo',
            r'^#grok', r'^#deepfakes', r'^#thursday',
            r'^#Anthropic', r'^#OpenAI', r'^#Google', r'^#Microsoft', r'^#Meta',
            r'^#Amazon', r'^#Tesla',
            r'^#macron', r'^#trump', r'^#biden', r'^#putin',
            r'^#Président', r'^#élysée',
            r'^#梅雨だから', r'^#あなたが', r'^#名前に',
            r'^#ミリオン', r'^#仮面ライダー',
            r'^#Fensterfreitag', r'^#insektensamstag', r'^#caturday',
            r'^#kungfusat', r'^#spillthetea', r'^#KidMadeUpHolidays',
            r'^#nationalsecurity',
            r'^#スポーツ', r'^#子ども', r'^#キッズ', r'^#価格',
            r'^#政治', r'^#社会', r'^#天気', r'^#災害',
            r'^#misskey',
            r'^#listeningclub', r'^#gercuw', r'^#myweekcounted',
            r'^#lastfm', r'^#scrobbles', r'^#spotify',
            r'^#youtube', r'^#netflix', r'^#disneyplus',
            r'^#hulu', r'^#twitch', r'^#tiktok',
            r'^#chatgpt', r'^#claude', r'^#gemini', r'^#gpt',
        ]
        for pattern in EXCLUDE_PATTERNS:
            check = '#' + name if not name.startswith('#') else name
            if re.match(pattern, check, re.IGNORECASE):
                reasons.append(f'exclude_pattern:{pattern}')
                break
        if not reasons:
            reasons.append('no_product_keyword_match')
        print(f'  #{t["name"]}: {", ".join(reasons)}')
