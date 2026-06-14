#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mastodon RSSフィード キーワード監視スクリプト
特定のキーワードを含む投稿をRSSで定期検知

Usage:
    python3 rss_keyword_monitor.py                     # 全キーワード監視
    python3 rss_keyword_monitor.py --keywords "iPhone,MacBook"  # 指定キーワード
    python3 rss_keyword_monitor.py --add-keyword "grep"          # キーワード追加
    python3 rss_keyword_monitor.py --list                        # 登録キーワード一覧
    python3 rss_keyword_monitor.py --report                    # レポート出力
"""

import subprocess, json, re, sys, argparse, os, hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

PROJECT_DIR = Path(__file__).parent.parent
JST = timezone(timedelta(hours=9))
DATA_DIR = Path(__file__).parent / 'data'
DATA_DIR.mkdir(exist_ok=True)

KEYWORDS_FILE = DATA_DIR / 'monitor_keywords.json'
HISTORY_FILE = DATA_DIR / 'keyword_history.json'

# デフォルト監視キーワード（商品・サービス・テクノロジー関連）
DEFAULT_KEYWORDS = [
    # ガジェット
    'iPhone', 'iPad', 'MacBook', 'MacBook Air', 'MacBook Pro',
    'AirPods', 'Apple Watch', 'Pixel', 'Galaxy', 'Surface',
    # カメラ
    'カメラ', 'ミラーレス', '一眼レフ', 'GoPro', 'レンズ',
    'Canon', 'Nikon', 'Sony', 'Fujifilm', 'Panasonic',
    # オーディオ
    'ヘッドホン', 'イヤホン', 'ノイズキャンセリング',
    'Sony WH', 'AirPods Pro', 'Bose', 'Sennheiser',
    # 家電
    'ダイソン', 'ルンバ', '掃除機', '冷蔵庫', '洗濯機',
    '炊飯器', '電子レンジ', 'エアコン',
    # ゲーム
    'Nintendo Switch', 'PlayStation', 'PS5', 'Xbox',
    'Steam Deck', 'Switch 2',
    # テクノロジー
    'AI', 'ChatGPT', 'Claude', 'Gemini', 'GPT',
    'M4', 'M3', 'Apple Intelligence',
    # サービス
    'Netflix', 'Spotify', 'Amazonプライム', 'YouTube',
]

MSTODON_INSTANCES = [
    'https://mstdn.jp',
]

def now_jst():
    return datetime.now(JST)

def now_jst_str():
    return now_jst().strftime('%Y-%m-%d %H:%M')

def load_keywords():
    if KEYWORDS_FILE.exists():
        with open(KEYWORDS_FILE) as f:
            data = json.load(f)
            return data.get('keywords', DEFAULT_KEYWORDS)
    return DEFAULT_KEYWORDS

def save_keywords(keywords):
    with open(KEYWORDS_FILE, 'w') as f:
        json.dump({'keywords': keywords, 'updated': now_jst_str()}, f, ensure_ascii=False, indent=2)

def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return {'snapshots': []}

def save_history(data):
    with open(HISTORY_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_rss_feed(instance, keyword):
    """Mastodon RSSフィードから特定キーワードを含む投稿を取得"""
    # Mastodon hashtag RSS: https://mstdn.jp/tags/{keyword}.rss
    # キーワードをハッシュタグ形式に
    tag = keyword.replace(' ', '').replace('#', '')
    # 日本語のままではURLにできないのでエンコード
    tag_encoded = keyword.replace(' ', '%20')
    
    url = f'{instance}/tags/{tag_encoded}.rss'
    try:
        result = subprocess.run(
            ['curl', '-sk', '--connect-timeout', '10', url],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode != 0:
            return []
        
        return parse_rss_items(result.stdout, keyword, instance)
    except Exception as e:
        return []

def parse_rss_items(xml_data, keyword, instance):
    """簡易RSSパーサー（xml使わずregexで）"""
    items = []
    for item_match in re.finditer(r'<item>(.*?)</item>', xml_data, re.DOTALL):
        item_xml = item_match.group(1)
        
        title_m = re.search(r'<title>(.*?)</title>', item_xml, re.DOTALL)
        title = strip_html(title_m.group(1)) if title_m else ''
        
        link_m = re.search(r'<link>(.*?)</link>', item_xml, re.DOTALL)
        link = link_m.group(1).strip() if link_m else ''
        
        desc_m = re.search(r'<description>(.*?)</description>', item_xml, re.DOTALL)
        desc = strip_html(desc_m.group(1)) if desc_m else ''
        
        pub_m = re.search(r'<pubDate>(.*?)</pubDate>', item_xml, re.DOTALL)
        pub_date = pub_m.group(1).strip() if pub_m else ''
        
        items.append({
            'keyword': keyword,
            'title': title,
            'link': link,
            'description': desc[:500],
            'pub_date': pub_date,
            'instance': instance,
        })
    
    return items

def strip_html(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'&#39;', "'", text)
    return text.strip()

def fetch_keyword_trends(instance, keyword):
    """Google Trends風にキーワードの検索関心をMastodonで推定"""
    # 過去7日の投稿数をカウント
    tag = keyword.replace(' ', '').replace('#', '')
    url = f'{instance}/api/v1/timelines/tag/{tag}'
    try:
        result = subprocess.run(
            ['curl', '-sk', '--connect-timeout', '10', url, '-G', '-d', 'limit=40'],
            capture_output=True, text=True, timeout=15
        )
        posts = json.loads(result.stdout)
        if not isinstance(posts, list):
            return 0
        
        # 7日以内の投稿のみカウント
        now_utc = datetime.now(timezone.utc)
        recent_count = 0
        for post in posts:
            date_str = post.get('created_at', '')
            if date_str:
                try:
                    post_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    if (now_utc - post_date).days <= 7:
                        recent_count += 1
                except:
                    pass
        
        return recent_count
    except:
        return 0

def monitor_all_keywords(dry_run=False):
    """全キーワードの監視を実行"""
    keywords = load_keywords()
    all_results = []
    
    print(f'=== RSSキーワード監視 ({len(keywords)} keywords) ===', file=sys.stderr)
    
    for keyword in keywords:
        for instance in MSTODON_INSTANCES:
            # RSSフィードから取得
            items = fetch_rss_feed(instance, keyword)
            
            if items:
                all_results.extend(items)
                print(f'  ✓ "{keyword}" → {len(items)} posts ({instance})', file=sys.stderr)
            else:
                # RSSにない場合はAPIで直接確認
                count = fetch_keyword_trends(instance, keyword)
                if count > 0:
                    print(f'  ~ "{keyword}" → {count} recent posts (via API)', file=sys.stderr)
                    all_results.append({
                        'keyword': keyword,
                        'title': f'({count} recent posts)',
                        'link': f'{instance}/tags/{keyword}',
                        'description': '',
                        'pub_date': now_jst_str(),
                        'instance': instance,
                        'recent_count': count,
                    })
    
    # 履歴に保存
    history = load_history()
    snapshot = {
        'timestamp': now_jst_str(),
        'findings': all_results,
        'keyword_counts': dict(Counter(r['keyword'] for r in all_results).most_common()),
    }
    history['snapshots'].append(snapshot)
    
    # 履歴は最新100件まで
    if len(history['snapshots']) > 100:
        history['snapshots'] = history['snapshots'][-100:]
    
    save_history(history)
    
    return all_results

def generate_report():
    """レポート生成"""
    history = load_history()
    keywords = load_keywords()
    
    lines = []
    lines.append(f'📊 RSSキーワード監視レポート ({now_jst_str()})')
    lines.append('=' * 50)
    
    snapshots = history.get('snapshots', [])
    if not snapshots:
        lines.append('まだデータがありません。')
        return '\n'.join(lines)
    
    # 最新スナップショット
    latest = snapshots[-1]
    findings = latest.get('findings', [])
    
    lines.append(f'\n🔍 最新スナップショット: {latest["timestamp"]}')
    lines.append(f'   検出投稿数: {len(findings)}')
    
    # キーワード別集計
    kw_counts = latest.get('keyword_counts', {})
    if kw_counts:
        lines.append(f'\n📈 キーワード別投稿数')
        for kw, count in sorted(kw_counts.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                lines.append(f'   {kw}: {count}')
    
    # 残存投稿
    total_kw = sum(1 for c in kw_counts.values() if c > 0)
    lines.append(f'\n   投稿ありキーワード: {total_kw}/{len(keywords)}')
    
    # 過去の推移
    if len(snapshots) >= 2:
        prev = snapshots[-2]
        prev_counts = prev.get('keyword_counts', {})
        curr_counts = kw_counts
        
        lines.append(f'\n📊 前回比 ({prev["timestamp"][:16]} → {latest["timestamp"][:16]})')
        all_kws = set(list(prev_counts.keys()) + list(curr_counts.keys()))
        changes = []
        for kw in all_kws:
            prev_c = prev_counts.get(kw, 0)
            curr_c = curr_counts.get(kw, 0)
            if curr_c != prev_c:
                delta = curr_c - prev_c
                sign = '↑' if delta > 0 else '↓'
                changes.append((kw, sign, abs(delta)))
        
        changes.sort(key=lambda x: x[2], reverse=True)
        for kw, sign, delta in changes[:10]:
            lines.append(f'   {kw}: {sign}{delta}')
    
    return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(description='RSSキーワード監視')
    parser.add_argument('--add-keyword', type=str, help='キーワード追加')
    parser.add_argument('--remove-keyword', type=str, help='キーワード削除')
    parser.add_argument('--list', action='store_true', help='登録キーワード一覧')
    parser.add_argument('--report', action='store_true', help='レポート出力')
    parser.add_argument('--keywords', type=str, help='カンマ区切りで指定')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    
    if args.list:
        keywords = load_keywords()
        for i, kw in enumerate(keywords, 1):
            print(f'{i}. {kw}')
        return
    
    if args.add_keyword:
        keywords = load_keywords()
        if args.add_keyword not in keywords:
            keywords.append(args.add_keyword)
            save_keywords(keywords)
            print(f'追加: {args.add_keyword}')
        else:
            print(f'既に登録済み: {args.add_keyword}')
        return
    
    if args.remove_keyword:
        keywords = load_keywords()
        if args.remove_keyword in keywords:
            keywords.remove(args.remove_keyword)
            save_keywords(keywords)
            print(f'削除: {args.remove_keyword}')
        return
    
    if args.report:
        print(generate_report())
        return
    
    # メイン: 監視実行
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(',')]
        # 一時キーワードで上書き
        original = load_keywords()
        save_keywords(keywords)
    
    results = monitor_all_keywords(dry_run=args.dry_run)
    
    # 結果表示
    print(generate_report())
    
    if results:
        print(f'\n=== 検出投稿サンプル ===')
        for r in results[:5]:
            print(f'  [{r["keyword"]}] {r.get("title", "")}')
            print(f'    {r.get("link", "")}')
            desc = r.get('description', '')
            if desc:
                print(f'    {desc[:100]}')
            print()

if __name__ == '__main__':
    main()
