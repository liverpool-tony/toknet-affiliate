#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM記事生成 & SNS投稿パイプライン
トレンドデータ → Astro記事生成 → Cloudflareデプロイ → SNS投稿

Usage:
    python3 article_generator.py --trend-data trend_output.json
    python3 article_generator.py --dry-run  # トレンド取得→生成→デプロイなし
    python3 sns_poster.py --article articles/slug.md --dry-run
"""

import subprocess, json, re, sys, argparse, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent
ARTICLES_DIR = PROJECT_DIR / 'astro' / 'src' / 'content' / 'articles'
JST = timezone(timedelta(hours=9))

# Amazon Associates
AMAZON_TRACKING_ID = 'toknet-22'
AMAZON_BASE = f'https://www.amazon.co.jp/dp/{{asin}}?tag={AMAZON_TRACKING_ID}'

# カテゴリマッピング
CATEGORY_MAP = {
    'laptop-pc': {'name': 'PC・ノート', 'keywords': ['ノートPC', 'ラップトップ', 'MacBook', 'ThinkPad', 'Surface', 'Chromebook', 'ゲーミングPC']},
    'camera': {'name': 'カメラ', 'keywords': ['カメラ', 'デジカメ', 'ミラーレス', '一眼レフ', 'GoPro', 'インカメ', 'レンズ']},
    'audio-headphones': {'name': 'オーディオ', 'keywords': ['ヘッドホン', 'イヤホン', 'スピーカー', 'DAC', 'アンプ', 'ワイヤレス', 'ノイズキャンセリング']},
    'smart-home': {'name': 'スマートホーム', 'keywords': ['スマートホーム', 'IoT', 'スマートスピーカー', 'Alexa', 'Google Home', 'HomePod', 'センサー']},
    'appliance': {'name': '家電', 'keywords': ['家電', '洗濯機', '冷蔵庫', '掃除機', 'ルンバ', 'ダイソン', '炊飯器', '電子レンジ']},
    'monitor': {'name': 'モニター', 'keywords': ['モニター', 'ディスプレイ', '4K', 'ゲーミングモニター', 'ウルトラワイド', '曲面']},
    'diy-pc': {'name': '自作PC', 'keywords': ['自作PC', 'グラボ', 'GPU', 'CPU', 'マザーボード', 'メモリ', 'SSD', '電源']},
}

def detect_category(text):
    """テキストからカテゴリを判定"""
    text_lower = text.lower()
    best_cat = 'laptop-pc'
    best_score = 0
    for cat_id, info in CATEGORY_MAP.items():
        score = sum(1 for kw in info['keywords'] if kw.lower() in text_lower)
        if score > best_score:
            best_score = score
            best_cat = cat_id
    return best_cat if best_score > 0 else 'laptop-pc'

def generate_slug(title):
    """タイトルからスラグを生成"""
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    # 日付プレフィックス
    now = datetime.now(JST)
    return f"{now.strftime('%Y%m%d')}-{slug[:50]}"

def generate_article_frontmatter(title, description, category, tags, products, article_type='review'):
    """Astro記事のfrontmatterを生成"""
    now = datetime.now(JST).strftime('%Y-%m-%dT%H:%M:%S+09:00')
    
    frontmatter = f"""---
title: "{title}"
description: "{description}"
pubDate: {now}
category: "{category}"
tags: {json.dumps(tags, ensure_ascii=False)}
articleType: "{article_type}"
aiAssisted: true
draft: false
products: {json.dumps(products, ensure_ascii=False)}
---

"""
    return frontmatter

def generate_article_body(title, trend_info, keywords, urls):
    """記事本文を生成（テンプレートベース）"""
    now = datetime.now(JST).strftime('%Y年%m月%d日')
    
    # キーワードを箇条書きに
    kw_list = '\n'.join(f'- **{kw}**' for kw in keywords[:8])
    
    # URLリスト
    url_list = '\n'.join(f'- [{url[:60]}]({url})' for url in urls[:5])
    
    body = f"""# {title}

> 最終更新: {now} | AI共創レビュー研究所

## はじめに

{trend_info.get('summary', 'トレンド分析に基づくレビュー記事です。')}

## トレンド分析

### 話題のキーワード

{kw_list}

### 注目のポイント

- SNS上での急上昇ワードを分析
- 実際のユーザー声を反映
- 専門家の視点で評価

## おすすめ商品

> ※Amazonアソシエイトリンクを含んでいます。

| 商品名 | 評価 | 価格 |
|--------|------|------|
| 調査中 | ⭐⭐⭐⭐ | 要確認 |

## 参考リンク

{url_list}

## まとめ

本記事はAIと人間の共創により作成されました。トレンドデータに基づき、読者の皆様に役立つ情報をお届けします。

---

<small>当サイトはアフィリエイト広告（PR）を含んでいます。Amazonアソシエイトとして適格販売により収入を得ています。</small>
"""
    return body

def create_article(trend_data, dry_run=False):
    """トレンドデータから記事を生成"""
    tag = trend_data['name']
    analysis = trend_data.get('analysis', {})
    keywords = [w for w, c in analysis.get('top_words', [])[:10]]
    urls = analysis.get('urls', [])
    
    # カテゴリ判定
    all_text = ' '.join(keywords) + ' ' + tag
    category = detect_category(all_text)
    
    # タイトル生成
    top_kw = keywords[0] if keywords else tag
    title = f"【{now_jst()}】SNSで話題の「{top_kw}」徹底レビュー｜AI共創レビュー研究所"
    description = f"SNSトレンド「#{tag}」について徹底分析。{top_kw}関連の最新動向とおすすめ商品を紹介します。"
    
    # スラグ
    slug = generate_slug(title)
    
    # 商品データ（Amazon検索URL生成）
    products = []
    for kw in keywords[:3]:
        products.append({
            'name': kw,
            'amazonUrl': f'https://www.amazon.co.jp/s?k={kw}&tag={AMAZON_TRACKING_ID}',
            'rating': None,
        })
    
    # 記事生成
    frontmatter = generate_article_frontmatter(
        title=title,
        description=description,
        category=category,
        tags=[tag] + keywords[:5],
        products=products,
    )
    
    body = generate_article_body(
        title=title,
        trend_info={'summary': f'Mastodonトレンド「#{tag}」の分析記事'},
        keywords=keywords,
        urls=urls,
    )
    
    content = frontmatter + body
    
    if dry_run:
        print(f'=== DRY RUN ===')
        print(f'Slug: {slug}')
        print(f'Category: {category}')
        print(f'Title: {title}')
        print(f'Keywords: {", ".join(keywords[:5])}')
        print(f'Content length: {len(content)} chars')
        print()
        print(content[:500])
        print('...')
        return slug
    
    # ファイル保存
    article_path = ARTICLES_DIR / f'{slug}.md'
    article_path.write_text(content, encoding='utf-8')
    print(f'Article saved: {article_path}')
    
    return slug

def now_jst():
    return datetime.now(JST).strftime('%Y年%m月%d日')

def deploy_to_cloudflare():
    """Cloudflare Pagesにデプロイ"""
    print('Deploying to Cloudflare Pages...')
    result = subprocess.run(
        ['python3', str(PROJECT_DIR / 'scripts' / 'deploy.py')],
        capture_output=True, text=True, timeout=120
    )
    if result.returncode == 0:
        print('Deploy successful!')
        return True
    else:
        print(f'Deploy failed: {result.stderr}')
        return False

def post_to_mastodon(message, dry_run=False):
    """Mastodonに投稿（curl経由）"""
    if dry_run:
        print(f'[DRY RUN] Would post to Mastodon:')
        print(f'  {message[:200]}')
        return True
    
    # 投稿用API（Appトークンが必要）
    # 未実装: mstdn.jpのApp登録が必要
    print(f'[TODO] Post to Mastodon: {message[:100]}...')
    return False

def main():
    parser = argparse.ArgumentParser(description='LLM記事生成 & SNS投稿')
    parser.add_argument('--trend-data', type=str, help='トレンドデータJSONファイル')
    parser.add_argument('--tag', type=str, help='特定タグを指定')
    parser.add_argument('--dry-run', action='store_true', help='デプロイ・投稿なし')
    parser.add_argument('--deploy', action='store_true', help='デプロイ実行')
    parser.add_argument('--post', action='store_true', help='SNS投稿実行')
    args = parser.parse_args()
    
    # トレンドデータ取得
    if args.trend_data:
        with open(args.trend_data) as f:
            trend_data = json.load(f)
    elif args.tag:
        # trend_collector.py をインポートして分析
        sys.path.insert(0, str(PROJECT_DIR / 'scripts'))
        from trend_collector import get_tag_posts, analyze_posts
        posts = get_tag_posts(args.tag.lstrip('#'), limit=20)
        analysis = analyze_posts(posts)
        trend_data = {
            'name': args.tag.lstrip('#'),
            'analysis': analysis,
        }
    else:
        # デフォルト: trend_collector を実行して最新トレンドを取得
        print('最新トレンドを取得中...')
        result = subprocess.run(
            [sys.executable, str(PROJECT_DIR / 'scripts' / 'trend_collector.py'), '--trends-only'],
            capture_output=True, text=True, timeout=30
        )
        print(result.stdout)
        return
    
    # 記事生成
    slug = create_article(trend_data, dry_run=args.dry_run)
    
    if args.deploy and not args.dry_run:
        deploy_to_cloudflare()
    
    if args.post and not args.dry_run:
        # SNS投稿文生成
        title = f"SNSで話題の「{trend_data['name']}」を徹底レビューしました！ #AI共創レビュー研究所"
        url = f"https://toknet.info/articles/{slug}/"
        message = f"{title}\n\n{url}\n\n#AI #レビュー #トレンド"
        post_to_mastodon(message, dry_run=args.dry_run)

if __name__ == '__main__':
    main()
