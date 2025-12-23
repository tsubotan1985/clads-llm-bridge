# デュアルエンドポイント機能実装サマリー

## 📋 実装概要

CLADS LLM Bridgeにデュアルエンドポイント機能を実装しました。これにより、単一のプロキシサーバー（ポート4321）から、2つの独立したエンドポイント（一般用4321、特別用4333）に拡張され、各モデルをエンドポイント毎に個別に公開制御できるようになりました。

## 🎯 実装目標

- ✅ ポート4321: 一般モデルのみアクセス可能な一般エンドポイント
- ✅ ポート4333: 全モデルにアクセス可能な特別エンドポイント（フルアクセス）
- ✅ ダッシュボードUIで各モデルのエンドポイント公開設定を個別に管理
- ✅ 既存データとの後方互換性の維持

## 🏗️ アーキテクチャ変更

### Before (単一エンドポイント)
```
[Web UI:4322] ──┐
                ├──> [Proxy Server:4321] ──> [All LLM Models]
                └──> [Database]
```

### After (デュアルエンドポイント)
```
[Web UI:4322] ──┬──> [General Proxy:4321] ──> [一般モデルのみ]
                │
                ├──> [Special Proxy:4333] ──> [全モデル]
                │
                └──> [Database with endpoint flags]
```

## 📊 実装詳細

### 1. データベーススキーマ拡張

**ファイル**: [`src/database/schema.py`](src/database/schema.py)

- `llm_configs`テーブルに新しいカラムを追加:
  - `available_on_4321` (INTEGER/BOOLEAN): 一般エンドポイント(4321)での公開可否
  - `available_on_4333` (INTEGER/BOOLEAN): 特別エンドポイント(4333)での公開可否
- スキーマバージョンを1から2へ更新

```sql
CREATE TABLE llm_configs (
    -- 既存のカラム
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service_type TEXT NOT NULL,
    display_name TEXT NOT NULL,
    model_name TEXT NOT NULL,
    -- ... 他のカラム ...
    
    -- 新規追加
    available_on_4321 INTEGER DEFAULT 1,  -- デフォルト: 有効
    available_on_4333 INTEGER DEFAULT 1   -- デフォルト: 有効
)
```

### 2. データベースマイグレーション

**ファイル**: [`src/database/migrations.py`](src/database/migrations.py)

- バージョン2マイグレーションを実装:
  - 既存テーブルに新カラム追加
  - 既存レコードはデフォルトで両エンドポイントで有効化（後方互換性）
  - メタデータテーブルのバージョン更新

```python
def _get_v2_migration_sql(self) -> str:
    """バージョン2へのマイグレーションSQL"""
    return """
    -- エンドポイント利用可能性カラムを追加
    ALTER TABLE llm_configs ADD COLUMN available_on_4321 INTEGER DEFAULT 1;
    ALTER TABLE llm_configs ADD COLUMN available_on_4333 INTEGER DEFAULT 1;
    
    -- メタデータ更新
    UPDATE migration_metadata SET version = 2;
    """
```

### 3. モデルクラスの拡張

**ファイル**: [`src/models/llm_config.py`](src/models/llm_config.py)

- `LLMConfig`クラスに新しいフィールドを追加:
  ```python
  @dataclass
  class LLMConfig:
      # 既存フィールド
      id: Optional[int] = None
      service_type: str = ""
      # ... 他のフィールド ...
      
      # 新規追加
      available_on_4321: bool = True
      available_on_4333: bool = True
  ```

- `to_dict()`メソッドでSQLite用にbooleanをintegerに変換:
  ```python
  def to_dict(self) -> Dict[str, Any]:
      data = {
          # ... 既存フィールド ...
          'available_on_4321': 1 if self.available_on_4321 else 0,
          'available_on_4333': 1 if self.available_on_4333 else 0,
      }
      return data
  ```

### 4. 設定サービスの更新

**ファイル**: [`src/config/configuration_service.py`](src/config/configuration_service.py)

主な変更点:
- すべてのSELECTクエリに新カラムを追加
- INSERTおよびUPDATE文に新フィールドを含める
- boolean値を適切にintegerに変換

```python
def get_llm_configs(self) -> List[LLMConfig]:
    cursor = self.conn.execute("""
        SELECT id, service_type, display_name, model_name, 
               api_key, base_url, is_enabled, notes,
               available_on_4321, available_on_4333
        FROM llm_configs
        ORDER BY display_name
    """)
    # ... レコード処理 ...
```

### 5. プロキシサーバーのフィルタリング実装

**ファイル**: [`src/proxy/proxy_server.py`](src/proxy/proxy_server.py)

#### 主要な変更:

1. **エンドポイントタイプの導入**:
   ```python
   class ProxyServer:
       def __init__(
           self,
           config_service: ConfigurationService,
           endpoint_type: str = "general"  # "general" or "special"
       ):
           self.endpoint_type = endpoint_type
   ```

2. **モデルフィルタリングメソッド**:
   ```python
   def _filter_models_by_endpoint(
       self, 
       configs: List[LLMConfig]
   ) -> List[LLMConfig]:
       """エンドポイントタイプに基づいてモデルをフィルタリング"""
       if self.endpoint_type == "general":
           return [c for c in configs if c.available_on_4321]
       elif self.endpoint_type == "special":
           return [c for c in configs if c.available_on_4333]
       return configs
   ```

3. **エンドポイント検証**:
   ```python
   async def chat_completions(self, request: Request):
       # ... リクエスト処理 ...
       
       # エンドポイント検証
       if self.endpoint_type == "general" and not config.available_on_4321:
           raise HTTPException(
               status_code=403,
               detail=f"Model '{model}' is not available on general endpoint (port 4321)"
           )
       elif self.endpoint_type == "special" and not config.available_on_4333:
           raise HTTPException(
               status_code=403,
               detail=f"Model '{model}' is not available on special endpoint (port 4333)"
           )
   ```

### 6. プロキシサーバー起動の変更

**ファイル**: [`src/proxy/startup.py`](src/proxy/startup.py)

- `ProxyServerManager`に`endpoint_type`パラメータを追加:
  ```python
  class ProxyServerManager:
      def __init__(
          self,
          config_service: ConfigurationService,
          port: int = 4321,
          endpoint_type: str = "general"
      ):
          self.endpoint_type = endpoint_type
          self.proxy_server = ProxyServer(
              config_service=config_service,
              endpoint_type=endpoint_type
          )
  ```

### 7. メインアプリケーションのデュアルサーバー起動

**ファイル**: [`main.py`](main.py)

#### 主要な変更:

1. **環境変数の追加**:
   ```python
   PROXY_PORT_GENERAL = int(os.getenv("PROXY_PORT_GENERAL", "4321"))
   PROXY_PORT_SPECIAL = int(os.getenv("PROXY_PORT_SPECIAL", "4333"))
   PROXY_PORT = PROXY_PORT_GENERAL  # 後方互換性
   ```

2. **2つのプロキシマネージャーの作成**:
   ```python
   # 一般エンドポイント
   proxy_manager_general = ProxyServerManager(
       config_service=config_service,
       port=PROXY_PORT_GENERAL,
       endpoint_type="general"
   )
   
   # 特別エンドポイント
   proxy_manager_special = ProxyServerManager(
       config_service=config_service,
       port=PROXY_PORT_SPECIAL,
       endpoint_type="special"
   )
   ```

3. **並行サーバー起動**:
   ```python
   async def run_all_servers():
       """すべてのサーバーを並行実行"""
       tasks = [
           asyncio.create_task(run_web_ui()),
           asyncio.create_task(proxy_manager_general.start()),
           asyncio.create_task(proxy_manager_special.start()),
       ]
       
       done, pending = await asyncio.wait(
           tasks,
           return_when=asyncio.FIRST_COMPLETED
       )
   ```

4. **統合ヘルスチェック**:
   ```python
   @app.get("/health")
   async def health_check():
       """統合ヘルスチェック"""
       return {
           "status": "ok",
           "web_ui": {"port": WEB_UI_PORT, "status": "running"},
           "proxy_general": {
               "port": PROXY_PORT_GENERAL,
               "status": "running" if proxy_manager_general else "stopped"
           },
           "proxy_special": {
               "port": PROXY_PORT_SPECIAL,
               "status": "running" if proxy_manager_special else "stopped"
           }
       }
   ```

### 8. Web UIの更新

**ファイル**: [`src/web/app.py`](src/web/app.py)

- フォームパラメータの追加:
  ```python
  available_on_4321: bool = Form(True)
  available_on_4333: bool = Form(True)
  ```

- バリデーション追加:
  ```python
  if not available_on_4321 and not available_on_4333:
      raise ValueError("少なくとも1つのエンドポイントを有効にしてください")
  ```

**ファイル**: [`src/web/templates/config.html`](src/web/templates/config.html)

- エンドポイント選択チェックボックスの追加:
  ```html
  <div class="form-group">
      <label>利用可能なエンドポイント:</label>
      <div class="checkbox-group">
          <label class="checkbox-label">
              <input type="checkbox" name="available_on_4321" 
                     value="true" checked>
              📡 4321 (一般エンドポイント)
          </label>
          <label class="checkbox-label">
              <input type="checkbox" name="available_on_4333" 
                     value="true" checked>
              🔓 4333 (特別エンドポイント)
          </label>
      </div>
  </div>
  ```

### 9. Docker設定の更新

**ファイル**: [`.env.example`](.env.example)

```bash
# Application Ports
WEB_UI_PORT=4322
PROXY_PORT_GENERAL=4321  # General endpoint (limited models)
PROXY_PORT_SPECIAL=4333  # Special endpoint (full access)

# Backward compatibility
PROXY_PORT=4321  # Default port for general endpoint
```

**ファイル**: [`docker-compose.yml`](docker-compose.yml)

```yaml
ports:
  - "${WEB_UI_PORT:-4322}:${WEB_UI_PORT:-4322}"              # Web UI
  - "${PROXY_PORT_GENERAL:-4321}:${PROXY_PORT_GENERAL:-4321}" # General proxy
  - "${PROXY_PORT_SPECIAL:-4333}:${PROXY_PORT_SPECIAL:-4333}" # Special proxy

environment:
  - WEB_UI_PORT=${WEB_UI_PORT:-4322}
  - PROXY_PORT_GENERAL=${PROXY_PORT_GENERAL:-4321}
  - PROXY_PORT_SPECIAL=${PROXY_PORT_SPECIAL:-4333}
  - PROXY_PORT=${PROXY_PORT:-4321}  # Backward compatibility

healthcheck:
  test: ["CMD", "sh", "-c", "curl -f http://localhost:${WEB_UI_PORT:-4322}/health && curl -f http://localhost:${PROXY_PORT_GENERAL:-4321}/health && curl -f http://localhost:${PROXY_PORT_SPECIAL:-4333}/health"]
```

### 10. ドキュメントの更新

**ファイル**: [`README.md`](README.md)

- デュアルエンドポイントアーキテクチャの説明を追加
- 各エンドポイントの使用例を追加
- トラブルシューティングセクションを更新
- 環境変数テーブルを更新

## 🔄 データマイグレーション戦略

1. **自動マイグレーション**: アプリケーション起動時に自動実行
2. **後方互換性**: 既存データは両エンドポイントで有効化
3. **ロールバック不要**: 新カラムはNULL可能でデフォルト値あり
4. **データ保全**: 既存の設定に影響なし

## ✅ 実装チェックリスト

### データベース層
- [x] スキーマ拡張（`available_on_4321`, `available_on_4333`カラム追加）
- [x] マイグレーションスクリプト作成（v1→v2）
- [x] スキーマバージョン更新（2に変更）

### モデル層
- [x] `LLMConfig`クラスにフィールド追加
- [x] `to_dict()`メソッドの更新
- [x] boolean-integer変換処理

### サービス層
- [x] `ConfigurationService`のCRUD操作更新
- [x] SELECT文への新カラム追加
- [x] INSERT/UPDATE文の更新

### プロキシ層
- [x] `ProxyServer`に`endpoint_type`パラメータ追加
- [x] モデルフィルタリングメソッド実装
- [x] `/v1/models`エンドポイントのフィルタリング
- [x] `/v1/chat/completions`のエンドポイント検証
- [x] `ProxyServerManager`の更新

### アプリケーション層
- [x] 2つのプロキシマネージャーの作成
- [x] 並行サーバー起動の実装
- [x] 環境変数の追加（`PROXY_PORT_GENERAL`, `PROXY_PORT_SPECIAL`）
- [x] 統合ヘルスチェックの実装
- [x] グレースフルシャットダウンの更新

### Web UI層
- [x] フォームパラメータの追加
- [x] チェックボックスUIの実装
- [x] JavaScriptフォーム処理の更新
- [x] バリデーションロジックの追加

### 設定ファイル
- [x] `.env.example`の更新
- [x] `docker-compose.yml`のポート設定
- [x] ヘルスチェック設定の更新

### ドキュメント
- [x] README.mdの更新
- [x] 実装サマリーの作成

## 🧪 テスト戦略

### 単体テスト
- [ ] `LLMConfig`モデルのシリアライゼーション
- [ ] `ConfigurationService`のCRUD操作
- [ ] `ProxyServer`のフィルタリングロジック

### 統合テスト
- [ ] データベースマイグレーション
- [ ] エンドポイント別モデル一覧取得
- [ ] エンドポイント別チャット補完
- [ ] 無効なモデルへのアクセス拒否

### エンドツーエンドテスト
- [ ] Web UIでのモデル設定
- [ ] 両エンドポイントでのAPI呼び出し
- [ ] 設定変更の即座反映

## 📊 動作確認手順

### 1. 環境起動
```bash
# Dockerコンテナ起動
docker-compose up -d

# ログ確認
docker-compose logs -f
```

### 2. データベースマイグレーション確認
```bash
# コンテナ内でSQLiteに接続
docker exec -it clads-llm-bridge sqlite3 /app/data/clads_llm_bridge.db

# スキーマ確認
.schema llm_configs

# マイグレーションバージョン確認
SELECT * FROM migration_metadata;
```

### 3. Web UI動作確認
1. http://localhost:4322 にアクセス
2. モデル設定画面で新しいチェックボックスが表示されることを確認
3. テストモデルを追加し、エンドポイントを選択的に有効化

### 4. API動作確認

**一般エンドポイント（4321）:**
```bash
# モデル一覧取得
curl http://localhost:4321/v1/models

# チャット補完（一般モデルのみ）
curl -X POST http://localhost:4321/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

**特別エンドポイント（4333）:**
```bash
# モデル一覧取得（全モデル）
curl http://localhost:4333/v1/models

# チャット補完（全モデル）
curl -X POST http://localhost:4333/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4",
    "messages": [{"role": "user", "content": "Hello"}]
  }'
```

### 5. エンドポイント検証テスト
```bash
# 4321で無効化されたモデルへのアクセス（エラーになるべき）
curl -X POST http://localhost:4321/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "special-model-only-on-4333",
    "messages": [{"role": "user", "content": "Test"}]
  }'
# 期待結果: 403 Forbidden
```

## 🔧 後方互換性

- 既存の`PROXY_PORT`環境変数は引き続きサポート（`PROXY_PORT_GENERAL`と同じ）
- 既存データは自動的に両エンドポイントで有効化
- マイグレーション前のクライアントコードは変更不要
- 4321ポートは引き続き一般エンドポイントとして機能

## 🚀 今後の拡張可能性

- [ ] 3つ以上のエンドポイントのサポート
- [ ] エンドポイント別のレート制限
- [ ] エンドポイント別の認証メカニズム
- [ ] エンドポイント別の使用統計
- [ ] 動的エンドポイント追加機能
- [ ] エンドポイントグループ管理

## 📝 注意事項

1. **最低1つのエンドポイント必須**: モデルは少なくとも1つのエンドポイントで有効化する必要があります
2. **SQLiteのBOOLEAN型**: INTEGER(0/1)として保存され、Pythonでbooleanに変換されます
3. **並行サーバー管理**: 両プロキシサーバーは独立して動作し、設定変更は両方に反映されます
4. **ポート競合**: 4321と4333が他のアプリケーションで使用されていないことを確認してください

## 🎉 実装完了

デュアルエンドポイント機能の実装が完了しました。この機能により、CLADS LLM Bridgeは異なるアクセスレベルのクライアントに対して、適切なモデルセットを柔軟に提供できるようになりました。

---

**実装日**: 2025-10-30  
**バージョン**: Database Schema v2  
**担当**: Roo (AI Assistant)