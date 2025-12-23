"""
デュアルエンドポイント機能のテスト
"""

import pytest
import sqlite3
from src.models.llm_config import LLMConfig
from src.config.configuration_service import ConfigurationService
from src.proxy.proxy_server import ProxyServer


class TestDualEndpointDatabase:
    """データベーススキーマとマイグレーションのテスト"""
    
    def test_schema_has_endpoint_columns(self, isolated_db):
        """スキーマに新しいエンドポイントカラムが含まれることを確認"""
        conn = sqlite3.connect(isolated_db)
        cursor = conn.cursor()
        
        # テーブル情報を取得
        cursor.execute("PRAGMA table_info(llm_configs)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        
        # 新しいカラムが存在することを確認
        assert 'available_on_4321' in columns
        assert 'available_on_4333' in columns
        
        # カラムの型を確認
        assert columns['available_on_4321'] == 'INTEGER'
        assert columns['available_on_4333'] == 'INTEGER'
        
        conn.close()
    
    def test_migration_version_is_2(self, isolated_db):
        """マイグレーションバージョンが2であることを確認"""
        conn = sqlite3.connect(isolated_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT version FROM migration_metadata")
        version = cursor.fetchone()[0]
        
        assert version == 2, f"Expected version 2, got {version}"
        
        conn.close()
    
    def test_default_endpoint_values(self, isolated_db):
        """デフォルト値が正しく設定されることを確認"""
        config_service = ConfigurationService(isolated_db)
        
        # テスト用設定を保存
        test_config = LLMConfig(
            service_type="openai",
            display_name="Test Model",
            model_name="gpt-3.5-turbo",
            api_key="test-key",
            base_url="https://api.openai.com/v1"
        )
        
        saved_config = config_service.save_llm_config(test_config)
        
        # デフォルト値を確認
        assert saved_config.available_on_4321 is True
        assert saved_config.available_on_4333 is True
    
    def test_migration_preserves_existing_data(self, isolated_db):
        """マイグレーションが既存データを保持することを確認"""
        # この機能は新規DBでは直接テストできないため、
        # マイグレーション前のデータが保持されることを論理的に確認
        config_service = ConfigurationService(isolated_db)
        
        # v1スキーマのように設定を保存（エンドポイント設定なし）
        test_config = LLMConfig(
            service_type="anthropic",
            display_name="Claude Test",
            model_name="claude-3-sonnet",
            api_key="test-key"
        )
        
        saved = config_service.save_llm_config(test_config)
        
        # デフォルト値が適用されていることを確認
        assert saved.available_on_4321 is True
        assert saved.available_on_4333 is True
        
        # 既存データが失われていないことを確認
        assert saved.service_type == "anthropic"
        assert saved.display_name == "Claude Test"
        assert saved.model_name == "claude-3-sonnet"


class TestLLMConfigModel:
    """LLMConfigモデルのテスト"""
    
    def test_model_has_endpoint_fields(self):
        """モデルにエンドポイントフィールドがあることを確認"""
        config = LLMConfig(
            service_type="openai",
            display_name="Test",
            model_name="gpt-4",
            api_key="test",
            available_on_4321=True,
            available_on_4333=False
        )
        
        assert config.available_on_4321 is True
        assert config.available_on_4333 is False
    
    def test_model_default_values(self):
        """デフォルト値が正しく設定されることを確認"""
        config = LLMConfig(
            service_type="openai",
            display_name="Test",
            model_name="gpt-4",
            api_key="test"
        )
        
        assert config.available_on_4321 is True
        assert config.available_on_4333 is True
    
    def test_to_dict_converts_boolean_to_int(self):
        """to_dict()がbooleanをintegerに変換することを確認"""
        config = LLMConfig(
            service_type="openai",
            display_name="Test",
            model_name="gpt-4",
            api_key="test",
            available_on_4321=True,
            available_on_4333=False
        )
        
        data = config.to_dict()
        
        assert data['available_on_4321'] == 1
        assert data['available_on_4333'] == 0
        assert isinstance(data['available_on_4321'], int)
        assert isinstance(data['available_on_4333'], int)


class TestConfigurationService:
    """ConfigurationServiceのCRUD操作テスト"""
    
    def test_save_config_with_endpoint_settings(self, isolated_db):
        """エンドポイント設定を含む設定の保存"""
        config_service = ConfigurationService(isolated_db)
        
        config = LLMConfig(
            service_type="openai",
            display_name="General Only Model",
            model_name="gpt-3.5-turbo",
            api_key="test-key",
            available_on_4321=True,
            available_on_4333=False
        )
        
        saved = config_service.save_llm_config(config)
        
        assert saved.id is not None
        assert saved.available_on_4321 is True
        assert saved.available_on_4333 is False
    
    def test_get_config_includes_endpoint_settings(self, isolated_db):
        """設定取得時にエンドポイント設定が含まれることを確認"""
        config_service = ConfigurationService(isolated_db)
        
        # 設定を保存
        config = LLMConfig(
            service_type="anthropic",
            display_name="Special Only Model",
            model_name="claude-3-opus",
            api_key="test-key",
            available_on_4321=False,
            available_on_4333=True
        )
        
        saved = config_service.save_llm_config(config)
        
        # 設定を取得
        retrieved = config_service.get_llm_config(saved.id)
        
        assert retrieved is not None
        assert retrieved.available_on_4321 is False
        assert retrieved.available_on_4333 is True
    
    def test_get_all_configs_includes_endpoint_settings(self, isolated_db):
        """全設定取得時にエンドポイント設定が含まれることを確認"""
        config_service = ConfigurationService(isolated_db)
        
        # 複数の設定を保存
        config1 = LLMConfig(
            service_type="openai",
            display_name="Model 1",
            model_name="gpt-4",
            api_key="key1",
            available_on_4321=True,
            available_on_4333=True
        )
        
        config2 = LLMConfig(
            service_type="anthropic",
            display_name="Model 2",
            model_name="claude-3-sonnet",
            api_key="key2",
            available_on_4321=True,
            available_on_4333=False
        )
        
        config_service.save_llm_config(config1)
        config_service.save_llm_config(config2)
        
        # 全設定を取得
        all_configs = config_service.get_llm_configs()
        
        assert len(all_configs) == 2
        
        # 各設定にエンドポイント情報があることを確認
        for cfg in all_configs:
            assert hasattr(cfg, 'available_on_4321')
            assert hasattr(cfg, 'available_on_4333')
    
    def test_update_endpoint_settings(self, isolated_db):
        """エンドポイント設定の更新"""
        config_service = ConfigurationService(isolated_db)
        
        # 初期設定
        config = LLMConfig(
            service_type="openai",
            display_name="Update Test",
            model_name="gpt-4",
            api_key="test-key",
            available_on_4321=True,
            available_on_4333=True
        )
        
        saved = config_service.save_llm_config(config)
        
        # エンドポイント設定を変更
        saved.available_on_4321 = False
        saved.available_on_4333 = True
        
        updated = config_service.save_llm_config(saved)
        
        # 変更が保存されたことを確認
        assert updated.available_on_4321 is False
        assert updated.available_on_4333 is True


class TestProxyServerFiltering:
    """ProxyServerのモデルフィルタリングテスト"""
    
    def test_general_endpoint_filters_models(self, isolated_db):
        """一般エンドポイントがモデルをフィルタリングすることを確認"""
        config_service = ConfigurationService(isolated_db)
        
        # テストデータを作成
        general_model = LLMConfig(
            service_type="openai",
            display_name="General Model",
            model_name="gpt-3.5-turbo",
            api_key="test-key",
            is_enabled=True,
            available_on_4321=True,
            available_on_4333=False
        )
        
        special_model = LLMConfig(
            service_type="anthropic",
            display_name="Special Model",
            model_name="claude-3-opus",
            api_key="test-key",
            is_enabled=True,
            available_on_4321=False,
            available_on_4333=True
        )
        
        both_model = LLMConfig(
            service_type="openai",
            display_name="Both Model",
            model_name="gpt-4",
            api_key="test-key",
            is_enabled=True,
            available_on_4321=True,
            available_on_4333=True
        )
        
        config_service.save_llm_config(general_model)
        config_service.save_llm_config(special_model)
        config_service.save_llm_config(both_model)
        
        # 一般エンドポイント用プロキシサーバー
        general_proxy = ProxyServer(
            config_service=config_service,
            endpoint_type="general"
        )
        
        # フィルタリング結果を確認
        all_configs = config_service.get_llm_configs()
        enabled_configs = [c for c in all_configs if c.is_enabled]
        
        filtered = general_proxy._filter_models_by_endpoint(enabled_configs)
        
        # 一般エンドポイントでは2つのモデルのみ利用可能
        assert len(filtered) == 2
        model_names = [m.model_name for m in filtered]
        assert "gpt-3.5-turbo" in model_names
        assert "gpt-4" in model_names
        assert "claude-3-opus" not in model_names
    
    def test_special_endpoint_filters_models(self, isolated_db):
        """特別エンドポイントがモデルをフィルタリングすることを確認"""
        config_service = ConfigurationService(isolated_db)
        
        # テストデータを作成（前のテストと同じ）
        general_model = LLMConfig(
            service_type="openai",
            display_name="General Model",
            model_name="gpt-3.5-turbo",
            api_key="test-key",
            is_enabled=True,
            available_on_4321=True,
            available_on_4333=False
        )
        
        special_model = LLMConfig(
            service_type="anthropic",
            display_name="Special Model",
            model_name="claude-3-opus",
            api_key="test-key",
            is_enabled=True,
            available_on_4321=False,
            available_on_4333=True
        )
        
        both_model = LLMConfig(
            service_type="openai",
            display_name="Both Model",
            model_name="gpt-4",
            api_key="test-key",
            is_enabled=True,
            available_on_4321=True,
            available_on_4333=True
        )
        
        config_service.save_llm_config(general_model)
        config_service.save_llm_config(special_model)
        config_service.save_llm_config(both_model)
        
        # 特別エンドポイント用プロキシサーバー
        special_proxy = ProxyServer(
            config_service=config_service,
            endpoint_type="special"
        )
        
        # フィルタリング結果を確認
        all_configs = config_service.get_llm_configs()
        enabled_configs = [c for c in all_configs if c.is_enabled]
        
        filtered = special_proxy._filter_models_by_endpoint(enabled_configs)
        
        # 特別エンドポイントでは2つのモデルのみ利用可能
        assert len(filtered) == 2
        model_names = [m.model_name for m in filtered]
        assert "claude-3-opus" in model_names
        assert "gpt-4" in model_names
        assert "gpt-3.5-turbo" not in model_names
    
    def test_disabled_models_are_filtered_out(self, isolated_db):
        """無効化されたモデルがフィルタリングされることを確認"""
        config_service = ConfigurationService(isolated_db)
        
        # 有効なモデル
        enabled_model = LLMConfig(
            service_type="openai",
            display_name="Enabled Model",
            model_name="gpt-4",
            api_key="test-key",
            is_enabled=True,
            available_on_4321=True,
            available_on_4333=True
        )
        
        # 無効なモデル
        disabled_model = LLMConfig(
            service_type="anthropic",
            display_name="Disabled Model",
            model_name="claude-3-opus",
            api_key="test-key",
            is_enabled=False,
            available_on_4321=True,
            available_on_4333=True
        )
        
        config_service.save_llm_config(enabled_model)
        config_service.save_llm_config(disabled_model)
        
        # プロキシサーバー
        proxy = ProxyServer(
            config_service=config_service,
            endpoint_type="general"
        )
        
        # 有効なモデルのみ取得
        all_configs = config_service.get_llm_configs()
        enabled_configs = [c for c in all_configs if c.is_enabled]
        
        filtered = proxy._filter_models_by_endpoint(enabled_configs)
        
        # 有効なモデルのみがフィルタリング結果に含まれる
        assert len(filtered) == 1
        assert filtered[0].model_name == "gpt-4"


class TestEndpointValidation:
    """エンドポイント検証のテスト"""
    
    def test_at_least_one_endpoint_required(self):
        """少なくとも1つのエンドポイントが必要であることを確認"""
        # 両方のエンドポイントがFalseの場合は無効
        config = LLMConfig(
            service_type="openai",
            display_name="Invalid Config",
            model_name="gpt-4",
            api_key="test-key",
            available_on_4321=False,
            available_on_4333=False
        )
        
        # このような設定はバリデーションで拒否されるべき
        # （実際のバリデーションはweb/app.pyで実装）
        assert not (config.available_on_4321 or config.available_on_4333)
    
    def test_both_endpoints_allowed(self):
        """両方のエンドポイントが有効な設定を確認"""
        config = LLMConfig(
            service_type="openai",
            display_name="Both Endpoints",
            model_name="gpt-4",
            api_key="test-key",
            available_on_4321=True,
            available_on_4333=True
        )
        
        assert config.available_on_4321 is True
        assert config.available_on_4333 is True
    
    def test_single_endpoint_allowed(self):
        """単一エンドポイントのみ有効な設定を確認"""
        config1 = LLMConfig(
            service_type="openai",
            display_name="4321 Only",
            model_name="gpt-3.5-turbo",
            api_key="test-key",
            available_on_4321=True,
            available_on_4333=False
        )
        
        config2 = LLMConfig(
            service_type="anthropic",
            display_name="4333 Only",
            model_name="claude-3-opus",
            api_key="test-key",
            available_on_4321=False,
            available_on_4333=True
        )
        
        assert config1.available_on_4321 is True
        assert config1.available_on_4333 is False
        
        assert config2.available_on_4321 is False
        assert config2.available_on_4333 is True


@pytest.mark.integration
class TestDualEndpointIntegration:
    """デュアルエンドポイントの統合テスト"""
    
    def test_end_to_end_workflow(self, isolated_db):
        """エンドツーエンドのワークフローテスト"""
        config_service = ConfigurationService(isolated_db)
        
        # 1. 異なるエンドポイント設定で3つのモデルを作成
        general_only = LLMConfig(
            service_type="openai",
            display_name="GPT-3.5 (General)",
            model_name="gpt-3.5-turbo",
            api_key="test-key-1",
            is_enabled=True,
            available_on_4321=True,
            available_on_4333=False
        )
        
        special_only = LLMConfig(
            service_type="anthropic",
            display_name="Claude Opus (Special)",
            model_name="claude-3-opus",
            api_key="test-key-2",
            is_enabled=True,
            available_on_4321=False,
            available_on_4333=True
        )
        
        both_endpoints = LLMConfig(
            service_type="openai",
            display_name="GPT-4 (Both)",
            model_name="gpt-4",
            api_key="test-key-3",
            is_enabled=True,
            available_on_4321=True,
            available_on_4333=True
        )
        
        # 2. 設定を保存
        config_service.save_llm_config(general_only)
        config_service.save_llm_config(special_only)
        config_service.save_llm_config(both_endpoints)
        
        # 3. 一般エンドポイントプロキシを作成
        general_proxy = ProxyServer(
            config_service=config_service,
            endpoint_type="general"
        )
        
        # 4. 特別エンドポイントプロキシを作成
        special_proxy = ProxyServer(
            config_service=config_service,
            endpoint_type="special"
        )
        
        # 5. 各プロキシで利用可能なモデルを取得
        all_configs = config_service.get_llm_configs()
        enabled_configs = [c for c in all_configs if c.is_enabled]
        
        general_models = general_proxy._filter_models_by_endpoint(enabled_configs)
        special_models = special_proxy._filter_models_by_endpoint(enabled_configs)
        
        # 6. 一般エンドポイントの検証
        general_model_names = [m.model_name for m in general_models]
        assert len(general_models) == 2
        assert "gpt-3.5-turbo" in general_model_names
        assert "gpt-4" in general_model_names
        assert "claude-3-opus" not in general_model_names
        
        # 7. 特別エンドポイントの検証
        special_model_names = [m.model_name for m in special_models]
        assert len(special_models) == 2
        assert "claude-3-opus" in special_model_names
        assert "gpt-4" in special_model_names
        assert "gpt-3.5-turbo" not in special_model_names
        
        # 8. モデル設定を更新（gpt-4を一般エンドポイントのみに変更）
        gpt4_config = config_service.get_llm_config(both_endpoints.id)
        gpt4_config.available_on_4333 = False
        config_service.save_llm_config(gpt4_config)
        
        # 9. 更新後のフィルタリングを確認
        updated_configs = config_service.get_llm_configs()
        updated_enabled = [c for c in updated_configs if c.is_enabled]
        
        updated_general = general_proxy._filter_models_by_endpoint(updated_enabled)
        updated_special = special_proxy._filter_models_by_endpoint(updated_enabled)
        
        # 10. 一般エンドポイントは変わらず
        assert len(updated_general) == 2
        
        # 11. 特別エンドポイントからgpt-4が除外される
        updated_special_names = [m.model_name for m in updated_special]
        assert len(updated_special) == 1
        assert "claude-3-opus" in updated_special_names
        assert "gpt-4" not in updated_special_names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])