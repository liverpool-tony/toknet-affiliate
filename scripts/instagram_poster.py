#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Instagram Graph API 自動投稿スクリプト
Meta Graph API経由でInstagram Business/Creatorアカウントに投稿する

Setup:
    1. Instagram Business/Creatorアカウント作成
    2. Facebook Page作成 → Instagramと連携
    3. Meta Developer App作成 (developers.facebook.com)
    4. App Review申請 → 以下の権限を取得:
       - instagram_basic
       - instagram_content_publish
       - pages_read_engagement
    5. Facebook Pageのアクセストークンを取得（60日有効）
    6. 環境変数に設定:
       export INSTAGRAM_ACCESS_TOKEN="<facebook_page_access_token>"
       export INSTAGRAM_IG_USER_ID="<instagram_business_account_id>"

API Flow (3-step):
    Step 1: POST /{ig-user-id}/media → container_id 取得
    Step 2: GET  /{container_id}?fields=status_code → "FINISHED" を待つ
    Step 3: POST /{ig-user-id}/media_publish → 投稿完了

Rate Limits:
    - 100投稿/24時間 (media_publish ベース)
    - 200リクエスト/時間 (Business Use Case)

Usage:
    python3 instagram_poster.py "投稿文" --image-url https://example.com/image.jpg
    python3 instagram_poster.py --dry-run "テスト投稿"
    python3 instagram_poster.py --article-title "記事タイトル" --url https://toknet.info/articles/slug
    python3 instagram_poster.py --check  # 認証確認
    python3 instagram_poster.py --hashtag-search "ガジェット" → 候補ハッシュタグ取得
"""

import subprocess, json, re, sys, argparse, os, time
from pathlib import Path
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
API_VERSION = "v22.0"
GRAPH_BASE = f"https://graph.facebook.com/{API_VERSION}"

# ===== Credentials =====

def get_env(key, default=None):
    return os.environ.get(key, default)

def load_credentials():
    return {
        'access_token': get_env('INSTAGRAM_ACCESS_TOKEN', ''),
        'ig_user_id': get_env('INSTAGRAM_IG_USER_ID', ''),
    }

# ===== Graph API helpers =====

def api_get(url, params=None):
    """Graph API GET request"""
    if params is None:
        params = {}
    params['access_token'] = load_credentials()['access_token']
    
    qs = '&'.join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{qs}"
    
    result = subprocess.run(
        ['curl', '-sS', '-L', full_url],
        capture_output=True, text=True, timeout=20
    )
    return json.loads(result.stdout)

def api_post(url, data=None, files=None):
    """Graph API POST request"""
    data = data or {}
    data['access_token'] = load_credentials()['access_token']
    
    cmd = ['curl', '-sS', '-L', '-X', 'POST', url]
    if files:
        for key, val in files.items():
            cmd.extend(['-F', f'{key}=@{val}'])
    for key, val in data.items():
        cmd.extend(['-d', f'{key}={val}'])
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)

# ===== IG User ID discovery =====

def discover_ig_user_id():
    """Instagram Business Account ID を自動発見"""
    creds = load_credentials()
    token = creds['access_token']
    
    # 1. まず Facebook Pages を取得して、紐づくInstagram Accountを探す
    url = f"{GRAPH_BASE}/me/accounts"
    result = api_get(url, {'fields': 'id,name,instagram_business_account'})
    
    pages = result.get('data', [])
    if not pages:
        print("ERROR: No Facebook Pages found. Create a Page and link your Instagram.")
        return None
    
    for page in pages:
        ig_account = page.get('instagram_business_account')
        if ig_account:
            ig_id = ig_account.get('id')
            print(f"Found IG account for page '{page['name']}' (page_id: {page['id']})")
            return ig_id
    
    print("ERROR: No Instagram Business Account linked to any Page.")
    print("  → Facebook PageでInstagramアカウントを連携してください")
    return None

def verify_credentials():
    """認証情報の確認"""
    creds = load_credentials()
    token = creds['access_token']
    ig_id = creds['ig_user_id']
    
    if not token:
        print("ERROR: INSTAGRAM_ACCESS_TOKEN が設定されていません")
        return False
    
    # アクセストークンのデバッグ
    url = f"{GRAPH_BASE}/debug_token"
    try:
        # これだけ app access token が必要なので curlで直接叩く
        app_token = get_env('INSTAGRAM_APP_ID', '') + '|' + get_env('INSTAGRAM_APP_SECRET', '')
        if not app_token.strip('|'):
            # debug_token は app token が必要。skipして /me で試す
            url2 = f"{GRAPH_BASE}/me"
            r = api_get(url2, {'fields': 'id,name'})
            if 'id' in r:
                print(f"✅ Token valid — Page/User: {r.get('name', r.get('id'))}")
                if not ig_id:
                    discovered = discover_ig_user_id()
                    if discovered:
                        print(f"→ INSTAGRAM_IG_USER_ID={discovered} を設定してください")
                return True
            else:
                print(f"❌ Token invalid: {r}")
                return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

# ===== Step 1: Create Media Container =====

def create_image_container(image_url, caption, ig_user_id):
    """画像投稿用のコンテナを作成"""
    url = f"{GRAPH_BASE}/{ig_user_id}/media"
    result = api_post(url, {
        'image_url': image_url,
        'caption': caption,
    })
    
    container_id = result.get('id')
    if not container_id:
        print(f"❌ Container作成失敗: {result}")
        return None
    
    print(f"✅ Container作成: {container_id}")
    return container_id

def create_carousel_container(items, caption, ig_user_id):
    """カルーセル投稿 (最大10画像)"""
    # 各画像の子コンテナを作成
    child_ids = []
    for item in items:
        url = f"{GRAPH_BASE}/{ig_user_id}/media"
        child = api_post(url, {
            'image_url': item['url'],
            'is_carousel_item': 'true',
            'access_token': load_credentials()['access_token'],
        })
        cid = child.get('id')
        if cid:
            child_ids.append(cid)
        else:
            print(f"⚠️ 子コンテナ作成失敗: {child}")
    
    if not child_ids:
        print("❌ カルーセル: 有効な子コンテナがありません")
        return None
    
    # カルーセルコンテナを作成
    url = f"{GRAPH_BASE}/{ig_user_id}/media"
    result = api_post(url, {
        'media_type': 'CAROUSEL',
        'children': ','.join(child_ids),
        'caption': caption,
    })
    
    container_id = result.get('id')
    if not container_id:
        print(f"❌ カルーセル作成失敗: {result}")
        return None
    
    print(f"✅ カルーセル作成: {container_id} ({len(child_ids)} images)")
    return container_id

# ===== Step 2: Poll container status =====

def poll_container_status(container_id, max_wait=60):
    """コンテナの処理完了を待つ"""
    url = f"{GRAPH_BASE}/{container_id}"
    
    for i in range(max_wait):
        result = api_get(url, {'fields': 'status_code,status'})
        status = result.get('status_code', 'UNKNOWN')
        
        if status == 'FINISHED':
            print(f"✅ Container ready ({i+1}s)")
            return True
        elif status == 'IN_PROGRESS':
            if (i + 1) % 10 == 0:
                print(f"  処理中... ({i+1}/{max_wait}s)")
            time.sleep(1)
        elif status == 'ERROR':
            print(f"❌ Container error: {result.get('status', 'unknown')}")
            return False
    
    print(f"❌ Container timeout ({max_wait}s)")
    return False

# ===== Step 3: Publish =====

def publish_container(container_id, ig_user_id):
    """コンテナを公開"""
    url = f"{GRAPH_BASE}/{ig_user_id}/media_publish"
    result = api_post(url, {
        'creation_id': container_id,
    })
    
    media_id = result.get('id')
    if not media_id:
        print(f"❌ 投稿失敗: {result}")
        return None
    
    print(f"✅ 投稿成功! media_id: {media_id}")
    # Note: media_id is NOT the shortcode. The permalink requires a separate API call.
    # Return media_id; the caller should use the Instagram Business Account's media list to find the permalink.
    return media_id

def get_media_permalink(media_id, ig_user_id=None):
    """メディアIDから正しいpermalinkを取得"""
    creds = load_credentials()
    token = creds['access_token']
    
    url = f"{GRAPH_BASE}/{media_id}"
    params = {'fields': 'id,permalink,timestamp', 'access_token': token}
    
    qs = '&'.join(f"{k}={v}" for k, v in params.items())
    full_url = f"{url}?{qs}"
    
    result = subprocess.run(
        ['curl', '-sS', '-L', full_url],
        capture_output=True, text=True, timeout=20
    )
    data = json.loads(result.stdout)
    
    permalink = data.get('permalink')
    if permalink:
        print(f"   Permalink: {permalink}")
    else:
        print(f"   ⚠️ permalink取得失敗: {data}")
    
    return permalink


# ===== High-level posting =====

def post_image(image_url, caption, ig_user_id=None):
    """画像を1枚投稿（3ステップフロー）"""
    creds = load_credentials()
    if not ig_user_id:
        ig_user_id = creds['ig_user_id']
    if not ig_user_id:
        ig_user_id = discover_ig_user_id()
        if not ig_user_id:
            return False
    
    # Step 1
    container_id = create_image_container(image_url, caption, ig_user_id)
    if not container_id:
        return False
    
    # Step 2
    if not poll_container_status(container_id):
        return False
    
    # Step 3
    media_id = publish_container(container_id, ig_user_id)
    if media_id is None:
        return False
    
    # Step 4: Get correct permalink
    permalink = get_media_permalink(media_id, ig_user_id)
    return permalink if permalink else media_id

def post_carousel(image_urls, caption, ig_user_id=None):
    """複数画像をカルーセル投稿"""
    creds = load_credentials()
    if not ig_user_id:
        ig_user_id = creds['ig_user_id']
    if not ig_user_id:
        print("ERROR: IG User ID not set")
        return False
    
    items = [{'url': u} for u in image_urls[:10]]
    
    container_id = create_carousel_container(items, caption, ig_user_id)
    if not container_id:
        return False
    
    if not poll_container_status(container_id, max_wait=90):
        return False
    
    media_id = publish_container(container_id, ig_user_id)
    return media_id is not None

# ===== Content Publishing Limit =====

def check_publishing_limit(ig_user_id=None):
    """現在の投稿制限を確認"""
    creds = load_credentials()
    if not ig_user_id:
        ig_user_id = creds['ig_user_id']
    if not ig_user_id:
        print("ERROR: IG User ID not set")
        return
    
    url = f"{GRAPH_BASE}/{ig_user_id}/content_publishing_limit"
    result = api_get(url)
    
    data = result.get('data', [{}])[0]
    print(f"📊 投稿制限状況:")
    print(f"  24h使用: {data.get('usage_count', '?')}")
    print(f"  制限値:  {data.get('limit', '?')}")

# ===== Format helpers =====

def format_article_post(title, description, url, tags=None, category=None, amazon_url=None):
    """記事投稿用キャプション生成（Instagram用）"""
    lines = []
    lines.append(f'📢 {title}')
    lines.append('')
    lines.append(description)
    lines.append('')
    
    # Amazonリンク（指定があれば）
    if amazon_url:
        lines.append(f'🛒 詳しくはこちら → {url}')
        lines.append(f'   Amazonで見る → {amazon_url}')
    else:
        lines.append(f'🔗 {url}')
    
    lines.append('')
    
    # ハッシュタグ
    hashtags = ['#AI共創レビュー研究所', '#AI', '#レビュー', '#テック', '#ガジェット']
    if tags:
        for t in tags[:5]:
            tag_clean = re.sub(r'[^\w]', '', t)
            if tag_clean:
                hashtags.append(f'#{tag_clean}')
    if category:
        hashtags.append(f'#{category}')
    
    lines.append(' '.join(hashtags))
    lines.append('')
    lines.append('※当サイトはAmazonアソシエイトを含むアフィリエイト広告を掲載しています')
    
    caption = '\n'.join(lines)
    
    # Instagram キャプション上限: 2,200文字
    if len(caption) > 2200:
        caption = caption[:2197] + '...'
    
    return caption

def trim_for_first_comment(text):
    """最初のコメント用（Instagram投稿後に最初のコメントを自動投稿する場合）"""
    # 300文字以内
    if len(text) > 300:
        return text[:297] + '...'
    return text

# ===== Hashtag search (optional) =====

def search_hashtag(tag_name):
    """ハッシュタグ検索"""
    creds = load_credentials()
    ig_id = creds['ig_user_id']
    if not ig_id:
        print("ERROR: IG User ID not set")
        return []
    
    # Step 1: ハッシュタグIDを検索
    url = f"{GRAPH_BASE}/ig_hashtag_search"
    result = api_get(url, {'q': tag_name, 'user_id': ig_id})
    
    hashtag_list = result.get('data', [])
    return hashtag_list

# ===== Main =====

def main():
    parser = argparse.ArgumentParser(description='Instagram投稿 (Graph API)')
    parser.add_argument('text', nargs='?', help='投稿キャプション')
    parser.add_argument('--image-url', type=str, help='画像URL (公開URL必須)')
    parser.add_argument('--image-path', type=str, help='画像ローカルパス (アップロード)')
    parser.add_argument('--dry-run', action='store_true', help='投稿せず内容表示')
    parser.add_argument('--check', action='store_true', help='認証確認')
    parser.add_argument('--hashtag-search', type=str, help='ハッシュタグ検索')
    parser.add_argument('--limit', action='store_true', help='投稿制限確認')
    parser.add_argument('--url', type=str, help='記事URL')
    parser.add_argument('--article-title', type=str, help='記事タイトル（自動キャプション生成）')
    parser.add_argument('--amazon-url', type=str, help='Amazon商品URL')
    parser.add_argument('--ig-user-id', type=str, help='Instagram Business Account ID')
    args = parser.parse_args()
    
    creds = load_credentials()
    
    # モード判定
    if args.check:
        verify_credentials()
        return
    
    if args.limit:
        check_publishing_limit(args.ig_user_id)
        return
    
    if args.hashtag_search:
        results = search_hashtag(args.hashtag_search)
        for r in results[:5]:
            print(f"  #{r.get('id')}: {r}")
        return
    
    if args.image_path and not args.image_url:
        print(f"⚠️ ローカル画像はアップロードが必要です: {args.image_path}")
        print(f"   toknet.infoの画像URLを推奨: https://toknet.info/og-default.png")
        print(f"   または --image-url で公開URLを指定")
        return
    
    # キャプション生成
    if args.article_title and args.url:
        caption = format_article_post(
            title=args.article_title,
            description='トレンド分析に基づくレビュー記事を公開しました！',
            url=args.url,
            amazon_url=args.amazon_url,
        )
    elif args.text:
        caption = args.text
    else:
        print('ERROR: text または --article-title + --url が必要')
        sys.exit(1)
    
    if args.dry_run:
        print('=== DRY RUN ===')
        print(f'  アカウント: {creds.get("ig_user_id", "未設定")}')
        print(f'  画像URL: {args.image_url or "なし"}')
        print(f'  キャプション:')
        print(f'  ---')
        print(f'  {caption}')
        print(f'  ---')
        return
    
    # 投稿実行
    ig_id = args.ig_user_id or creds['ig_user_id']
    if not ig_id:
        print("ERROR: IG User IDが必要です。--ig-user-id または INSTAGRAM_IG_USER_ID 環境変数で指定")
        sys.exit(1)
    
    if args.image_url:
        success = post_image(args.image_url, caption, ig_user_id=ig_id)
    else:
        # テキストのみは投稿できず、画像が必須
        print("ERROR: Instagram投稿には画像が必須です。--image-url で画像URLを指定してください")
        sys.exit(1)
    
    if success:
        print('🎉 投稿完了!')
    else:
        print('❌ 投稿失敗')
        sys.exit(1)

if __name__ == '__main__':
    main()
