#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
追加トレンド収集モジュール
mstdn.jp の他のソースからのトレンドを補完する

- はてなブックマーク (テック系人気エントリー)
- ITmedia NEWS RSS
- Engadget 日本版 RSS
- 価格.com 新着・人気 (スクレイピング)

標準ライブラリのみで動作（pip install 不要）
"""

import subprocess, json, re, sys, time, hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter
import xml.etree.ElementTree as ET

JST = timezone(timedelta(hours=9))
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / 'data'
TREND_CACHE_FILE = DATA_DIR / 'multi_trend_cache.json'

# 商品関連キーワード（スコアリング用）
PRODUCT_KEYWORDS = [
    'ノートPC', 'パソコン', 'PC', 'カメラ', 'レンズ', 'ヘッドホン', 'イヤホン',
    'スマホ', 'iPhone', 'Android', 'タブレット', 'iPad', 'Apple',
    'Nintendo', 'Switch', 'PS5', 'PlayStation', 'Xbox', 'ゲーム',
    '家電', '洗濯機', '冷蔵庫', '掃除機', 'ダイソン',
    'モニター', 'ディスプレイ', '4K', 'SSD', 'メモリ', 'グラボ',
    'レビュー', 'おすすめ', 'ランキング', '比較',
    'セール', '割引', '安い', '激安', 'お買い得',
    'laptop', 'notebook', 'camera', 'headphone', 'earphone',
    'smartphone', 'tablet', 'monitor', 'display', 'gaming',
    # 'deal', 'sale' removed — meta-words, not product names
    # 追加: 多様な商品キーワード
    'MacBook', 'iMac', 'MacStudio', 'MacPro', 'AirPods', 'AppleWatch', 'Watch',
    'Sony', 'Panasonic', 'Sharp', '東芝', 'Hitachi', 'Canon', 'Nikon', 'Fujifilm',
    'Olympus', 'SIGMA', 'TAMRON', 'Bose', 'Sennheiser', 'AudioTechnica', 'JBL',
    'Polaroid', 'ポラロイド', 'インスタントカメラ', 'インスタント', 'フィルムカメラ',
    'Razer', 'Logitech', 'Corsair', 'SteelSeries',
    'Kindle', 'FireTV', 'Chromecast', 'RaspberryPi',
    'ドローン', 'DJI', 'Oculus', 'MetaQuest',
    '電動', '充電', 'バッテリー', 'ワイヤレス', 'Bluetooth',
    '新作', '発売', '予約', '限定', 'プレオーダー',
    'Claude', 'GPT', 'Gemini', 'AI',
    'iPad', 'iPod', 'AirTag', 'HomePod', 'AppleTV',
    '買取', '下取り', 'リセール', '中古', '整備品',
    '価格', '最安値', '価格比較', 'クチコミ',
    'ポラロイド', 'Polaroid', 'インスタント',
    'Roku', 'roku', 'FireTV', 'FireStick', 'Chromecast', 'AppleTV', 'Apple TV',
    'Spotify', 'YouTube', 'Netflix', 'DisneyPlus', 'Hulu',
    'Nintendo', 'PlayStation', 'Xbox', 'SteamDeck', 'Steam',
    'キーボード', 'マウス', 'トラックパッド',
    'プリンタ', 'スキャナ', 'プロジェクター',
    'ウェアラブル', 'フィットネス', '健康',
    'コスメ', '美容',
    '時計', 'メガネ',
    'dyson', 'bose', 'sony', 'canon', 'nikon',
    # 追加: mstdn.jpでトレンドになりやすいソフトウェア・サービス名
    'cursor', 'starbucks', 'deltachat', 'signal', 'telegram',
    'notion', 'slack', 'discord', 'github', 'gitlab',
    'vscode', 'vim', 'neovim', 'emacs',
    'docker', 'kubernetes', 'terraform',
    'vercel', 'netlify', 'railway',
    'openai', 'anthropic', 'mistral',
    'spotify', 'applemusic', 'youtube', 'netflix',
    'tesla', 'rivian',
    'ikea', 'muji', 'uniqlo',
    'hp', 'dell', 'lenovo', 'asus',
    'samsung', 'lg', 'xiaomi',
    'intel', 'amd', 'nvidia',
    'gopro', 'insta360', 'dji',
    'kindle', 'kobo',
    'anker', 'belkin', 'ugreen',
    'logitech', 'razer', 'corsair',
    # XR / スマートグラス
    'XR', 'XREAL', 'AURA', 'スマートグラス',
]


def fetch_url(url, timeout=15):
    """curl経由でURLを取得"""
    try:
        result = subprocess.run(
            ['curl', '-sk', '--connect-timeout', '10', '-m', str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
        return None
    except (subprocess.TimeoutExpired, Exception):
        return None


def fetch_rss(url):
    """RSS/Atomフィードを取得してエントリーリストを返す"""
    content = fetch_url(url, timeout=15)
    if not content:
        return []

    entries = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    # RSS 2.0
    for item in root.iter('item'):
        title = item.findtext('title', '')
        link = item.findtext('link', '')
        desc = item.findtext('description', '')
        if title:
            entries.append({'title': title.strip(), 'link': link.strip(), 'description': desc.strip() if desc else ''})

    # Atom
    if not entries:
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        for entry in root.findall('.//atom:entry', ns):
            title = entry.findtext('atom:title', '', ns)
            link_el = entry.find('atom:link', ns)
            link = link_el.get('href', '') if link_el is not None else ''
            summary = entry.findtext('atom:summary', '', ns)
            if title:
                entries.append({'title': title.strip(), 'link': link.strip(), 'description': summary.strip() if summary else ''})

    return entries


def extract_keywords(text):
    """テキストから商品関連キーワードを抽出"""
    found = []
    text_lower = text.lower()
    for kw in PRODUCT_KEYWORDS:
        if kw.lower() in text_lower:
            found.append(kw)
    return found


def scrape_hatena_tech():
    """はてなブックマック - テック系人気エントリー"""
    entries = fetch_rss('https://b.hatena.ne.jp/hotentry/it.rss')
    if not entries:
        return []

    results = []
    for entry in entries[:20]:
        title = entry['title']
        keywords = extract_keywords(title)
        if keywords:
            results.append({
                'source': 'hatena',
                'title': title,
                'url': entry.get('link', ''),
                'keywords': keywords,
                'score': len(keywords) * 10,  # キーワード数で簡易スコア
            })
    return results


def scrape_itmedia_news():
    """ITmedia NEWS RSS"""
    entries = fetch_rss('https://rss.itmedia.co.jp/rss/2.0/news_bursts.xml')
    if not entries:
        return []

    results = []
    for entry in entries[:20]:
        title = entry['title']
        keywords = extract_keywords(title)
        if keywords:
            results.append({
                'source': 'itmedia',
                'title': title,
                'url': entry.get('link', ''),
                'keywords': keywords,
                'score': len(keywords) * 10,
            })
    return results


def scrape_engadget_jp():
    """Engadget 日本版 RSS"""
    entries = fetch_rss('https://japanese.engadget.com/rss.xml')
    if not entries:
        return []

    results = []
    for entry in entries[:20]:
        title = entry['title']
        keywords = extract_keywords(title)
        if keywords:
            results.append({
                'source': 'engadget',
                'title': title,
                'url': entry.get('link', ''),
                'keywords': keywords,
                'score': len(keywords) * 10,
            })
    return results


def collect_multi_trends():
    """複数のソースからトレンドを収集"""
    collected = {
        'sources': {},
        'all_keywords': Counter(),
        'all_items': [],
        'errors': [],
        'collected_at': datetime.now(JST).isoformat(),
    }

    sources = [
        ('hatena', scrape_hatena_tech),
        ('itmedia', scrape_itmedia_news),
        ('engadget', scrape_engadget_jp),
    ]

    for name, fetcher in sources:
        try:
            items = fetcher()
            collected['sources'][name] = len(items)
            collected['all_items'].extend(items)
            for item in items:
                for kw in item['keywords']:
                    collected['all_keywords'][kw] += 1
            print(f"  ✅ {name}: {len(items)} items", file=sys.stderr)
        except Exception as e:
            collected['errors'].append(f"{name}: {e}")
            print(f"  ⚠️ {name}: {e}", file=sys.stderr)

    # キーワード頻度でトップトレンドを決定
    top_keywords = collected['all_keywords'].most_common(10)
    collected['top_keywords'] = [{'keyword': k, 'count': v} for k, v in top_keywords]

    return collected


def select_trend_topic(collected, used_cache=True, exclude_tags=None):
    """収集結果から記事化するトピックを選択

    Args:
        collected: マルチソース収集結果
        used_cache: キャッシュ使用フラグ（互換性維持）
        exclude_tags: 除外するタグ名のセット（既に投稿済みタグ）
    """
    if not collected['all_items']:
        return None

    exclude = exclude_tags or set()
    # exclude をセットに統一し、小文字化して正規化
    if isinstance(exclude, (list, tuple)):
        exclude = set(exclude)
    # 小文字化して正規化（大文字小文字の不一致による除外漏れを防ぐ）
    exclude = {t.strip().lower() for t in exclude}

    # 英日対応表: 正規化用（excludeに日本語タグが含まれる場合の照合用）
    _JA_EN_MAP = {
        'ポラロイド': 'polaroid', 'インスタントカメラ': 'instantcamera',
        'インスタント': 'instant', 'フィルムカメラ': 'filmcamera',
        'ノートパソコン': 'laptop', 'パソコン': 'pc',
        'スマートフォン': 'smartphone', 'スマホ': 'smartphone',
        'タブレット': 'tablet', 'ヘッドホン': 'headphone',
        'イヤホン': 'earphone', 'スピーカー': 'speaker',
        'モニター': 'monitor', 'ディスプレイ': 'display',
        'カメラ': 'camera', 'レンズ': 'lens',
        'ゲーム機': 'gaming', 'ゲーム': 'game',
        'ドローン': 'drone', '時計': 'watch',
        'テレビ': 'tv', 'プロジェクター': 'projector',
    }
    # excludeを拡張: 英日対応の逆マッピングも追加
    exclude_expanded = set(exclude)
    for ja, en in _JA_EN_MAP.items():
        if en in exclude:
            exclude_expanded.add(ja)
        if ja in exclude:
            exclude_expanded.add(en)

    # メタタグ（商品名でない汎用ワード）— 記事の品質が大幅に低下するため除外
    META_TAGS = {
        'レビュー', 'おすすめ', '比較', 'ランキング', 'review', 'best',
        'top', 'comparison', 'vs', '選び方', 'ガイド', 'guide', 'howto',
        'how-to', 'ニュース', 'news', '話題', 'トレンド', 'trend', 'sns',
        'で話題', '徹底', '徹底レビュー', 'インスタント',
        '価格', '最安値', '価格比較', 'クチコミ',
        # 範囲が広すぎて商品レビューにならないタグ
        'スポーツ', '子ども', 'キッズ', 'ニュース', '政治', '社会',
        'ライフスタイル', '生活', '仕事', 'ビジネス',
        # 企業名・サービス名（商品レビューにならない）
        'SpaceX', 'SBG', 'SoftBank', 'Google', 'Amazon', 'Meta',
        'Microsoft', 'Tesla', 'Toyota', 'NTT',
        # 抽象的なカテゴリ名
        'インフラ', 'Home', 'IoT', 'クラウド', 'ブロックチェーン',
        'スタートアップ', '投資', 'IPO', '決算', '業績',
        # その他
        'イベント', 'セミナー', 'カンファレンス', '展示会',
        '求人', '採用', '人事', '組織',
        # 外国地名・政治タグ
        'Algeria', 'Poland', 'Gaza', 'France', 'Germany', 'Brazil',
        'India', 'China', 'Korea', 'Russia', 'Mexico',
        # SNSプラットフォーム名
        'Twitter', 'X', 'Instagram', 'Facebook', 'YouTube', 'TikTok',
        'Netflix', 'Spotify', 'DisneyPlus', 'Hulu',
        # AI/テック企業・サービス名（商品レビューにならない）
        # Sony, Panasonic, Apple, Samsung, Nintendo は商品名として有効なので除外しない
        # ただし Google, openai, Gemini, Anthropic は企業/サービス名であり商品名でない
        'Google', 'Gemini', 'openai', 'OpenAI', 'Anthropic', 'Claude', 'AI',
        'GPT', 'ChatGPT', 'Scheduled', 'タスク',
        # 抽象的なIT用語（商品レビューにならない）
        'Patching', 'Service', 'Coding', 'コーディング', 'プログラミング',
        'セキュリティ', '脆弱性', 'アップデート', 'Update',
        # その他メタワード
        'AURA', 'gentechnik', 'Gentechnik',
        '発売', '予約', '新作',
        'エッセイ',
        'デスク', 'ベッド',
        # 抽象的な機能・アプリカテゴリ（商品レビューにならない）
        'マルチタスク', 'アプリ', 'ゲーミングモード',
        # その他の抽象タグ
        'オタク', 'デジタル',
        # ギリシャ文字（モデル名/バージョン名）
        'Zeta',
        # 金融カテゴリ（商品レビューにならない）
        'メガバンク',
        # 非商品トピック
        'ミュトス',
    }

    # キーワード頻度 + ソース数の多いものを優先
    keyword_scores = {}
    for item in collected['all_items']:
        for kw in item['keywords']:
            if kw.lower() in exclude_expanded or kw in META_TAGS:
                continue  # 既に投稿済みタグまたはメタタグはスキップ
            if kw not in keyword_scores:
                keyword_scores[kw] = {'score': 0, 'items': [], 'sources': set()}
            keyword_scores[kw]['score'] += item['score']
            keyword_scores[kw]['items'].append(item)
            keyword_scores[kw]['sources'].add(item['source'])

    # ソース数でボーナス（複数ソースで上がっているトピックは優先）
    ranked = []
    for kw, data in keyword_scores.items():
        multi_source_bonus = len(data['sources']) * 20
        total = data['score'] + multi_source_bonus
        ranked.append({
            'tag': kw,
            'score': total,
            'source_count': len(data['sources']),
            'items': data['items'][:3],
            'sources': list(data['sources']),
        })

    ranked.sort(key=lambda x: (x['score'], x['source_count'], len(x['tag'])), reverse=True)

    if ranked:
        return ranked[0]

    # フォールバック: 全キーワードが除外された場合、ニュースタイトルから
    # 固有名詞（大文字始まりの英単語やカタカナ語）を抽出して新トピックを探す
    import re
    fallback_candidates = {}
    for item in collected['all_items']:
        title = item.get('title', '')
        # カタカナ語（3文字以上）を抽出
        for word in re.findall(r'[\u30a0-\u30ff]{3,}', title):
            if word not in exclude_expanded and word not in META_TAGS:
                if word not in fallback_candidates:
                    fallback_candidates[word] = {'score': 0, 'items': [], 'sources': set()}
                fallback_candidates[word]['score'] += item['score']
                fallback_candidates[word]['items'].append(item)
                fallback_candidates[word]['sources'].add(item['source'])
        # 大文字始まりの英単語（2文字以上）を抽出
        for word in re.findall(r'[A-Z][a-zA-Z]{1,}', title):
            wl = word.lower()
            if wl not in exclude_expanded and word not in META_TAGS:
                if word not in fallback_candidates:
                    fallback_candidates[word] = {'score': 0, 'items': [], 'sources': set()}
                fallback_candidates[word]['score'] += item['score']
                fallback_candidates[word]['items'].append(item)
                fallback_candidates[word]['sources'].add(item['source'])

    if fallback_candidates:
        ranked2 = []
        for kw, data in fallback_candidates.items():
            multi_source_bonus = len(data['sources']) * 20
            total = data['score'] + multi_source_bonus
            ranked2.append({
                'tag': kw,
                'score': total,
                'source_count': len(data['sources']),
                'items': data['items'][:3],
                'sources': list(data['sources']),
            })
        ranked2.sort(key=lambda x: x['score'], reverse=True)
        return ranked2[0] if ranked2 else None

    return None


def get_multi_trends(use_cache=True):
    """マルチソーストレンドを取得（キャッシュ付き）"""
    # キャッシュ確認
    if use_cache and TREND_CACHE_FILE.exists():
        try:
            with open(TREND_CACHE_FILE) as f:
                cached = json.load(f)
            cached_at = datetime.fromisoformat(cached['collected_at'])
            age_min = (datetime.now(JST) - cached_at).total_seconds() / 60
            if age_min < 60:  # 1時間以内のキャッシュは有効
                print(f"  📦 マルチトレンドキャッシュ使用 ({age_min:.0f}min old)", file=sys.stderr)
                return cached
        except (json.JSONDecodeError, KeyError):
            pass

    # 新規取得
    collected = collect_multi_trends()

    # キャッシュ保存
    DATA_DIR.mkdir(exist_ok=True)
    with open(TREND_CACHE_FILE, 'w') as f:
        json.dump(collected, f, ensure_ascii=False, indent=2)

    return collected


if __name__ == '__main__':
    print("マルチソーストレンド収集テスト", file=sys.stderr)
    result = get_multi_trends(use_cache=False)
    print(f"\nソース別: {result['sources']}", file=sys.stderr)
    print(f"キーワード別: {result['top_keywords'][:10]}", file=sys.stderr)
    topic = select_trend_topic(result)
    if topic:
        print(f"\n選択トピック: {topic['tag']} (score: {topic['score']}, sources: {topic['sources']})", file=sys.stderr)
