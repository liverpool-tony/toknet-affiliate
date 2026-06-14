#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDCA クローズループ
- Cloudflare Analytics → アクセスデータ取得
- 記事のパフォーマンス測定
- トレンド予測のフィードバック

Usage:
    python3 pdca_loop.py                    # 週次レポート
    python3 pdca_loop.py --daily            # 日次サマリー
    python3 pdca_loop.py --feedback         # トレンド予測フィードバック
"""

import subprocess, json, re, sys, os, argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
JST = timezone(timedelta(hours=9))

# データファイル
DATA_DIR = Path(__file__).parent / 'data'
DATA_DIR.mkdir(exist_ok=True)

METRICS_FILE = DATA_DIR / 'metrics.json'
TREND_LOG_FILE = DATA_DIR / 'trend_log.json'

def now_jst_str():
    return datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')

# ============================================================
# 1. Cloudflare Analytics データ取得
# ============================================================

def fetch_cloudflare_analytics(days=7):
    """Cloudflare Analytics APIでアクセスデータを取得"""
    # Cloudflare API認証
    api_token = os.environ.get('CLOUDFLARE_API_TOKEN', '')
    account_id = os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')
    zone_id = os.environ.get('CLOUDFLARE_ZONE_ID', '')  # toknet.info zone
    
    if zone_id:
        # Zone Analytics を使用
        return fetch_zone_analytics(zone_id, api_token, days)
    else:
        # Pages Analytics はDashboardで手動確認
        print('NOTE: CLOUDFLARE_ZONE_ID が未設定。Cloudflare Dashboardで確認してください。')
        return None

def fetch_zone_analytics(zone_id, api_token, days=7):
    """Zone Analytics API"""
    until = datetime.now(JST).strftime('%Y-%m-%dT%H:%M:%SZ')
    since = (datetime.now(JST) - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    
    url = f'https://api.cloudflare.com/client/v4/zones/{zone_id}/analytics/dashboard'
    result = subprocess.run([
        'curl', '-s', '-X', 'GET', url,
        '-H', f'Authorization: Bearer {{api_token}}',
        '-H', 'Content-Type: application/json',
        '-G', '-d', f'since={since}',
        '-d', f'until={until}',
    ], capture_output=True, text=True, timeout=30)
    
    data = json.loads(result.stdout)
    if data.get('success') and data.get('result'):
        return data['result']
    else:
        print(f'Analytics API error: {data.get("errors", result.stdout)}')
        return None

# ============================================================
# 2. メトリクス記録
# ============================================================

def record_article_metrics(title, url, category, trend_tag, sns_platform='mastodon'):
    """記事のメトリクスを記録"""
    metrics = load_metrics()
    
    entry = {
        'timestamp': datetime.now(JST).isoformat(),
        'type': 'article',
        'title': title,
        'url': url,
        'category': category,
        'trend_tag': trend_tag,
        'sns_platform': sns_platform,
        'views': 0,      # 後でAnalyticsから更新
        'clicks': 0,     # Amazonクリック数
        'conversions': 0, # Amazon成約数
    }
    
    metrics['entries'].append(entry)
    save_metrics(metrics)
    return entry

def record_trend_snapshot():
    """現在のトレンドをスナップショット保存（予測精度測定用）"""
    print('現在のトレンドを記録中...')
    
    sys.path.insert(0, str(Path(__file__).parent))
    from trend_collector import get_trending_tags
    
    tags = get_trending_tags(limit=20)
    
    snapshot = {
        'timestamp': datetime.now(JST).isoformat(),
        'tags': [
            {
                'name': t['name'],
                'total_uses_7d': t['total_uses_7d'],
                'total_accts_7d': t['total_accts_7d'],
                'score': t['score'],
                'is_product': t['is_product'],
            }
            for t in tags
        ]
    }
    
    trend_log = load_trend_log()
    trend_log['snapshots'].append(snapshot)
    save_trend_log(trend_log)
    print(f'トレンドスナップショット保存: {len(snapshot["tags"])} tags')

def load_metrics():
    if METRICS_FILE.exists():
        with open(METRICS_FILE) as f:
            return json.load(f)
    return {'entries': [], 'last_updated': None}

def save_metrics(data):
    data['last_updated'] = datetime.now(JST).isoformat()
    with open(METRICS_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_trend_log():
    if TREND_LOG_FILE.exists():
        with open(TREND_LOG_FILE) as f:
            return json.load(f)
    return {'snapshots': [], 'predictions': []}

def save_trend_log(data):
    with open(TREND_LOG_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ============================================================
# 3. パフォーマンスレポート
# ============================================================

def generate_daily_report():
    """日次レポート"""
    metrics = load_metrics()
    trend_log = load_trend_log()
    
    lines = []
    lines.append(f'📊 日次レポート ({now_jst_str()})')
    lines.append('=' * 50)
    
    # 記事パフォーマンス
    entries = metrics.get('entries', [])
    if entries:
        lines.append(f'\n📝 記事パフォーマンス ({len(entries)}件)')
        lines.append('-' * 40)
        for e in entries[-10:]:  # 最新10件
            date = e['timestamp'][:10]
            title = e['title'][:40]
            views = e.get('views', 0)
            lines.append(f'  [{date}] {title}')
            lines.append(f'    views: {views}')
    else:
        lines.append('\n📝 まだ記事がありません')
    
    # トレンド推移
    snapshots = trend_log.get('snapshots', [])
    if snapshots:
        lines.append(f'\n📈 トレンドスナップショット ({len(snapshots)}件)')
        lines.append('-' * 40)
        for s in snapshots[-5:]:
            date = s['timestamp'][:16]
            tag_count = len(s.get('tags', []))
            product_count = sum(1 for t in s.get('tags', []) if t.get('is_product'))
            lines.append(f'  [{date}] 全{tag_count}タグ / 商品系{product_count}件')
    
    report = '\n'.join(lines)
    return report

def generate_weekly_report():
    """週次レポート"""
    metrics = load_metrics()
    trend_log = load_trend_log()
    
    lines = []
    lines.append(f'📊 週次レポート ({now_jst_str()})')
    lines.append('=' * 50)
    
    # アクセストップページ
    lines.append('\n🏆 アクセス上位')
    entries = metrics.get('entries', [])
    if entries:
        sorted_entries = sorted(entries, key=lambda x: x.get('views', 0), reverse=True)
        for i, e in enumerate(sorted_entries[:10], 1):
            title = e.get('title', '?')[:40]
            views = e.get('views', 0)
            lines.append(f'  {i}. {title} ({views} views)')
    else:
        lines.append('  データがありません')
    
    # カテゴリ別パフォーマンス
    lines.append('\n📂 カテゴリ別')
    categories = {}
    for e in entries:
        cat = e.get('category', 'unknown')
        categories.setdefault(cat, {'count': 0, 'views': 0})
        categories[cat]['count'] += 1
        categories[cat]['views'] += e.get('views', 0)
    
    for cat, data in sorted(categories.items(), key=lambda x: x[1]['views'], reverse=True):
        lines.append(f'  {cat}: {data["count"]}記事 / {data["views"]}views')
    
    # トレンド予測精度
    lines.append('\n🎯 トレンド予測精度')
    snapshots = trend_log.get('snapshots', [])
    if len(snapshots) >= 2:
        # 前週のスナップショットから、どのタグが実際に記事になったか検証
        prev_tags = set(t['name'] for t in snapshots[-2].get('tags', []))
        curr_tags = set(t['name'] for t in snapshots[-1].get('tags', []))
        new_tags = curr_tags - prev_tags
        retained_tags = curr_tags & prev_tags
        lines.append(f'  継続タグ: {len(retained_tags)}')
        lines.append(f'  新規タグ: {len(new_tags)}')
        lines.append(f'  予測精度(継続率): {len(retained_tags)/len(prev_tags)*100:.0f}%' if prev_tags else '  N/A')
    else:
        lines.append('  データ不足（2週分以上のスナップショットが必要）')
    
    report = '\n'.join(lines)
    return report

def generate_feedback():
    """トレンド予測のフィードバック（改善提案）"""
    trend_log = load_trend_log()
    metrics = load_metrics()
    
    lines = []
    lines.append(f'🔄 トレンド予測フィードバック ({now_jst_str()})')
    lines.append('=' * 50)
    
    snapshots = trend_log.get('snapshots', [])
    if not snapshots:
        lines.append('スナップショットがありません。まず --record で記録してください。')
        return '\n'.join(lines)
    
    # 最新スナップショットのタグを分析
    latest = snapshots[-1]
    tags = latest.get('tags', [])
    
    # 頻出タグ（過去のスナップショットも含む）
    all_tag_names = []
    for s in snapshots:
        all_tag_names.extend(t['name'] for t in s.get('tags', []))
    
    from collections import Counter
    tag_freq = Counter(all_tag_names)
    
    lines.append('\n📊 頻出トレンドタグ')
    for tag, count in tag_freq.most_common(15):
        is_product = any(t.get('is_product') for t in tags if t['name'] == tag)
        marker = '🛍️' if is_product else '🚫'
        lines.append(f'  {marker} #{tag} — {count}回出現')
    
    # 商品系タグのキーワード分析
    lines.append('\n🛍️ 商品系キーワード分析')
    product_tags = [t for t in tags if t.get('is_product')]
    if product_tags:
        for t in product_tags[:10]:
            lines.append(f'  #{t["name"]} (score: {t["score"]})')
    else:
        lines.append('  商品系タグは現在ありません')
    
    # 改善提案
    lines.append('\n💡 改善提案')
    
    if len(product_tags) < 3:
        lines.append('  - 商品系タグ検出が少ない。除外パターンを調整するか、時間帯を変えてみてください')
    
    sport_tags = sum(1 for t in tags if t['name'].lower() in [
        'nba', 'nbafinals', 'nfl', 'mlb', 'nhl', 'knicks', 'wm2026', 'wm'
    ])
    if sport_tags > 3:
        lines.append(f'  - スポーツ関連タグが{sport_tags}件。より除外パターンを追加してください')
    
    if len(tag_freq) > 0:
        top_non_product = [t for t, _ in tag_freq.most_common(20) if not any(
            pt['name'] == t and pt.get('is_product') for pt in tags
        )]
        if top_non_product:
            lines.append(f'  - 除外検討: {", ".join(f"#{t}" for t in top_non_product[:5])}')
    
    return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(description='PDCAクローズループ')
    parser.add_argument('--daily', action='store_true', help='日次レポート')
    parser.add_argument('--weekly', action='store_true', help='週次レポート')
    parser.add_argument('--feedback', action='store_true', help='トレンド予測フィードバック')
    parser.add_argument('--record', action='store_true', help='トレンドスナップショット記録')
    args = parser.parse_args()
    
    if args.record:
        record_trend_snapshot()
        return
    
    if args.feedback:
        print(generate_feedback())
        return
    
    if args.weekly:
        print(generate_weekly_report())
        return
    
    # デフォルト: 日次
    print(generate_daily_report())

if __name__ == '__main__':
    main()
