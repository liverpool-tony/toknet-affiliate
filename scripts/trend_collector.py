#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mastodon トレンド収集
mstdn.jp のトレンドタグからバズる商品・サービスを特定する

Usage:
    python3 trend_collector.py                  # 全処理実行
    python3 trend_collector.py --trends-only     # トレンドタグのみ表示
    python3 trend_collector.py --analyze TAG     # 特定タグの投稿分析
"""

import subprocess, json, re, sys, argparse, time, math
from datetime import datetime, timezone, timedelta
from collections import Counter
from pathlib import Path

BASE_URL = 'https://mstdn.jp'
JST = timezone(timedelta(hours=9))
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / 'data'
CACHE_FILE = DATA_DIR / 'trend_cache.json'
CACHE_TTL_SECONDS = 3600  # キャッシュ有効期限: 1時間

# 除外タグ（スポーツ・政治・ハッシュタグゲーム等）
EXCLUDE_PATTERNS = [
    # スポーツ
    r'^#nba', r'^#nbafinals', r'^#nfl', r'^#mlb', r'^#nhl',
    r'^#knicks', r'^#lakers', r'^#warriors', r'^#celtics',
    r'^#wm2026$', r'^#wm$', r'^#worldcup', r'^#ワールドカップ',
    # 政治・社会
    r'^#poland', r'^#gaza', r'^#deepfakes', r'^#ガザ',
    # ハッシュタグゲーム・お遊び
    r'^#appetizersabook', r'^#hashtaggames', r'^#throwbackthursday',
    r'^#thursdayfivelist', r'^#thursdayfive', r'^#blowinginthewind',
    r'^#doorsday', r'^#jと打って', r'^#今でも怖いもの',
    r'^#io写真', r'^#mexrsa', r'^#musiquinta',
    # その他
    r'^#grok$', r'^#deepfakes', r'^#thursday$',
]

# 商品・サービス関連キーワード
PRODUCT_KEYWORDS = [
    # 日本語
    'セール', '割引', 'クーポン', 'ポイント', '値下げ', '安い', '激安', 'お買い得',
    'ノートPC', 'パソコン', 'PC', 'カメラ', 'レンズ', 'ヘッドホン', 'イヤホン',
    'スマホ', 'iPhone', 'Android', 'タブレット', 'iPad', 'Apple',
    'Nintendo', 'Switch', 'PS5', 'PlayStation', 'Xbox', 'ゲーム',
    '家電', '洗濯機', '冷蔵庫', '掃除機', 'ダイソン', '炊飯器',
    'モニター', 'ディスプレイ', '4K', 'SSD', 'メモリ', 'グラボ',
    'Amazon', '楽天', 'ヨドバシ', 'ビックカメラ', '価格比較',
    'レビュー', 'おすすめ', 'ランキング', '比較', '検証',
    # 英語
    'deal', 'sale', 'discount', 'coupon', 'cheap', 'budget',
    'laptop', 'notebook', 'camera', 'headphone', 'earphone',
    'smartphone', 'tablet', 'monitor', 'display', 'gaming',
    'review', 'best', 'top', 'vs', 'comparison',
    'tech', 'gadget', 'device', 'gear',
]

# 日本語ストップワード（簡易的なものに絞る）
STOP_WORDS = {
    # 英語
    'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her',
    'was', 'one', 'our', 'out', 'has', 'his', 'how', 'its', 'may', 'new', 'now',
    'old', 'see', 'way', 'who', 'did', 'get', 'let', 'say', 'she', 'too', 'use',
    'https', 'http', 'www', 'com', 'org', 'net', 'html', 'htm', 'php',
    'this', 'that', 'with', 'from', 'they', 'been', 'have', 'will', 'each',
    'make', 'like', 'long', 'look', 'many', 'some', 'them', 'then', 'than',
    'only', 'come', 'over', 'such', 'also', 'back', 'well', 'most', 'into',
    'very', 'just', 'more', 'here', 'what', 'when', 'your', 'about', 'could',
    'would', 'should', 'which', 'their', 'there', 'these', 'those', 'where',
    'while', 'after', 'before', 'under', 'again', 'further', 'once',
    # 日本語（頻出するが分析価値の低いもの）
    'それ', 'この', 'あの', 'ない', 'ある', 'いる', 'なる', 'する', 'から',
    'まで', 'もの', 'ため', 'これ', 'あれ', 'でも', 'まだ', 'もう', 'だけ',
    'より', 'など', 'なか', 'では', 'そして', 'または', 'について', 'に対して',
    'によって', 'において', 'として', 'という', 'というのは', 'というもの',
    'というわけ', 'ということで', 'というか', 'というより', 'というほど',
    'という感じ', 'という意味', 'という考え', 'という立場', 'という視点',
    'という点', 'という面', 'という部分', 'という要素', 'という条件', 'という状況',
    'という状態', 'という形', 'という方式', 'という方法', 'という手段', 'という工夫',
    'という努力', 'という取り組み', 'という試み', 'という挑戦', 'という経験',
    'という体験', 'という感覚', 'という印象', 'という評価', 'という判断',
    'という認識', 'という理解', 'という解釈', 'という見方', 'という視座',
    'という視界', 'という視野', 'という範囲', 'という領域', 'という分野',
    'という部門', 'というカテゴリ', 'という分類', 'という区分', 'という区切り',
    'という段落', 'という章', 'という節', 'という項', 'という条', 'という款',
    'という号', 'という版', 'という巻', 'という冊', 'という編', 'という部',
    'という編成', 'という構成', 'という構造', 'という仕組み', 'というシステム',
    'というプログラム', 'というソフトウェア', 'というアプリケーション',
    'というアプリ', 'というツール', 'という機能', 'という性能', 'という仕様',
    'というスペック', 'という能力', 'という容量', 'というサイズ', 'という大きさ',
    'という規模', 'という量', 'という数', 'という値', 'というデータ', 'という情報',
    'という内容', 'という中身', 'という実態', 'という実情',
    'ない', 'なる', 'する', 'ある', 'いる', 'れる', 'られる', 'せる',
    'させる', 'たい', 'たがる', 'よう', 'そう', 'らしい', 'みたい', 'だろう',
    'でしょう', 'ません', 'ました', 'まして', 'ます', 'でした', 'だっ', 'だ',
    'である', 'であり', 'ですら', 'きり', 'ばかり', 'なんか', 'なんて',
}


def api_get(path, params=None, retries=3):
    """mstdn.jp APIをcurl経由で呼ぶ（指数バックオフ付きリトライ）"""
    url = f'{BASE_URL}{path}'
    if params:
        qs = '&'.join(f'{k}={v}' for k, v in params.items())
        url += '?' + qs

    for attempt in range(retries):
        try:
            result = subprocess.run(
                ['curl', '-sk', '--connect-timeout', '10', '-m', '20', url],
                capture_output=True, text=True, timeout=25
            )
            if result.returncode == 0 and result.stdout.strip():
                data = json.loads(result.stdout)
                return data
            # curl成功だが空レスポース or JSONパース失敗
            if attempt < retries - 1:
                wait = 2 ** attempt  # 1s, 2s, 4s
                print(f"    ⏳ リトライ待機 ({wait}s)...", file=sys.stderr)
                time.sleep(wait)
                continue
            raise RuntimeError(f"curl returned empty/invalid response after {retries} attempts")
        except json.JSONDecodeError:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"JSON parse error: {result.stdout[:100]}")
        except subprocess.TimeoutExpired:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Request timeout after {retries} attempts")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"Request failed after {retries} attempts: {e}")

    raise RuntimeError("Unreachable: api_get loop ended without return/raise")


def is_product_related(tag_name):
    """タグが商品・サービス関連か判定"""
    for pattern in EXCLUDE_PATTERNS:
        if re.match(pattern, tag_name, re.IGNORECASE):
            return False
    tag_lower = tag_name.lower()
    for kw in PRODUCT_KEYWORDS:
        if kw.lower() in tag_lower:
            return True
    return False


def strip_html(text):
    return re.sub(r'<[^>]+>', '', text)


def load_cache():
    """キャッシュを読み込み、有効期限をチェック"""
    if not CACHE_FILE.exists():
        return None, "no_cache"
    try:
        with open(CACHE_FILE) as f:
            cached = json.load(f)
        cached_at = datetime.fromisoformat(cached['cached_at'])
        age = (datetime.now(JST) - cached_at).total_seconds()
        if age > CACHE_TTL_SECONDS:
            return cached.get('tags', []), f"expired ({age/60:.0f}min old)"
        return cached.get('tags', []), f"valid ({age/60:.0f}min old)"
    except (json.JSONDecodeError, KeyError, ValueError):
        return None, "corrupt"


def save_cache(tags):
    """キャッシュを保存"""
    DATA_DIR.mkdir(exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump({
            'tags': tags,
            'cached_at': datetime.now(JST).isoformat()
        }, f, ensure_ascii=False)


def get_trending_tags(limit=20):
    """トレンドタグを取得してスコアリング"""
    # まずキャッシュを試す
    cached_tags, cache_status = load_cache()
    if cached_tags and cache_status.startswith("valid"):
        print(f"  📦 キャッシュ使用: {cache_status}", file=sys.stderr)
        return cached_tags

    # API取得を試みる
    try:
        tags = api_get('/api/v1/trends/tags', {'limit': str(limit)})
        results = []
        for t in tags:
            name = t['name']
            hist = t.get('history', [])
            today_uses = int(hist[0]['uses']) if hist else 0
            today_accts = int(hist[0]['accounts']) if hist else 0
            total_uses_7d = sum(int(h['uses']) for h in hist[:7])
            total_accts_7d = sum(int(h['accounts']) for h in hist[:7])

            # スコア = 7日合計uses * log(accounts+1)（拡散度を重視）
            score = total_uses_7d * math.log(total_accts_7d + 1)

            results.append({
                'name': name,
                'today_uses': today_uses,
                'today_accts': today_accts,
                'total_uses_7d': total_uses_7d,
                'total_accts_7d': total_accts_7d,
                'score': round(score, 1),
                'is_product': is_product_related('#' + name),
            })

        results.sort(key=lambda x: x['score'], reverse=True)
        save_cache(results)
        return results

    except Exception as e:
        print(f"  ⚠️ API取得失敗: {e}", file=sys.stderr)
        if cached_tags:
            print(f"  📦 期限切れキャッシュ使用: {cache_status}", file=sys.stderr)
            return cached_tags
        raise RuntimeError("トレンド取得不可（API・キャッシュ両方失敗）")


def get_tag_posts(tag_name, limit=20):
    """特定タグの投稿を取得"""
    return api_get(f'/api/v1/timelines/tag/{tag_name}', {'limit': str(limit)})


def analyze_posts(posts):
    """投稿からキーワード・URL・商品名を抽出"""
    all_text = []
    all_urls = []
    engagement_scores = []

    for s in posts:
        content = strip_html(s.get('content', ''))
        all_text.append(content)

        # URL抽出
        urls = re.findall(r'https?://[^\s<>"\']+', content)
        all_urls.extend(urls)

        # エンゲージメントスコア
        boosts = s.get('reblogs_count', 0)
        favs = s.get('favourites_count', 0)
        engagement_scores.append(boosts * 3 + favs)

    # 頻出単語抽出
    word_counter = Counter()
    for text in all_text:
        words = re.findall(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]+|[a-zA-Z]{3,}', text)
        for w in words:
            if len(w) >= 2:
                word_counter[w] += 1

    filtered_words = {
        w: c for w, c in word_counter.most_common(50)
        if w not in STOP_WORDS and len(w) >= 2
    }

    return {
        'post_count': len(posts),
        'avg_engagement': sum(engagement_scores) / len(engagement_scores) if engagement_scores else 0,
        'top_words': list(filtered_words.items())[:20],
        'urls': list(set(all_urls))[:10],
        'sample_texts': all_text[:5],
    }


def format_report(tags_with_analysis):
    """レポートを整形"""
    now = datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')
    lines = []
    lines.append(f'📊 Mastodon トレンドレポート ({now})')
    lines.append('=' * 50)
    lines.append('')

    product_tags = [t for t in tags_with_analysis if t['is_product']]
    other_tags = [t for t in tags_with_analysis if not t['is_product']]

    lines.append(f'🛍️ 商品・サービス関連トップ ({len(product_tags)}件)')
    lines.append('-' * 40)
    for i, t in enumerate(product_tags[:10], 1):
        lines.append(f'{i}. #{t["name"]}')
        lines.append(f'   7日計: {t["total_uses_7d"]}投稿 / {t["total_accts_7d"]}人')
        lines.append(f'   スコア: {t["score"]}')
        if t.get('analysis'):
            a = t['analysis']
            lines.append(f'   平均エンゲージメント: {a["avg_engagement"]:.1f}')
            if a['top_words']:
                words_str = ', '.join(f'{w}({c})' for w, c in a['top_words'][:8])
                lines.append(f'   頻出ワード: {words_str}')
            if a['urls']:
                lines.append(f'   参照URL: {a["urls"][0]}')
        lines.append('')

    lines.append(f'📌 全トレンドタグ（除外含む）')
    lines.append('-' * 40)
    for t in tags_with_analysis[:20]:
        marker = '🛍️' if t['is_product'] else '🚫'
        lines.append(f'  {marker} #{t["name"]} - {t["total_uses_7d"]}uses (score:{t["score"]})')

    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description='Mastodon トレンド収集')
    parser.add_argument('--trends-only', action='store_true', help='トレンドタグのみ表示')
    parser.add_argument('--analyze', type=str, help='特定タグの投稿を分析')
    parser.add_argument('--top', type=int, default=10, help='分析する商品系タグの数')
    args = parser.parse_args()

    if args.analyze:
        tag = args.analyze.lstrip('#')
        print(f'=== #{tag} 投稿分析 ===')
        posts = get_tag_posts(tag, limit=20)
        analysis = analyze_posts(posts)
        print(f'取得投稿数: {analysis["post_count"]}')
        print(f'平均エンゲージメント: {analysis["avg_engagement"]:.1f}')
        print(f'頻出ワード: {", ".join(f"{w}({c})" for w, c in analysis["top_words"][:15])}')
        if analysis['urls']:
            print(f'参照URL:')
            for u in analysis['urls'][:5]:
                print(f'  {u}')
        print()
        print('--- 投稿サンプル ---')
        for i, text in enumerate(analysis['sample_texts'][:5], 1):
            print(f'{i}. {text[:150]}')
        return

    print('トレンドタグ取得中...', file=sys.stderr)
    tags = get_trending_tags(limit=20)

    if args.trends_only:
        for t in tags:
            marker = '🛍️' if t['is_product'] else '🚫'
            print(f'{marker} #{t["name"]} - {t["total_uses_7d"]}uses (score:{t["score"]})')
        return

    product_tags = [t for t in tags if t['is_product']]
    print(f'商品系タグ {len(product_tags)}件 を分析中...', file=sys.stderr)

    for t in product_tags[:args.top]:
        tag_name = t['name']
        try:
            posts = get_tag_posts(tag_name, limit=15)
            t['analysis'] = analyze_posts(posts)
            print(f'  ✓ #{tag_name}: {t["analysis"]["post_count"]}投稿分析完了', file=sys.stderr)
        except Exception as e:
            print(f'  ✗ #{tag_name}: {e}', file=sys.stderr)

    report = format_report(tags)
    print(report)


if __name__ == '__main__':
    main()
