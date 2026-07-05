リポジトリの検証のみ実行（変更はしない）。

1. `cd ~/Projects/toknet-affiliate`（またはプロジェクトルート）
2. `python3 scripts/pipeline.py --dry-run` — 終了コードと「選択タグ」行を要約
3. `cd astro && npm run build` — 終了コードとビルドされたページ数の目安を要約
4. 失敗時はログの最後 30 行相当を引用し、原因仮説を 1〜3 個

結果を日本語で短く報告する。