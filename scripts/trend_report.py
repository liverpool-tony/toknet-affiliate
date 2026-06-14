#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統合トレンドレポート生成
Mastodonトレンド + RSSキーワード監視 → 統合レポート

Usage:
    python3 trend_report.py              # 統合レポート生成→Telegram送信
    python3 trend_report.py --json       # JSON出力
"""

import subprocess, json, sys, argparse, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
JST = timezone(timedelta(hours=9))

def now_jst_str():
    return datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')

def run_trend_collector():
    """トレンドタグ収集"""
    sys.path.insert(0, str(Path(__file__).parent))
    from trend_collector import get_trending_tags
    return get_trending_tags(limit=20)

def run_rss_monitor(keywords=None):
    """RSSキーワード監視"""
    script = str(Path(__file__).parent / 'rss_keyword_monitor.py')
    args = [sys.executable, script]
    if keywords:
        args += ['--keywords', ','.join(keywords)]
    result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    return result.stdout

def run_tag_analysis(tag_name, limit=10):
    """特定タグの投稿詳細分析"""
    sys.path.insert(0, str(Path(__file__).parent))
    from trend_collector import get_tag_posts, analyze_posts
    posts = get_tag_posts(tag_name, limit=limit)
    return analyze_posts(posts)

def generate_unified_report():
    """統合レポート生成"""
    lines = []
    now = now_jst_str()
    
    lines.append(f'📊 AI共創レビュー研究所 トレンドレポート')
    lines.append(f'🕐 {now}')
    lines.append('=' * 40)
    
    # === Section 1: トレンドタグ ===
    lines.append(f'\n📈 [1/3] Mastodonトレンドタグ TOP10')
    lines.append('-' * 40)
    
    try:
        tags = run_trend_collector()
        for i, t in enumerate(tags[:10], 1):
            marker = '🛍️' if t['is_product'] else '  '
            lines.append(f'{marker}{i}. #{t["name"]}')
            lines.append(f'     7日: {t["total_uses_7d"]}投稿 / {t["total_accts_7d"]}人 (score:{t["score"]})')
    except Exception as e:
        lines.append(f'  エラー: {e}')
    
    # === Section 2: 商品系タグの詳細 ===
    lines.append(f'\n🔍 [2/3] 商品系タグ詳細分析')
    lines.append('-' * 40)
    
    try:
        product_tags = [t for t in tags if t['is_product']][:5]
        if product_tags:
            sys.path.insert(0, str(Path(__file__).parent))
            from trend_collector import get_tag_posts, analyze_posts
            
            for t in product_tags:
                tag_name = t['name']
                try:
                    posts = get_tag_posts(tag_name, limit=10)
                    analysis = analyze_posts(posts)
                    
                    lines.append(f'\n  📌 #{tag_name}')
                    lines.append(f'     投稿数: {analysis["post_count"]} / 平均エンゲージメント: {analysis["avg_engagement"]:.1f}')
                    
                    if analysis['top_words']:
                        words_str = ', '.join(f'{w}({c})' for w, c in analysis['top_words'][:5])
                        lines.append(f'     頻出ワード: {words_str}')
                    
                    if analysis['urls']:
                        lines.append(f'     参照: {analysis["urls"][0][:80]}')
                except Exception as e:
                    lines.append(f'  📌 #{tag_name}: 分析エラー ({e})')
        else:
            lines.append('  商品系タグはありませんでした')
    except Exception as e:
        lines.append(f'  エラー: {e}')
    
    # === Section 3: キーワード監視 ===
    lines.append(f'\n📡 [3/3] キーワードRSS監視')
    lines.append('-' * 40)
    
    data_dir = Path(__file__).parent / 'data'
    history_file = data_dir / 'keyword_history.json'
    if history_file.exists():
        with open(history_file) as f:
            history = json.load(f)
        snapshots = history.get('snapshots', [])
        if snapshots:
            latest = snapshots[-1]
            kw_counts = latest.get('keyword_counts', {})
            active = {k: v for k, v in kw_counts.items() if v > 0}
            if active:
                for kw, count in sorted(active.items(), key=lambda x: x[1], reverse=True)[:10]:
                    lines.append(f'  📎 {kw}: {count}投稿')
            else:
                lines.append('  現在アクティブなキーワードはありません')
            
            lines.append(f'  監視キーワード総数: {len(kw_counts)}')
        else:
            lines.append('  まだ履歴がありません')
    else:
        lines.append('  まだ監視データがありません。rss_keyword_monitor.py を実行してください')
    
    # === Summary ===
    lines.append(f'\n💡 次のアクション')
    lines.append('-' * 40)
    lines.append(f'  トレンドに基づく記事生成: python3 scripts/article_generator.py --tag <タグ名>')
    lines.append(f'  新着キーワード追加: python3 scripts/rss_keyword_monitor.py --add-keyword "新キーワード"')
    lines.append(f'  レポート再生成: python3 scripts/trend_report.py')
    
    return '\n'.join(lines)

def main():
    parser = argparse.ArgumentParser(description='統合トレンドレポート')
    parser.add_argument('--json', action='store_true', help='JSON出力')
    args = parser.parse_args()
    
    report = generate_unified_report()
    print(report)

if __name__ == '__main__':
    main()
