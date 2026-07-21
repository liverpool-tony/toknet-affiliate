#!/usr/bin/env python3
"""
Google Search Console 確認スクリプト
- サイトマップ送信状況
- インデックス状況（site: クエリ）
- robots.txt / sitemap の健全性チェック
- GSC API（認証済み場合）でカバレッジレポート

Usage: ~/.hermes/hermes-agent/venv/bin/python3 scripts/gsc_check.py
"""
import json
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

SITE = "https://toknet.info"
SITEMAP_URL = f"{SITE}/sitemap-index.xml"
ROBOTS_URL = f"{SITE}/robots.txt"

def fetch(url, timeout=10):
    """Fetch URL and return (status_code, body_text)"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; GSC-Checker/1.0)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return 0, str(e)

def check_robots():
    print("=" * 60)
    print("1. robots.txt チェック")
    print("=" * 60)
    status, body = fetch(ROBOTS_URL)
    if status == 200:
        print(f"  ✅ robots.txt 存在 (HTTP {status})")
        # Check for disallow rules
        disallows = [l for l in body.splitlines() if l.lower().startswith("disallow")]
        if disallows:
            print(f"  ⚠️  Disallow ルールあり:")
            for d in disallows:
                print(f"     {d}")
        else:
            print("  ✅ Disallow ルールなし（全ページクロール許可）")
        # Check sitemap reference
        if "sitemap" in body.lower():
            print("  ✅ Sitemap 参照あり")
        else:
            print("  ⚠️  Sitemap 参照なし → robots.txt に Sitemap: を追加推奨")
    else:
        print(f"  ❌ robots.txt 取得失敗 (HTTP {status})")

def check_sitemap():
    print("\n" + "=" * 60)
    print("2. サイトマップ チェック")
    print("=" * 60)
    status, body = fetch(SITEMAP_URL)
    if status == 200:
        print(f"  ✅ sitemap-index.xml 存在 (HTTP {status})")
        # Count URLs in sitemap index
        index_urls = re.findall(r"<loc>(.*?)</loc>", body)
        print(f"  📁 サブサイトマップ: {len(index_urls)}")
        # Fetch each sub-sitemap and count article URLs
        total_urls = 0
        article_urls = []
        for sub_url in index_urls:
            sub_status, sub_body = fetch(sub_url)
            if sub_status == 200:
                sub_locs = re.findall(r"<loc>(.*?)</loc>", sub_body)
                total_urls += len(sub_locs)
                article_urls.extend([u for u in sub_locs if "/articles/" in u])
        print(f"  📄 総URL数: {total_urls}")
        print(f"  📝 記事URL: {len(article_urls)}")
        if article_urls:
            print(f"  最初: {article_urls[0]}")
            print(f"  最後: {article_urls[-1]}")
    else:
        print(f"  ❌ サイトマップ取得失敗 (HTTP {status})")
        # Try alternate paths
        for alt in ["/sitemap.xml", "/sitemap-0.xml"]:
            s, _ = fetch(SITE + alt)
            if s == 200:
                print(f"  💡 代替サイトマップ発見: {SITE}{alt}")

def check_indexing():
    print("\n" + "=" * 60)
    print("3. Google インデックス状況（簡易チェック）")
    print("=" * 60)
    # Check a few key pages
    test_pages = [
        ("/", "トップページ"),
        ("/articles/ai-glasses-comparison-2026/", "AIグラス比較（新規）"),
        ("/articles/smartwatch-comparison-2026/", "スマートウォッチ比較（新規）"),
        ("/about/", "About"),
    ]
    for path, name in test_pages:
        status, _ = fetch(SITE + path)
        icon = "✅" if status == 200 else "❌"
        print(f"  {icon} {name}: HTTP {status} ({SITE}{path})")

    # Check if Google has indexed (via site: query - may be blocked)
    print("\n  🔍 Google インデックス確認:")
    print("  → https://search.google.com/search-console で以下を確認:")
    print("    1. プロパティ追加（toknet.info）")
    print("    2. 所有権確認（DNS TXT レコード or HTMLファイル）")
    print("    3. サイトマップ送信: " + SITEMAP_URL)
    print("    4. カバレッジレポートでエラー確認")
    print("    5. URL検査で個別ページのインデックス状況確認")

def check_gsc_api():
    """Try GSC API if credentials exist"""
    print("\n" + "=" * 60)
    print("4. Google Search Console API")
    print("=" * 60)
    
    # Check for GSC credentials
    cred_paths = [
        Path.home() / ".hermes" / "gsc-service-account.json",
        Path.home() / ".hermes" / "ga4-service-account.json",  # Same SA might have GSC access
    ]
    
    cred_file = None
    for p in cred_paths:
        if p.exists():
            cred_file = p
            break
    
    if not cred_file:
        print("  ⚠️  GSC用認証情報なし")
        print("  → GA4用SAにSearch Console API権限を追加すれば利用可能")
        return
    
    print(f"  📄 認証ファイル: {cred_file}")
    
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        
        creds = service_account.Credentials.from_service_account_file(
            str(cred_file),
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
        )
        service = build("searchconsole", "v1", credentials=creds)
        
        # Check site list
        sites = service.sites().list().execute()
        site_entries = sites.get("siteEntry", [])
        toknet_sites = [s for s in site_entries if "toknet" in s.get("siteUrl", "")]
        
        if toknet_sites:
            print(f"  ✅ GSC プロパティ発見: {toknet_sites[0]['siteUrl']}")
            site_url = toknet_sites[0]["siteUrl"]
            
            # Get search analytics
            from datetime import datetime, timedelta
            end = datetime.now().strftime("%Y-%m-%d")
            start = (datetime.now() - timedelta(days=28)).strftime("%Y-%m-%d")
            
            response = service.searchanalytics().query(
                siteUrl=site_url,
                body={
                    "startDate": start,
                    "endDate": end,
                    "dimensions": ["query"],
                    "rowLimit": 20,
                    "orderBy": "clicks"
                }
            ).execute()
            
            rows = response.get("rows", [])
            if rows:
                print(f"\n  📊 直近28日間の検索クエリ (上位20件):")
                print(f"  {'クエリ':<40} {'クリック':>8} {'表示':>8} {'CTR':>8} {'順位':>8}")
                print(f"  {'-'*72}")
                for row in rows:
                    keys = row.get("keys", [""])[0]
                    clicks = row.get("clicks", 0)
                    impressions = row.get("impressions", 0)
                    ctr = row.get("ctr", 0) * 100
                    position = row.get("position", 0)
                    print(f"  {keys:<40} {clicks:>8} {impressions:>8} {ctr:>7.1f}% {position:>7.1f}")
            else:
                print("  ⚠️  検索クエリデータなし（インデックスされていない可能性）")
            
            # Check coverage
            print(f"\n  📋 カバレッジ状況:")
            print(f"  → GSCコンソールで確認: https://search.google.com/search-console/coverage")
        else:
            print("  ⚠️  GSCにtoknet.infoのプロパティが未登録")
            print("  → GSCコンソールでプロパティ追加が必要")
            print("  → https://search.google.com/search-console/about")
    
    except ImportError:
        print("  ⚠️  google-api-python-client 未インストール")
        print("  → pip install google-api-python-client google-auth")
    except Exception as e:
        print(f"  ❌ GSC API エラー: {e}")

def main():
    print("🔍 toknet.info Google Search Console 確認レポート")
    print(f"   実行時刻: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    check_robots()
    check_sitemap()
    check_indexing()
    check_gsc_api()
    
    print("\n" + "=" * 60)
    print("📋 次のアクション")
    print("=" * 60)
    print("  1. GSCにプロパティ登録（未登録の場合）")
    print("  2. サイトマップ送信: " + SITEMAP_URL)
    print("  3. カバレッジエラー修正")
    print("  4. 主要記事のURL検査 → インデックス登録リクエスト")
    print("  5. 1週間後に再実行してインデックス状況確認")

if __name__ == "__main__":
    main()
