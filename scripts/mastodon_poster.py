#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mastodon 自動投稿スクリプト
mstdn.jp APIを使用して投稿する

Setup:
    1. mstdn.jp でアプリ作成: https://mstdn.jp/settings/applications
    2. client_id, client_secret を取得
    3. 環境変数に設定:
       export MSTODON_CLIENT_ID="your_client_id"
       export MSTODON_CLIENT_SECRET="your_client_secret"
       export MSTODON_ACCESS_TOKEN="your_access_token"

Usage:
    python3 mastodon_poster.py "投稿文" --url https://example.com
    python3 mastodon_poster.py --dry-run "テスト投稿"
"""

import subprocess, json, re, sys, argparse, os
from pathlib import Path

# mstdn.jp API
MSTODON_BASE = 'https://mstdn.jp'

def get_env(key, default=None):
    return os.environ.get(key, default)

def load_credentials():
    """認証情報を読み込む"""
    return {
        'client_id': get_env('MSTODON_CLIENT_ID', ''),
        'client_secret': get_env('MSTODON_CLIENT_SECRET', ''),
        'access_token': get_env('MSTODON_ACCESS_TOKEN', ''),
    }

def get_access_token(client_id, client_secret):
    """OAuth2 クライアント認証でアクセストークン取得"""
    url = f'{MSTODON_BASE}/oauth/token'
    result = subprocess.run([
        'curl', '-sk', '-X', 'POST', url,
        '-d', f'grant_type=client_credentials',
        '-d', f'client_id={client_id}',
        '-d', f'client_secret={client_secret}',
    ], capture_output=True, text=True, timeout=15)
    data = json.loads(result.stdout)
    return data.get('access_token', '')

def post_status(text, credentials, dry_run=False, language='ja'):
    """投稿"""
    token = credentials.get('access_token', '')
    if not token:
        # 新規取得を試みる
        cid = credentials.get('client_id', '')
        csecret = credentials.get('client_secret', '')
        if cid and csecret:
            token = get_access_token(cid, csecret)
    
    if not token and not dry_run:
        print('ERROR: No access token. Set MSTODON_ACCESS_TOKEN env var.', file=sys.stderr)
        sys.exit(1)
    
    if dry_run:
        print(f'[DRY RUN] Mastodon投稿:')
        print(f'  Language: {language}')
        print(f'  Content: {text[:300]}')
        if len(text) > 300:
            print(f'  ... ({len(text)} chars total)')
        return True
    
    url = f'{MSTODON_BASE}/api/v1/statuses'
    result = subprocess.run([
        'curl', '-sk', '-X', 'POST', url,
        '-H', f'Authorization: Bearer {token}',
        '-H', 'Content-Type: application/json',
        '-d', json.dumps({
            'status': text,
            'language': language,
            'visibility': 'public',
        }, ensure_ascii=False),
    ], capture_output=True, text=True, timeout=15)
    
    data = json.loads(result.stdout)
    if 'id' in data:
        print(f'投稿成功: {data["id"]}')
        return True
    else:
        print(f'投稿失敗: {data.get("error", result.stdout)}')
        return False

def post_with_media(text, image_path, credentials, dry_run=False):
    """画像付き投稿"""
    if dry_run:
        print(f'[DRY RUN] 画像付き投稿: {image_path}')
        return post_status(text, credentials, dry_run=True)
    
    token = credentials.get('access_token', '')
    if not token:
        print('ERROR: No access token.')
        return False
    
    # 画像アップロード
    upload_url = f'{MSTODON_BASE}/api/v1/media'
    result = subprocess.run([
        'curl', '-sk', '-X', 'POST', upload_url,
        '-H', f'Authorization: Bearer {token}',
        '-F', f'file=@{image_path}',
    ], capture_output=True, text=True, timeout=30)
    
    media_data = json.loads(result.stdout)
    media_id = media_data.get('id')
    
    if not media_id:
        print(f'画像アップロード失敗: {result.stdout}')
        return False
    
    # 投稿
    status_url = f'{MSTODON_BASE}/api/v1/statuses'
    result = subprocess.run([
        'curl', '-sk', '-X', 'POST', status_url,
        '-H', f'Authorization: Bearer {token}',
        '-H', 'Content-Type: application/json',
        '-d', json.dumps({
            'status': text,
            'media_ids': [media_id],
            'language': 'ja',
            'visibility': 'public',
        }, ensure_ascii=False),
    ], capture_output=True, text=True, timeout=15)
    
    data = json.loads(result.stdout)
    if 'id' in data:
        print(f'画像付き投稿成功: {data["id"]}')
        return True
    else:
        print(f'投稿失敗: {data.get("error", result.stdout)}')
        return False

def format_article_post(title, description, url, tags=None, category=None):
    """記事投稿用のテキストを生成"""
    lines = []
    lines.append(f'📢 {title}')
    lines.append('')
    lines.append(description)
    lines.append('')
    lines.append(f'🔗 {url}')
    lines.append('')
    
    if tags:
        tag_str = ' '.join(f'#{t}' for t in tags[:5])
        lines.append(tag_str)
    
    lines.append('')
    lines.append('#AI共創レビュー研究所 #AI #レビュー')
    
    text = '\n'.join(lines)
    
    # Mastodonは500文字制限
    if len(text) > 500:
        text = text[:497] + '...'
    
    return text

def main():
    parser = argparse.ArgumentParser(description='Mastodon投稿')
    parser.add_argument('text', nargs='?', help='投稿テキスト')
    parser.add_argument('--url', type=str, help='記事URL')
    parser.add_argument('--article-title', type=str, help='記事タイトル（自動フォーマット）')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--image', type=str, help='画像パス')
    args = parser.parse_args()
    
    credentials = load_credentials()
    
    if args.article_title and args.url:
        # 自動フォーマット
        text = format_article_post(
            title=args.article_title,
            description='トレンド分析に基づくレビュー記事を公開しました。',
            url=args.url,
        )
    elif args.text:
        text = args.text
    else:
        print('ERROR: text または --article-title + --url が必要')
        return
    
    if args.image:
        post_with_media(text, args.image, credentials, dry_run=args.dry_run)
    else:
        post_status(text, credentials, dry_run=args.dry_run)

if __name__ == '__main__':
    main()
