# Sora2 Video Generation MVP

このリポジトリは、OpenAI Sora2 動画生成 API を利用してテキストから動画を生成・再生できる MVP Web アプリです。Node.js ベースのバックエンドが OpenAI Videos API と連携し、ジョブの状態を定期的にポーリングしてフロントエンドに結果を提供します。

## 構成

- **server/**: Express バックエンド。動画生成リクエストの転送、SQLite によるジョブ永続化、OpenAI Videos API のポーリングを担当します。
- **frontend/**: バニラ HTML/CSS/JS で実装した UI。プロンプト送信、ジョブ一覧表示、生成済み動画の再生・ダウンロードを提供します。
- **docs/**: アーキテクチャおよび設計資料。

## 必要条件

- Node.js 18 以上
- npm
- OpenAI API キー (環境変数 `OPENAI_API_KEY`)

## セットアップ

```bash
npm install
export OPENAI_API_KEY="sk-..."
npm run dev
```

サーバー起動後、ブラウザで `http://localhost:8000/` にアクセスするとフロントエンドが表示されます。

### 主要な環境変数

| 変数名 | 説明 | デフォルト |
| ------ | ---- | ---------- |
| `OPENAI_API_KEY` | OpenAI API キー | 必須 |
| `OPENAI_API_BASE_URL` | OpenAI API ベース URL | `https://api.openai.com/v1` |
| `PORT` | Express サーバーのポート番号 | `8000` |
| `POLL_INTERVAL_MS` | ジョブ状態をポーリングする間隔 (ミリ秒) | `10000` |

`.env` ファイルを作成すると自動的に読み込まれます。

## テスト

現時点では自動テストは未整備です。`npm run dev` を実行し、ブラウザまたは API クライアントからエンドポイントを確認してください。

## 今後の改善アイデア

- 認証・認可の導入
- 失敗ジョブの再実行やキャンセル操作
- OpenAI API からのイベント駆動型更新 (Webhook) 対応
- CI による Lint / Test の自動化
