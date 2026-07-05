# UAT チェックリスト（変更前に案として提示）

ユーザー承認後に実装し、完了時に結果を報告する。

## 必須（毎回）

- [ ] `python3 scripts/pipeline.py --dry-run` — exit 0 または商品タグ 0 の既知 exit 1
- [ ] `cd astro && npm run build` — exit 0、ページ数が極端に減っていない

## フロント変更時

- [ ] トップ・記事 1 件・about が 200（ローカル `npm run dev` または build preview）
- [ ] `rel=canonical` が `https://toknet.info/...`（www 混在なし）
- [ ] PR / AI 表記がファーストビューに残っている（BaseLayout / ArticleLayout）
- [ ] 新規記事 frontmatter が `astro/src/content/config.ts` と整合（`rating` nullable 等）

## パイプライン変更時

- [ ] `--dry-run` ログに「選択タグ」が商品系であること（非商品なら META_TAGS 議論は別 PR）
- [ ] 記事出力パスが `astro/src/content/articles/` のみ
- [ ] `x_search_trends.json` を触る変更なら `items` キー形状のテスト or validate スクリプト

## デプロイ関連（ユーザーが GO した場合のみ）

- [ ] `scripts/deploy.py` はユーザー環境で実行（トークンはエージェントがログに出さない）

## レポート形式

```text
UAT: pipeline dry-run → OK/FAIL (要約1行)
UAT: astro build → OK/FAIL (ページ数)
その他: ...
```