#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""流入前提条件の監視チェッカー（cron 毎 run / 手動で実行）

「アクセスが無い」の再発防止として、検索流入の前提が壊れていないかを
外形監視する。標準ライブラリのみ。exit code は常に 0（監視であってゲートではない）。

Usage: python3 scripts/traffic_check.py
"""
import re
import subprocess
import sys

BASE = 'https://toknet.info'


def fetch(url, head=False):
    """(status_code, body) を返す。失敗時は (0, '')"""
    cmd = ['curl', '-sk', '--connect-timeout', '10', '-m', '20',
           '-o', '-', '-w', '\n__STATUS__%{http_code}', url]
    if head:
        cmd = ['curl', '-skI', '--connect-timeout', '10', '-m', '20',
               '-o', '-', '-w', '\n__STATUS__%{http_code}', url]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout
        body, _, status = out.rpartition('__STATUS__')
        return int(status.strip() or 0), body
    except Exception:
        return 0, ''


def main():
    results = []

    def check(name, ok, detail=''):
        mark = '✅' if ok else '❌'
        results.append(f"  {mark} {name}" + (f" — {detail}" if detail else ''))
        return ok

    # 1. www → apex 301（GSC 重複・DOMAIN ERROR インデックスの原因）
    status, body = fetch('https://www.toknet.info/', head=True)
    loc = re.search(r'(?im)^location:\s*(\S+)', body)
    check('www→apex 301', status in (301, 308) and loc and 'toknet.info' in loc.group(1),
          f"www が HTTP {status}（301 でなければ Cloudflare Redirect Rule 未設定）")

    # 2. 存在しないパスが 404 を返す（ソフト 404 の監視）
    status, _ = fetch(f'{BASE}/zzz-traffic-check-404/', head=True)
    check('404 ステータス', status == 404, f"未存在パスが HTTP {status}（200 なら dist/404.html 不在）")

    # 3. sitemap
    status, body = fetch(f'{BASE}/sitemap-0.xml')
    n_urls = len(re.findall(r'<url>', body))
    check('sitemap', status == 200 and n_urls > 0, f"{n_urls} URLs")
    www_leak = 'www.toknet.info' in body
    check('sitemap に www 混入なし', not www_leak)

    # 4. トップページの基本シグナル
    status, body = fetch(f'{BASE}/')
    check('トップ 200', status == 200, f"HTTP {status}")
    check('GA4 タグ', 'G-ZGT1S0ZHPR' in body)
    check('canonical apex', f'rel="canonical" href="{BASE}/"' in body)
    m = re.search(r'<title>([^<]*)</title>', body)
    title = m.group(1) if m else ''
    check('タイトルにブランド重複なし', title.count('AI共創レビュー研究所') <= 1, title[:60])

    # 5. robots.txt が検索を許可
    status, body = fetch(f'{BASE}/robots.txt')
    check('robots.txt 検索許可', status == 200 and 'search=yes' in body and 'Sitemap:' in body)

    print('📈 traffic_check:')
    print('\n'.join(results))
    ng = sum(1 for r in results if '❌' in r)
    print(f"  → {len(results) - ng}/{len(results)} OK" + ('' if ng == 0 else f"（❌ {ng} 件は run-log で報告すること）"))
    sys.exit(0)


if __name__ == '__main__':
    main()
