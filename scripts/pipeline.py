#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統合パイプライン: トレンド収集 → 記事生成 → デプロイ → SNS投稿

毎時cronで実行されるメインパイプライン。
mstdn.jpトレンド + RSSキーワード → 記事生成 → Cloudflareデプロイ → Instagram投稿 + X用テンプレートTelegram通知

Usage:
    python3 pipeline.py                # 全処理実行
    python3 pipeline.py --dry-run      # デプロイ・投稿なし（テスト）
    python3 pipeline.py --skip-deploy  # デプロイスキップ
    python3 pipeline.py --skip-post    # SNS投稿スキップ
"""

import subprocess, json, re, sys, argparse, os, time, traceback, glob
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

# .env 読み込み（~/.hermes/.env から環境変数をロード）
def _load_env():
    env_path = Path.home() / '.hermes' / '.env'
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, val = line.partition('=')
                    key = key.strip()
                    val = val.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = val

_load_env()

JST = timezone(timedelta(hours=9))
PROJECT_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = Path(__file__).parent
ARTICLES_DIR = PROJECT_DIR / 'astro' / 'src' / 'content' / 'articles'

# Amazon Associates
AMAZON_TRACKING_ID = 'toknet-22'

# カテゴリマッピング
CATEGORY_MAP = {
    'laptop-pc': {'name': 'PC・ノート', 'keywords': ['ノートPC', 'ラップトップ', 'MacBook', 'ThinkPad', 'Surface', 'Chromebook', 'ゲーミングPC']},
    'camera': {'name': 'カメラ', 'keywords': ['カメラ', 'デジカメ', 'ミラーレス', '一眼レフ', 'GoPro', 'インカメ', 'レンズ', 'Polaroid', 'ポラロイド', 'インスタント', 'フィルム']},
    'audio-headphones': {'name': 'オーディオ', 'keywords': ['ヘッドホン', 'イヤホン', 'スピーカー', 'DAC', 'アンプ', 'ワイヤレス', 'ノイズキャンセリング']},
    'smart-home': {'name': 'スマートホーム', 'keywords': ['スマートホーム', 'IoT', 'スマートスピーカー', 'Alexa', 'Google Home', 'HomePod', 'センサー']},
    'appliance': {'name': '家電', 'keywords': ['家電', '洗濯機', '冷蔵庫', '掃除機', 'ルンバ', 'ダイソン', '炊飯器', '電子レンジ']},
    'monitor': {'name': 'モニター', 'keywords': ['モニター', 'ディスプレイ', '4K', 'ゲーミングモニター', 'ウルトラワイド', '曲面']},
    'diy-pc': {'name': '自作PC', 'keywords': ['自作PC', 'グラボ', 'GPU', 'CPU', 'マザーボード', 'メモリ', 'SSD', '電源']},
    'gaming': {'name': 'ゲーミング', 'keywords': ['ゲーミング', 'Switch', 'PS5', 'Xbox', 'Steam', 'ゲーム', 'Nintendo']},
}

# 商品本文のテンプレートバリエーション
ARTICLE_TEMPLATES = [
    # テンプレート1: 比較レビュー型
    """## はじめに

SNS上で急上昇している「{tag}」について、トレンド分析と商品レビューをまとめました。
直近7日間でSNS上での投稿数は{uses}件、{accts}人のユーザーが言及していました。

## トレンド分析

### 話題のキーワード

{keywords_section}

### SNSの反響

{sns_reaction}

## おすすめ商品

> ※Amazonアソシエイトリンクを含んでいます。

{products_section}

## 選び方のポイント

{selection_points}

## 参考リンク

{links_section}

## まとめ

本記事はAIと人間の共創により作成されました。トレンドデータに基づき、読者の皆様に役立つ情報をお届けします。
""",
    # テンプレート2: トレンド深掘り型
    """## はじめに

「{tag}」がSNSで話題に！直近7日間のトレンドデータを徹底分析しました。
スコア{score}ポイントを獲得し、>{users_threshold}件以上の投稿を集めています。

## トレンドの背景

{trend_background}

### 注目キーワード

{keywords_section}

## 市場動向とおすすめ

{products_section}

## 購入時の注意点

{selection_points}

## 参考情報

{links_section}

## まとめ

{summary}
""",
]


def now_jst_str():
    return datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')


def now_jst_short():
    return datetime.now(JST).strftime('%Y年%m月%d日')


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


def _normalize_tag(tag):
    """タグを正規化: 小文字化 + 英日統合"""
    t = tag.strip().lower()
    return _JA_EN_MAP.get(t, t)


def get_recently_used_tags(hours=24):
    """過去hours時間以内に投稿された記事のプライマリタグを収集（frontmatterのtagsの最初の1件のみ）

    ファイルの更新時刻（mtime）を使用し、ファイル名の日付に依存しない。
    これにより、同じタグの短時間での重複投稿を正確に防止する。
    日本語タグと英語タグの正規化も行う（例: ポラロイド → polaroid）。
    """
    # 正規化はモジュールレベルの _normalize_tag() を使用
    used_tags = set()
    cutoff = datetime.now(JST) - timedelta(hours=hours)

    for fpath in glob.glob(str(ARTICLES_DIR / '*.md')):
        try:
            # ファイルの更新時刻を使用（filenameの日付ではなく）
            mtime = os.path.getmtime(fpath)
            file_dt = datetime.fromtimestamp(mtime, tz=JST)
            if file_dt < cutoff:
                continue
        except (OSError, ValueError):
            continue

        # frontmatterからtagsを抽出 — プライマリタグ（最初の1件）のみ使用
        # 2番目以降のタグはニュースタイトル由来のノイズが多いため重複判定に使わない
        # draft: true の記事は公開されていないので重複チェックに含めない
        try:
            with open(fpath, encoding='utf-8') as f:
                content = f.read(2000)
            if re.search(r'^draft:\s*true', content, re.MULTILINE):
                continue
            m = re.search(r'tags:\s*\[([^\]]*)\]', content)
            if m:
                tags_raw = m.group(1)
                first_tag = re.search(r'["\']([^"\']+)["\']', tags_raw)
                if first_tag:
                    # 正規化して追加（英日統合）
                    used_tags.add(_normalize_tag(first_tag.group(1)))
        except Exception:
            pass

    return used_tags


# ===== Step 1: トレンド収集 =====

def collect_trends(use_realtime=False):
    """トレンド収集: mstdn.jp + マルチソース(RSS) 併用
    
    Args:
        use_realtime: Trueならキャッシュを使わずリアルタイム取得
    """
    print("\n" + "=" * 50)
    print("📊 Step 1: トレンド収集（マルチソース）")
    print("=" * 50)

    sys.path.insert(0, str(SCRIPTS_DIR))
    from trend_collector import get_trending_tags, get_tag_posts, analyze_posts, is_product_related

    analyzed = []
    errors = []
    all_tags = []
    used_cache = False

    # --- ソース1: mstdn.jp トレンドタグ ---
    print("  📡 ソース1: mstdn.jp トレンドタグ")
    try:
        # use_realtime=True ならキャッシュを無視してAPI再取得
        if use_realtime:
            from trend_collector import CACHE_FILE
            import os
            if CACHE_FILE.exists():
                os.remove(CACHE_FILE)
                print("    🗑️ キャッシュクリア（リアルタイム取得）")
        tags = get_trending_tags(limit=30)
        all_tags = tags
        product_tags = [t for t in tags if is_product_related('#' + t['name'])][:10]
        print(f"    → 商品系タグ: {len(product_tags)}/{len(tags)}")

        for t in product_tags[:5]:
            try:
                posts = get_tag_posts(t['name'], limit=10)
                analysis = analyze_posts(posts)
                analyzed.append({
                    'tag': t['name'],
                    'score': t['score'],
                    'total_uses_7d': t['total_uses_7d'],
                    'total_accts_7d': t['total_accts_7d'],
                    'analysis': analysis,
                    'source': 'mastodon',
                })
                print(f"    ✅ #{t['name']} — score:{t['score']}")
                if len(analyzed) >= 3:
                    break
            except Exception as e:
                print(f"    ⚠️ #{t['name']} — 分析エラー: {e}")

        if not product_tags:
            errors.append("mstdn.jp: 商品系タグ0件")
    except Exception as e:
        errors.append(f"mstdn.jp取得失敗: {e}")
        print(f"    ⚠️ mstdn.jp失敗: {e}")

    # --- ソース2: マルチソースRSS（はてな・ITmedia・Engadget） ---
    if len(analyzed) < 5:
        remaining = 5 - len(analyzed)
        print(f"  📡 ソース2: マルチソースRSS（あと{remaining}件）")
        try:
            from multi_trend_collector import get_multi_trends, select_trend_topic
            multi = get_multi_trends(use_cache=not use_realtime)
            # 最近使われたタグを除外して選択する（run_pipeline側の重複チェックを補完）
            _exclude = get_recently_used_tags(hours=24) if not use_realtime else set()

            # 複数のトピックを候補として追加（remaining件分）
            for _i in range(remaining):
                topic = select_trend_topic(multi, used_cache=True, exclude_tags=_exclude)
                if not topic:
                    break

                tag_name = topic['tag']
                source_labels = {
                    'hatena': 'はてなブックマーク',
                    'itmedia': 'ITmedia',
                    'engadget': 'Engadget',
                }
                source_str = '/'.join(source_labels.get(s, s) for s in topic.get('sources', []))
                news_items = topic.get('items', [])
                news_urls = [item.get('url', '') for item in news_items[:3] if item.get('url')]
                news_titles = [item.get('title', '') for item in news_items[:3] if item.get('title')]

                # ニュースタイトルからキーワード抽出
                combined_text = ' '.join(news_titles) + ' ' + tag_name
                from trend_collector import analyze_posts, strip_html
                word_counter = Counter()
                words = re.findall(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]+|[a-zA-Z]{3,}', combined_text)
                for w in words:
                    if len(w) >= 2:
                        word_counter[w] += 1
                top_words = list(word_counter.items())[:10]

                analyzed.append({
                    'tag': tag_name,
                    'score': topic['score'],
                    'total_uses_7d': 0,
                    'total_accts_7d': 0,
                    'analysis': {
                        'post_count': len(news_items),
                        'avg_engagement': 0,
                        'top_words': top_words,
                        'urls': news_urls,
                        'sample_texts': news_titles,
                    },
                    'source': f"rss({source_str})",
                })
                print(f"    ✅ [RSS] #{tag_name} — score:{topic['score']} (sources: {source_str})")
                # 次の選択からこのタグを除外
                _exclude.add(tag_name)

            if not any(a.get('source', '').startswith('rss') for a in analyzed):
                errors.append("マルチソース: 商品系トピック0件")
                print("    ⚠️ マルチソース: 該当トピックなし")
        except Exception as e:
            errors.append(f"マルチソース: {e}")
            print(f"    ⚠️ マルチソースエラー: {e}")

    # --- ソース3: RSSキーワード監視（フォールバック） ---
    if len(analyzed) < 1:
        print("  📡 ソース3: RSSキーワード監視（最終フォールバック）")
        data_dir = SCRIPTS_DIR / 'data'
        history_file = data_dir / 'keyword_history.json'
        if history_file.exists():
            with open(history_file) as f:
                history = json.load(f)
            snapshots = history.get('snapshots', [])
            if snapshots:
                latest = snapshots[-1]
                kw_counts = latest.get('keyword_counts', {})
                keyword_hits = {k: v for k, v in kw_counts.items() if v > 0}
                if keyword_hits:
                    top_kw = max(keyword_hits, key=keyword_hits.get)
                    analyzed.append({
                        'tag': top_kw,
                        'score': keyword_hits[top_kw],
                        'total_uses_7d': 0,
                        'total_accts_7d': 0,
                        'analysis': {
                            'post_count': 0, 'avg_engagement': 0,
                            'top_words': [(top_kw, keyword_hits[top_kw])],
                            'urls': [], 'sample_texts': [],
                        },
                        'source': 'keyword_monitor',
                    })
                    print(f"    ✅ [KW] #{top_kw}")

    if not analyzed:
        print("  ❌ 全ソースからトレンド取得不可。パイプライン終了。")
        return {'trend_tags': [], 'keyword_hits': {}, 'all_tags': [], 'errors': errors}

    return {
        'trend_tags': analyzed,
        'keyword_hits': {},
        'all_tags': all_tags,
        'errors': errors,
    }


# ===== Step 2: 記事生成 =====

def detect_category(text):
    text_lower = text.lower()
    best_cat = 'laptop-pc'
    best_score = 0
    for cat_id, info in CATEGORY_MAP.items():
        score = sum(1 for kw in info['keywords'] if kw.lower() in text_lower)
        if score > best_score:
            best_score = score
            best_cat = cat_id
    # キーワードが全くマッチしない場合は 'laptop-pc' ではなく最も汎用的なカテゴリを返す
    # ただし、明らかに無関係なタグ（スポーツ、子ども等）には category を空に近い値を設定
    if best_score == 0:
        # 無関係タグ検出: 商品レビューとして不適切なトピック
        _IRRELEVANT = {'スポーツ', '子ども', '価格', 'ニュース', '政治', '社会'}
        if text_lower.strip() in _IRRELEVANT or any(t in text_lower for t in _IRRELEVANT):
            return 'gaming'  # 最も汎用的なカテゴリ（フォールバック）
    return best_cat if best_score > 0 else 'laptop-pc'


def generate_slug(title):
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    now = datetime.now(JST)
    return f"{now.strftime('%Y%m%d')}-{slug[:50]}"


def build_product_section(keywords, tag):
    """商品セクションを生成"""
    if not keywords:
        return "| 商品名 | 評価 | 価格 |\n|--------|------|------|\n| 調査中 | ⭐⭐⭐⭐ | 要確認 |"

    lines = []
    for kw in keywords[:3]:
        amazon_url = f'https://www.amazon.co.jp/s?k={kw}&tag={AMAZON_TRACKING_ID}'
        lines.append(f"- **{kw}** — [Amazonで価格を見る]({amazon_url})")

    return '\n'.join(lines)


def build_selection_points(keywords, tag):
    """選び方のポイントを生成"""
    points = []

    # カテゴリ特有の選び方
    if any(kw in tag for kw in ['PC', 'pc', 'ノート', 'ラップトップ']):
        points = [
            "用途（ビジネス/ゲーム/クリエイティブ）を明確にする",
            "予算に応じてCPU・メモリ・ストレージを選ぶ",
            "Amazonの価格変動をチェックして最良のタイミングで購入する",
        ]
    elif any(kw in tag for kw in ['カメラ', 'レンズ']):
        points = [
            "撮影シーン（風景/ポートレート/動画）に適した機種を選ぶ",
            "レンズ交換の必要性を確認する",
            "中古・整備品も検討するとコスパが良い",
        ]
    elif any(kw in tag for kw in ['ヘッドホン', 'イヤホン']):
        points = [
            "有線/ワイヤレス/ANCの必要性を整理する",
            "実際のイ装着心地をレビューで確認する",
            "Amazonのセール時期を狙うとお得",
        ]
    else:
        points = [
            "自分のニーズに合ったスペック・機能を確認する",
            "Amazon価格変動をチェックして最良のタイミングで購入する",
            "レビュー・比較記事を参考にする",
        ]

    return '\n'.join(f'- {p}' for p in points)


def filter_product_keywords(keywords, tag):
    """キーワードリストから商品・製品関連のみをフィルタリング

    ニュースタイトルから抽出された長いフレーズ（6文字以上の日本語や
    助詞で始まるフレーズ）を除外し、実際の商品名・技術用語のみを残す。
    純日本語フレーズはPRODUCT_KW_SETに含まれる場合のみ採用する。
    """
    # 既知の商品キーワード（部分一致）
    PRODUCT_KW_SET = {
        'ノートPC', 'パソコン', 'PC', 'カメラ', 'レンズ', 'ヘッドホン', 'イヤホン',
        'スマホ', 'iPhone', 'Android', 'タブレット', 'iPad', 'Apple',
        'Nintendo', 'Switch', 'PS5', 'PlayStation', 'Xbox', 'ゲーム',
        '家電', '洗濯機', '冷蔵庫', '掃除機', 'ダイソン', '炊飯器',
        'モニター', 'ディスプレイ', '4K', 'SSD', 'メモリ', 'グラボ',
        'レビュー', 'おすすめ', 'ランキング', '比較',
        'セール', '割引', '安い', '激安', 'お買い得',
        'MacBook', 'iMac', 'MacStudio', 'MacPro',
        'AirPods', 'AppleWatch', 'Watch',
        'Sony', 'Panasonic', 'Sharp', 'Canon', 'Nikon', 'Fujifilm',
        'Bose', 'Sennheiser', 'AudioTechnica', 'JBL',
        'Razer', 'Logitech', 'Corsair',
        'Kindle', 'FireTV', 'Chromecast', 'RaspberryPi',
        'ドローン', 'DJI', 'Oculus', 'MetaQuest',
        '電動', '充電', 'バッテリー', 'ワイヤレス', 'Bluetooth',
        '新作', '発売', '予約', '限定', 'プレオーダー',
        'インスタントカメラ', 'ポラロイド',
        'laptop', 'notebook', 'camera', 'headphone', 'earphone',
        'smartphone', 'tablet', 'monitor', 'display', 'gaming',
        'review', 'best', 'top', 'tech', 'gadget',  # 'deal','sale' removed: meta-words not product names
        'apple', 'samsung', 'sony', 'nintendo', 'playstation',
        'new', 'release', 'launch', 'unboxing',
        '任天堂', '東芝', 'Hitachi', 'Olympus', 'SIGMA', 'TAMRON',
        'SteelSeries', '買取', '買い替え', 'iPhone16', 'Galaxy',
    }
    # 助詞・助動詞で始まるフレーズはノイズ
    NOISE_PREFIXES = {'は', 'が', 'を', 'に', 'で', 'と', 'の', 'も', 'や', 'から',
                       'まで', 'より', 'など', 'って', 'という', 'というのは'}
    # URLパラメータ・HTMLフラグメントなどのノイズ語
    NOISE_WORDS = {'utm', 'amp', 'ref', 'src', 'cid', 'gclid', 'fbclid', 'mc_cid',
                   'mc_eid', 'yclid', 'msclkid', 'dclid', 'zanpid', 'igshid',
                   'feature', 'share', 'via', 'from', 'html', 'http', 'https',
                   'com', 'org', 'net', 'www', 'co', 'jp', 'io', 'app',
                   'index', 'page', 'article', 'post', 'story', 'news',
                   'the', 'and', 'for', 'this', 'that', 'with', 'from', 'have',
                   'been', 'were', 'are', 'was', 'will', 'would', 'could', 'should',
                   'not', 'but', 'all', 'can', 'had', 'her', 'his', 'how', 'its',
                   'may', 'new', 'now', 'old', 'see', 'way', 'who', 'did', 'get',
                   'let', 'say', 'she', 'too', 'use', 'one', 'our', 'out', 'has',
                   'each', 'make', 'like', 'long', 'look', 'many', 'some', 'them',
                   'then', 'than', 'only', 'come', 'over', 'such', 'also', 'back',
                   'well', 'most', 'into', 'very', 'just', 'more', 'here', 'what',
                   'when', 'your', 'about', 'which', 'their', 'there', 'these',
                   'those', 'where', 'while', 'after', 'before', 'under', 'again',
                   'further', 'once', 'sns', 'twitter', 'instagram', 'facebook',
                   'youtube', 'tiktok', 'line', 'xcom', 'com', 'de', 'en', 'fr',
                   'review', 'レビュー',  # メタ語（商品名でない）
                   'html', 'css', 'jpg', 'png', 'gif', 'pdf', 'zip', 'mp3', 'mp4',
                   'www', 'http', 'https', 'ftp', 'url', 'uri', 'api', 'sdk',
                   'gen',  # "Gen" as in "5th Gen" — too generic as product name
                   }
    filtered = []
    tag_added = False
    for w in keywords:
        # タグ自体は常に含め、先頭に配置
        if w == tag:
            if not tag_added:
                filtered.insert(0, w)
                tag_added = True
            continue
        # 6文字以上の日本語フレーズはニュース文の断片なので除外
        # （PRODUCT_KW_SETに明示的に含まれる場合のみ例外）
        if re.match(r'^[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]+$', w) and len(w) >= 6:
            if w not in PRODUCT_KW_SET:
                continue
        # 助詞で始まるフレーズはノイズ
        if any(w.startswith(p) for p in NOISE_PREFIXES):
            continue
        # ノイズワード（URLパラメータ等）は除外
        if w.lower() in NOISE_WORDS:
            continue
        # 既知の商品キーワードに部分一致するもののみ採用
        w_lower = w.lower()
        is_known = any(kw.lower() in w_lower or w_lower in kw.lower() for kw in PRODUCT_KW_SET)
        if is_known:
            filtered.append(w)
    # タグがraw_keywordsに含まれていない場合でも先頭に追加
    if not tag_added:
        filtered.insert(0, tag)
    return filtered if filtered else [tag]


def generate_article(trend_data, template_idx=0, dry_run=False):
    """トレンドデータからAstro記事を生成

    dry_run=True の場合、ファイル書き込みを行わない（重複チェック回避）。
    """
    tag = trend_data['tag']
    analysis = trend_data.get('analysis', {})
    raw_keywords = [w for w, c in analysis.get('top_words', [])[:10]]
    keywords = filter_product_keywords(raw_keywords, tag)
    urls = analysis.get('urls', [])
    score = trend_data.get('score', 0)
    uses = trend_data.get('total_uses_7d', 0)
    accts = trend_data.get('total_accts_7d', 0)
    post_count = analysis.get('post_count', 0)
    source = trend_data.get('source', 'unknown')

    all_text = ' '.join(keywords) + ' ' + tag
    category = detect_category(all_text)

    top_kw = keywords[0] if keywords else tag

    # ソース別のタイトル調整
    if source.startswith('rss'):
        title_prefix = "【ニュース】"
    elif source == 'keyword_monitor':
        title_prefix = "【注目キーワード】"
    else:
        title_prefix = "【SNSトレンド】"
    title = f"{title_prefix}【{now_jst_short()}】SNSで話題の「{top_kw}」徹底レビュー｜AI共創レビュー研究所"
    description = f"SNSトレンド「#{tag}」について徹底分析。{top_kw}関連の最新動向とおすすめ商品を紹介します。"
    slug = generate_slug(title)

    # キーワードセクション
    keywords_section = '\n'.join(f'- **{kw}**' for kw in keywords[:8]) if keywords else '- 分析中'

    # SNSの反響 / ニュースソース
    if source == 'mastodon' and post_count > 0:
        avg_eng = analysis.get('avg_engagement', 0)
        sns_reaction = f"SNS上では{post_count}件の投稿が分析され、平均エンゲージメントは{avg_eng:.1f}でした。"
        if analysis.get('sample_texts'):
            sample = analysis['sample_texts'][0][:100]
            sns_reaction += f'\n\n> ユーザー投稿例: 「{sample}...」'
    elif source.startswith('rss'):
        source_name = source.replace('rss(', '').replace(')', '')
        news_count = analysis.get('post_count', 0)
        sns_reaction = f"{source_name}のニュース記事{news_count}件から抽出されたトレンドキーワードです。"
        if analysis.get('sample_texts'):
            sample = analysis['sample_texts'][0][:100]
            sns_reaction += f'\n\n> 関連記事: 「{sample}...」'
    else:
        sns_reaction = "キャッシュモードのため、投稿分析はスキップされました。次回実行時に最新データを取得します。"

    # トレンドの背景
    if source == 'mastodon':
        trend_background = f"「{tag}」は直近7日間でSNS上に{uses}件の投稿、{accts}人のユーザーが言及。スコア{score}と話題性が高くなっています。"
    elif source.startswith('rss'):
        source_name = source.replace('rss(', '').replace(')', '')
        trend_background = f"「{tag}」は{source_name}のニュースで複数取り上げられています。スコア{score}。"
    else:
        trend_background = f"「{tag}」はキーワード監視で検出されました。スコア{score}。"

    # 商品データ
    products = []
    for kw in keywords[:3]:
        products.append({
            'name': kw,
            'amazonUrl': f'https://www.amazon.co.jp/s?k={kw}&tag={AMAZON_TRACKING_ID}',
            'rating': None,
        })

    products_section = build_product_section(keywords, tag)

    # 選び方
    selection_points = build_selection_points(keywords, tag)

    # リンクセクション
    links_section = '\n'.join(f'- [{url[:60]}]({url})' for url in urls[:5]) if urls else '- 分析中'

    # まとめ
    summary = f"「{tag}」は{top_kw}関連の商品が特に注目されています。本記事はAIと人間の共創により、トレンドデータに基づいた客観的な情報をお届けします。"

    # テンプレート選択
    tpl = ARTICLE_TEMPLATES[template_idx % len(ARTICLE_TEMPLATES)]

    # 本文生成
    body = tpl.format(
        tag=tag,
        score=score,
        uses=uses,
        accts=accts,
        users_threshold=100,
        top_kw=top_kw,
        keywords_section=keywords_section,
        sns_reaction=sns_reaction,
        trend_background=trend_background,
        products_section=products_section,
        selection_points=selection_points,
        links_section=links_section,
        summary=summary,
    )

    # Frontmatter — tagsとproductsはフィルタリング済みキーワードのみ使用
    # 重複排除: tagとkeywords[:3]の重複を除去し、先頭にタグを配置
    now = datetime.now(JST).strftime('%Y-%m-%dT%H:%M:%S+09:00')
    unique_tags = [tag]
    for kw in keywords[:3]:
        if kw not in unique_tags:
            unique_tags.append(kw)
    tags_json = json.dumps(unique_tags, ensure_ascii=False)
    # productsもフィルタリング済みキーワードから生成
    products = []
    for kw in keywords[:3]:
        products.append({
            'name': kw,
            'amazonUrl': f'https://www.amazon.co.jp/s?k={kw}&tag={AMAZON_TRACKING_ID}',
            'rating': None,
        })
    products_json = json.dumps(products, ensure_ascii=False)

    frontmatter = f"""---
title: "{title}"
description: "{description}"
pubDate: {now}
category: "{category}"
tags: {tags_json}
articleType: "review"
aiAssisted: true
draft: false
products: {products_json}
---

"""

    content = frontmatter + body
    article_path = ARTICLES_DIR / f'{slug}.md'

    if dry_run:
        print(f"  [DRY RUN] 記事ファイル書き込みスキップ: {article_path.name}")
    else:
        article_path.write_text(content, encoding='utf-8')

    print(f"  📝 記事生成: {article_path.name} (source: {source})")
    return slug, title, description, category, products


# ===== Step 3: デプロイ =====

def deploy_to_cloudflare(dry_run=False):
    """Cloudflare Pagesにデプロイ"""
    print("\n" + "=" * 50)
    print("🚀 Step 3: Cloudflare Pagesデプロイ")
    print("=" * 50)

    if dry_run:
        print("  [DRY RUN] デプロイスキップ")
        return True

    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / 'deploy.py')],
            capture_output=True, text=True, timeout=120
        )

        if result.returncode == 0:
            print("  ✅ デプロイ成功")
            return True
        else:
            print(f"  ❌ デプロイ失敗 (exit code: {result.returncode})")
            if result.stderr:
                print(f"  stderr: {result.stderr[:300]}")
            return False
    except subprocess.TimeoutExpired:
        print("  ❌ デプロイタイムアウト (120s)")
        return False
    except Exception as e:
        print(f"  ❌ デプロイ例外: {e}")
        return False


# ===== Step 4: SNS投稿 =====

def post_to_instagram(title, slug, description, products, dry_run=False):
    """Instagram投稿"""
    print("\n" + "=" * 50)
    print("📸 Step 4a: Instagram投稿")
    print("=" * 50)

    url = f"https://www.toknet.info/articles/{slug}/"
    amazon_url = products[0]['amazonUrl'] if products else None

    sys.path.insert(0, str(SCRIPTS_DIR))
    from instagram_poster import format_article_post

    caption = format_article_post(
        title=title,
        description=description,
        url=url,
        amazon_url=amazon_url,
    )

    if dry_run:
        print(f"  [DRY RUN] 投稿スキップ")
        print(f"  キャプション: {caption[:100]}...")
        return True

    image_url = "https://www.toknet.info/og-default.png"

    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / 'instagram_poster.py'),
             '--image-url', image_url,
             '--article-title', title,
             '--url', url,
             '--amazon-url', amazon_url or ''],
            capture_output=True, text=True, timeout=120
        )

        print(result.stdout)
        if result.returncode != 0:
            print(f"  ❌ 投稿失敗: {result.stderr[:200]}")
            return False

        # Extract permalink from output — check permalink first, media_id as fallback
        ig_url = None
        mid = None
        for line in result.stdout.split('\n'):
            if 'Permalink:' in line:
                ig_url = line.split('Permalink:')[1].strip()
                break
            elif 'media_id:' in line and not mid:
                mid = line.split('media_id:')[1].strip()
        
        if ig_url:
            print(f"  ✅ Instagram投稿成功: {ig_url}")
        elif mid:
            print(f"  ℹ️ media_id={mid} (permalink not available)")
            print("  ✅ Instagram投稿成功 (permalink未取得)")
        else:
            print("  ✅ Instagram投稿成功 (permalink未取得)")
        return True
    except subprocess.TimeoutExpired:
        print("  ❌ Instagram投稿タイムアウト")
        return False
    except Exception as e:
        print(f"  ❌ Instagram投稿例外: {e}")
        return False


def post_to_mastodon(title, slug, description, dry_run=False):
    """Mastodon投稿"""
    print("\n" + "=" * 50)
    print("🐘 Step 4b: Mastodon投稿")
    print("=" * 50)

    url = f"https://www.toknet.info/articles/{slug}/"

    sys.path.insert(0, str(SCRIPTS_DIR))
    from mastodon_poster import format_article_post

    text = format_article_post(
        title=title,
        description=description,
        url=url,
    )

    if dry_run:
        print(f"  [DRY RUN] 投稿スキップ")
        print(f"  テキスト: {text[:100]}...")
        return True

    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / 'mastodon_poster.py'),
             '--url', url,
             '--article-title', title],
            capture_output=True, text=True, timeout=30
        )

        print(result.stdout)
        if result.returncode != 0:
            print(f"  ❌ Mastodon投稿失敗: {result.stderr[:200]}")
            return False

        print("  ✅ Mastodon投稿成功")
        return True
    except subprocess.TimeoutExpired:
        print("  ❌ Mastodon投稿タイムアウト")
        return False
    except Exception as e:
        print(f"  ❌ Mastodon投稿例外: {e}")
        return False


def send_telegram_notification(title, slug, description, products, trend_source, dry_run=False):
    """X(Twitter)用テンプレートをTelegramに送信"""
    print("\n" + "=" * 50)
    print("📱 Step 4c: X用テンプレート → Telegram通知")
    print("=" * 50)

    url = f"https://www.toknet.info/articles/{slug}/"
    amazon_url = products[0]['amazonUrl'] if products else None

    lines = []
    lines.append(f"📢 {title}")
    lines.append("")
    lines.append(f"🔗 {url}")
    if amazon_url:
        lines.append(f"🛒 {amazon_url}")
    lines.append("")
    lines.append(f"📊 トレンド根拠: #{trend_source}")
    lines.append("")
    lines.append("#AI共創レビュー研究所 #AI #レビュー #テック #ガジェット")
    lines.append("")
    lines.append("※Amazonアソシエイトリンクを含みます")

    message = '\n'.join(lines)

    if dry_run:
        print(f"  [DRY RUN] Telegram通知スキップ")
        print(f"  ---")
        print(f"  {message}")
        print(f"  ---")
        return True

    # Telegram通知はHermes経由（send_message）ではなく、ファイル出力
    # cronのstdoutがTelegramに届く設計
    print(message)
    return True


# ===== Main Pipeline =====


def run_pipeline(dry_run=False, skip_deploy=False, skip_post=False):
    """統合パイプライン実行"""
    print("🚀 AI共創レビュー研究所 統合パイプライン")
    print(f"🕐 {now_jst_str()}")
    print(f"    Mode: {'DRY RUN' if dry_run else 'LIVE'}")

    pipeline_errors = []

    # Step 1: トレンド収集（リアルタイム取得）
    try:
        trend_data = collect_trends(use_realtime=True)
    except Exception as e:
        print(f"\n❌ Step 1 致命的エラー: {e}")
        traceback.print_exc()
        return False

    if not trend_data['trend_tags']:
        print("\n⚠️ 商品系トレンドタグが見つかりませんでした。パイプライン終了。")
        return False

    # 重複チェック: 過去24時間のタグを除外
    used_tags = get_recently_used_tags(hours=24)
    candidates = [t for t in trend_data['trend_tags']
                  if _normalize_tag(t['tag']) not in used_tags]

    if not candidates:
        print(f"\n⚠️ 全候補タグが24時間以内に使用済みです。パイプライン終了。")
        print(f"   使用済みタグ: {used_tags}")
        return False

    # 最良のタグを選択（スコア最高、重複除外済み）
    best = candidates[0]
    print(f"\n🎯 選択タグ: #{best['tag']} (score: {best['score']}, source: {best.get('source', 'unknown')})")

    # Step 2: 記事生成
    print("\n" + "=" * 50)
    print("📝 Step 2: 記事生成")
    print("=" * 50)

    try:
        slug, title, description, category, products = generate_article(best, dry_run=dry_run)
    except Exception as e:
        print(f"\n❌ Step 2 致命的エラー: {e}")
        traceback.print_exc()
        return False

    # Step 3: デプロイ
    deployed = deploy_to_cloudflare(dry_run=dry_run or skip_deploy)
    if not deployed and not (dry_run or skip_deploy):
        pipeline_errors.append("デプロイ失敗")

    # Step 4: SNS投稿
    mastodon_token = os.environ.get('MSTODON_ACCESS_TOKEN', '')
    if not mastodon_token:
        print("\n⚠️ MSTODON_ACCESS_TOKEN 未設定 → Mastodon投稿をスキップします")
        print("   → 設定方法: ~/.hermes/.env に MSTODON_ACCESS_TOKEN=... を追加")

    if not skip_post and deployed:
        # Instagram投稿
        try:
            ig_ok = post_to_instagram(title, slug, description, products, dry_run=dry_run)
            if not ig_ok:
                pipeline_errors.append("Instagram投稿失敗")
        except Exception as e:
            print(f"  ❌ Instagram投稿例外: {e}")
            pipeline_errors.append(f"Instagram投稿例外: {e}")

        # Mastodon投稿
        if mastodon_token:
            try:
                mast_ok = post_to_mastodon(title, slug, description, dry_run=dry_run)
                if not mast_ok:
                    pipeline_errors.append("Mastodon投稿失敗")
            except Exception as e:
                print(f"  ❌ Mastodon投稿例外: {e}")
                pipeline_errors.append(f"Mastodon投稿例外: {e}")
        else:
            print("  ℹ️ Mastodon投稿スキップ（トークン未設定）")

        # X用テンプレート通知
        try:
            send_telegram_notification(title, slug, description, products, best['tag'], dry_run=dry_run)
        except Exception as e:
            print(f"  ❌ Telegram通知例外: {e}")
            pipeline_errors.append(f"Telegram通知例外: {e}")

    # サマリー
    print("\n" + "=" * 50)
    print("📊 パイプライン完了")
    print("=" * 50)
    print(f"  タイトル: {title}")
    print(f"  URL: https://www.toknet.info/articles/{slug}/")
    print(f"  カテゴリ: {category}")
    print(f"  トレンド根拠: #{best['tag']} (score: {best['score']}, source: {best.get('source', 'unknown')})")

    if pipeline_errors:
        print(f"\n  ⚠️ エラー ({len(pipeline_errors)}件):")
        for err in pipeline_errors:
            print(f"    - {err}")
    else:
        print(f"\n  ✅ 全ステップ正常完了")

    for err in trend_data.get('errors', []):
        print(f"  ⚠️ {err}")

    return True


def main():
    parser = argparse.ArgumentParser(description='統合パイプライン')
    parser.add_argument('--dry-run', action='store_true', help='デプロイ・投稿なし')
    parser.add_argument('--skip-deploy', action='store_true', help='デプロイスキップ')
    parser.add_argument('--skip-post', action='store_true', help='SNS投稿スキップ')
    args = parser.parse_args()

    success = run_pipeline(
        dry_run=args.dry_run,
        skip_deploy=args.skip_deploy,
        skip_post=args.skip_post,
    )

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
