フェーズ 1: 監査のみ（**アプリコードは変更しない**）。

1. `docs/CLAUDE_CODE_BRIEF.md` と `docs/improvement-backlog.md` を読む
2. `scripts/pipeline.py`、`multi_trend_collector.py`、`trend_collector.py`、`astro/src/content/config.ts`、主要 layouts を読む
3. バックログ B1–B14 を grep/読取で検証し、今日の日付で `docs/refactor-audit-YYYY-MM-DD.md` を新規作成
4. 完了後、P0 推奨 3 件を 1 段落ずつ要約（まだ実装しない）

$ARGUMENTS があれば、監査の焦点をそこに当てる（例: `category` / `instagram` / `tests`）。