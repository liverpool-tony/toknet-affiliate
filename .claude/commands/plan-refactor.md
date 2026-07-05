フェーズ 2: 改善計画のみ（**実装はユーザーの GO までしない**）。

前提: `docs/refactor-audit-*.md` が存在する。無ければ先に `/audit` を提案。

1. 最新の audit を読む
2. `docs/improvement-plan-YYYY-MM-DD.md` を作成（P0/P1/P2、各項目に受け入れ条件）
3. 最初の 2 週間の PR 列（タイトル・変更ファイル・検証方法）
4. ユーザーに「GO で P0 の PR #1 から着手」と伝える

$ARGUMENTS: 計画のスコープ（例: `pipeline-only` / `astro-only`）