# Hermes 引き継ぎタスク（2026-07-07 Claude Code より）

> **2026-07-07 更新**: Task 1（PR マージ）と Task 2（検証）はユーザー承認のもと Claude Code が実施済み
> （PR #2〜#11 全マージ、traffic_check 8/9 OK、残 ❌ は www 301 = ユーザーのトークン権限待ちのみ）。
> **残タスクは Task 3（IG 画像の JPEG 差替え）、Task 4（IG 停止のユーザー確認）、Task 5（毎 run 監視）**。

> 実行者: Hermes（composer 2.5）。**このドキュメントを上から順に実行**する。
> 各コマンドは `~/Projects/toknet-affiliate` で実行。判断に迷ったら中断してユーザーに報告。
> 前提知識: `docs/repo-structure.md`（未マージなら PR #4 の Files タブで読める）と skill `toknet-affiliate-pipeline`。

## 実行条件

- [ ] cron 実行時刻（08:30–08:45 / 20:30–20:45 JST）を避ける
- [ ] `git -C ~/Projects/toknet-affiliate branch --show-current` が `main` であること（違えば checkout main）
- [ ] 開始時に `git stash list` を確認し、`WIP on fix/` や `WIP on feat/` があれば**触らずユーザーに報告**（Claude Code の作業残骸の可能性）

## Task 1: PR を順番にマージ（レビュー済み前提。ユーザーから本タスクの依頼があった時点で承認とみなす）

**この順番厳守**（#2 が後続の前提になるため）:

```bash
cd ~/Projects/toknet-affiliate
for pr in 2 3 4 5 6 7 8 9 10 11; do
  gh pr merge $pr --rebase --delete-branch || echo "PR #$pr マージ失敗 → 記録して次へ"
done
```

- マージ失敗（コンフリクト）した PR は**スキップして番号を報告**（無理に解決しない）
- 全マージ後、ローカル 2 checkout を同期:

```bash
git stash && git pull --rebase origin main && git stash pop || true
git -C astro stash && git -C astro pull --rebase origin main && git -C astro stash pop || true
```

## Task 2: マージ後の検証

```bash
python3 scripts/validate_x_search_trends.py        # exit 0
python3 scripts/pipeline.py --dry-run              # exit 0、「全ステップ正常完了」
cd astro && npm run build && cd ..                 # 成功（192 pages 前後）
```

CI デプロイ（push で自動）完了の 3 分後に本番確認:

```bash
curl -sk -o /dev/null -w '%{http_code}\n' https://toknet.info/zzz-404-test/      # 期待: 404（PR #6 の効果）
curl -sk -o /dev/null -w '%{http_code}\n' https://toknet.info/category/wearable/ # 期待: 200（PR #2 の効果）
```

次回 FULL RUN の run-log で以下を確認して報告:
- `Building (always rebuild before deploy)` が出る（PR #3）
- デプロイ直後に新記事 URL が 200（従来は次 run まで未反映）
- `⚠️ カテゴリ判定: キーワード未マッチ` が出たらタグを報告（キーワード辞書追加の材料）

## Task 3: Instagram 投稿画像を JPEG に差替え（実装、30 分）

根拠: `docs/instagram-recovery.md`（公式は JPEG のみサポート。現行 og-default.png が code 9004 の有力原因）

1. `public/og-default.png` から JPEG を生成: `astro/public/ig-default.jpg`（sharp が依存にある: `npx sharp-cli` か Python PIL は無いので `sips -s format jpeg astro/public/og-default.png --out astro/public/ig-default.jpg`）
2. ルート `public/` にも同じファイルを置く（二重 clone のため両方）
3. `scripts/pipeline.py` の `image_url = "https://toknet.info/og-default.png"` を `https://toknet.info/ig-default.jpg` に変更
4. dry-run 確認 → 通常の push 手順でコミット（`fix(instagram): 投稿画像を JPEG に差替え (9004対策)`）

## Task 4: Instagram API 投稿の一時停止（**ユーザー確認必須 — 勝手に実施しない**）

`docs/instagram-recovery.md` の復旧手順: action block 中に API を叩き続けると延長されるため、**7〜14 日の投稿停止を推奨**。ユーザーが承認したら cron run では `--skip-post` を使うか、Instagram ステップのみスキップし、run-log に「IG 停止中 (day N)」と記録。

## Task 5: 流入前提の監視（毎 run、恒久タスク）

毎 run の Step として `python3 scripts/traffic_check.py` を実行し、❌ があれば run-log に転記する。
特に以下の 2 件は 2026-07-07 時点で既知の未解決（解消したら報告）:
- `www→apex 301` — ユーザーの GO 待ち（Cloudflare Redirect Rule）
- `404 ステータス` — PR #6 マージで解消

あわせて週 1 回、`site:toknet.info` の Bing/Google での件数を目視確認し報告（IndexNow は 2026-07-07 に 134 URL 送信済み。数日でBingに出始めるはず）。

## やらないこと（Claude Code 担当のため触らない）

- `scripts/trend_config.py` への設定集約・`tests/` 追加（改善計画 PR#5/#6）
- リポジトリ一本化（docs/repo-structure.md の移行手順）
- 未知のコンフリクト解決・force push

## 報告フォーマット（実行後にユーザーへ）

```
■ PR マージ: 成功 [#..]/失敗 [#..と理由]
■ 検証: dry-run / build / 404 / wearable の各結果
■ JPEG 差替え: コミットハッシュ
■ 次回 run で確認する項目: （上記 Task 2 後半）
■ 要ユーザー判断: IG 投稿停止の可否
```
