# cron エージェント運用手順（repo 内正本）

> 対象: 12h cron でパイプラインを実行するエージェント（現行: Hermes）。
> リポ外 skill（`toknet-affiliate-pipeline`）と矛盾する場合は**このドキュメントとリポジトリのコードが正**。
> 作成: 2026-07-07（改善計画 PR#11 / 監査 B10）

## 実行シーケンス

```bash
cd ~/Projects/toknet-affiliate

# Step 0: X トレンド JSON を書き、契約を検証する
#   書き込み先: scripts/data/x_search_trends.json（下記契約）
python3 scripts/validate_x_search_trends.py   # exit 0 を確認。1 なら書き直し

# Step 1: DRY RUN（選択タグの確認）
python3 scripts/pipeline.py --dry-run

# Step 2: 選択タグが非商品（企業名・抽象語・地名等）なら META_TAGS に追加して再 DRY RUN
#   編集先: scripts/multi_trend_collector.py の META_TAGS
#   （設定集約後は scripts/trend_config.py — 改善計画 PR#5 マージ後に読み替え）

# Step 3: FULL RUN
python3 scripts/pipeline.py            # 記事生成 → ビルド → デプロイ → SNS
#   ※ deploy.py は常にビルドしてからデプロイする（PR#3 以降）

# Step 4: commit & push
python3 scripts/pipeline.py は記事の commit を行わない（現行）。
#   手動手順（CLAUDE.md と同じ）:
cd astro && git add src/content/articles/<新記事>.md && git commit -m "feat: add ..." && git push origin main
cd .. && git add astro && git commit -m "chore: update astro submodule pointer" && git push origin main
#   reject 時: git stash（未追跡キャッシュ退避）→ git pull --rebase origin main → git push → git stash pop
#   （--commit オプション採用後（PR#10）は `python3 scripts/pipeline.py --commit` に置き換え可）
```

## X トレンド JSON の契約

`scripts/data/x_search_trends.json` **のみ**が有効な受け渡しファイル。

```json
{
  "items": [
    {"source": "x_search", "title": "…", "url": "https://…",
     "keywords": ["商品名1", "商品名2"], "score": 55}
  ],
  "collected_at": "2026-07-07T09:00:00+09:00"
}
```

- **`items` キー必須**。`results` / `trends` は無効（バリデータがエラーにする）
- 各 item: `keywords`（非空 list[str]）と `score`（数値）必須。`source`/`title`/`url` 推奨
- keywords は具体的な商品名・製品カテゴリのみ（META_TAGS 該当語は不可）
- **書き込み後に必ず読み戻して検証**（並行書き込みで UTF-8 が壊れた実績あり）。
  `python3 scripts/validate_x_search_trends.py` が U+FFFD 破損も検出する
- 別パス（`data/x_search_results.json` 等）への書き込みは無効 — パイプラインは読まない

## やってはいけないこと

- `source .env` / シェルでの `.env` パース（特殊文字で壊れる）。env は Python 側で読む
- `scripts/deploy.py` 単体を本番運用に使う（デバッグ用。正は `pipeline.py`）
- コンプライアンス要素（PR 表記・AI 明示・rel="sponsored"）の削除・弱化
- **このディレクトリのブランチを勝手に rebase/stash しない** — 人間/Claude Code の PR 作業ブランチが
  checkout されている場合がある。cron 開始時に `git branch --show-current` が main 以外なら
  main に checkout してから作業し、終了時の状態を run-log に残すこと

## 報告ルール（run-log）

毎 run 最低限:
- 選択タグ・score・source / 生成記事 slug と category（**mismatch があれば必ず記載**。
  `⚠️ カテゴリ判定: キーワード未マッチ` の警告行はそのまま転記）
- デプロイ結果（`Building (always rebuild before deploy)` の有無）
- Instagram 結果（エラー code/subcode/fbtrace_id）
- git push の結果（reject → リカバリした場合はその旨）
- META_TAGS / キーワード辞書に追加した語

## 既知のエラーパターン

| 症状 | 原因 | 対処 |
|------|------|------|
| Instagram code 4 (subcode 2207051) | アカウントの action block | コード側では直らない。ブロック解除待ち + 投稿間隔を空ける。`docs/instagram-recovery.md` 参照 |
| Instagram code 9004 (subcode 2207052) | OGP 画像 URL に Instagram が到達できない | デプロイ完了前に投稿している可能性。デプロイ後に十分待つ |
| RSS ソース 0 件 | フィード死亡 or キーワード全滅 | stderr の診断ログ（fetch失敗/パース失敗/形式不明）で切り分け |
| push reject | 並行 push | stash → pull --rebase → push → stash pop |
| 選択タグが非商品 | META_TAGS 未登録 | Step 2 の手順で追加 |
