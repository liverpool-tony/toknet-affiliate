# リポジトリ構成の実態と一本化移行手順書

> 作成: 2026-07-06（監査 B5/N1 のフォローアップ、改善計画 PR#4）
> 現状維持のための説明書 + いつでも着手できる一本化手順を記す。

## 1. 現在の構成（重要: 直感に反する）

`astro/` は **submodule ではなく、同一 GitHub リポジトリのもう 1 つの clone** である。

```text
GitHub: liverpool-tony/toknet-affiliate  ← リポジトリは 1 つだけ
│
├─ ~/Projects/toknet-affiliate/          # 親 checkout（cwd）
│   ├── scripts/      # パイプライン（ここが実行される）
│   ├── src/          # サイト一式（CI はここからビルド）
│   ├── docs/
│   └── astro  ……… gitlink（同一リポの commit を指す）
│
└─ ~/Projects/toknet-affiliate/astro/    # 第 2 checkout（同じリポ）
    ├── scripts/      # 同内容（実行されない）
    ├── src/          # パイプラインの書き込み先・ローカルビルドの対象
    └── astro ……… gitlink（自己参照）
```

### 同期メカニズム（誰もコピーしていない）

1. パイプラインが `astro/src/content/articles/` に記事を書く
2. Hermes が `astro/` 内で commit → push（remote main が進む）
3. 親で `git pull --rebase` → **同じコミットが親の `src/` にも現れる**
4. 親で `git add astro` → gitlink 更新 →「chore: update astro submodule pointer」

### デプロイ経路（2 本）

| 経路 | トリガ | ビルド元 |
|------|--------|----------|
| `scripts/deploy.py`（pipeline Step3） | cron | `astro/src` → `astro/dist` |
| GitHub Actions `deploy.yml` | main への push | checkout 直下の `src/`（= 親視点のルート src） |

両方とも Cloudflare Pages プロジェクト `toknet-affiliate` を上書きする。**push のたびに CI が後勝ちで再デプロイ**するため、通常は CI の成果物が最終状態。

### 既知の罠

- gitlink は常に 1 コミット遅れで「M astro」が出続ける（自己参照ゆえ永遠に追いつかない）。無害。
- `.gitmodules` はこの PR で追加した（fresh clone + `git submodule update --init` を可能にするため）。**`--recursive` は使わないこと** — 自己参照 submodule が無限に入れ子で clone される。
- 親 push は Hermes の astro push と競合しやすい → `git stash`（未追跡キャッシュ退避）→ `pull --rebase` → push が定石。
- `node_modules/.astro/data-store.json` は誤って git 追跡されており、ビルドのたびに dirty になる（P2 残骸掃除 N8 で解消予定）。

## 2. 一本化移行手順書（GO 後に実施、想定 1〜2 時間 + cron 1 サイクル監視）

ゴール: 第 2 checkout（`astro/`）を廃止し、親 checkout のルート `src/` を唯一のサイトにする。

### 事前条件

- [ ] Hermes cron を 1 サイクル停止（またはメンテナンスウィンドウ確保）
- [ ] 直前の run-log が正常（デプロイ・push とも成功）であること
- [ ] `git -C astro status` がクリーン（未 push コミットなし）

### 手順

1. **パイプラインのパス変更**（コード変更はこの 1 点のみ）
   - `scripts/pipeline.py` / `scripts/article_generator.py`: `ARTICLES_DIR = PROJECT_DIR / 'astro' / 'src' / ...` → `PROJECT_DIR / 'src' / ...`
   - `scripts/deploy.py`: `PROJECT_DIR = ~/Projects/toknet-affiliate/astro` → `~/Projects/toknet-affiliate`
2. **gitlink と .gitmodules の除去**
   ```bash
   git rm --cached astro && git rm .gitmodules
   git commit -m "chore: astro 二重 clone を廃止しルートに一本化"
   ```
3. **ディレクトリ退避**（即削除しない）
   ```bash
   mv astro ../toknet-affiliate-astro-backup
   ```
4. **ルートで検証**: `python3 scripts/pipeline.py --dry-run` && `npx astro build`
5. **push**（CI デプロイが走る = 一本化後の最初の本番反映）
6. **Hermes skill の改修**（リポ外 `~/.hermes/skills/toknet-affiliate-pipeline/SKILL.md`）
   - `cd astro && npm run build` → ルートで `npm run build`
   - 「Submodule push → 親 pointer 更新」の 2 段 push 手順を単純な 1 回 push に
   - Project Layout 図の更新
7. **CLAUDE.md / README / docs の更新**（submodule 記述の削除）
8. **cron 1 サイクル監視**: run-log で記事生成→デプロイ→push が単一リポで完結することを確認
9. 1 週間問題なければバックアップ削除

### ロールバック

手順 2〜3 を逆再生（`mv` で戻し `git revert`）。remote は同一リポなのでデータ喪失リスクはない。

### 代替案（不採用の理由）

- **真の submodule 化**（astro を別リポに分離）: CI secrets 再設定・履歴分割・Hermes 改修がより大きく、二重管理も残るため不採用。
