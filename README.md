# CLADS LLM Bridge Server

複数のLLMサービスに統一されたOpenAI互換APIアクセスを提供するローカルDockerベースのLLM APIリレーサーバーです。

## 🚀 主な機能

- **設定用Web UI** (ポート 4322): 複数のLLMサービス設定を管理
- **LLMプロキシサーバー** (ポート 4321): OpenAI互換APIエンドポイント
- **モニタリングダッシュボード**: 使用統計、クライアント/モデルランキング
- **Dockerサポート**: 永続データストレージによる簡単なデプロイメント
- **リアルタイム設定反映**: Web UI設定変更の即座反映機能
- **手動設定リロード**: ワンクリックでプロキシサーバー設定更新

## 🌟 対応サービス

- **OpenAI** - GPT-3.5, GPT-4シリーズ
- **Anthropic (Claude)** - Claude 3 Haiku, Sonnet, Opus
- **Google AI Studio (Gemini)** - Gemini Pro, Gemini Pro Vision
- **OpenRouter** - 複数のLLMプロバイダーへのアクセス
- **VS Code LM Proxy** - VS Code組み込みLLM
- **LM Studio** - ローカルLLMホスティング
- **カスタムOpenAI互換API** - その他のOpenAI形式API

## ⚡ クイックスタート

### 🔧 スタートアップスクリプトを使用（最も簡単）

```bash
# 開発モードで開始
./start.sh dev

# 本番モードで開始
./start.sh prod

# ログを表示
./start.sh logs

# ステータスを確認
./start.sh status

# アプリケーションを停止
./start.sh stop
```

### 🐳 Docker Composeを使用

```bash
# 開発モード（デフォルト）
docker-compose up -d

# 本番モード
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# ログを表示
docker-compose logs -f
```

### 🔨 手動でのDockerビルド

```bash
# イメージをビルド
docker build -t clads-llm-bridge .

# コンテナを実行
docker run -d \
  -p 4321:4321 \
  -p 4322:4322 \
  -v clads_data:/app/data \
  --name clads-llm-bridge \
  clads-llm-bridge
```

### 💻 開発環境（Dockerなし）

```bash
# 依存関係をインストール
pip install -r requirements.txt

# アプリケーションを実行
python main.py
```

## 🔗 アクセス方法

- **設定UI**: http://localhost:4322
- **プロキシAPI**: http://localhost:4321
- **デフォルトパスワード**: llm-bridge

## 📡 APIアクセス詳細ガイド

### 🎯 基本APIエンドポイント

CLADS LLM Bridgeは標準的なOpenAI APIと完全互換性があります。

#### 1. 利用可能なモデル一覧の取得

```bash
curl -X GET http://localhost:4321/v1/models
```

**レスポンス例：**
```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-4",
      "object": "model",
      "created": 1677610602,
      "owned_by": "openai",
      "permission": [],
      "root": "gpt-4",
      "parent": null
    },
    {
      "id": "claude-3-sonnet",
      "object": "model",
      "created": 1677610602,
      "owned_by": "anthropic",
      "permission": [],
      "root": "claude-3-sonnet",
      "parent": null
    }
  ]
}
```

#### 2. チャット補完（非ストリーミング）

```bash
curl -X POST http://localhost:4321/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {
        "role": "user",
        "content": "Hello, how are you?"
      }
    ],
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

**レスポンス例：**
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1677652288,
  "model": "gpt-4",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello! I'm doing well, thank you for asking. How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 12,
    "completion_tokens": 19,
    "total_tokens": 31
  }
}
```

#### 3. ストリーミングチャット補完

```bash
curl -X POST http://localhost:4321/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [
      {
        "role": "user",
        "content": "Write a short story"
      }
    ],
    "stream": true,
    "max_tokens": 200,
    "temperature": 0.8
  }'
```

**ストリーミングレスポンス例：**
```
data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"gpt-4","choices":[{"index":0,"delta":{"role":"assistant","content":"Once"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"gpt-4","choices":[{"index":0,"delta":{"content":" upon"},"finish_reason":null}]}

data: {"id":"chatcmpl-123","object":"chat.completion.chunk","created":1677652288,"model":"gpt-4","choices":[{"index":0,"delta":{"content":" a"},"finish_reason":null}]}

data: [DONE]
```

#### 4. レガシー補完エンドポイント

```bash
curl -X POST http://localhost:4321/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "prompt": "Write a haiku about programming:",
    "max_tokens": 50,
    "temperature": 0.7
  }'
```

### 🔍 ヘルスチェックエンドポイント

#### システムヘルス確認

```bash
curl -X GET http://localhost:4321/health
```

**レスポンス例：**
```json
{
  "status": "ok",
  "timestamp": "2024-01-01T12:00:00.000Z"
}
```

#### サービスヘルス詳細

```bash
curl -X GET http://localhost:4321/health/services
```

**レスポンス例：**
```json
{
  "openai": {
    "status": "healthy",
    "last_check": "2024-01-01T12:00:00.000Z",
    "response_time_ms": 150
  },
  "anthropic": {
    "status": "healthy",
    "last_check": "2024-01-01T12:00:00.000Z",
    "response_time_ms": 200
  }
}
```

### 🐍 Python クライアントコード例

#### OpenAIライブラリを使用

```python
import openai

# CLADS LLM Bridgeを指すようにベースURLを設定
client = openai.OpenAI(
    base_url="http://localhost:4321/v1",
    api_key="dummy-key"  # APIキーは不要ですが、ライブラリの要求により設定
)

# チャット補完の使用
response = client.chat.completions.create(
    model="gpt-4",
    messages=[
        {"role": "user", "content": "Python でHello Worldを書いて"}
    ],
    max_tokens=100
)

print(response.choices[0].message.content)

# ストリーミング使用
stream = client.chat.completions.create(
    model="claude-3-sonnet",
    messages=[
        {"role": "user", "content": "短い詩を書いて"}
    ],
    stream=True,
    max_tokens=150
)

for chunk in stream:
    if chunk.choices[0].delta.content is not None:
        print(chunk.choices[0].delta.content, end="")
```

#### Requestsライブラリを使用

```python
import requests
import json

# 非ストリーミングリクエスト
def chat_completion(message, model="gpt-4"):
    url = "http://localhost:4321/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    
    data = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "max_tokens": 200,
        "temperature": 0.7
    }
    
    response = requests.post(url, headers=headers, json=data)
    return response.json()

# 使用例
result = chat_completion("こんにちは、AIアシスタント！")
print(result["choices"][0]["message"]["content"])

# ストリーミングリクエスト
def chat_completion_stream(message, model="gpt-4"):
    url = "http://localhost:4321/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    
    data = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "stream": True,
        "max_tokens": 200,
        "temperature": 0.7
    }
    
    response = requests.post(url, headers=headers, json=data, stream=True)
    
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith('data: '):
                data_str = line[6:]  # Remove 'data: ' prefix
                if data_str == '[DONE]':
                    break
                try:
                    data = json.loads(data_str)
                    content = data["choices"][0]["delta"].get("content", "")
                    if content:
                        print(content, end="", flush=True)
                except json.JSONDecodeError:
                    continue

# ストリーミング使用例
chat_completion_stream("JavaScriptでフィボナッチ数列を書いて")
```

### 🌐 cURLを使った詳細な例

#### 複数のメッセージを含む会話

```bash
curl -X POST http://localhost:4321/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "claude-3-sonnet",
    "messages": [
      {
        "role": "system",
        "content": "あなたは親切で知識豊富なAIアシスタントです。"
      },
      {
        "role": "user",
        "content": "機械学習とは何ですか？"
      },
      {
        "role": "assistant",
        "content": "機械学習は、コンピューターがデータから自動的にパターンを学習し、予測や判断を行う技術です。"
      },
      {
        "role": "user",
        "content": "深層学習との違いは何ですか？"
      }
    ],
    "max_tokens": 300,
    "temperature": 0.5
  }'
```

#### 異なるモデルパラメータでのテスト

```bash
# 創造的な回答（高い温度）
curl -X POST http://localhost:4321/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "未来の都市について想像して書いて"}],
    "max_tokens": 200,
    "temperature": 1.0,
    "top_p": 0.9
  }'

# 一貫した回答（低い温度）
curl -X POST http://localhost:4321/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Pythonでリストをソートする方法"}],
    "max_tokens": 150,
    "temperature": 0.1
  }'
```

### 📊 エラーハンドリング

APIはHTTP標準ステータスコードを使用します：

- **200**: 成功
- **400**: リクエストが不正
- **401**: 認証エラー（設定されたAPIキーが無効）
- **404**: モデルが見つからない
- **429**: レート制限に達した
- **500**: サーバー内部エラー
- **503**: サービス利用不可（上流APIがダウン）

**エラーレスポンス例：**
```json
{
  "error": {
    "message": "Model 'invalid-model' not found",
    "type": "invalid_request_error",
    "param": "model",
    "code": "model_not_found"
  }
}
```

### 🔧 設定管理Web UI

設定Web UIでは以下の操作が可能です：

1. **http://localhost:4322** にアクセス
2. デフォルトパスワード「llm-bridge」でログイン
3. LLMサービスの追加・編集・削除
4. モデル設定のテスト
5. 使用統計の確認
6. **リアルタイム設定更新**: 設定変更は即座にプロキシサーバーに反映
7. **手動リロード機能**: 「Reload Config」ボタンで強制的に設定を再読み込み

### ⚡ 設定反映機能

**自動リロード（設定変更時）:**
- 設定保存時
- 設定削除時
- 設定有効/無効切り替え時

**手動リロード:**
- Web UI右上の「**Reload Config**」ボタン
- APIエンドポイント: `POST /admin/reload`
- リロード結果をリアルタイムで表示

### 📈 モニタリング機能

- **リアルタイム統計**: リクエスト数、トークン使用量、応答時間
- **クライアントランキング**: IPアドレス別の使用統計
- **モデルランキング**: モデル別の人気度と性能
- **時系列データ**: 時間別、日別、週別の傾向分析

## ⚙️ 環境設定

### 🔑 APIキー設定ガイド

#### Google AI Studio (Gemini) APIキー設定

**1. Google AI Studio APIキーの取得**

1. [Google AI Studio](https://aistudio.google.com/) にアクセス
2. Googleアカウントでサインイン
3. 左側の「API キー」セクションに移動
4. 「APIキーを作成」をクリック
5. 新しいAPIキーをコピーして保存

**2. CLADS LLM Bridgeでの設定**

方法1: 環境変数を使用（推奨）
```bash
# .envファイルに追加
echo "GEMINI_API_KEY=your-google-ai-studio-api-key-here" >> .env

# Dockerコンテナを再起動
docker-compose restart
```

方法2: Web UIで設定
1. http://localhost:4322 にアクセス
2. 「llm-bridge」でログイン
3. 「新しいLLM設定を追加」をクリック
4. 以下の設定を入力：
   - **サービスタイプ**: `Google AI Studio (Gemini)`
   - **公開名**: `Gemini 2.5 Pro` (任意の名前)
   - **モデル名**: `gemini-2.5-pro` または `gemini-2.5-flash`
   - **APIキー**: 取得したGoogle AI Studio APIキー
   - **ベースURL**: 空欄のまま（自動設定）

**3. 利用可能なGeminiモデル**

| モデル名 | 説明 | 設定時のモデル名 |
|----------|------|------------------|
| Gemini 2.5 Pro | 最新の高性能モデル | `gemini-2.5-pro` |
| Gemini 2.5 Flash | 高速レスポンスモデル | `gemini-2.5-flash` |
| Gemini 1.5 Pro | 長いコンテキスト対応 | `gemini-1.5-pro` |
| Gemini 1.5 Flash | バランス型モデル | `gemini-1.5-flash` |

**4. APIリクエスト例**

```bash
# Gemini 2.5 Proを使用
curl -X POST http://localhost:4321/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gemini-2.5-pro",
    "messages": [
      {
        "role": "user",
        "content": "こんにちは！Geminiを使ってテストしています。"
      }
    ],
    "max_tokens": 100,
    "temperature": 0.7
  }'
```

**5. 重要な注意点**

- **Google Cloud vs Google AI Studio**: CLADS LLM BridgeはGoogle AI Studio APIを使用します（Google Cloud Vertex AIではありません）
- **料金**: Google AI Studioには無料枠があります。詳細は[公式料金ページ](https://ai.google.dev/pricing)をご確認ください
- **レート制限**: Google AI Studioには1日あたりのリクエスト制限があります
- **地域制限**: 一部の地域ではGoogle AI Studioが利用できない場合があります

#### その他のAPIキー設定

各サービスのAPIキー設定については、Web UI（http://localhost:4322）の「ヘルプ」セクションをご参照ください。

### 環境変数

アプリケーションは以下の環境変数で設定可能です：

| 変数名 | デフォルト値 | 説明 |
|--------|-------------|------|
| `WEB_UI_PORT` | `4322` | 設定用Web UIのポート |
| `PROXY_PORT` | `4321` | LLMプロキシサーバーのポート |
| `LOG_LEVEL` | `INFO` | ログレベル (DEBUG, INFO, WARNING, ERROR) |
| `INITIAL_PASSWORD` | `llm-bridge` | 初期管理者パスワード |
| `DATA_DIR` | `data` | データディレクトリ |
| `DATABASE_PATH` | `data/clads_llm_bridge.db` | データベースファイルパス |
| `GEMINI_API_KEY` | - | Google AI Studio APIキー |
| `OPENAI_API_KEY` | - | OpenAI APIキー |
| `ANTHROPIC_API_KEY` | - | Anthropic APIキー |

### 環境ファイルの使用

1. サンプル環境ファイルをコピー：
   ```bash
   cp .env.example .env
   ```

2. `.env`ファイルを設定に応じて編集

3. 環境ファイルを指定して起動：
   ```bash
   docker-compose --env-file .env up -d
   ```

## 🏗️ プロジェクト構成

```
clads-llm-bridge/
├── src/
│   ├── config/              # 設定管理
│   ├── proxy/               # LLMプロキシサーバー
│   ├── monitoring/          # 使用量モニタリング
│   ├── auth/                # 認証システム
│   ├── database/            # データベース管理
│   ├── models/              # データモデル
│   └── web/                 # Web UI
├── tests/                   # ユニットテスト
├── data/                    # 永続データストレージ
├── requirements.txt         # Python依存関係
├── Dockerfile              # マルチステージコンテナビルド
├── docker-compose.yml      # 開発用デプロイメント
├── docker-compose.prod.yml # 本番用デプロイメント
├── docker-compose.override.yml # 開発用オーバーライド
├── .env.example            # 環境変数テンプレート
├── start.sh                # 簡単デプロイメントスクリプト
├── DOCKER.md               # Dockerデプロイメントガイド
└── main.py                 # アプリケーションエントリーポイント
```

## 📖 追加ドキュメント

- **[Dockerデプロイメントガイド](DOCKER.md)**: 包括的なDockerデプロイメントドキュメント
- **[実装サマリー](TASK*_IMPLEMENTATION_SUMMARY.md)**: 各機能の実装詳細

## 🚨 トラブルシューティング

### よくある問題と解決方法

1. **ポートが使用中**
   ```bash
   # ポート使用状況を確認
   lsof -i :4321
   lsof -i :4322
   ```

2. **データベース権限エラー**
   ```bash
   # データディレクトリの権限を確認・修正
   chmod 755 data/
   chmod 644 data/clads_llm_bridge.db
   ```

3. **設定変更が反映されない**
   - **Web UI右上の「Reload Config」ボタンをクリック**
   - または手動でAPIを呼び出し：
     ```bash
     curl -X POST http://localhost:4321/admin/reload
     ```
   - 設定保存/削除時は自動的にリロードされます

4. **Gemini (Google AI Studio) 接続エラー**
   - APIキーが正しく設定されているか確認
   - Google AI Studio（Vertex AIではない）のAPIキーを使用
   - モデル名は `gemini-2.5-pro` や `gemini-2.5-flash` を使用
   - 地域制限やレート制限を確認

5. **上流APIエラー**
   - 設定UI (http://localhost:4322) でAPI設定をテスト
   - APIキーの有効性を確認
   - レート制限やクォータを確認

6. **メモリ不足**
   ```bash
   # Dockerコンテナのリソース使用量を確認
   docker stats clads-llm-bridge
   ```

### ログの確認

```bash
# アプリケーションログ
docker-compose logs -f

# 特定のサービスのログ
docker-compose logs -f web
docker-compose logs -f proxy

# ローカルログファイル
tail -f logs/clads_llm_bridge.log
tail -f logs/errors.log
tail -f logs/access.log
```

## 🤝 貢献

このプロジェクトへの貢献を歓迎します！問題報告や機能提案がございましたら、GitHubのIssueをご利用ください。

## 📄 ライセンス

このプロジェクトはMITライセンスの下で公開されています。

---

**🎉 CLADS LLM Bridge Serverで、複数のAIモデルを統一的に活用しましょう！**