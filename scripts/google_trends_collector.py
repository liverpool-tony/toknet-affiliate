#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Trends トレンド収集モジュール
RSSフィードから急上昇キーワードを取得し、商品関連をフィルタリング

情報源:
  - 日本: https://trends.google.co.jp/trending/rss?geo=JP
  - 米国: https://trends.google.com/trending/rss?geo=US

使い方:
    python3 google_trends_collector.py           # 日本+米国トレンド取得
    python3 google_trends_collector.py --geo JP  # 日本のみ
    python3 google_trends_collector.py --json    # JSON出力
"""

import subprocess, json, re, sys, argparse, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))

RSS_FEEDS = {
    'JP': 'https://trends.google.co.jp/trending/rss?geo=JP',
    'US': 'https://trends.google.com/trending/rss?geo=US',
}

# 除外キーワード（商品系でないトピック）
EXCLUDE_KEYWORDS = [
    # 芸能/エンタメ（商品リンクが弱い）
    '芸能', 'ドラマ', '映画', '俳優', '女優', 'アイドル', 'バラエティ',
    '離婚', '不倫', '結婚', '恋愛', 'スカンダル',
    '芸人', 'コメディアン', '歌手', 'アーティスト', 'バンド', 'ライブ', 'コンサート',
    # スポーツ（直接商品リンクが弱い）
    'サッカー', '野球', '競馬', '競輪', 'ゴルフ', 'テニス',
    'Jリーグ', 'MLB', 'NFL', 'NBA', 'W杯',
    # 政治・社会・災害
    '選挙', '首相', '大臣', '国会', '法案', '裁判', '逮捕', '起訴',
    '地震', '台風', '洪水', '災害', '事故',
    # 英語
    'actor', 'actress', 'movie', 'film', 'drama', 'celebrity', 'divorce',
    'scandal', 'wedding', 'dating',
    'football', 'baseball', 'soccer', 'tennis', 'golf',
    'election', 'president', 'congress', 'court', 'arrest',
    'earthquake', 'hurricane', 'disaster', 'accident',
    # 人名パターン（「○○ △△ 出演」など）
    '出演', '主演', '出演者', 'cast',
]

# 商品系キーワード（Tech/Gadget/Lifestyle）
PRODUCT_KEYWORDS = [
    # テック/ガジェット (優先度: 高)
    'iPhone', 'iPad', 'MacBook', 'Apple', 'Android', 'Samsung', 'Galaxy',
    'ノートPC', 'パソコン', 'PC', 'laptop', 'desktop',
    'ヘッドホン', 'イヤホン', 'AirPods', 'headphone', 'earphone',
    'カメラ', 'デジカメ', 'ミラーレス', 'Canon', 'Sony', 'Nikon',
    'Nintendo', 'Switch', 'PS5', 'PlayStation', 'Xbox', 'Steam',
    'モニター', 'ディスプレイ', 'monitor', 'display',
    'SSD', 'メモリ', 'グラボ', 'GPU', 'CPU', 'マザーボード', 'PCケース',
    # スマートホーム/IoT
    'スマートホーム', 'IoT', 'Alexa', 'Google Home', 'HomePod',
    '掃除機', 'ルンバ', 'ダイソン', 'dyson',
    # 家電
    '家電', '冷蔵庫', '洗濯機', '炊飯器', '電子レンジ', 'エアコン',
    # サービス/サブスク
    'ChatGPT', 'AI', 'LLM', 'Claude', 'Gemini', 'Perplexity',
    'Netflix', 'Spotify', 'YouTube', 'Amazon Prime',
    'サブスク', 'subscr',
    # 投資/金融 (商品リンクは弱いが、ガジェット企業関連は◎)
    'IPO', 'stock', '株', '株式', 'Tesla', 'SpaceX', 'NVIDIA', 'AMD',
    'Bitcoin', 'BTC', 'Ethereum', 'ETH', '暗号資産', '仮想通貨',
    # 買い物/セール
    'Amazon', '楽天', 'セール', 'ブラックフライデー', 'プライムデー',
    'ポイント', 'クーポン', '値下げ', '激安',
    # 車/移動
    'Tesla', 'EV', '電気自動車', 'BYD', 'Toyota',
    # 英語テック
    'tech', 'gadget', 'device', 'review', 'benchmark', 'release', 'launch',
    'announced', 'unveiled', 'new', 'best', 'top', 'vs', 'comparison',
    'laptop', 'smartphone', 'tablet', 'camera', 'headphone', 'earbuds',
    'monitor', 'keyboard', 'mouse', 'router', 'ssd', 'ram',
    'iPhone', 'iPad', 'MacBook', 'iMac', 'Apple Watch', 'AirPods',
    'Samsung', 'Galaxy', 'Pixel', 'OnePlus', 'Xiaomi',
    'Nintendo', 'Switch', 'PlayStation', 'Xbox',
    'NVIDIA', 'AMD', 'Intel', 'Qualcomm',
    'OpenAI', 'Anthropic', 'Microsoft', 'Google', 'Meta',
]

def fetch_rss(url, timeout=20):
    """RSSフィードをcurlで取得"""
    result = subprocess.run(
        ['curl', '-sS', '-L', '--max-time', str(timeout), url],
        capture_output=True, text=True, timeout=timeout + 5
    )
    if result.returncode != 0:
        return None
    return result.stdout

def parse_google_trends_rss(xml_text, geo='JP'):
    """Google Trends RSS（実はHTML summary）からキーワードを抽出
    
    Google Trendsの「RSS」は実際にはHTMLページとして返される。
    web_extractで取得した形式: ## タイトル + 説明文 のリスト
    """
    items = []
    
    # ## で始まるセクションで分割
    sections = re.split(r'\n## ', xml_text)
    
    for section in sections:
        lines = section.strip().split('\n')
        if not lines:
            continue
        
        title_line = lines[0].strip()
        
        # セクションヘッダをスキップ
        if title_line.startswith('# Google Trends') or title_line.startswith('A summary'):
            continue
        if '急上昇' in title_line or 'Trending' in title_line:
            continue
        
        # タイトルからキーワードを抽出
        # 形式: "1. **キーワード** (NNN+ searches)" または "キーワード"
        keyword = None
        searches = 0
        
        # "1. **キーワード** (200+ searches)" パターン
        m = re.match(r'\d+\.\s+\*\*(.+?)\*\*\s*\((\d+)\+', title_line)
        if m:
            keyword = m.group(1).strip()
            searches = int(m.group(2))
        else:
            # フォールバック: 最初の行をキーワードとして使用
            keyword = re.sub(r'[#*\d.]+', '', title_line).strip()
            if not keyword or len(keyword) > 60:
                continue
        
        if not keyword:
            continue

        # 説明文を結合
        description = ' '.join(lines[1:]) if len(lines) > 1 else ''
        
        items.append({
            'keyword': keyword,
            'searches': searches,
            'description': description[:300],
            'geo': geo,
            'source': 'google_trends',
        })
    
    return items

def is_excluded(keyword, description=''):
    """除外判定"""
    text = (keyword + ' ' + description).lower()
    for exc in EXCLUDE_KEYWORDS:
        if exc.lower() in text:
            return True
    return False

def is_product_related(keyword, description=''):
    """商品関連判定"""
    text = (keyword + ' ' + description).lower()
    for pk in PRODUCT_KEYWORDS:
        if pk.lower() in text:
            return True
    return False

def score_trend(item):
    """トレンドスコアリング (0-100)"""
    score = 0
    
    # 検索ボリュームベース
    searches = item.get('searches', 0)
    if searches >= 1000:
        score += 40
    elif searches >= 500:
        score += 30
    elif searches >= 200:
        score += 20
    elif searches >= 100:
        score += 10
    
    # 商品関連ボーナス
    if is_product_related(item['keyword'], item.get('description', '')):
        score += 30
    
    # 米国トレンドはテック情報が多いため軽いボーナス
    if item.get('geo') == 'US':
        score += 5
    
    return score

def collect_google_trends(geo_list=None, filter_product=True):
    """Google Trends收集中"""
    if geo_list is None:
        geo_list = ['JP', 'US']
    
    all_items = []
    
    for geo in geo_list:
        url = RSS_FEEDS.get(geo)
        if not url:
            continue
        
        print(f"  📡 Google Trends ({geo}): {url}")
        raw = fetch_rss(url)
        
        if not raw:
            print(f"  ⚠️ Google Trends ({geo}) 取得失敗")
            continue
        
        items = parse_google_trends_rss(raw, geo=geo)
        print(f"  ✅ {len(items)}件取得")
        
        for item in items:
            item['score'] = score_trend(item)
            item['is_product'] = is_product_related(item['keyword'], item.get('description', ''))
            item['is_excluded'] = is_excluded(item['keyword'], item.get('description', ''))
        
        all_items.extend(items)
    
    # 除外フィルタ
    active = [i for i in all_items if not i['is_excluded']]
    
    # 商品系フィルタ（フィルタモード時）
    if filter_product:
        product_items = [i for i in active if i['is_product']]
        # 商品系が3件未満なら、上位スコアの非商品系も含める
        if len(product_items) < 3:
            non_product = [i for i in active if not i['is_product']]
            non_product.sort(key=lambda x: x['score'], reverse=True)
            product_items.extend(non_product[:3 - len(product_items)])
        active = product_items
    
    # スコア順ソート
    active.sort(key=lambda x: x['score'], reverse=True)
    
    return active

def main():
    parser = argparse.ArgumentParser(description='Google Trends収集')
    parser.add_argument('--geo', type=str, default='JP,US', help='カンマ区切り (JP,US)')
    parser.add_argument('--json', action='store_true', help='JSON出力')
    parser.add_argument('--all', action='store_true', help='フィルタなし全件')
    args = parser.parse_args()
    
    geo_list = [g.strip() for g in args.geo.split(',')]
    items = collect_google_trends(geo_list=geo_list, filter_product=not args.all)
    
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
        return
    
    print(f"\n{'='*50}")
    print(f"Google Trends 収集結果: {len(items)}件")
    print(f"{'='*50}")
    
    for i, item in enumerate(items[:15], 1):
        marker = '🛍️' if item['is_product'] else '  '
        print(f"{marker}{i}. {item['keyword']} ({item['geo']}) — score:{item['score']} searches:{item.get('searches', '?')}")
        if item.get('description'):
            print(f"     {item['description'][:100]}")

if __name__ == '__main__':
    main()
