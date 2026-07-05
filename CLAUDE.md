# toknet.info（AI共創レビュー研究所）

Hermes が運用、cron、日次メンテを担当。このリポジトリでは **リファクタ・改善計画・小さな PR** に集中する。

## 作業ディレクトリ

```text
~/Projects/toknet-affiliate   # 常にここを cwd にする（親リポジトリ）
```

サイト本体は **`astro/`（git submodule）**。記事・レイアウトは `astro/src/`。パイプラインはルートの **`scripts/`**。

## 最初に読む

1. `docs/CLAUDE_CODE_BRIEF.md` — 参画依頼・成果物・制約の全文
2. `docs/improvement-backlog.md` — 技術的負債の優先リスト

## 検証（変更のたびに）

```bash
python3 scripts/pipeline.py --dry-run
cd astro && npm run build
```

任意: `cd astro && npx tsc --noEmit --skipLibCheck`

## 秘密情報

- **読まない・コミットしない**: `~/.hermes/.env`、任意の `.env`、トークン・API キー
- パイプラインは Python で `~/.hermes/.env` を読む設計。ローカル検証はユーザーが env を用意する

## ユーザー（渡邉雄太）

- 報告は **日本語**。結論 → 次アクション
- 大きな変更は **UAT 案を先に提示** → 承認後実装（`docs/uat-checklist.md`）
- 「**GO**」= 確認なしで実行。中間失敗は黙ってリトライし最終結果のみ

## フェーズ

| フェーズ | やること |
|----------|----------|
| 1 監査 | `docs/refactor-audit-YYYY-MM-DD.md` のみ（コード変更なし） |
| 2 計画 | `docs/improvement-plan-YYYY-MM-DD.md`（P0/P1/P2、2 週間の PR 列） |
| 3 実装 | ユーザーが GO した項目から。1 PR = 1 論点 |

スラッシュ: `/verify` `/audit` `/plan-refactor`

## Git（submodule）

記事は `astro/src/content/articles/`。push 手順:

```bash
cd astro && git add -A && git commit -m "..." && git push origin main
cd .. && git add astro && git commit -m "chore: update astro submodule" && git push origin main
```

reject 時: `git pull --rebase origin main` → push。unstaged キャッシュがあるときは `git stash` してから rebase。

## 壊さない契約

- 本番は `python3 scripts/pipeline.py`（`deploy.py` 単体はデバッグ用）
- X トレンド JSON は **`scripts/data/x_search_trends.json` の `items` キー**（`results` は無効）
- `astro/src/content/config.ts`: `products[].rating` は **nullable**
- 正規 URL: `https://toknet.info`（Amazon 登録は www だがサイト canonical は apex）
- Amazon: `tag=toknet-22`。コンプライアンス（PR 表記・AI 明示）は `astro` レイアウトで維持

## リポジトリ

`https://github.com/liverpool-tony/toknet-affiliate`