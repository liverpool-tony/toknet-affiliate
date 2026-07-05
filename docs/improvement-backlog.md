# 改善バックログ（要検証）

Claude Code の監査でコードと照合し、計画で優先度を再付けすること。

## P0 候補（構造・品質）

| ID | 問題 | 望ましい方向 | 主なファイル |
|----|------|--------------|--------------|
| B1 | `detect_category()` がウェアラブル・AI レコーダー等を `laptop-pc` に落とす | `wearable` 等の CATEGORY_MAP、サイト category ページと整合 | `scripts/pipeline.py`, `astro/src/pages/category/` |
| B2 | `pipeline.py` モノリス（収集・生成・デプロイ・SNS） | `trends/` `content/` `publish/` 等へ分割、CLI は薄く | `scripts/pipeline.py` |
| B3 | 記事生成後の git commit がパイプラインにない | オプション `--commit` または post-step ドキュメント＋スクリプト | `scripts/pipeline.py`, `docs/` |
| B4 | `validate_x_search_trends.py` が repo に無いことがある | `scripts/` に常設、dry-run 前に呼べる | `scripts/` |
| B5 | ルート `src/content/articles/` と `astro/` の二重パス | 書き込み先一本化、レガシー削除 or ガード | `scripts/pipeline.py`, `src/` |

## P1 候補（保守性）

| ID | 問題 | 望ましい方向 |
|----|------|--------------|
| B6 | META_TAGS / KNOWN_FUN_TAGS の巨大インライン集合 | YAML/JSON 設定 + テスト |
| B7 | mstdn / RSS / タグ正規化のエッジケース（case, 短英字タグ） | `trend_collector.py` の単体テスト + フィクスチャ |
| B8 | Instagram: リモート OGP・code 4/9004 | ローカル取得アップロード等（API 調査付き） | `instagram_poster.py` |
| B9 | Engadget/Hatena RSS が常に 0 件の報告 | `multi_trend_collector.py` の fetch 診断・フォールバック |
| B10 | cron エージェント向けドキュメントが repo 外 skill のみ | `docs/cron-agent.md`（x_search JSON 手順、報告ルール） |

## P2 候補（UX / SEO）

| ID | 問題 | 望ましい方向 |
|----|------|--------------|
| B11 | GSC 重複・リダイレクト（www/apex） | canonical・`astro.config`・Cloudflare ルールの一貫性 |
| B12 | 記事テンプレートの品質（キーワードノイズ） | `filter_product_keywords()` 強化 |
| B13 | UAT 自動化 | `scripts/uat_check.py`（HTTP、meta、build） |
| B14 | README と実ディレクトリの不一致 | README 更新 |

## 検証コマンド

```bash
cd ~/Projects/toknet-affiliate
python3 scripts/pipeline.py --dry-run
cd astro && npm run build
```

## 参照（Hermes skill 要約）

- X JSON: `{"items": [...], "collected_at": "..."}` のみ有効
- Submodule push: astro 先 → 親で pointer 更新 → rebase 必要時あり