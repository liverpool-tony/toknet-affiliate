# Claude Code の起動手順

## 前提

- [Claude Code](https://code.claude.com/) インストール済み（`claude --version`）
- 認証済み（`claude auth status`）

## 初回（このリポジトリ）

`CLAUDE.md` と `.claude/` は既に用意済み。**`/init` は不要**（上書きしたくない場合は実行しない）。

```bash
cd ~/Projects/toknet-affiliate
claude
```

初回のみワークスペース信頼ダイアログ → **Yes**。

## 推奨フロー

| 順番 | 操作 |
|------|------|
| 1 | `/audit` または「フェーズ1: 監査のみ。docs/refactor-audit を作成」 |
| 2 | 計画レビュー後 `/plan-refactor` |
| 3 | ユーザーが **GO** と言ったら P0 から PR 単位で実装 |
| 随時 | `/verify` |

## 非対話（Hermes / スクリプトから）

```bash
cd ~/Projects/toknet-affiliate
claude -p 'フェーズ1監査のみ。docs/CLAUDE_CODE_BRIEF.md に従い refactor-audit を今日の日付で作成。コード変更禁止。' \
  --allowedTools 'Read,Write,Edit,Bash' --max-turns 25
```

## 作業ディレクトリ

必ず **リポジトリルート** `~/Projects/toknet-affiliate`。`astro/` だけを cwd にしない（パイプラインと submodule 操作のため）。

## 詳細

- 参画ブリーフ: [CLAUDE_CODE_BRIEF.md](./CLAUDE_CODE_BRIEF.md)
- 負債リスト: [improvement-backlog.md](./improvement-backlog.md)
- UAT: [uat-checklist.md](./uat-checklist.md)