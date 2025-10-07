# Sora2 Video Generation MVP

このリポジトリは、OpenAI の Sora2 動画生成 API を利用した MVP Web アプリです。テキストプロンプトから動画生成ジョブを作成し、進捗をポーリングし、完成した動画を再生・ダウンロードできます。

## 構成

- **backend/**: FastAPI ベースの BFF。動画生成リクエストの転送、ジョブの永続化、OpenAI API のポーリングを担当します。
- **frontend/**: バニラ HTML/CSS/JS で実装したシングルページ UI。プロンプト送信、ジョブ一覧表示、動画再生を提供します。
- **docs/**: アーキテクチャ設計資料。

## 必要条件

- Python 3.11 以上
- OpenAI API キー (環境変数 `OPENAI_API_KEY`)

## セットアップ

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."
uvicorn backend.main:app --reload
```

サーバー起動後、ブラウザで `http://localhost:8000/` にアクセスするとフロントエンドが表示されます。

## 環境変数

| 変数名 | 説明 | デフォルト |
| ------ | ---- | ---------- |
| `OPENAI_API_KEY` | OpenAI API キー | 必須 |
| `DATABASE_URL` | SQLAlchemy 対応の DB URL | `sqlite:///./sora2.db` |
| `OPENAI_API_BASE` | OpenAI API のベース URL | `https://api.openai.com/v1` |
| `OPENAI_VIDEO_MODEL` | 使用する動画モデル名 | `sora-1.0` |
| `OPENAI_VIDEO_BETA_HEADER` | ベータ機能ヘッダー | `video-generation=2` |
| `POLL_INTERVAL_SECONDS` | ジョブポーリング間隔(秒) | `10` |

## テスト

現時点では自動テストは未整備です。FastAPI の組み込みドキュメント (`/docs`) を用いて API エンドポイントを確認できます。

## 今後の改善

- 認証・認可の実装
- E2E テスト自動化
- 失敗ジョブの再実行やキャンセル機能
