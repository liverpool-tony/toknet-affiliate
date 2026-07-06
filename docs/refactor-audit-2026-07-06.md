# リファクタ監査 2026-07-06（フェーズ 1）

> 監査のみ。アプリコードは未変更。検証コマンド: 読取・grep・RSS疎通チェック（curl HEAD相当）のみ実行。

## 1. アーキテクチャ（実態）

```text
┌──────────────────────────── scripts/pipeline.py (1,027行・毎時cron) ────────────────────────────┐
│ Step1 収集         Step2 生成            Step3 デプロイ        Step4 SNS                        │
│ trend_collector ─┐                                                                              │
│ multi_trend_    ─┼→ detect_category() → deploy.py           → instagram_poster.py              │
│  collector       │   generate_article()   (wrangler pages     → mastodon_poster.py              │
│ keyword_history ─┘   → astro/src/content/  deploy, astro/dist) → Telegram(stdout)               │
│                        articles/*.md                                                            │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

astro/ (submodule, Astro 5 static)
  src/content/config.ts + utils.ts（getSortedPosts が両方に重複定義）
  src/layouts/{BaseLayout, ArticleLayout}.astro
  src/pages/{index, about, articles/[slug], category/[category]}.astro
  .github/workflows/deploy.yml → Cloudflare Pages "toknet-affiliate"

親リポジトリ（このリポ）
  src/ … astro/src の**ほぼ完全な複製**（197ファイル、git管理下、今日時点で diff なし）
  astro.config.mjs / package.json … ルート自体が独立した Astro サイトとしてビルド可能
  .github/workflows/deploy.yml → **同じ** Cloudflare Pages "toknet-affiliate" にデプロイ
```

**デプロイ経路が 3 本ある**（いずれも project-name=toknet-affiliate）:

1. ローカル `scripts/deploy.py`（pipeline Step3、astro/dist を deploy）
2. astro submodule の GitHub Actions（astro リポ push 時、astro/src からビルド）
3. 親リポジトリの GitHub Actions（親リポ push 時、**ルートの src/ 複製**からビルド）

経路 3 はルートの複製 `src/` を使うため、複製の同期が漏れた瞬間に**古い内容で本番を上書き**しうる。後述 B5。

## 2. テスト・CI の有無

| 項目 | 状況 |
|------|------|
| 単体テスト | **なし**（`tests/` ディレクトリ、pytest 設定とも存在しない） |
| E2E/UAT | `scripts/uat_test.py`（380行、本番URLへのHTTPチェック）のみ。ローカル検証には使えない |
| CI | 親・astro 双方に `deploy.yml`（ビルド+デプロイのみ）。**lint/test/型チェックのステップなし** |
| 型チェック | `npx tsc --noEmit` は手動運用（CLAUDE.md 記載）。CI 未組込 |

## 3. バックログ検証結果（B1–B14）

凡例: ✅ 確認（コードで裏付け） / ⚠️ 部分的に確認 / ❓ 要確認（コードだけでは断定不可）

### P0 候補

#### B1 ✅ `detect_category()` の laptop-pc 偏重 — **データで確認、想定より深刻**

- `scripts/pipeline.py:363-396`: `best_cat = 'laptop-pc'` がデフォルトで、スコア 0 の場合も最終行 `return best_cat if best_score > 0 else 'laptop-pc'` で laptop-pc に落ちる。ソフトウェア/AI 系タグ（`_SOFTWARE_AI`）も laptop-pc に統合。
- 実データ: 全 187 記事中 **148 件（79%）が `laptop-pc`**。`wearable` カテゴリは CATEGORY_MAP にもサイト側にも存在しない。
- **さらに悪いことに、カテゴリ slug がサイトと不整合**:
  - pipeline 側: `appliance` / `monitor`（`scripts/pipeline.py:51-52`）
  - サイト側: `home-appliances` / `monitors`（`astro/src/pages/category/[category].astro:6`）
  - 結果、`appliance` 6 件 + `monitor` 1 件 = **7 記事がどのカテゴリページにも載らず**、記事内パンくず（`[slug].astro:63` が `/category/{post.data.category}/` へ直リンク）は **404 リンク**になる。
  - 記事実データの category 内訳: laptop-pc 148 / camera 15 / audio-headphones 7 / gaming 6 / appliance 6 / monitors 2 / monitor 1 / home-appliances 1 / diy-pc 1（手動修正らしき `monitors`/`home-appliances` も混在 = 二重の表記ゆれ）。

#### B2 ✅ pipeline.py モノリス

- 1,027 行に収集・生成・デプロイ・SNS・重複判定・カテゴリ判定・テンプレートが同居。
- 正規化マップ `_JA_EN_MAP` が **3 箇所に重複定義**（`pipeline.py:134`、`trend_collector.py:241`、`multi_trend_collector.py:277`）。内容は微妙に違う（例: trend_collector 版のみ `ノートpc`・`腕時計` あり）。
- PRODUCT_KEYWORDS も `trend_collector.py:81` と `multi_trend_collector.py:27` に別内容で二重定義。片方だけ直す事故が構造的に起きる状態。

#### B3 ✅ 記事生成後の git commit がパイプラインにない

- `pipeline.py` に git 操作は一切なし（grep で確認）。FULL RUN 後のコミットは Hermes/手動依存。直近コミット（ed85c8e, 470b55a）も手動運用の形跡。

#### B4 ✅ `validate_x_search_trends.py` が存在しない

- `scripts/` に無し。`git log --all -- 'scripts/validate*'` でも履歴ゼロ（**一度もコミットされたことがない**）。
- 一方 `multi_trend_collector.py:205-215` の `_load_x_search_trends()` は `items` キー欠落時に黙って `[]` を返すため、Hermes が誤形式（`results` キー等）で書いても**検知されない**。

#### B5 ✅ ルート `src/` の複製 — **想定より広範囲**

- レガシーは記事だけでなく**サイト一式**: ルートに `src/`（197 ファイル git 管理下）、`astro.config.mjs`、`package.json`（astro 依存）、`.github/workflows/deploy.yml` があり、親リポ push のたびに**ルート複製から本番へデプロイされる**。
- 今日時点で `diff -rq src/content/articles astro/src/content/articles` は差分ゼロだが、inode は別（ハードリンクでなくコピー）。pipeline は astro/ のみに書くため、**何かが複製を同期し続けている（要確認: Hermes cron?）**。同期が止まれば経路 3 が古いサイトで本番を上書きする。

### P1 候補

#### B6 ✅ 巨大インライン集合

- `multi_trend_collector.py:299-349` META_TAGS（約 50 行、コメントに場当たり追加の履歴が見える）、`trend_collector.py:26-78` EXCLUDE_PATTERNS / `:81-152` PRODUCT_KEYWORDS / `:301-336` KNOWN_FUN_TAGS・KNOWN_GENERIC_TAGS、`pipeline.py:462-514` PRODUCT_KW_SET・NOISE_WORDS。テストなしの一枚岩。Hermes の「即時 META_TAGS 追加」運用がこのファイル直編集に依存している点も分割時の考慮事項。

#### B7 ✅ トレンド判定のエッジケースにテストなし

- `is_product_related()`（`trend_collector.py:261-352`）は否定先読み・部分一致・正規化が絡む 90 行の関数で、`^[a-zA-Z]{1,3}$` の早期 return（:271）と後段の同一チェック（:312）が重複するなどロジックが読み切れない状態。単体テスト 0 件。

#### B8 ⚠️ Instagram リモート OGP 依存

- `pipeline.py:765` で `image_url = "https://toknet.info/og-default.png"` 固定、`instagram_poster.py` はリモート URL を Graph API に渡す設計（`create_image_container`）。コミット b916d99 が「publish API 失敗を直近メディアと突合して回復」を入れており、**code 4/9004 が実際に頻発している傍証**。ローカル画像アップロード方式への変更は Graph API 仕様調査が必要（バックログ通り）。

#### B9 ⚠️ RSS 0 件問題 — **Engadget は根本原因確定、はてなは再現せず**

- 疎通確認（本日実施）:
  - `japanese.engadget.com/rss.xml` → **接続不能（HTTP 000）**。Engadget 日本版は閉鎖済みであり、恒久的に 0 件。フィード削除 or 代替（ギズモード等）への差し替えが必要。
  - `b.hatena.ne.jp/hotentry/it.rss` → 200 / 216KB 正常。「常に 0 件」は再現せず。`extract_keywords()` のフィルタで全滅している可能性あり（要ログ確認）。
  - ITmedia → 200 正常。
- `fetch_url()`（`multi_trend_collector.py:84-95`）は失敗を `None` で握りつぶし、`fetch_rss` も `[]` を返すだけで **0 件の理由（DNS 失敗か、パース失敗か、キーワード全滅か）が区別できない**。診断ログの追加が妥当。

#### B10 ✅ cron エージェント向けドキュメントが repo 内にない

- `docs/` は CLAUDE_CODE_BRIEF / CLAUDE_CODE_INIT / astro-architecture / improvement-backlog / uat-checklist のみ。`docs/cron-agent.md` 該当なし。

### P2 候補

#### B11 ⚠️ www/apex 一貫性

- astro 側は一貫して apex（`astro.config.mjs` site、BaseLayout の canonical 生成 `BaseLayout.astro:10-17` は正しく trailing-slash 正規化あり）。
- ただし `scripts/uat_test.py` のデフォルト URL が `https://www.toknet.info`（apex が正）。`setup_www_redirect.py` は存在するが Cloudflare 側ルールの現状は**要確認**（API/Dashboard 確認が必要）。
- GSC の重複解消はコードだけでは検証不可（要確認）。

#### B12 ⚠️ テンプレート品質

- `filter_product_keywords()`（`pipeline.py:454-554`）は既に多段フィルタ（長い日本語フレーズ除外・助詞プレフィックス・NOISE_WORDS・短語の部分一致禁止）を実装済み。ただしテストが無く、`build_product_section` はキーワードを Amazon 検索 URL に流すだけの薄い内容。品質改善はキーワード側よりテンプレート/本文生成側の論点。

#### B13 ⚠️ UAT 自動化 — 半分存在する

- バックログの `scripts/uat_check.py` は無いが、実質同等の `scripts/uat_test.py`（380 行、HTTP・メタ検証）が既にある。バックログ側の記述が古い。不足はローカルビルド検証（build 成果物チェック）と CI 組込。

#### B14 ✅ README 不一致

- README は「Node.js - 記事生成スクリプト」「astro/scripts/」構成を記載。実際は**ルート `scripts/` の Python** パイプライン。ディレクトリ図も実態（ルート src/ 複製、docs/、data/ 等）と不一致。`README.md.bak` も放置。

## 4. 監査中に新規発見した問題（バックログ外）

| ID | 深刻度 | 問題 |
|----|--------|------|
| N1 | **P0 級** | **`.gitmodules` が存在しない**。`git ls-files -s astro` は gitlink (160000) を返すが `git submodule status` は `fatal: no submodule mapping found`。フレッシュ clone で submodule を初期化できず、CLAUDE.md 記載の submodule 運用手順と矛盾。 |
| N2 | **P0 級（要確認）** | **`deploy.py` は `astro/dist` が存在すると再ビルドしない**（`deploy.py:46-56`）。pipeline は記事生成→deploy.py 呼び出しの順なので、dist が残っていると**新記事を含まない古い dist をデプロイ**する。現状 dist の mtime は本日 08:36 で、外部（Hermes?）が別途ビルドしている可能性が高いが、pipeline 単体では壊れている。要確認: Hermes cron に `npm run build` があるか。 |
| N3 | P1 | **Review 構造化データで rating を捏造**: `[slug].astro:25` `"ratingValue": product.rating \|\| 4` — 全記事 rating: null なので**常に 4 を出力**。実測に基づかないレビュー評価のマークアップはガイドライン違反リスク（リッチリザルトのペナルティ対象になりうる）。 |
| N4 | P1 | **GA4 測定 ID 不一致**: ブリーフは `G-GKJN4ZB5SV`、`BaseLayout.astro:42,47` は `G-ZGT1S0ZHPR`。どちらが正か要確認（計測が別プロパティに流れている可能性）。 |
| N5 | P2 | `getSortedPosts` が `config.ts:28` と `utils.ts:3` に重複定義。ArticleLayout は config 側、ページ群は utils 側を import しており片方だけの修正事故を誘発。config.ts にクエリ関数を置くのは Astro の慣例からも外れる。 |
| N6 | P2 | 表記バグ: `[slug].astro:112` 「参考**价**格」（簡体字）、`pipeline.py:441` 「実際の**イ**装着心地」。生成記事すべてに露出。 |
| N7 | P2 | 環境変数名 `MSTODON_ACCESS_TOKEN`（`pipeline.py:954`）— `MASTODON` の typo に見える。`~/.hermes/.env` 側と一致しているなら動くが、名称統一の際は両側同時変更が必要（要確認）。 |
| N8 | P2 | ルートに `pipeline_run.log`、`README.md.bak`、`trend_collector.py.bak`、`dist/`、`wrangler.toml`+`wrangler.jsonc` 併存などの残骸。`.gitignore` は `scripts/data/*.json` を無視する一方 `x_search_trends.json` の受け渡しに支障がないか要確認。 |

## 5. P0 推奨 3 件（フェーズ 2 で詳細化）

1. **カテゴリ整合の修正（B1 + slug 不整合）** — CATEGORY_MAP とサイトの category slug を単一ソース化し、`appliance`/`monitor` → サイト側 slug に統一、既存 7 記事の frontmatter 移行、`wearable` 等の追加、laptop-pc デフォルトの見直し。効果: 404 パンくず解消・79% 偏重の是正。小さく安全な PR に分割可能。
2. **デプロイ経路の一本化（B5 + N1 + N2）** — ルート複製 `src/`・ルート deploy.yml の停止（or ガード）、`.gitmodules` 復旧、`deploy.py` の「dist があれば再ビルドしない」を「常にビルド」へ。効果: 「古いサイトで本番上書き」という最も破壊的な事故経路の遮断。
3. **設定の外部化 + 最小テスト（B2/B6/B7 の第一歩）** — `_JA_EN_MAP`・PRODUCT_KEYWORDS・META_TAGS 等の三重定義を `scripts/config/*.json`（または .py 1 ファイル）に集約し、`is_product_related` / `filter_product_keywords` / `detect_category` に pytest を付ける。効果: Hermes の即時タグ追加が 1 箇所で済み、モノリス分割（B2）の足場になる。

## 6. 要確認事項の追加調査結果（2026-07-06 同日実施）

読み取り専用の調査（crontab / launchd / Hermes skill 読取 / git remote / 本番 curl）で 4 点すべて解が出た。

### B5/N1 の正体: 「submodule」は同一リポジトリの二重 clone ✅ 確定

```bash
git remote -v            # → liverpool-tony/toknet-affiliate
git -C astro remote -v   # → liverpool-tony/toknet-affiliate（同一！）
git merge-base --is-ancestor ed85c8e HEAD  # → astro のコミットが親履歴に含まれる
```

- 親リポと `astro/` は **同じ GitHub リポジトリ** を origin に持つ。`astro/` は submodule ではなく**自分自身の別 clone**（gitlink だけ `git add astro` で入り、`.gitmodules` が無いのはこのため）。
- 同期メカニズム: astro/ から push → 同じ remote main に載る → 親で `git pull --rebase`（Hermes の毎 run 手順）→ astro のコミットがルート `src/` に落ちてくる。「誰かがコピーしている」のではなく **git が同期している**。
- 帰結: 履歴には記事コミットが親・astro 両視点で二重に見え、CI（deploy.yml は同一ファイル）は push のたびにルート `src/` からビルド・デプロイ。壊れにくいが極めて紛らわしく、B5 の解消は「レガシー削除」ではなく**リポジトリ構成の正常化**（本当の分離 or submodule 廃止して一本化）が論点になる。

### N2: Hermes cron の build 順序 ✅ 確定（deploy が先、build が後）

- Hermes skill `toknet-affiliate-pipeline` の Cron 手順: 「3. FULL RUN → 4. Verify build: `cd astro && npm run build`」。build は**デプロイ後の検証**として実行される。
- よって pipeline 内の `deploy.py` は**前回 run の dist** を配信（新記事は wrangler 経路では次回 run まで未反映）。アーカイブ skill にも「stale dist は silent failure mode。deploy 前に必ず build」と自覚の記録あり。
- 実害は「push 後に CI がルート src/ から再ビルド・再デプロイする」ことで結果的に緩和されている可能性が高いが、これは上記の偶発的な二重デプロイに依存した動作。P0-2（デプロイ一本化）で `deploy.py` を「常にビルド→デプロイ」へ直すのが正道。

### N4: GA4 ID ✅ ほぼ確定（本番は G-ZGT1S0ZHPR）

- 本番 HTML（`curl https://toknet.info/`）が配信中の ID: **G-ZGT1S0ZHPR**。
- astro 履歴: 7651b88（2026-06-14）「GA4 ID change」で導入。`G-GKJN4ZB5SV` は astro 履歴に一度も登場せず、ブリーフ（docs/CLAUDE_CODE_BRIEF.md）のみに記載 = **旧 ID か誤記の可能性大**。
- 残るユーザー確認（GA4 管理画面が必要）: [analytics.google.com] → 管理 → データストリーム で G-ZGT1S0ZHPR のプロパティに計測が届いているか（リアルタイムレポートで自分のアクセスが見えれば OK）。G-GKJN4ZB5SV のプロパティが別にあるなら破棄 or ブリーフ修正。

### B11: www→apex リダイレクト ✅ 未設定を実測確認

```bash
curl -skI https://www.toknet.info/           # → HTTP/2 200（リダイレクトされない）
curl -skI https://www.toknet.info/articles/  # → HTTP/2 200
```

- www が apex と**同一コンテンツを 200 で二重配信**しており、GSC 重複の直接原因。canonical タグは apex を指すため致命傷ではないが、301 が正道。
- 修正・確認はユーザー（or Hermes）の Cloudflare Dashboard: toknet.info ゾーン → Rules → Redirect Rules に `www.toknet.info/* → https://toknet.info/$1` (301) を追加。リポジトリの `scripts/setup_www_redirect.py` が API での設定を試みた形跡（実行はフェーズ 3 で GO 後）。

---
*作成: Claude Code（フェーズ 1 監査）。当初の要確認 4 点は同日中に上記の通り解決。ユーザーにしかできない残作業: GA4 管理画面での G-GKJN4ZB5SV プロパティの確認のみ。*
