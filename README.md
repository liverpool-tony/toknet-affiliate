# AI共創レビュー研究所（toknet.info）

> AIと人間の共創による、透明性の高い商品レビュー・比較サイト
> https://toknet.info

## 構成

| レイヤ | 技術 | 場所 |
|--------|------|------|
| サイト | Astro 5（静的生成） | `src/`（記事: `src/content/articles/`） |
| パイプライン | Python 3（標準ライブラリのみ） | `scripts/`（エントリ: `pipeline.py`） |
| ホスティング | Cloudflare Pages | GitHub Actions（`.github/workflows/deploy.yml`）+ `scripts/deploy.py` |
| 運用 | Hermes cron（12h） | 手順: [docs/cron-agent.md](docs/cron-agent.md) |

⚠️ `astro/` は submodule ではなく**同一リポジトリの第 2 clone**です。詳細と一本化計画: [docs/repo-structure.md](docs/repo-structure.md)

## パイプライン

```text
トレンド収集（mstdn.jp / はてな / ITmedia / RSS / X search）
  → 記事生成（astro/src/content/articles/*.md）
  → ビルド & Cloudflare Pages デプロイ
  → SNS 投稿（Instagram / Mastodon）+ X 用テンプレート通知
```

```bash
python3 scripts/pipeline.py --dry-run   # テスト（デプロイ・投稿なし）
python3 scripts/pipeline.py             # 本番
python3 scripts/validate_x_search_trends.py  # X トレンド JSON の契約検証
```

## サイト開発

```bash
npm install
npm run dev     # 開発サーバー
npm run build   # ビルド（dist/）
```

## ドキュメント

- [docs/CLAUDE_CODE_BRIEF.md](docs/CLAUDE_CODE_BRIEF.md) — Claude Code 参画ブリーフ（起動手順は [docs/CLAUDE_CODE_INIT.md](docs/CLAUDE_CODE_INIT.md)）
- [docs/cron-agent.md](docs/cron-agent.md) — cron エージェント運用手順（正本）
- [docs/repo-structure.md](docs/repo-structure.md) — リポ構成の実態と一本化手順
- [docs/refactor-audit-2026-07-06.md](docs/refactor-audit-2026-07-06.md) — 監査（フェーズ 1）
- [docs/improvement-plan-2026-07-06.md](docs/improvement-plan-2026-07-06.md) — 改善計画（フェーズ 2）

## コンプライアンス（削除・弱化禁止）

- ファーストビューに PR / アフィリエイト明示、記事に AI 作成明示
- Amazon アソシエイト: `tag=toknet-22`、リンクに `rel="sponsored"`
- 導線: SNS → 記事 → Amazon（直リンク広告禁止）

## ライセンス

Private
