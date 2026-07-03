#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UAT (User Acceptance Test) スクリプト
toknet.info サイトの主要機能を自動検証

Usage:
    python3 uat_test.py              # 全テスト実行
    python3 uat_test.py --url URL     # ベースURLを指定（デフォルト: https://www.toknet.info）
    python3 uat_test.py --json        # JSON形式で結果出力
"""

import subprocess, json, re, sys, argparse, os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter

JST = timezone(timedelta(hours=9))

class UATResult:
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
        self.warnings = 0
    
    def add_pass(self, name, detail=""):
        self.tests.append({"status": "PASS", "name": name, "detail": detail})
        self.passed += 1
    
    def add_fail(self, name, detail=""):
        self.tests.append({"status": "FAIL", "name": name, "detail": detail})
        self.failed += 1
    
    def add_warn(self, name, detail=""):
        self.tests.append({"status": "WARN", "name": name, "detail": detail})
        self.warnings += 1
    
    def summary(self):
        total = len(self.tests)
        return f"Total: {total} | Pass: {self.passed} | Fail: {self.failed} | Warn: {self.warnings}"

def curl_get(url, timeout=15):
    """curlでGETリクエスト"""
    result = subprocess.run(
        ['curl', '-sSk', '--connect-timeout', '10', '-L', url],
        capture_output=True, text=True, timeout=timeout
    )
    return result.stdout, result.returncode

def check_http_status(url, expected=200):
    """HTTPステータスチェック"""
    try:
        result = subprocess.run(
            ['curl', '-sk', '-o', '/dev/null', '-w', '%{http_code}', '--connect-timeout', '10', url],
            capture_output=True, text=True, timeout=15
        )
        return int(result.stdout.strip()) == expected
    except:
        return False

def check_page_contains(url, text):
    """ページ内に特定テキストが含まれるか"""
    body, status = curl_get(url)
    if status != 200:
        return False
    return text in body

def check_page_not_contains(url, text):
    """ページ内に特定テキストが含まれないか"""
    body, status = curl_get(url)
    if status != 200:
        return False
    return text not in body

def check_meta_tag(url, tag_name, expected_content=None):
    """メタタグの内容をチェック"""
    body, status = curl_get(url)
    if status != 200:
        return False, f"HTTP {status}"
    
    # HTMLを1行に圧縮（改行をスペースに）
    body_flat = body.replace('\n', ' ').replace('\r', ' ')
    
    if tag_name == "og:image":
        pattern = r'<meta\s+property="og:image"\s+content="([^"]+)"'
    elif tag_name == "description":
        pattern = r'<meta\s+name="description"\s+content="([^"]+)"'
    elif tag_name == "title":
        pattern = r'<title>([^<]+)</title>'
    else:
        pattern = rf'<meta\s+name="{tag_name}"\s+content="([^"]+)"'
    
    match = re.search(pattern, body_flat, re.IGNORECASE)
    if not match:
        return False, f"Meta tag '{tag_name}' not found in {len(body_flat)} chars"
    
    content = match.group(1).strip()
    if expected_content and expected_content not in content:
        return False, f"Expected '{expected_content}' in '{content}'"
    
    return True, content

def check_amazon_links(base_url):
    """Amazonリンクが有効な形式かチェック"""
    articles_dir = Path(__file__).parent.parent / 'astro' / 'src' / 'content' / 'articles'
    issues = []
    
    for md_file in articles_dir.glob('*.md'):
        content = md_file.read_text()
        # amazonUrlを抽出
        for match in re.finditer(r'amazonUrl:\s*"([^"]+)"', content):
            url = match.group(1)
            # ダミーASINをチェック
            if 'B0D1GK4V3R' in url:
                issues.append(f"❌ {md_file.name}: ダミーASIN使用 → {url}")
            elif '/dp/' in url and 'tag=toknet-22' not in url:
                issues.append(f"⚠️ {md_file.name}: tag付きでないASINリンク → {url}")
            elif '/s?k=' in url and 'tag=toknet-22' not in url:
                issues.append(f"⚠️ {md_file.name}: tag付きでない検索リンク → {url}")
            elif 'tag=toknet-22' in url:
                pass  # OK
            else:
                issues.append(f"⚠️ {md_file.name}: 不明なURL形式 → {url}")
    
    return issues

def check_article_pages(base_url):
    """全記事ページの動作チェック"""
    articles_dir = Path(__file__).parent.parent / 'astro' / 'src' / 'content' / 'articles'
    results = []
    
    for md_file in articles_dir.glob('*.md'):
        content = md_file.read_text()
        # slugを抽出（ファイル名から）
        slug = md_file.stem
        url = f"{base_url}/articles/{slug}/"
        
        # HTTPステータス
        if check_http_status(url):
            results.append(f"✅ {slug}: 200 OK")
        else:
            results.append(f"❌ {slug}: HTTPエラー")
    
    return results

def check_category_pages(base_url):
    """カテゴリページの動作チェック"""
    categories = ['laptop-pc', 'camera', 'audio-headphones', 'smart-home', 'home-appliances', 'monitors', 'diy-pc', 'gaming']
    results = []
    
    for cat in categories:
        url = f"{base_url}/category/{cat}/"
        if check_http_status(url):
            # カテゴリ名が含まれるか
            body, _ = curl_get(url)
            if cat.replace('-', ' ').title() in body or len(body) > 1000:
                results.append(f"✅ /category/{cat}/: 200 OK")
            else:
                results.append(f"⚠️ /category/{cat}/: コンテンツ不足")
        else:
            results.append(f"❌ /category/{cat}/: HTTPエラー")
    
    return results

def check_seo_files(base_url):
    """SEO関連ファイルの存在チェック"""
    results = []
    
    # robots.txt
    if check_http_status(f"{base_url}/robots.txt"):
        body, _ = curl_get(f"{base_url}/robots.txt")
        if 'sitemap' in body.lower():
            results.append("✅ /robots.txt: 存在（sitemap記載あり）")
        else:
            results.append("⚠️ /robots.txt: 存在（sitemap記載なし）")
    else:
        results.append("❌ /robots.txt: 404")
    
    # sitemap
    if check_http_status(f"{base_url}/sitemap-index.xml"):
        results.append("✅ /sitemap-index.xml: 200 OK")
    else:
        results.append("❌ /sitemap-index.xml: 404")
    
    return results

def check_related_articles(base_url):
    """関連記事が表示されているかチェック"""
    articles_dir = Path(__file__).parent.parent / 'astro' / 'src' / 'content' / 'articles'
    results = []
    
    for md_file in articles_dir.glob('*.md'):
        slug = md_file.stem
        url = f"{base_url}/articles/{slug}/"
        body, status = curl_get(url)
        
        if status != 200:
            continue
        
        # 関連記事セクションがあるか
        if '関連記事' in body:
            # 関連記事の中にリンクがあるか
            # <h3>関連記事</h3> の後に <a href="/articles/..."> があるか
            section = body.split('関連記事')[1][:500] if '関連記事' in body else ''
            links = re.findall(r'href="/articles/([^"]+)/"', section)
            
            if links:
                results.append(f"✅ {slug}: 関連記事あり（{len(links)}件）")
            else:
                results.append(f"⚠️ {slug}: 関連記事セクションあるが記事なし")
        else:
            results.append(f"⚠️ {slug}: 関連記事セクションなし")
    
    return results

def check_amazon_link_format(base_url):
    """Amazonリンクの形式チェック"""
    articles_dir = Path(__file__).parent.parent / 'astro' / 'src' / 'content' / 'articles'
    results = []
    dummy_count = 0
    search_count = 0
    asin_count = 0
    
    for md_file in articles_dir.glob('*.md'):
        content = md_file.read_text()
        for match in re.finditer(r'amazonUrl:\s*"([^"]+)"', content):
            url = match.group(1)
            if 'B0D1GK4V3R' in url:
                dummy_count += 1
            elif '/s?k=' in url:
                search_count += 1
            elif '/dp/' in url:
                asin_count += 1
    
    if dummy_count > 0:
        results.append(f"❌ ダミーASIN使用: {dummy_count}件")
    else:
        results.append(f"✅ ダミーASINなし")
    
    results.append(f"📊 検索結果URL: {search_count}件, ASIN直リンク: {asin_count}件")
    
    return results

def run_all_tests(base_url):
    """全テスト実行"""
    r = UATResult()
    
    print(f"\n{'='*60}", file=sys.stderr)
    print(f"UAT Test Suite — {base_url}", file=sys.stderr)
    print(f"🕐 {datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')}", file=sys.stderr)
    print(f"{'='*60}\n", file=sys.stderr)
    
    # 1. トップページ
    print("[1/7] トップページ...", file=sys.stderr)
    if check_http_status(f"{base_url}/"):
        r.add_pass("トップページ HTTP 200")
    else:
        r.add_fail("トップページ HTTP 200")
    
    # 2. 記事ページ
    print("[2/7] 記事ページ...", file=sys.stderr)
    article_results = check_article_pages(base_url)
    for res in article_results:
        if res.startswith("✅"):
            r.add_pass(res[2:])
        else:
            r.add_fail(res[2:])
    
    # 3. カテゴリページ
    print("[3/7] カテゴリページ...", file=sys.stderr)
    cat_results = check_category_pages(base_url)
    for res in cat_results:
        if res.startswith("✅"):
            r.add_pass(res[2:])
        elif res.startswith("⚠️"):
            r.add_warn(res[2:])
        else:
            r.add_fail(res[2:])
    
    # 4. SEOファイル
    print("[4/7] SEOファイル...", file=sys.stderr)
    seo_results = check_seo_files(base_url)
    for res in seo_results:
        if res.startswith("✅"):
            r.add_pass(res[2:])
        elif res.startswith("⚠️"):
            r.add_warn(res[2:])
        else:
            r.add_fail(res[2:])
    
    # 5. Amazonリンク
    print("[5/7] Amazonリンク...", file=sys.stderr)
    amazon_results = check_amazon_link_format(base_url)
    for res in amazon_results:
        if res.startswith("❌"):
            r.add_fail(res[2:])
        elif res.startswith("📊"):
            r.add_pass(res[2:])
        else:
            r.add_pass(res[2:])
    
    # 6. 関連記事
    print("[6/7] 関連記事...", file=sys.stderr)
    related_results = check_related_articles(base_url)
    for res in related_results:
        if res.startswith("✅"):
            r.add_pass(res[2:])
        elif res.startswith("⚠️"):
            r.add_warn(res[2:])
        else:
            r.add_fail(res[2:])
    
    # 7. メタタグ
    print("[7/7] メタタグ...", file=sys.stderr)
    
    # OG画像 — HTML内の文言検索（check_page_odiesは使用せず直接チェック）
    body_top, _ = curl_get(f"{base_url}/")
    if body_top and "og-default.png" in body_top:
        r.add_pass("OG画像設定", "og-default.png を確認")
    elif body_top:
        r.add_fail("OG画像設定", f"og-default.png 不在。meta: {[m for m in re.findall(r'<meta[^>]*og:image[^>]*>', body_top)]}")
    else:
        r.add_fail("OG画像設定", "ページを取得できず")
    
    # description — ページ内にdescriptionが含まれるか
    if body_top and 'content="AIと人間の共創' in body_top:
        r.add_pass("メタディスクリプション")
    elif body_top:
        r.add_fail("メタディスクリプション", "description メタタグの内容が不正")
    else:
        r.add_fail("メタディスクリプション", "ページを取得できず")
    
    # 構造化データ（JSON-LD）
    body, _ = curl_get(f"{base_url}/")
    if 'application/ld+json' in body:
        r.add_pass("構造化データ（JSON-LD）")
    else:
        r.add_fail("構造化データ（JSON-LD）")
    
    return r

def main():
    parser = argparse.ArgumentParser(description="UAT Test Suite")
    parser.add_argument('--url', default='https://toknet.info', help='Base URL')
    parser.add_argument('--json', action='store_true', help='JSON output')
    args = parser.parse_args()
    
    result = run_all_tests(args.url)
    
    if args.json:
        output = {
            "timestamp": datetime.now(JST).isoformat(),
            "base_url": args.url,
            "summary": result.summary(),
            "tests": result.tests,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*60}")
        print("UAT テスト結果")
        print(f"{'='*60}")
        
        for t in result.tests:
            icon = "✅" if t["status"] == "PASS" else "❌" if t["status"] == "FAIL" else "⚠️"
            print(f"  {icon} {t['name']}")
            if t["detail"]:
                print(f"     → {t['detail']}")
        
        print(f"\n{result.summary()}")
        print(f"{'='*60}")
        
        if result.failed > 0:
            print(f"\n❌ {result.failed}件の失敗があります。修正してください。")
            sys.exit(1)
        else:
            print(f"\n✅ 全テスト合格です。")

if __name__ == '__main__':
    main()
