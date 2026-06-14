# Astro + Cloudflare Pages 構成

## アーキテクチャ

```
toknet-astro/
├── src/
│   ├── pages/           # ページ（Markdown/MDX）
│   │   ├── index.astro              # トップページ
│   │   ├── category/
│   │   │   ├── laptop-pc.astro      # カテゴリTOP
│   │   │   ├── camera.astro
│   │   │   └── ...
│   │   ├── review/
│   │   │   └── [slug].md            # レビュー記事（動的）
│   │   ├── comparison/
│   │   │   └── [slug].md            # 比較記事
│   │   ├── ranking/
│   │   │   └── [category].md        # ランキング
│   │   └── api/
│   │       └── articles.json.ts     # 記事データAPI
│   ├── components/      # UIコンポーネント
│   │   ├── ProductCard.astro
│   │   ├── AmazonLink.astro         # Amazonリンク（PR表記付き）
│   │   ├── AIDisclaimer.astro       # AI表記コンポーネント
│   │   ├── PRBanner.astro           # PRバナー
│   │   ├── ComparisonTable.astro
│   │   ├── StarRating.astro
│   │   └── SEOHead.astro
│   ├── layouts/         # レイアウト
│   │   ├── BaseLayout.astro
│   │   └── ArticleLayout.astro
│   ├── content/         # コンテンツ（AI生成Markdown）
│   │   ├── config.ts
│   │   └── articles/    # 全記事データ
│   ├── styles/          # CSS
│   │   └── global.css
│   └── utils/           # ユーティリティ
│       ├── amazon.ts    # Amazonリンク生成
│       ├── seo.ts       # SEOヘルパー
│       └── structured-data.ts # 構造化データ
├── public/              # 静的アセット
│   ├── robots.txt
│   └── sitemap.xml
├── astro.config.mjs
├── package.json
├── tsconfig.json
└── wrangler.toml        # Cloudflare Pages設定
```

## デプロイ先

- **Cloudflare Pages**: 無料（月50万リクエストまで）
- **ドメイン**: toknet.info（お名前.com → Cloudflare DNSに変更）
- **ビルド**: `npm run build` → Cloudflareに自動デプロイ
- **記事管理**: MarkdownファイルをGitで管理（AIが直接編集可能）

## 料金

| 項目 | 月額 |
|------|------|
| Cloudflare Pages | 無料 |
| ドメイン (toknet.info) | 既存（年約1,200円） |
| Google AI Pro | $10（約1,500円） |
| **合計** | **約1,600円/月** |

## AIエージェントとの親和性

- 全記事がMarkdownファイル → AIが直接読み書き可能
- Git管理 → AIがコミット・プッシュ可能
- API経由でAmazon商品データを取得 → AIが自動で記事を生成
- 構造化データの自動生成 → AIがJSON-LDを自動作成
