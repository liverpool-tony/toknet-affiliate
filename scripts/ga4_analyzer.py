#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GA4 Data API アナライザー — toknet.info 用
サービスアカウントJSONで認証し、ページ別・期間別のトラフィックデータを取得。

Usage:
    python3 ga4_analyzer.py                    # 直近7日間のサマリー
    python3 ga4_analyzer.py --days 30          # 直近30日間
    python3 ga4_analyzer.py --top 20           # 上位20ページ
    python3 ga4_analyzer.py --json             # JSON出力（PDCAエンジン用）
    python3 ga4_analyzer.py --compare          # 前期比較

前提:
    1. Google Cloud Console でサービスアカウント作成
    2. GA4 プロパティ (G-ZGT1S0ZHPR) に「閲覧者」権限で追加
    3. サービスアカウントJSONを ~/.hermes/ga4-service-account.json に保存
    4. pip install google-analytics-data
"""

import argparse, json, os, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
PROPERTY_ID = "properties/472074982"  # G-ZGT1S0ZHPR に対応（要確認）
SA_JSON_PATH = Path.home() / ".hermes" / "ga4-service-account.json"

def get_client():
    """サービスアカウントでGA4 Data APIクライアントを生成"""
    try:
        from google.analytics.data_v1beta import BetaAnalyticsDataClient
        from google.oauth2 import service_account
    except ImportError:
        print("ERROR: google-analytics-data 未インストール", file=sys.stderr)
        print("  pip3 install google-analytics-data", file=sys.stderr)
        sys.exit(1)

    if not SA_JSON_PATH.exists():
        print(f"ERROR: サービスアカウントJSONが見つからない: {SA_JSON_PATH}", file=sys.stderr)
        print("設定手順:", file=sys.stderr)
        print("  1. https://console.cloud.google.com/apis/credentials → サービスアカウント作成", file=sys.stderr)
        print("  2. 「Analytics Data API」を有効化", file=sys.stderr)
        print("  3. JSONキーをダウンロード → ~/.hermes/ga4-service-account.json に保存", file=sys.stderr)
        print("  4. GA4管理 → プロパティアクセス管理 → サービスアカウントメールを「閲覧者」で追加", file=sys.stderr)
        sys.exit(1)

    credentials = service_account.Credentials.from_service_account_file(
        str(SA_JSON_PATH),
        scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )
    return BetaAnalyticsDataClient(credentials=credentials)


def run_report(client, property_id, dimensions, metrics, date_ranges, order_bys=None, limit=100):
    """GA4レポート実行"""
    from google.analytics.data_v1beta.types import (
        RunReportRequest, Dimension, Metric, DateRange, OrderBy, DimensionOrderBy
    )

    request = RunReportRequest(
        property=property_id,
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=[DateRange(start_date=dr[0], end_date=dr[1]) for dr in date_ranges],
        limit=limit,
    )
    if order_bys:
        request.order_bys = order_bys

    response = client.run_report(request)
    rows = []
    for row in response.rows:
        d = {dim.name: val.value for dim, val in zip(response.dimension_headers, row.dimension_values)}
        m = {met.name: val.value for met, val in zip(response.metric_headers, row.metric_values)}
        rows.append({"dimensions": d, "metrics": m})
    return rows


def analyze(days=7, top_n=10, compare=False):
    """メイン分析"""
    client = get_client()
    now = datetime.now(JST)
    end = now.strftime("%Y-%m-%d")
    start = (now - timedelta(days=days)).strftime("%Y-%m-%d")

    result = {
        "generated_at": now.isoformat(),
        "period": {"start": start, "end": end, "days": days},
        "property": "G-ZGT1S0ZHPR",
    }

    # 1. 全体サマリー
    summary = run_report(
        client, PROPERTY_ID,
        dimensions=[],
        metrics=["sessions", "totalUsers", "screenPageViews", "averageSessionDuration", "bounceRate"],
        date_ranges=[(start, end)]
    )
    if summary:
        s = summary[0]["metrics"]
        result["summary"] = {
            "sessions": int(s.get("sessions", 0)),
            "users": int(s.get("totalUsers", 0)),
            "pageviews": int(s.get("screenPageViews", 0)),
            "avg_session_duration_sec": round(float(s.get("averageSessionDuration", 0)), 1),
            "bounce_rate": round(float(s.get("bounceRate", 0)) * 100, 1),
        }

    # 2. ページ別トップ
    pages = run_report(
        client, PROPERTY_ID,
        dimensions=["pagePath", "pageTitle"],
        metrics=["sessions", "totalUsers", "screenPageViews", "averageSessionDuration"],
        date_ranges=[(start, end)],
        limit=top_n,
    )
    result["top_pages"] = [
        {
            "path": p["dimensions"]["pagePath"],
            "title": p["dimensions"]["pageTitle"],
            "sessions": int(p["metrics"]["sessions"]),
            "users": int(p["metrics"]["totalUsers"]),
            "pageviews": int(p["metrics"]["screenPageViews"]),
            "avg_duration_sec": round(float(p["metrics"]["averageSessionDuration"]), 1),
        }
        for p in pages
    ]

    # 3. トラフィックソース
    sources = run_report(
        client, PROPERTY_ID,
        dimensions=["sessionDefaultChannelGroup"],
        metrics=["sessions", "totalUsers"],
        date_ranges=[(start, end)],
    )
    result["traffic_sources"] = [
        {
            "channel": s["dimensions"]["sessionDefaultChannelGroup"],
            "sessions": int(s["metrics"]["sessions"]),
            "users": int(s["metrics"]["totalUsers"]),
        }
        for s in sources
    ]

    # 4. 日別トレンド
    daily = run_report(
        client, PROPERTY_ID,
        dimensions=["date"],
        metrics=["sessions", "totalUsers", "screenPageViews"],
        date_ranges=[(start, end)],
        limit=days,
    )
    result["daily_trend"] = [
        {
            "date": d["dimensions"]["date"],
            "sessions": int(d["metrics"]["sessions"]),
            "users": int(d["metrics"]["totalUsers"]),
            "pageviews": int(d["metrics"]["screenPageViews"]),
        }
        for d in sorted(daily, key=lambda x: x["dimensions"]["date"])
    ]

    # 5. 前期比較
    if compare:
        prev_end = (now - timedelta(days=days)).strftime("%Y-%m-%d")
        prev_start = (now - timedelta(days=days * 2)).strftime("%Y-%m-%d")
        prev = run_report(
            client, PROPERTY_ID,
            dimensions=[],
            metrics=["sessions", "totalUsers", "screenPageViews"],
            date_ranges=[(prev_start, prev_end)]
        )
        if prev:
            p = prev[0]["metrics"]
            result["previous_period"] = {
                "period": {"start": prev_start, "end": prev_end},
                "sessions": int(p.get("sessions", 0)),
                "users": int(p.get("totalUsers", 0)),
                "pageviews": int(p.get("screenPageViews", 0)),
            }
            if result.get("summary"):
                cur = result["summary"]
                prev_s = result["previous_period"]
                result["changes"] = {
                    "sessions_pct": round((cur["sessions"] - prev_s["sessions"]) / max(prev_s["sessions"], 1) * 100, 1),
                    "users_pct": round((cur["users"] - prev_s["users"]) / max(prev_s["users"], 1) * 100, 1),
                    "pageviews_pct": round((cur["pageviews"] - prev_s["pageviews"]) / max(prev_s["pageviews"], 1) * 100, 1),
                }

    # 6. イベント（Amazonクリック等）
    try:
        events = run_report(
            client, PROPERTY_ID,
            dimensions=["eventName"],
            metrics=["eventCount"],
            date_ranges=[(start, end)],
            limit=20,
        )
        result["events"] = [
            {"name": e["dimensions"]["eventName"], "count": int(e["metrics"]["eventCount"])}
            for e in events
        ]
    except Exception:
        result["events"] = []

    return result


def format_text_report(data):
    """人間が読めるテキストレポート"""
    lines = []
    lines.append(f"📊 toknet.info GA4分析レポート")
    lines.append(f"期間: {data['period']['start']} 〜 {data['period']['end']} ({data['period']['days']}日間)")
    lines.append("=" * 50)

    if "summary" in data:
        s = data["summary"]
        lines.append(f"\n【全体サマリー】")
        lines.append(f"  セッション: {s['sessions']}")
        lines.append(f"  ユーザー数: {s['users']}")
        lines.append(f"  ページビュー: {s['pageviews']}")
        lines.append(f"  平均滞在時間: {s['avg_session_duration_sec']}秒")
        lines.append(f"  直帰率: {s['bounce_rate']}%")

    if "changes" in data:
        c = data["changes"]
        lines.append(f"\n【前期比較】")
        lines.append(f"  セッション: {c['sessions_pct']:+.1f}%")
        lines.append(f"  ユーザー: {c['users_pct']:+.1f}%")
        lines.append(f"  PV: {c['pageviews_pct']:+.1f}%")

    if data.get("top_pages"):
        lines.append(f"\n【上位ページ TOP{len(data['top_pages'])}】")
        for i, p in enumerate(data["top_pages"], 1):
            lines.append(f"  {i}. {p['path']}")
            lines.append(f"     {p['title'][:50]}")
            lines.append(f"     セッション={p['sessions']} PV={p['pageviews']} 滞在={p['avg_duration_sec']}秒")

    if data.get("traffic_sources"):
        lines.append(f"\n【トラフィックソース】")
        for s in data["traffic_sources"]:
            lines.append(f"  {s['channel']}: {s['sessions']}セッション ({s['users']}ユーザー)")

    if data.get("events"):
        lines.append(f"\n【イベント】")
        for e in data["events"]:
            lines.append(f"  {e['name']}: {e['count']}回")

    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GA4 Analyzer for toknet.info")
    parser.add_argument("--days", type=int, default=7, help="分析期間（日数）")
    parser.add_argument("--top", type=int, default=10, help="上位ページ数")
    parser.add_argument("--json", action="store_true", help="JSON出力")
    parser.add_argument("--compare", action="store_true", help="前期比較")
    parser.add_argument("--output", type=str, help="出力ファイルパス")
    args = parser.parse_args()

    data = analyze(days=args.days, top_n=args.top, compare=args.compare)

    if args.json:
        output = json.dumps(data, ensure_ascii=False, indent=2)
    else:
        output = format_text_report(data)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"✅ {args.output} に保存")
    else:
        print(output)
