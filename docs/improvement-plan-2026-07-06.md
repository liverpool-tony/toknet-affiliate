# 改善計画 2026-07-06（フェーズ 2）

> 根拠: [refactor-audit-2026-07-06.md](refactor-audit-2026-07-06.md)。**実装は各項目へのユーザー GO 後**（フェーズ 3、1 PR = 1 論点）。
>
> ユーザー決定済み事項:
> - リポ構成（B5）は**最小ガード**に留め、一本化への移行手順書を残す（いつでも着手可能に）
> - Instagram（B8）は **P1 調査スパイクのみ**（主因の action block はコードで直らないため）

---

## P0（3 件）

### P0-1 カテゴリ整合（B1 + slug 不整合）

- **目的**: 404 パンくずの解消と、187 記事中 148 件（79%）が laptop-pc に落ちる分類崩壊の是正。
- **範囲**:
  1. `scripts/pipeline.py` CATEGORY_MAP のキーを `appliance`→`home-appliances`、`monitor`→`monitors` に統一（サイト側 `astro/src/pages/category/[category].astro:6` が正）
  2. 既存記事 7 件（`category: "appliance"` 6 件 + `"monitor"` 1 件）の frontmatter 移行
  3. `wearable` カテゴリ新設（キーワード: スマートグラス、ウェアラブル、AIペンダント、AIボイスレコーダー、スマートウォッチ、Watch、fitbit、garmin 等 — Hermes run-log の実 mismatch 事例から採録）。category ページ・nav への追加を含む
  4. laptop-pc 無条件デフォルトの見直し（`detect_category()` `scripts/pipeline.py:363-396`）
- **リスク**: カテゴリ判定変更で既存記事の再分類は行わない（frontmatter 移行は slug 不整合 7 件のみ）。Hermes cron と同時編集の競合 → マージは cron の谷間（12h 周期）で。
- **受け入れ条件**:
  - `grep -h '^category:' astro/src/content/articles/*.md | sort -u` の全値がサイト定義カテゴリ（8 種 + wearable）に含まれる
  - 全記事のパンくず `/category/{category}/` が build 成果物に存在（404 ゼロ）
  - 既知 mismatch ケース（スマートグラス、AIボイスレコーダー、ウェアラブル、Plaud NotePin S）が unittest で正カテゴリに分類される

### P0-2 デプロイ経路の安全化（N2 + N1 + B5 最小ガード）

- **目的**: 「古い dist / 古い複製で本番を上書きする」事故経路の遮断。監査で確定した通り、`deploy.py` は dist が存在すると再ビルドせず（`scripts/deploy.py:46`）、Hermes cron は build を deploy の**後**に実行するため、wrangler 経路は常に 1 run 遅れの配信。
- **範囲**:
  1. `scripts/deploy.py`: 常に `npm run build` → deploy の順に（dist 有無での分岐を廃止）
  2. `.gitmodules` 追加（`path = astro` / `url = https://github.com/liverpool-tony/toknet-affiliate.git` の自己参照。fresh clone を可能にする）
  3. `docs/repo-structure.md` 新規: 現構成（同一リポ二重 clone、git pull 同期、CI がルート src/ からビルド）の説明と、**一本化への移行手順書**（ルートを唯一のサイトにする全ステップ、Hermes skill `toknet-affiliate-pipeline` の改修点、ロールバック手順を含む）
- **リスク**: deploy.py のビルド追加で cron 実行時間が数十秒延びる（許容）。`.gitmodules` はローカル既存 clone に影響なし。
- **受け入れ条件**:
  - 記事生成→デプロイの同一 run で、dist に新記事 slug のディレクトリが含まれる
  - fresh clone + `git submodule update --init` が成功する
  - 移行手順書に一本化の全ステップ（Hermes 側改修点含む）が記載され、次期計画から参照可能

### P0-3 設定の単一ソース化 + 最小テスト（B6/B7、B2 の足場）

- **目的**: `_JA_EN_MAP` の三重定義（`pipeline.py:134` / `trend_collector.py:241` / `multi_trend_collector.py:277`、内容も不一致）、PRODUCT_KEYWORDS の二重定義、META_TAGS 等の巨大インライン集合を 1 ファイルに集約し、判定ロジックに回帰テストを付ける。Hermes の「即時 META_TAGS 追加」が 1 箇所編集で完結するようにする。
- **範囲**:
  1. `scripts/trend_config.py` 新規: `JA_EN_MAP`, `PRODUCT_KEYWORDS`, `META_TAGS`, `EXCLUDE_PATTERNS`, `KNOWN_FUN_TAGS`, `KNOWN_GENERIC_TAGS`, `NOISE_WORDS`, `CATEGORY_MAP` を移設（挙動不変。三重定義の差分は和集合を取り、差異は docstring に記録）
  2. `pipeline.py` / `trend_collector.py` / `multi_trend_collector.py` の参照置換
  3. `tests/` 新規: stdlib `unittest`（**pytest 非依存** — 「標準ライブラリのみ」制約を維持）で `is_product_related` / `filter_product_keywords` / `detect_category` の回帰テスト。Hermes run-log の実事例（`#top` 除外、`#nvidia` META_TAGS、`polaroid` 正規化等）をフィクスチャ化
- **リスク**: 和集合による挙動変化の可能性 → 集約前後で dry-run の選択タグ一致を確認してからマージ。Hermes skill の META_TAGS 編集手順が変わる → P1-5 `cron-agent.md` と同時期に skill 更新を依頼。
- **受け入れ条件**:
  - 集約前後で `pipeline.py --dry-run` の選択タグが不変
  - `python3 -m unittest discover tests` が green
  - META_TAGS への語追加が `trend_config.py` 1 ファイルの編集で全収集経路に反映される

---

## P1

- **P1-1 Review スキーマの rating 捏造除去 + 誤字修正（N3/N6）** — `astro/src/pages/articles/[slug].astro:25` の `"ratingValue": product.rating || 4` を廃止し、rating が無い場合は Review スキーマ自体を出力しない（Article スキーマは維持）。あわせて `参考价格`（簡体字、`[slug].astro:112`）と `実際のイ装着心地`（`pipeline.py:441`）を修正。**受け入れ条件**: rating: null の記事の HTML に Review スキーマが無い／build 成功／リッチリザルトテストで警告なし。
- **P1-2 Engadget 死亡フィード対応 + fetch 診断ログ（B9）** — 閉鎖済み `japanese.engadget.com/rss.xml`（監査時 HTTP 000）を削除 or 代替（ギズモード・ジャパン等）に差替え。`fetch_url`/`fetch_rss`（`multi_trend_collector.py:84-129`）に失敗理由（接続不能/パース失敗/キーワード全滅）の stderr ログを追加。**受け入れ条件**: dry-run 出力でソース別の件数と 0 件理由が判別できる。
- **P1-3 x_search_trends バリデータ常設（B4）** — `scripts/validate_x_search_trends.py` を新規常設（`items` キー・各 item の形状・UTF-8 健全性を検査）し、pipeline の Step 1 前に呼ぶ。`_load_x_search_trends()`（`multi_trend_collector.py:205`）の黙殺を警告ログに変更。**受け入れ条件**: `results` キーの不正 JSON で非ゼロ exit + 明示エラー。
- **P1-4 記事 commit 自動化オプション（B3）** — `pipeline.py --commit` で FULL RUN 後に astro→親の 2 段 push（CLAUDE.md 記載の手順 + rebase/stash リカバリ）を実行。デフォルトは現状維持（Hermes 手動）。**受け入れ条件**: dry-run では no-op、`--commit` 付き実 run でコミットが生成される。
- **P1-5 `docs/cron-agent.md`（B10）** — x_search JSON の手順（`items` 形状、書込→読み戻し検証）、META_TAGS 追加の新手順（P0-3 後は `trend_config.py`）、報告ルールを repo 内に明文化。Hermes skill との整合を取る（矛盾時はリポジトリが正）。**受け入れ条件**: Hermes skill 側の参照先更新依頼が出せる状態。
- **P1-6 Instagram 調査スパイク（B8、コード変更なし）** — Graph API のローカル画像アップロード可否（resumable upload / メディア URL 要件）の調査と、action block（code 4 / subcode 2207051、約 24 日継続）の解除手順・再発防止（投稿頻度・キャプション要因）を `docs/instagram-recovery.md` にまとめる。実装 PR は調査結果を見て次期計画で判断。**受け入れ条件**: 調査ドキュメントに「実装可否 + 推奨アプローチ + 工数見積」が記載される。
- **P1-7 ドキュメント同期（B14 + N4）** — README を実態（ルート `scripts/` の Python パイプライン、astro/ 構成、docs/）に合わせ刷新、`README.md.bak` 削除、ブリーフ（CLAUDE_CODE_BRIEF.md）の GA4 ID を `G-ZGT1S0ZHPR` に修正（本番配信中の ID、2026-06-14 の astro コミット 7651b88 で変更済みのもの）。**受け入れ条件**: README の記述と `ls` の実態が一致。

---

## P2（次期計画で優先度再付け）

| 項目 | 内容 |
|------|------|
| B2 本格モジュール分割 | `scripts/` を `trends/` `content/` `publish/` に分割、CLI は薄く。P0-3 のテスト整備後に着手 |
| B11 www→apex 301 | Cloudflare Dashboard（Rules → Redirect Rules）での 301 追加（ops 作業）+ `uat_test.py` デフォルト URL の apex 化。監査で www が 200 二重配信中と実測確認済み |
| B12 記事テンプレート品質 | 本文生成側の強化（商品セクションの実質化、テンプレバリエーション追加） |
| B13 UAT の CI 組込 | `uat_test.py` をデプロイ後チェックとして CI に組込 |
| N5 `getSortedPosts` 重複解消 | `astro/src/content/config.ts:28` と `utils.ts:3` の重複定義を utils 側に一本化 |
| N8 残骸掃除 | `*.bak`、`pipeline_run*.log`、`wrangler.toml`/`wrangler.jsonc` 併存、ルート `dist/` の整理 |
| リポ一本化の本体実施 | P0-2 の移行手順書（`docs/repo-structure.md`）に従い次期計画で実施 |

---

## 最初の 2 週間の PR 列

各 PR 後の共通検証: `python3 scripts/pipeline.py --dry-run` + `cd astro && npm run build`（任意で `npx tsc --noEmit --skipLibCheck`）。

| # | 週 | タイトル | 主な変更ファイル | 個別検証 |
|---|----|----------|------------------|----------|
| 1 | 1 | fix(category): カテゴリ slug 統一と 7 記事の移行 | `scripts/pipeline.py`, `astro/src/pages/category/[category].astro`, 該当記事 7 件 | category 値の網羅 grep がサイト定義に収まる |
| 2 | 1 | feat(category): wearable カテゴリ新設とデフォルト見直し | `scripts/pipeline.py`, `[category].astro`, `BaseLayout.astro`(nav), `ArticleLayout.astro`(サイドバー) | 既知 mismatch 4 事例の分類確認 |
| 3 | 1 | fix(deploy): deploy.py を常にビルド→デプロイに | `scripts/deploy.py` | 生成→デプロイ同一 run で dist に新 slug |
| 4 | 1 | chore(repo): .gitmodules 追加 + repo-structure.md | `.gitmodules`, `docs/repo-structure.md` | fresh clone + `git submodule update --init` 成功 |
| 5 | 1 | refactor(config): 判定設定を trend_config.py に集約 | `scripts/trend_config.py`(新規), `pipeline.py`, `trend_collector.py`, `multi_trend_collector.py` | 集約前後で dry-run 選択タグ不変 |
| 6 | 1 | test: unittest 導入（判定 3 関数） | `tests/`(新規) | `python3 -m unittest discover tests` green |
| 7 | 2 | fix(seo): rating 捏造除去 + 誤字修正 | `astro/src/pages/articles/[slug].astro`, `scripts/pipeline.py` | rating 無し記事に Review スキーマが出ない |
| 8 | 2 | fix(trends): Engadget フィード対応 + fetch 診断ログ | `scripts/multi_trend_collector.py` | ソース別件数と失敗理由が出力される |
| 9 | 2 | feat(validate): x_search_trends バリデータ常設 | `scripts/validate_x_search_trends.py`(新規), `scripts/pipeline.py` | 不正 JSON（`results` キー）で fail |
| 10 | 2 | feat(pipeline): --commit オプション | `scripts/pipeline.py`, `docs/` | dry-run で no-op、実 run でコミット生成 |
| 11 | 2 | docs: cron-agent.md + README 刷新 + ブリーフ GA4 修正 | `docs/cron-agent.md`(新規), `README.md`, `docs/CLAUDE_CODE_BRIEF.md` | レビューのみ |
| 12 | 2 | docs: Instagram 調査スパイク成果 | `docs/instagram-recovery.md`(新規) | レビューのみ |

### 運用上の注記

- **マージタイミング**: PR#1/2/5 は Hermes cron（12h 周期、直近は 08:35 実行）と同一ファイルを触るため、cron 実行の谷間でマージする。マージ後最初の cron run の run-log を確認。
- **Hermes 連携**: PR#5 マージ時点で Hermes skill `toknet-affiliate-pipeline` の META_TAGS 編集手順（`multi_trend_collector.py` 直編集 → `trend_config.py` 編集）の更新が必要。PR#11 の `cron-agent.md` に新手順を記載し、skill 側の更新を依頼する。
- **B11（www リダイレクト）**: PR ではなく Cloudflare Dashboard の ops 作業。GO があれば `scripts/setup_www_redirect.py` の実行で対応可能（要 API トークン権限確認）。

---

## 着手方法

**GO で P0 の PR#1 から着手します。**「PR#3 だけ先に」等の項目別 GO も可能です。各 PR は日本語説明付きで作成し、マージ前に dry-run + build の結果を報告します。
