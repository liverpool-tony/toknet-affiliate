# Claude Code 参画ブリーフ — toknet.info

> ルートの `CLAUDE.md` から参照。`cd ~/Projects/toknet-affiliate && claude` でこのプロジェクトを開けば自動読み込みされる。

## 役割

- コードベース監査、改善計画（優先度付き）、小さな PR 単位のリファクタ
- Hermes（別エージェント）が 12h cron・META_TAGS 即時追加・運用 run-log を継続。**構造改善と技術的負債解消**に専念

## プロジェクト概要

| 項目 | 内容 |
|------|------|
| サイト | https://toknet.info（canonical apex） |
| コンセプト | AI×人間の透明な商品レビュー（体験・選び方・比較）。旧「価格比較」モデルは避ける |
| スタック | Astro 5（`astro/`）、Python `scripts/`、Cloudflare Pages、GA4 `G-GKJN4ZB5SV` |
| Amazon | トラッキング ID `toknet-22`、登録ドメイン `www.toknet.info` |
| リポジトリ | `liverpool-tony/toknet-affiliate`、`astro/` は submodule |

## ディレクトリ（実態）

```text
~/Projects/toknet-affiliate/
├── scripts/
│   ├── pipeline.py              # 統合エントリ
│   ├── multi_trend_collector.py
│   ├── trend_collector.py
│   ├── deploy.py, instagram_poster.py, mastodon_poster.py
│   └── data/                    # キャッシュ（*.json は .gitignore 一部）
├── astro/                       # 本番サイト（記事: astro/src/content/articles/）
├── src/content/articles/        # レガシー重複の可能性（パイプラインは astro のみ）
└── docs/                        # 監査・計画・UAT
```

## パイプライン契約

1. `python3 scripts/pipeline.py --dry-run` → 問題なければ本番（引数なし）
2. トレンド: mstdn.jp → RSS → keyword fallback + `x_search_trends.json`（`items` 配列）
3. `source .env` 禁止。シェルで `.env` を grep/cut しない（特殊文字で壊れる）
4. FULL RUN 後、記事の **git commit は pipeline が行わない**（cron/Hermes が手動。自動化は改善候補）

## 成果物（順序厳守）

### フェーズ 1 — 監査のみ

`docs/refactor-audit-YYYY-MM-DD.md`

- アーキテクチャ（テキスト図可）
- テスト・CI の有無
- `docs/improvement-backlog.md` の各項目をコード上で検証（推測は「要確認」）

**このフェーズではアプリコードを変更しない。**

### フェーズ 2 — 計画

`docs/improvement-plan-YYYY-MM-DD.md`

- P0 / P1 / P2（目的・範囲・リスク・受け入れ条件）
- 最初の 2 週間でマージする PR の列（1 PR = 1 論点）
- P0 を 3 件に絞った推奨

**ユーザーの GO まで実装しない。**

### フェーズ 3 — 実装

- 各 PR 後: `pipeline.py --dry-run` + `cd astro && npm run build`
- PR 説明は日本語推奨

## コンプライアンス（削除・弱化禁止）

- ファーストビュー: PR / アフィリエイト / AI 作成の明示（Amazon 2026/04）
- 導線: SNS → 記事 → Amazon（直リンク広告禁止）
- ステマ規制: 目立つ表記

## Hermes との分担

| Hermes | Claude Code |
|--------|-------------|
| cron、即時 META_TAGS、x_search JSON | 設定の単一化、テスト、モジュール分割 |
| skill / run-log | `docs/` とコードの同期 |
| 運用レポート | PR・監査ドキュメント |

詳細運用は Hermes 側 skill `toknet-affiliate-pipeline`（リポジトリ外）にあり。矛盾時は **リポジトリのコードを正**とし、skill の「pending-code-changes」を計画に取り込む。

## ブロック時のみ質問

それ以外は監査・計画を進め、不明点はドキュメントに「要確認」と書く。