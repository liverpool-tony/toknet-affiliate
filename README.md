# AI共創レビュー研究所

> AIと人間の共創による、透明性の高い商品レビュー・比較サイト

## 技術スタック
- **Astro 5** - 静的サイトジェネレーター
- **TypeScript** - 型安全
- **Cloudflare Pages** - ホスティング（無料）
- **Node.js** - 記事生成スクリプト

## セットアップ
```bash
npm install
npm run dev    # 開発サーバー起動
npm run build  # ビルド
```

## ディレクトリ構成
```
astro/
├── src/
│   ├── layouts/       # レイアウト
│   ├── pages/         # ページ
│   ├── components/    # コンポーネント
│   ├── content/       # 記事コンテンツ
│   └── styles/        # スタイル
├── scripts/           # 記事生成スクリプト
├── public/            # 静的アセット
└── dist/              # ビルド出力
```

## ライセンス
Private

## Claude Code（リファクタ参画）

作業ディレクトリ `~/Projects/toknet-affiliate` で `claude` を起動。手順は [docs/CLAUDE_CODE_INIT.md](docs/CLAUDE_CODE_INIT.md)。
