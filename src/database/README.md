# Database Module

This module handles SQLite database operations for CLADS LLM Bridge.

## Components

### DatabaseConnection
Thread-safe SQLite connection manager with:
- Automatic database file creation
- Context managers for transactions
- Row factory for dict-like access
- Foreign key constraint enforcement

### DatabaseSchema
Defines the complete database schema including:
- `llm_configs` - LLM service configurations
- `usage_records` - API usage tracking
- `health_status` - Service health checks
- `auth_config` - Web UI authentication
- `schema_version` - Migration tracking

### DatabaseMigrations
Handles schema migrations and initialization:
- Version tracking and validation
- Automatic migration application
- Database reset functionality
- Schema validation

## Usage

### Initialize Database
```python
from database import DatabaseConnection, DatabaseMigrations

# Initialize database
db = DatabaseConnection()
migrations = DatabaseMigrations(db)
migrations.initialize_database()
```

### Use Database Connection
```python
# Execute queries with automatic transaction management
with db.get_cursor() as cursor:
    cursor.execute("INSERT INTO llm_configs (...) VALUES (...)", params)

# Execute simple queries
results = db.execute_query("SELECT * FROM llm_configs WHERE enabled = ?", (True,))
affected = db.execute_update("UPDATE llm_configs SET enabled = ? WHERE id = ?", (False, "config-1"))
```

### Command Line Initialization
```bash
# Initialize database from command line
python3 src/database/init_db.py
```

## Database Schema

The database includes the following tables:

- **llm_configs**: LLM service configurations with constraints on service types
- **usage_records**: API usage logs with indexes for efficient querying
- **health_status**: Service health check results with foreign key to configs
- **auth_config**: Single-row authentication configuration
- **schema_version**: Migration version tracking

All tables include appropriate indexes for performance and constraints for data integrity.