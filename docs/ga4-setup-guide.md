# GA4 Data API 設定ガイド — toknet.info

## 目的
`scripts/ga4_analyzer.py` が GA4 Data API からトラフィックデータを取得できるようにする。

## 手順（約5分）

### 1. Google Cloud Console でサービスアカウント作成
1. https://console.cloud.google.com/apis/credentials にアクセス
2. 「認証情報を作成」→「サービスアカウント」
3. 名前: `toknet-ga4-reader`（任意）
4. 役割: 不要（GA4側で権限付与するため）
5. 「完了」

### 2. Analytics Data API を有効化
1. https://console.cloud.google.com/apis/library/analyticsdata.googleapis.com
2. 「有効にする」をクリック

### 3. JSONキーをダウンロード
1. 作成したサービスアカウントをクリック
2. 「キー」タブ → 「鍵を追加」→ 「新しい鍵を作成」
3. JSON形式を選択 → ダウンロード
4. ファイルを `~/.hermes/ga4-service-account.json` にリネームして移動:
   ```bash
   mv ~/Downloads/toknet-ga4-reader-xxxxx.json ~/.hermes/ga4-service-account.json
   ```

### 4. GA4 プロパティにサービスアカウントを追加
1. https://analytics.google.com/ にアクセス
2. toknet.info プロパティを選択
3. 左下「管理」→「プロパティアクセス管理」
4. 「+」→「ユーザーを追加」
5. サービスアカウントのメールアドレス（JSONファイルの `client_email` 字段）を入力
6. 役割: **「閲覧者」** を選択
7. 「追加」

### 5. プロパティIDの確認
GA4管理画面 → 「プロパティ設定」→「プロパティの詳細」に表示される数字。
`ga4_analyzer.py` の `PROPERTY_ID` を `properties/XXXXXXXXX` 形式で更新する。

現在の設定: `properties/472074982`（要確認）

確認コマンド:
```bash
python3 scripts/ga4_analyzer.py --days 1 --top 5
```

## 確認
```bash
# テスト実行
python3 scripts/ga4_analyzer.py --days 7 --top 10 --compare

# JSON出力（PDCAエンジン用）
python3 scripts/ga4_analyzer.py --days 7 --json --output /tmp/ga4_test.json
```

## トラブルシューティング
| エラー | 原因 | 対処 |
|--------|------|------|
| `403 Permission denied` | GA4プロパティにサービスアカウント未追加 | 手順4を確認 |
| `404 Property not found` | PROPERTY_ID が間違っている | 手順5で正しいIDを確認 |
| `ModuleNotFoundError` | google-analytics-data 未インストール | `pip3 install google-analytics-data` |
| `DefaultCredentialsError` | JSONファイルのパスが違う | `~/.hermes/ga4-service-account.json` にあるか確認 |
