# Instagram 投稿の調査スパイクと復旧手順（B8）

> 作成: 2026-07-07（改善計画 PR#12、コード変更なし）
> 対象エラー: code 4 / subcode 2207051（action block、~24 日継続）、code 9004 / subcode 2207052（メディア取得失敗）

## 結論（TL;DR）

1. **「ローカル画像アップロード」は画像投稿では不可能** — Graph API の画像投稿は公開 URL（`image_url`）のみ。バイナリ/resumable アップロードは REELS（動画）専用。バックログ B8 の「ローカル取得アップロード」方針は**実装不能なので取り下げ**る。
2. **画像は JPEG のみサポート。現在 PNG を投稿しており、これが code 9004 の有力な根本原因** — `https://toknet.info/og-default.png` は `content-type: image/png`（実測 2026-07-07）。公式ドキュメント: 「JPEG is the only image format supported」。
3. **code 4 / 2207051 はアカウント側のスパム判定ブロック** — コードでは直らない。下記の復旧手順で解除を待つ。

## 調査結果詳細

### 画像の供給方法（Meta 公式ドキュメントより）

- 投稿フロー: `POST /{ig-user-id}/media`（`image_url` + `caption`）→ コンテナ → `media_publish`
- 「We cURL media used in publishing attempts, so the media must be hosted on a publicly accessible server」— **公開 URL 必須**
- resumable upload（`upload_type=resumable`、rupload.facebook.com）は `media_type=REELS` のみ
- **JPEG のみサポート**（MPO/JPS 等の拡張 JPEG も不可）
- API 投稿は **24 時間で 100 件**まで。現在の使用量は `GET /{ig-user-id}/content_publishing_limit` で取得可能

### code 9004 / subcode 2207052（"Only photo or video can be accepted as media type"）

Instagram 側が `image_url` の取得・解釈に失敗したときに出る。本サイトの要因候補（可能性順）:

1. **PNG である**（公式サポート外。通っていた時期があるのは content sniffing の気まぐれ）
2. デプロイ未完了のタイミングで投稿（URL が一時 404/5xx）— PR#3 の常時ビルド化で悪化しない
3. `x-content-type-options: nosniff` ヘッダとの組み合わせで PNG が弾かれやすい

### code 4 / subcode 2207051（action block）

- 意味: 「投稿アクションがスパムと疑われている」— アカウント/アプリ単位の一時ブロック
- 本アカウントの状況: run-log 上 2026-06-07 頃から継続（コンテナ作成は成功、publish のみ失敗）
- 誘発要因（推定）: 定型キャプション + 同一画像（og-default.png）+ 12h 間隔の機械的投稿

## 推奨アクション

### 即効（次の実装 PR 候補、工数 30 分）

- [ ] `public/` に **JPEG 版の投稿用画像**（例 `ig-default.jpg`、1080×1080 推奨）を追加し、
      `pipeline.py:post_to_instagram` の `image_url` を差し替える（9004 対策）
- [ ] `instagram_poster.py` に `GET /content_publishing_limit` の残量ログを追加（診断向上）

### アカウント復旧（ユーザー操作、コード外）

1. **API 投稿を 7〜14 日完全停止**する（cron の Instagram ステップをスキップ。ブロック中に叩き続けると延長される）
2. Instagram アプリに当該アカウントでログインし、警告表示があれば「問題を報告」から異議申し立て
3. 停止期間中に**手動で 2〜3 件**、通常の投稿を行い健全なシグナルを作る
4. 再開時は **1 日 1 件**に減らし、キャプションのバリエーション（テンプレート複数化）を入れる
5. 2 週間安定したら 12h 間隔に戻すか判断

### 再発防止（P2 候補）

- キャプションテンプレートの複数化・記事固有要素の増量（定型度を下げる）
- 記事ごとの OGP 画像生成（同一画像の連投を避ける。Astro ビルド時に satori/sharp 等で生成）— 工数 0.5〜1 日

## 参考（一次情報）

- [Content Publishing — Meta for Developers](https://developers.facebook.com/docs/instagram-platform/content-publishing/)（公開 URL 必須・JPEG のみ・100 件/24h）
- [Resumable Uploads — Meta for Developers](https://developers.facebook.com/docs/instagram-platform/content-publishing/resumable-uploads/)（REELS 専用）
- [Error Codes — Meta for Developers](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/error-codes/)
- [ContentStudio: Instagram Errors While Publishing](https://docs.contentstudio.io/article/693-instagram-errors-while-publishing)（2207051 = spam 判定の解説）
