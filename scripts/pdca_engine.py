#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PDCA Engine — toknet.info 自動改善エンジン

GA4データ + サイトコンテンツ監査 → 改善アクション提案 → 実行 → 効果測定

Modes:
    python3 pdca_engine.py audit          # コンテンツ監査（GA4不要）
    python3 pdca_engine.py analyze        # GA4分析（サービスアカウント必要）
    python3 pdca_engine.py report         # 統合レポート（監査+分析）
    python3 pdca_engine.py fix-categories # カテゴリ誤分類の自動修正
    python3 pdca_engine.py fix-titles     # タイトル改善提案
    python3 pdca_engine.py status         # 前回からの改善状況

PDCA Cycle:
    Plan:  GA4データ分析 → 問題特定（低トラフィック記事、誤分類、薄いコンテンツ）
    Do:    自動修正（カテゴリ、タイトル、メタディスクリプション）
    Check: 次回実行時にGA4データで効果測定
    Act:   成功パターンを次回の記事生成に反映
"""

import argparse, json, os, re, sys, glob
from datetime import datetime, timedelta, timezone
from pathlib import Path
from collections import Counter

JST = timezone(timedelta(hours=9))
PROJECT_DIR = Path(__file__).parent.parent
ARTICLES_DIR = PROJECT_DIR / "astro" / "src" / "content" / "articles"
PDCA_STATE_FILE = PROJECT_DIR / "scripts" / "data" / "pdca_state.json"

# カテゴリキーワード（pipeline.pyと同期）
CATEGORY_KEYWORDS = {
    "wearable": ["ウェアラブル", "スマートウォッチ", "スマートグラス", "スマートリング", "スマートバンド",
                  "AIペンダント", "AIグラス", "AIボイスレコーダー", "ボイスレコーダー",
                  "Apple Watch", "AppleWatch", "Galaxy Watch", "Pixel Watch", "Fitbit", "Garmin",
                  "XREAL", "Ray-Ban Meta", "骨伝導", "フィットネストラッカー", "Plaud", "NotePin",
                  "Metaグラス", "スマートグラス"],
    "laptop-pc": ["ノートPC", "ラップトップ", "MacBook", "ThinkPad", "Surface", "Chromebook",
                   "ゲーミングPC", "デスクトップ", "ミニPC"],
    "camera": ["カメラ", "デジカメ", "ミラーレス", "一眼レフ", "GoPro", "インカメ", "レンズ",
               "Polaroid", "ポラロイド", "インスタント", "フィルム", "アクションカメラ"],
    "audio-headphones": ["ヘッドホン", "イヤホン", "スピーカー", "DAC", "アンプ", "ワイヤレス",
                          "ノイズキャンセリング", "オープンイヤー", "TWS", "AirPods", "earbuds"],
    "smart-home": ["スマートホーム", "IoT", "スマートスピーカー", "Alexa", "Google Home",
                    "HomePod", "センサー", "Roku", "FireTV", "Chromecast", "AppleTV", "ストリーミング"],
    "home-appliances": ["家電", "洗濯機", "冷蔵庫", "掃除機", "ルンバ", "ダイソン", "炊飯器",
                         "電子レンジ", "エアコン", "空気清浄機", "加湿器"],
    "monitors": ["モニター", "ディスプレイ", "4K", "ゲーミングモニター", "ウルトラワイド", "曲面"],
    "diy-pc": ["自作PC", "グラボ", "GPU", "CPU", "マザーボード", "メモリ", "SSD", "電源", "RTX", "GeForce"],
    "gaming": ["ゲーミング", "Switch", "PS5", "Xbox", "Steam", "ゲーム", "Nintendo", "SteamDeck"],
    "smartphone": ["iPhone", "Android", "スマホ", "Galaxy", "Pixel", "Xperia", "スマートフォン",
                    "タブレット", "iPad"],
    "software": ["ソフトウェア", "アプリ", "AI", "クラウド", "SaaS", "ツール", "サービス",
                  "Cursor", "VSCode", "Docker", "NotebookLM", "翻訳", "音声クローン"],
}

# 記事タイプ分類
ARTICLE_TYPES = {
    "trend_auto": r"^\d{8}-",  # 自動生成トレンド記事
    "static_review": r"^[a-z]",  # 手書きレビュー
}


def load_articles():
    """全記事のfrontmatterをパース"""
    articles = []
    for f in sorted(ARTICLES_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8")
        # frontmatter抽出
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
        if not m:
            continue
        fm_text, body = m.group(1), m.group(2)
        fm = {}
        for line in fm_text.splitlines():
            if ":" in line:
                key, _, val = line.partition(":")
                fm[key.strip()] = val.strip().strip('"').strip("'")
        articles.append({
            "file": str(f),
            "filename": f.name,
            "title": fm.get("title", ""),
            "description": fm.get("description", ""),
            "category": fm.get("category", ""),
            "tags": fm.get("tags", ""),
            "pubDate": fm.get("pubDate", ""),
            "body_length": len(body),
            "body_words": len(body.split()),
            "is_auto": bool(re.match(r"^\d{8}-", f.name)),
            "products": fm.get("products", ""),
        })
    return articles


def detect_correct_category(article):
    """記事のタイトル・タグ・本文から正しいカテゴリを推定"""
    text = f"{article['title']} {article['tags']} {article['description']}".lower()
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[cat] = score
    if not scores:
        return None
    return max(scores, key=scores.get)


def audit_content(articles=None):
    """コンテンツ監査 — 問題点を検出"""
    if articles is None:
        articles = load_articles()

    issues = {
        "miscategorized": [],
        "thin_content": [],
        "generic_titles": [],
        "missing_description": [],
        "duplicate_topics": [],
        "category_distribution": {},
        "auto_vs_static": {"auto": 0, "static": 0},
        "total": len(articles),
    }

    title_patterns = Counter()

    for a in articles:
        # 1. カテゴリ誤分類チェック
        correct = detect_correct_category(a)
        if correct and correct != a["category"]:
            issues["miscategorized"].append({
                "file": a["filename"],
                "current": a["category"],
                "suggested": correct,
                "title": a["title"][:60],
            })

        # 2. 薄いコンテンツ（自動記事で2000字未満）
        if a["is_auto"] and a["body_length"] < 2000:
            issues["thin_content"].append({
                "file": a["filename"],
                "length": a["body_length"],
                "title": a["title"][:60],
            })

        # 3. 汎用的すぎるタイトル
        if "SNSで話題" in a["title"] or "徹底レビュー" in a["title"]:
            issues["generic_titles"].append({
                "file": a["filename"],
                "title": a["title"],
            })
            # タイトルパターン抽出
            pattern = re.sub(r"「[^」]+」", "「X」", a["title"])
            pattern = re.sub(r"\d{4}年\d{2}月\d{2}日", "DATE", pattern)
            title_patterns[pattern] += 1

        # 4. description欠落
        if not a["description"] or len(a["description"]) < 20:
            issues["missing_description"].append({
                "file": a["filename"],
                "title": a["title"][:60],
            })

        # 5. カテゴリ分布
        cat = a["category"] or "unknown"
        issues["category_distribution"][cat] = issues["category_distribution"].get(cat, 0) + 1

        # 6. auto/static分類
        if a["is_auto"]:
            issues["auto_vs_static"]["auto"] += 1
        else:
            issues["auto_vs_static"]["static"] += 1

    issues["title_patterns"] = dict(title_patterns.most_common(10))

    # 重複トピック検出（同じタグが複数記事で使われている）
    tag_articles = {}
    for a in articles:
        if a["is_auto"]:
            # タグからトピック抽出
            tags = re.findall(r'"([^"]+)"', a["tags"])
            if tags:
                primary = tags[0].lower()
                tag_articles.setdefault(primary, []).append(a["filename"])

    for tag, files in tag_articles.items():
        if len(files) >= 3:
            issues["duplicate_topics"].append({
                "tag": tag,
                "count": len(files),
                "files": files[:5],
            })

    return issues


def fix_categories(articles=None, dry_run=True):
    """カテゴリ誤分類の自動修正"""
    if articles is None:
        articles = load_articles()

    fixes = []
    for a in articles:
        correct = detect_correct_category(a)
        if correct and correct != a["category"]:
            fixes.append({
                "file": a["file"],
                "filename": a["filename"],
                "old": a["category"],
                "new": correct,
                "title": a["title"][:60],
            })
            if not dry_run:
                text = Path(a["file"]).read_text(encoding="utf-8")
                text = text.replace(
                    f'category: "{a["category"]}"',
                    f'category: "{correct}"',
                    1
                )
                Path(a["file"]).write_text(text, encoding="utf-8")

    return fixes


def generate_title_suggestions(articles=None):
    """タイトル改善提案"""
    if articles is None:
        articles = load_articles()

    suggestions = []
    for a in articles:
        if not a["is_auto"]:
            continue
        title = a["title"]
        if "SNSで話題" not in title:
            continue

        # タグ抽出
        tags = re.findall(r'"([^"]+)"', a["tags"])
        topic = tags[0] if tags else "商品"

        # 日付抽出
        date_m = re.search(r"(\d{4})年(\d{2})月(\d{2})日", title)
        date_str = f"{date_m.group(1)}年{date_m.group(2)}月{date_m.group(3)}日" if date_m else ""

        # 改善パターン
        new_titles = [
            f"【{date_str}】{topic}のおすすめ5選｜価格・性能を比較",
            f"{topic}は買い？最新トレンドとおすすめモデルを徹底比較",
            f"【最新】{topic}の人気モデル比較｜用途別おすすめガイド",
        ]

        suggestions.append({
            "file": a["filename"],
            "current": title,
            "suggestions": new_titles,
        })

    return suggestions


def load_pdca_state():
    """前回のPDCA状態を読み込み"""
    if PDCA_STATE_FILE.exists():
        return json.loads(PDCA_STATE_FILE.read_text(encoding="utf-8"))
    return None


def save_pdca_state(state):
    """PDCA状態を保存"""
    PDCA_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PDCA_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_report(audit_result, ga4_data=None):
    """統合PDCAレポート生成"""
    now = datetime.now(JST)
    lines = []
    lines.append(f"🔄 toknet.info PDCAレポート")
    lines.append(f"生成: {now.strftime('%Y-%m-%d %H:%M JST')}")
    lines.append("=" * 55)

    # --- Plan: 現状分析 ---
    lines.append(f"\n📋 PLAN（現状分析）")
    lines.append(f"  総記事数: {audit_result['total']}")
    lines.append(f"  自動記事: {audit_result['auto_vs_static']['auto']}")
    lines.append(f"  手書き記事: {audit_result['auto_vs_static']['static']}")
    lines.append(f"\n  カテゴリ分布:")
    for cat, count in sorted(audit_result["category_distribution"].items(), key=lambda x: -x[1]):
        pct = count / audit_result["total"] * 100
        bar = "█" * int(pct / 2)
        lines.append(f"    {cat:20s} {count:3d} ({pct:4.1f}%) {bar}")

    # --- 問題点 ---
    lines.append(f"\n⚠️ 検出された問題:")
    lines.append(f"  カテゴリ誤分類: {len(audit_result['miscategorized'])}件")
    lines.append(f"  薄いコンテンツ: {len(audit_result['thin_content'])}件")
    lines.append(f"  汎用タイトル: {len(audit_result['generic_titles'])}件")
    lines.append(f"  description不足: {len(audit_result['missing_description'])}件")
    lines.append(f"  重複トピック: {len(audit_result['duplicate_topics'])}件")

    if audit_result["miscategorized"]:
        lines.append(f"\n  【誤分類サンプル（上位5件）】")
        for m in audit_result["miscategorized"][:5]:
            lines.append(f"    {m['filename'][:50]}")
            lines.append(f"      {m['current']} → {m['suggested']}")

    # --- GA4データ ---
    if ga4_data:
        lines.append(f"\n📊 GA4データ（{ga4_data['period']['start']}〜{ga4_data['period']['end']}）")
        if "summary" in ga4_data:
            s = ga4_data["summary"]
            lines.append(f"  セッション: {s['sessions']}")
            lines.append(f"  ユーザー: {s['users']}")
            lines.append(f"  PV: {s['pageviews']}")
            lines.append(f"  直帰率: {s['bounce_rate']}%")
        if "changes" in ga4_data:
            c = ga4_data["changes"]
            lines.append(f"  前期比: セッション{c['sessions_pct']:+.1f}% ユーザー{c['users_pct']:+.1f}% PV{c['pageviews_pct']:+.1f}%")
        if ga4_data.get("top_pages"):
            lines.append(f"\n  【上位ページ】")
            for p in ga4_data["top_pages"][:5]:
                lines.append(f"    {p['path']}: {p['sessions']}セッション")
    else:
        lines.append(f"\n📊 GA4データ: 未取得（サービスアカウント未設定）")
        lines.append(f"  → ~/.hermes/ga4-service-account.json を設定すると有効化")

    # --- Do: 推奨アクション ---
    lines.append(f"\n🔧 DO（推奨アクション）")
    lines.append(f"  1. カテゴリ修正: {len(audit_result['miscategorized'])}件 → `python3 scripts/pdca_engine.py fix-categories`")
    lines.append(f"  2. タイトル改善: {len(audit_result['generic_titles'])}件 → 検索意図に合ったタイトルに変更")
    lines.append(f"  3. 記事の充実: 平均{sum(a['body_length'] for a in load_articles()) // max(len(load_articles()), 1)}字 → 3000字以上を目標")
    lines.append(f"  4. smartphone/softwareカテゴリ追加: iPhone/AI関連がlaptop-pcに誤分類")

    # --- Check: 前回比較 ---
    prev_state = load_pdca_state()
    if prev_state:
        lines.append(f"\n📈 CHECK（前回比較）")
        prev_issues = prev_state.get("issue_counts", {})
        curr_issues = {
            "miscategorized": len(audit_result["miscategorized"]),
            "thin_content": len(audit_result["thin_content"]),
            "generic_titles": len(audit_result["generic_titles"]),
        }
        for key in curr_issues:
            prev_val = prev_issues.get(key, "?")
            curr_val = curr_issues[key]
            if isinstance(prev_val, int):
                diff = curr_val - prev_val
                arrow = "✅" if diff < 0 else ("➡️" if diff == 0 else "⚠️")
                lines.append(f"  {arrow} {key}: {prev_val} → {curr_val} ({diff:+d})")
            else:
                lines.append(f"  {key}: {curr_val} (前回データなし)")

    # --- Act: 次回への反映 ---
    lines.append(f"\n🎯 ACT（次回への反映）")
    lines.append(f"  - pipeline.py の CATEGORY_MAP に smartphone/software カテゴリ追加")
    lines.append(f"  - 記事テンプレート: 「SNSで話題」→ 検索意図ベースのタイトルに変更")
    lines.append(f"  - 最低文字数: 2000字 → 3500字に引き上げ")

    # 状態保存
    save_pdca_state({
        "timestamp": now.isoformat(),
        "issue_counts": {
            "miscategorized": len(audit_result["miscategorized"]),
            "thin_content": len(audit_result["thin_content"]),
            "generic_titles": len(audit_result["generic_titles"]),
            "missing_description": len(audit_result["missing_description"]),
            "duplicate_topics": len(audit_result["duplicate_topics"]),
        },
        "category_distribution": audit_result["category_distribution"],
        "total_articles": audit_result["total"],
    })

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDCA Engine for toknet.info")
    parser.add_argument("mode", choices=["audit", "analyze", "report", "fix-categories", "fix-titles", "status"],
                        help="実行モード")
    parser.add_argument("--dry-run", action="store_true", default=True, help="修正を適用しない（デフォルト）")
    parser.add_argument("--apply", action="store_true", help="修正を適用する")
    parser.add_argument("--json", action="store_true", help="JSON出力")
    parser.add_argument("--output", type=str, help="出力ファイル")
    args = parser.parse_args()

    if args.mode == "audit":
        result = audit_content()
        if args.json:
            output = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            output = json.dumps(result, ensure_ascii=False, indent=2)
        print(output)

    elif args.mode == "analyze":
        try:
            from ga4_analyzer import analyze as ga4_analyze
            data = ga4_analyze(days=7, top_n=15, compare=True)
            print(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            print(f"GA4分析エラー: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.mode == "report":
        audit = audit_content()
        ga4_data = None
        try:
            from ga4_analyzer import analyze as ga4_analyze
            ga4_data = ga4_analyze(days=7, top_n=15, compare=True)
        except Exception:
            pass
        report = generate_report(audit, ga4_data)
        if args.output:
            Path(args.output).write_text(report, encoding="utf-8")
            print(f"✅ {args.output} に保存")
        else:
            print(report)

    elif args.mode == "fix-categories":
        dry = not args.apply
        fixes = fix_categories(dry_run=dry)
        print(f"{'[DRY RUN] ' if dry else ''}カテゴリ修正: {len(fixes)}件")
        for f in fixes:
            print(f"  {f['filename'][:50]}: {f['old']} → {f['new']}")
        if dry and fixes:
            print(f"\n適用するには: python3 scripts/pdca_engine.py fix-categories --apply")

    elif args.mode == "fix-titles":
        suggestions = generate_title_suggestions()
        print(f"タイトル改善提案: {len(suggestions)}件")
        for s in suggestions[:10]:
            print(f"\n  {s['file'][:50]}")
            print(f"  現在: {s['current']}")
            for i, t in enumerate(s["suggestions"], 1):
                print(f"  案{i}: {t}")

    elif args.mode == "status":
        state = load_pdca_state()
        if state:
            print(json.dumps(state, ensure_ascii=False, indent=2))
        else:
            print("PDCA状態なし（初回実行）")
