"""Database schema definitions."""


class DatabaseSchema:
    """SQLite database schema for CLADS LLM Bridge."""
    
    # Schema version for migrations
    CURRENT_VERSION = 2
    
    @staticmethod
    def get_create_tables_sql() -> str:
        """Get SQL to create all tables."""
        return """
        -- Schema version tracking
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- LLM service configurations
        CREATE TABLE IF NOT EXISTS llm_configs (
            id TEXT PRIMARY KEY,
            service_type TEXT NOT NULL,
            base_url TEXT NOT NULL,
            api_key TEXT NOT NULL DEFAULT '',
            model_name TEXT NOT NULL DEFAULT '',
            public_name TEXT NOT NULL DEFAULT '',
            enabled BOOLEAN NOT NULL DEFAULT 1,
            available_on_4321 BOOLEAN NOT NULL DEFAULT 1,
            available_on_4333 BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            
            CONSTRAINT chk_service_type CHECK (
                service_type IN (
                    'openai', 'anthropic', 'gemini', 'openrouter',
                    'vscode_proxy', 'lmstudio', 'openai_compatible', 'none'
                )
            )
        );
        
        -- Usage records for monitoring
        CREATE TABLE IF NOT EXISTS usage_records (
            id TEXT PRIMARY KEY,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            client_ip TEXT NOT NULL,
            model_name TEXT NOT NULL,
            public_name TEXT NOT NULL DEFAULT '',
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            response_time_ms INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'success',
            error_message TEXT,
            
            CONSTRAINT chk_status CHECK (status IN ('success', 'error')),
            CONSTRAINT chk_tokens CHECK (
                input_tokens >= 0 AND 
                output_tokens >= 0 AND 
                total_tokens >= 0
            ),
            CONSTRAINT chk_response_time CHECK (response_time_ms >= 0)
        );
        
        -- Health status for services
        CREATE TABLE IF NOT EXISTS health_status (
            service_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            last_checked TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            error_message TEXT,
            response_time_ms INTEGER,
            model_count INTEGER,
            
            CONSTRAINT chk_health_status CHECK (status IN ('OK', 'NG')),
            CONSTRAINT chk_health_response_time CHECK (
                response_time_ms IS NULL OR response_time_ms >= 0
            ),
            CONSTRAINT chk_model_count CHECK (
                model_count IS NULL OR model_count >= 0
            ),
            FOREIGN KEY (service_id) REFERENCES llm_configs(id) ON DELETE CASCADE
        );
        
        -- Authentication table for web UI
        CREATE TABLE IF NOT EXISTS auth_config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    
    @staticmethod
    def get_create_indexes_sql() -> str:
        """Get SQL to create database indexes for performance."""
        return """
        -- Indexes for usage_records table (for monitoring queries)
        CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage_records(timestamp);
        CREATE INDEX IF NOT EXISTS idx_usage_client_ip ON usage_records(client_ip);
        CREATE INDEX IF NOT EXISTS idx_usage_model_name ON usage_records(model_name);
        CREATE INDEX IF NOT EXISTS idx_usage_status ON usage_records(status);
        CREATE INDEX IF NOT EXISTS idx_usage_client_timestamp ON usage_records(client_ip, timestamp);
        CREATE INDEX IF NOT EXISTS idx_usage_model_timestamp ON usage_records(model_name, timestamp);
        
        -- Indexes for llm_configs table
        CREATE INDEX IF NOT EXISTS idx_llm_configs_service_type ON llm_configs(service_type);
        CREATE INDEX IF NOT EXISTS idx_llm_configs_enabled ON llm_configs(enabled);
        
        -- Indexes for health_status table
        CREATE INDEX IF NOT EXISTS idx_health_status_last_checked ON health_status(last_checked);
        CREATE INDEX IF NOT EXISTS idx_health_status_status ON health_status(status);
        """
    
    @staticmethod
    def get_initial_data_sql() -> str:
        """Get SQL to insert initial data."""
        return """
        -- Insert initial schema version
        INSERT OR IGNORE INTO schema_version (version) VALUES (1);
        
        -- Insert default authentication (password: Hakodate4)
        -- This will be handled by AuthenticationService.initialize_default_password()
        -- to ensure proper bcrypt hashing
        """
    
    @staticmethod
    def get_full_schema_sql() -> str:
        """Get complete SQL to initialize the database."""
        return (
            DatabaseSchema.get_create_tables_sql() + 
            "\n\n" + 
            DatabaseSchema.get_create_indexes_sql() + 
            "\n\n" + 
            DatabaseSchema.get_initial_data_sql()
        )